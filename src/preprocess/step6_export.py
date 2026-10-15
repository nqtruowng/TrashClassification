"""Bước 7: xuất ảnh và nhãn YOLO hợp lệ, giữ nguyên split và trạng thái duyệt."""

from collections import Counter
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re
import shutil
import tempfile

from PIL import Image
import yaml

from .step1_config import PROJECT_ROOT, artifact_path, require
from .step5_split import SPLITS, SPLIT_FIELDS


def label_errors(objects, class_count):
    """Kiểm tra toàn bộ nhãn, kể cả cạnh box; một box sai sẽ loại cả ảnh."""
    errors = []
    if not objects:
        return ["missing_or_empty_label"]
    for index, obj in enumerate(objects, 1):
        class_id, box = obj.get("target_class_id"), obj.get("bbox_xywh")
        if type(class_id) is not int or not 0 <= class_id < class_count:
            errors.append(f"box {index}: invalid_class_id")
        if not isinstance(box, list) or len(box) != 4 or not all(
                type(v) in (int, float) and math.isfinite(v) for v in box):
            errors.append(f"box {index}: invalid_coordinates")
            continue
        x, y, width, height = box
        if not (0 <= x <= 1 and 0 <= y <= 1 and 0 < width <= 1 and 0 < height <= 1):
            errors.append(f"box {index}: invalid_coordinates")
        elif min(x-width/2, y-height/2) < -1e-9 or max(x+width/2, y+height/2) > 1+1e-9:
            errors.append(f"box {index}: edges_outside_image")
    return errors


def load_export_rows(config, root):
    """Đối chiếu checksum, metadata và giao nhau giữa các split trước khi xuất."""
    clean = artifact_path(config, "clean/annotations.jsonl", root)
    manifest = artifact_path(config, "split-manifest.csv", root)
    require(clean.is_file() and manifest.is_file(), "export", "run clean and split first")
    previous = json.loads(clean.with_name("summary.json").read_text(encoding="utf-8"))
    split_summary = json.loads(manifest.with_name("split-summary.json").read_text(encoding="utf-8"))
    clean_data, split_data = clean.read_bytes(), manifest.read_bytes()
    checksums = {"clean": hashlib.sha256(clean_data).hexdigest(),
                 "split": hashlib.sha256(split_data).hexdigest()}
    require(config == previous["configuration"] == split_summary["configuration"]
            and checksums["clean"] == previous["annotations_sha256"] == split_summary["input_sha256"]
            and checksums["split"] == split_summary["manifest_sha256"],
            "export", "checksum/configuration mismatch; rerun upstream stages")
    rows = [json.loads(line) for line in clean_data.decode("utf-8").splitlines()]
    by_id = {row["image_id"]: row for row in rows}
    require(bool(rows) and len(rows) == len(by_id) == previous["kept"] == split_summary["images"],
            "export", "empty, duplicate or incomplete clean input")
    reader = csv.DictReader(io.StringIO(split_data.decode("utf-8"), newline=""))
    require(reader.fieldnames == list(SPLIT_FIELDS), "export", "unexpected split manifest columns")
    seen, owners = set(), {key: {} for key in ("group_id", "file_sha256", "pixel_sha256")}
    for record in reader:
        image_id = record["image_id"]
        require(image_id in by_id and image_id not in seen and re.fullmatch(r"[0-9a-f]{64}", image_id),
                "export", "unknown, duplicate or unsafe image ID")
        seen.add(image_id)
        row = by_id[image_id]
        for key in SPLIT_FIELDS:
            if key == "split":
                continue
            value = json.loads(record[key]) if key in ("target_class_ids", "ready_for_training") else record[key]
            require(value == row[key], image_id, f"split/clean metadata mismatch: {key}")
        split = record["split"]
        require(split in SPLITS, image_id, "unknown split")
        row["split"] = split
        for key, values in owners.items():
            require(bool(row[key]) and values.setdefault(row[key], split) == split,
                    "export", f"cross-split overlap in {key}")
    require(seen == set(by_id), "export", "split manifest does not cover clean input")
    counts = Counter(row["split"] for row in rows)
    require(all(counts[s] == split_summary["splits"][s]["images"] for s in SPLITS),
            "export", "split counts differ from summary")
    return sorted(rows, key=lambda row: row["image_id"]), checksums


def run_export(config, warnings, *, project_root=PROJECT_ROOT):
    """Xuất vào thư mục tạm, kiểm tra ảnh/TXT rồi công bố dataset cùng báo cáo.

    Loại cả ảnh khi nhãn không hợp lệ; không cắt box, không duyệt nhãn tự động.
    Ảnh thay đổi so với clean làm dừng xuất để chạy lại pipeline. Đầu ra đã có
    dữ liệu được bảo vệ, không ghi đè hoặc trộn thêm file của lần chạy khác.
    """
    root = project_root.resolve()
    output = root / "processed-data"
    require(output.resolve() == output and not output.is_symlink(), "export", "unsafe output directory")
    require(not output.exists() or output.is_dir() and not any(output.iterdir()),
            "export", "processed-data must be absent or empty; existing data is preserved")
    report_path = artifact_path(config, "export-summary.json", root)
    rows, checksums = load_export_rows(config, root)
    sources = {s["id"]: (root / s["local_root"]).resolve() for s in config["sources"]}
    require(not any(output.is_relative_to(p) or p.is_relative_to(output) for p in sources.values()),
            "export", "output overlaps a source directory")
    kept, excluded = [], []
    for row in rows:
        errors = label_errors(row["objects"], len(config["classes"]))
        if errors:
            excluded.append({key: row[key] for key in ("image_id", "source_dataset", "original_path", "split")}
                            | {"errors": errors})
        else:
            require(set(row["target_class_ids"]) == {o["target_class_id"] for o in row["objects"]},
                    row["image_id"], "target class metadata mismatch")
            kept.append(row)
    require(bool(kept), "export", "no valid labeled images remain")
    summary = {"schema_version": 1, "configuration": config, "warnings": list(warnings),
               "input_sha256": checksums, "input_images": len(rows), "images": len(kept),
               "excluded_images": len(excluded), "exclusions": excluded, "splits": {},
               "scope": "YOLO export with technical checks; annotation status is preserved, not automatically approved.",
               "files_sha256": {}}
    for split in SPLITS:
        subset = [r for r in kept if r["split"] == split]
        require(bool(subset) or config["split"][split] == 0, "export", f"no valid images in {split}")
        images = Counter(c for r in subset for c in set(r["target_class_ids"]))
        boxes = Counter(o["target_class_id"] for r in subset for o in r["objects"])
        summary["splits"][split] = {
            "images": len(subset), "ratio": len(subset)/len(kept),
            "excluded_images": sum(r["split"] == split for r in excluded),
            "sources": dict(Counter(r["source_dataset"] for r in subset)),
            "images_by_class": {name: images[i] for i, name in enumerate(config["classes"])},
            "boxes_by_class": {name: boxes[i] for i, name in enumerate(config["classes"])},
            "annotation_statuses": dict(Counter(r["annotation_status"] for r in subset)),
            "ready_for_training": sum(r["ready_for_training"] is True for r in subset),
        }
    summary["warnings"].append("Export does not verify semantic label quality or resolve duplicate label conflicts.")
    with tempfile.TemporaryDirectory(prefix=".export-", dir=report_path.parent) as temporary:
        stage = Path(temporary) / "dataset"
        for kind in ("images", "labels"):
            for split in SPLITS:
                (stage / kind / split).mkdir(parents=True)
        for index, row in enumerate(kept, 1):
            image_id, split = row["image_id"], row["split"]
            require(row["source_dataset"] in sources, image_id, "unknown source")
            original = (sources[row["source_dataset"]] / row["original_path"]).resolve()
            source = (root / row["image_path"]).resolve()
            normalized = root / "artifacts/clean/images" / f"{image_id}.png"
            require(original.is_relative_to(sources[row["source_dataset"]])
                    and (source == original or source == normalized.resolve()), image_id, "unexpected image path")
            image_path = stage / "images" / split / f"{image_id}{source.suffix.lower()}"
            label_path = stage / "labels" / split / f"{image_id}.txt"
            shutil.copyfile(source, image_path)
            image_hash = hashlib.sha256(image_path.read_bytes()).hexdigest()
            if source == original:
                require(image_hash == row["file_sha256"], image_id, "source image changed; rerun clean and split")
            with Image.open(image_path) as image:
                image.load()
                require(image.mode == "RGB" and image.getexif().get(274, 1) == 1
                        and image.size == (row["width"], row["height"]), image_id, "image is not normalized")
                pixel_hash = hashlib.sha256(f"RGB:{image.width}:{image.height}:".encode() + image.tobytes()).hexdigest()
                require(pixel_hash == row["pixel_sha256"], image_id, "image pixels changed; rerun clean and split")
            label = "".join(str(obj["target_class_id"]) + " " + " ".join(format(v, ".17g") for v in obj["bbox_xywh"])
                            + "\n" for obj in row["objects"])
            label_path.write_text(label, encoding="utf-8", newline="\n")
            # Đọc lại TXT để kiểm tra chính nội dung sẽ dùng huấn luyện.
            parsed = [{"target_class_id": int(parts[0]), "bbox_xywh": list(map(float, parts[1:]))}
                      for parts in (line.split() for line in label_path.read_text(encoding="utf-8").splitlines())]
            require(len(parsed) == len(row["objects"]) and not label_errors(parsed, len(config["classes"])),
                    image_id, "exported label is invalid")
            summary["files_sha256"][image_path.relative_to(stage).as_posix()] = image_hash
            summary["files_sha256"][label_path.relative_to(stage).as_posix()] = hashlib.sha256(label_path.read_bytes()).hexdigest()
            if index % 1000 == 0:
                print(f"Export checked {index}/{len(kept)} images", flush=True)
        data_yaml = stage / "data.yaml"
        data_yaml.write_text(yaml.safe_dump({"path": output.as_posix(), **{s: f"images/{s}" for s in SPLITS},
                                           "nc": len(config["classes"]), "names": config["classes"]},
                                          sort_keys=False, allow_unicode=True), encoding="utf-8")
        summary["files_sha256"]["data.yaml"] = hashlib.sha256(data_yaml.read_bytes()).hexdigest()
        actual = {p.relative_to(stage).as_posix() for p in stage.rglob("*") if p.is_file()}
        require(actual == set(summary["files_sha256"]) and len(actual) == 2*len(kept)+1,
                "export", "unexpected or missing dataset files")
        report = Path(temporary) / report_path.name
        report.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if output.exists():
            output.rmdir()  # Chỉ xóa thư mục rỗng đã kiểm tra, không xóa dữ liệu cũ.
        stage.rename(output)
        report.replace(report_path)
    print(f"Exported {len(kept)} images; excluded {len(excluded)} invalid labels.", flush=True)
    return output / "data.yaml", report_path
