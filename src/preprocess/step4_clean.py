"""Bước 4: lọc ảnh/nhãn lỗi và ảnh trùng, giữ ảnh có box nguồn, gom nhóm chống rò rỉ."""

from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
from pathlib import Path
import tempfile

from PIL import Image, ImageChops, ImageOps, ImageStat

from .step1_config import PROJECT_ROOT, artifact_path, require
from .step3_remap import source_path


def normalize_image(image):
    """Áp EXIF, đổi RGB; nền trong suốt được ghép trên trắng, không resize/crop."""
    image = ImageOps.exif_transpose(image)
    if image.mode in ("RGBA", "LA") or "transparency" in image.info:
        rgba = image.convert("RGBA")
        background = Image.new("RGBA", image.size, "white")
        image = Image.alpha_composite(background, rgba)
    return image.convert("RGB")


def orient_box(box, orientation):
    """Đổi box YOLO theo đủ 8 hướng EXIF, giữ hệ tọa độ chuẩn hóa [0, 1]."""
    x, y, width, height = box
    centers = {1: (x, y), 2: (1-x, y), 3: (1-x, 1-y), 4: (x, 1-y),
               5: (y, x), 6: (1-y, x), 7: (1-y, 1-x), 8: (y, 1-x)}
    return [*centers[orientation], *([height, width] if orientation >= 5 else [width, height])]


def inspect_for_cleaning(row, local, images_dir):
    """Giải mã ảnh, tính hash và thumbnail; chỉ ghi bản PNG nếu cần chuẩn hóa.

    Lỗi đã biết ở bước 3 bị loại ngay. File mới phát hiện lỗi cũng không được nhận.
    Thumbnail chỉ dùng tìm gần trùng; ảnh đầu ra giữ nguyên kích thước/tỷ lệ.
    """
    result = {"image_id": row["image_id"], "source_dataset": row["source_dataset"],
              "original_path": row["original_path"], "decision": "keep", "reasons": []}
    if row["record_type"] != "image" or row["image_status"] == "decode_error":
        result.update(decision="remove", reasons=["invalid_image" if row["record_type"] == "image" else "orphan_label"])
        return result
    path = source_path(local, row["original_path"])
    try:
        data = path.read_bytes()
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            orientation = image.getexif().get(274, 1)
            if orientation not in range(1, 9):
                raise ValueError(f"unsupported EXIF orientation: {orientation}")
            if image.size != (row["width"], row["height"]) or orientation != row["exif_orientation"]:
                raise ValueError("image metadata changed since inventory; rerun inventory and remap")
            changed = orientation != 1 or image.mode != "RGB" or "transparency" in image.info
            normalized = normalize_image(image)
        width, height = normalized.size
        pixel_hash = hashlib.sha256(f"RGB:{width}:{height}:".encode() + normalized.tobytes()).hexdigest()
        small = normalized.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
        pixels = list(small.get_flattened_data())
        dhash = sum((pixels[y*9+x] > pixels[y*9+x+1]) << (y*8+x) for y in range(8) for x in range(8))
        result.update(file_sha256=hashlib.sha256(data).hexdigest(), pixel_sha256=pixel_hash,
                      dhash=f"{dhash:016x}", width=width, height=height, orientation=orientation,
                      normalized=changed, _thumbnail=normalized.resize((16, 16), Image.Resampling.LANCZOS).tobytes(),
                      _textured=max(pixels)-min(pixels) >= 12)
        if changed:
            normalized.save(images_dir / f"{row['image_id']}.png", exif=b"")
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as exc:
        result.update(decision="remove", reasons=["invalid_image"], error=str(exc))
    return result


def verify_near_copy(left, right, paths):
    """Xác nhận bản gần như giống hệt bằng pixel toàn ảnh, không chỉ bằng dHash.

    Đưa về kích thước nhỏ hơn chỉ để so sánh: MAE <= 2/255, RMS <= 4/255,
    tối đa 1% mẫu kênh màu lệch hơn 16/255. Ảnh đầu ra không bị resize.
    Cặp chưa đạt chỉ được gom nhóm để tránh leakage; trả cả số đo để truy vết.
    """
    with Image.open(paths[left["image_id"]]) as image:
        a = normalize_image(image)
    with Image.open(paths[right["image_id"]]) as image:
        b = normalize_image(image)
    size = (min(a.width, b.width), min(a.height, b.height))
    if a.size != size:
        a = a.resize(size, Image.Resampling.LANCZOS)
    if b.size != size:
        b = b.resize(size, Image.Resampling.LANCZOS)
    difference = ImageChops.difference(a, b)
    histogram = difference.histogram()
    large = sum(sum(histogram[offset+17:offset+256]) for offset in (0, 256, 512))
    statistics = ImageStat.Stat(difference)
    mae = sum(statistics.mean)/3
    rms = (sum(v*v for v in statistics.rms)/3)**.5
    fraction = large/(a.width*a.height*3)
    return {"confirmed": mae <= 2 and rms <= 4 and fraction <= .01,
            "comparison_size": list(size), "pixel_mae": round(mae, 6),
            "pixel_rms": round(rms, 6), "large_delta_fraction": round(fraction, 6)}


def group_duplicates(records, rows, paths):
    """Gom trùng pixel và ứng viên gần trùng; giữ cạnh bằng chứng cho báo cáo.

    Chỉ mục 5 phần của dHash tìm đủ các cặp cách nhau tối đa 4 bit. Kiểm tra
    thêm tỷ lệ ảnh và sai khác thumbnail; bỏ tìm gần trùng với ảnh gần đơn sắc.
    Hai hệ nhóm riêng: nhóm xóa bản sao và nhóm rộng hơn để chia tập an toàn.
    """
    parent = list(range(len(records)))
    copies = list(range(len(records)))

    def find(tree, item):
        """Tìm gốc nhóm và nén đường đi để các lần tra cứu tiếp theo nhanh hơn."""
        while tree[item] != item:
            tree[item] = tree[tree[item]]
            item = tree[item]
        return item

    def join(tree, a, b):
        """Gộp hai nhóm, chọn gốc ổn định theo thứ tự bản ghi."""
        a, b = find(tree, a), find(tree, b)
        tree[max(a, b)] = min(a, b)

    pixels, bands, edges = {}, defaultdict(list), []
    for i, item in enumerate(records):
        if "pixel_sha256" not in item or item["decision"] == "remove":
            continue
        pixel = item["pixel_sha256"]
        if pixel in pixels:
            j = pixels[pixel]
            join(parent, i, j)
            join(copies, i, j)
            edges.append({"left": records[j]["image_id"], "right": item["image_id"],
                          "match": "file" if item["file_sha256"] == records[j]["file_sha256"] else "pixels"})
            continue
        pixels[pixel] = i
        if not item["_textured"]:
            continue
        value = int(item["dhash"], 16)
        keys = [(part, (value >> (part*13)) & 8191) for part in range(5)]
        candidates = sorted({j for key in keys for j in bands[key]})
        for j in candidates:
            other = records[j]
            distance = (value ^ int(other["dhash"], 16)).bit_count()
            if distance > 4 or abs((item["width"]/item["height"])/(other["width"]/other["height"])-1) > .01:
                continue
            delta = sum(abs(a-b) for a, b in zip(item["_thumbnail"], other["_thumbnail"]))/768
            if delta > 8:
                continue
            join(parent, i, j)
            verification = verify_near_copy(item, other, paths)
            if verification["confirmed"]:
                join(copies, i, j)
            edges.append({"left": other["image_id"], "right": item["image_id"],
                          "match": "near_copy" if verification["confirmed"] else "near_candidate", "hamming": distance,
                          "thumbnail_mae": round(delta, 4), **verification})
        for key in keys:
            bands[key].append(i)
        if (i+1) % 2000 == 0:
            print(f"  Grouping: {i+1}/{len(records)}", flush=True)
    groups, duplicate_groups = defaultdict(list), defaultdict(list)
    for i, item in enumerate(records):
        if "pixel_sha256" in item and item["decision"] != "remove":
            groups[find(parent, i)].append(i)
            duplicate_groups[find(copies, i)].append(i)
    for members in groups.values():
        group_id = min(records[i]["image_id"] for i in members)
        for i in members:
            records[i]["group_id"] = group_id
    for members in duplicate_groups.values():
        # Kiểm tra mâu thuẫn trước khi chọn đại diện; không tự coi nhãn đại diện là đúng.
        signatures = {json.dumps({"classes": rows[i]["target_class_ids"],
                                  "boxes": sorted((obj["target_class_id"], *orient_box(obj["bbox_xywh"], records[i]["orientation"]))
                                                  for obj in rows[i]["objects"])},
                                 sort_keys=True) for i in members}
        conflict = len(signatures) > 1
        # Chất lượng nhãn và độ phân giải đứng trước ID; không ưu tiên thứ tự nguồn.
        chosen = min(members, key=lambda i: ("invalid_label" in rows[i]["reasons"], not bool(rows[i]["objects"]),
                                             -records[i]["width"]*records[i]["height"], records[i]["image_id"]))
        for i in members:
            records[i]["duplicate_of"] = records[chosen]["image_id"] if i != chosen else None
            if conflict:
                records[i]["label_conflict"] = True
            if i != chosen:
                records[i].update(decision="remove", reasons=["duplicate_image"])
    return edges


def run_clean(config, warnings, *, project_root=PROJECT_ROOT):
    """Chạy bước 4 vào artifacts/clean, chỉ giữ ảnh có nhãn nguồn hợp lệ và không trùng.

    Giữ raw-data bất biến; ảnh lỗi không có trong annotations đầu ra. Chỉ lưu ảnh
    chuẩn hóa nếu thực sự thay đổi. Thư mục tạm thay kết quả cũ khi hoàn tất.
    """
    root = project_root.resolve()
    annotations = artifact_path(config, "annotations.jsonl", root)
    remap_summary = artifact_path(config, "remap-summary.json", root)
    output = artifact_path(config, "clean", root)
    require(annotations.is_file() and remap_summary.is_file(), "clean", "run --stage remap first")
    previous = json.loads(remap_summary.read_text(encoding="utf-8"))
    checksum = hashlib.sha256(annotations.read_bytes()).hexdigest()
    require(checksum == previous["annotations_sha256"] and config == previous["configuration"],
            "clean", "remap checksum/configuration mismatch; rerun remap")
    if output.exists():
        require((output / "summary.json").is_file() and
                {p.name for p in output.iterdir()} <= {"annotations.jsonl", "decisions.jsonl", "summary.json", "images"},
                str(output), "unexpected files in managed output directory")
    with annotations.open(encoding="utf-8") as stream:
        rows = [json.loads(line) for line in stream]
    require(len({r["image_id"] for r in rows if r["record_type"] == "image"}) ==
            sum(r["record_type"] == "image" for r in rows), "clean", "duplicate image IDs in input")
    sources = {s["id"]: (root / s["local_root"]).resolve() for s in config["sources"]}
    paths = {r["image_id"]: source_path(sources[r["source_dataset"]], r["original_path"])
             for r in rows if r["record_type"] == "image"}
    with tempfile.TemporaryDirectory(prefix=".clean-", dir=output.parent) as temporary:
        stage = Path(temporary) / "next"
        images_dir = stage / "images"
        images_dir.mkdir(parents=True)
        print(f"Cleaning {len(rows)} records (4 image readers)...", flush=True)
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = pool.map(inspect_for_cleaning, rows,
                               (sources[r["source_dataset"]] for r in rows),
                               (images_dir for _ in rows), buffersize=8)
            records = []
            for i, result in enumerate(results, 1):
                records.append(result)
                if i % 1000 == 0:
                    print(f"  Decoded: {i}/{len(rows)}", flush=True)
        edges = group_duplicates(records, rows, paths)
        summary = {"schema_version": 1, "input_sha256": checksum, "configuration": config,
                   "warnings": warnings, "input_records": len(rows), "kept": 0, "removed": 0,
                   "removal_reasons": Counter(), "by_source": {}, "matches": Counter(e["match"] for e in edges),
                   "normalized_images": 0, "label_conflicts": 0,
                   "near_policy": "dHash <=4 bits, aspect ratio within 1%, RGB thumbnail MAE <=8/255; "
                                  "compare all pixels at smaller shared dimensions; delete near copies only if RGB "
                                  "MAE <=2/255, RMS <=4/255 and <=1% channels differ >16/255. "
                                  "Other candidates share group_id for train/val splitting.",
                   "scope": "Existing valid source boxes only; labels still require review. No split assignment."}
        clean_path, decisions_path = stage / "annotations.jsonl", stage / "decisions.jsonl"
        with clean_path.open("w", encoding="utf-8", newline="\n") as clean, decisions_path.open("w", encoding="utf-8", newline="\n") as decisions:
            for row, result in zip(rows, records):
                for key in ("_thumbnail", "_textured"):
                    result.pop(key, None)
                # Chỉ dùng nhãn có sẵn; không đưa ảnh cần gán/sửa nhãn vào đầu ra sạch.
                if result["decision"] == "keep":
                    label_reason = {"missing": "missing_label", "empty_unverified": "empty_label_unverified",
                                    "invalid": "invalid_label"}.get(
                                        row["original_annotation_status"])
                    if label_reason:
                        result.update(decision="remove", reasons=[label_reason])
                count = summary["by_source"].setdefault(row["source_dataset"], {"kept": 0, "removed": 0})
                kept = result["decision"] == "keep"
                summary["kept" if kept else "removed"] += 1
                count["kept" if kept else "removed"] += 1
                normalized_path = images_dir / f"{row['image_id']}.png"
                if not kept:
                    summary["removal_reasons"].update(result["reasons"])
                    normalized_path.unlink(missing_ok=True)
                else:
                    orientation = result["orientation"]
                    row.update(group_id=result["group_id"], file_sha256=result["file_sha256"],
                               pixel_sha256=result["pixel_sha256"], original_exif_orientation=orientation,
                               original_image_size=[row["width"], row["height"]],
                               width=result["width"], height=result["height"], mode="RGB", exif_orientation=1,
                               image_path=(output / "images" / normalized_path.name).relative_to(root).as_posix()
                               if result["normalized"] else paths[row["image_id"]].as_posix())
                    if orientation != 1:
                        for obj in row["objects"]:
                            obj["original_bbox_xywh"] = obj["bbox_xywh"]
                            obj["bbox_xywh"] = orient_box(obj["bbox_xywh"], orientation)
                    if result.get("label_conflict"):
                        row["annotation_status"] = "needs_review"
                        row["reasons"].append("duplicate_label_conflict")
                        summary["label_conflicts"] += 1
                    summary["normalized_images"] += result["normalized"]
                    clean.write(json.dumps(row, ensure_ascii=False) + "\n")
                decisions.write(json.dumps({"record_type": "decision", **result}, ensure_ascii=False) + "\n")
            for edge in edges:
                decisions.write(json.dumps({"record_type": "match", **edge}) + "\n")
        summary["annotations_sha256"] = hashlib.sha256(clean_path.read_bytes()).hexdigest()
        summary["decisions_sha256"] = hashlib.sha256(decisions_path.read_bytes()).hexdigest()
        (stage / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        # Chỉ thay thư mục đầu ra do bước này quản lý, giữ kết quả cũ nếu chạy lỗi.
        backup = Path(temporary) / "previous"
        if output.exists():
            output.rename(backup)
        try:
            stage.rename(output)
        except OSError:
            if backup.exists():
                backup.rename(output)
            raise
    print(f"Cleaned: {summary['kept']} kept, {summary['removed']} removed; {dict(summary['removal_reasons'])}", flush=True)
    return output / "annotations.jsonl", output / "summary.json"
