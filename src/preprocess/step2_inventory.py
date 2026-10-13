"""Bước 2: kiểm kê ảnh/nhãn của các nguồn và xuất manifest cùng thống kê."""

import csv
from collections import Counter
import hashlib
import json
import math
import re
import tempfile
import warnings as image_warnings
from pathlib import Path

from PIL import Image

from .step1_config import PROJECT_ROOT, artifact_path, require


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp", ".gif", ".heic"}
MANIFEST_FIELDS = (
    "record_type", "image_id", "source_dataset", "original_path", "original_split", "scene_type",
    "source_classes", "source_class_ids", "width", "height", "mode", "exif_orientation",
    "annotation_type", "label_path", "annotation_status", "image_status", "object_count", "role", "errors",
)


def index_source(source, root):
    """Bước 2: lập chỉ mục ảnh/nhãn theo cấu trúc của từng nguồn.

    Giữ lớp thư mục, split gốc và bối cảnh; bỏ file phụ. Chuẩn hóa tên không phân
    biệt hoa thường để ghép ảnh/TXT trong cùng nguồn/split/thư mục, báo lỗi nếu trùng.
    Trả về gốc nguồn, hai chỉ mục ảnh/nhãn và số file bỏ qua; chưa đọc nội dung ảnh.
    """
    local = (root / source["local_root"]).resolve()
    images, labels, ignored = {}, {}, 0
    for path in sorted(local.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(local)
        parts, suffix = relative.parts, path.suffix.lower()
        if any(p.startswith(".") or p == "__MACOSX" for p in parts):
            ignored += 1
            continue
        is_image = suffix in IMAGE_SUFFIXES
        is_label = suffix == ".txt" and source["annotation_type"] != "folder_classification"
        if not (is_image or is_label):
            ignored += 1
            continue
        split, scene, folder_class = "", "", ""
        key = relative.with_suffix("").as_posix().casefold()
        if source["annotation_type"] == "yolo_split":
            require(len(parts) >= 3 and parts[0] in ("train", "val", "valid", "test")
                    and parts[1] == ("images" if is_image else "labels"),
                    str(path), "expected split/images or split/labels layout")
            split = parts[0]
            key = (Path(split) / Path(*parts[2:]).with_suffix("")).as_posix().casefold()
        elif source["annotation_type"] == "folder_classification":
            require(len(parts) >= 2 and parts[0] in source["mapping"], str(path), "unknown folder class")
            folder_class = parts[0]
            if len(parts) > 2:
                require(parts[1] in ("default", "real_world"), str(path), "unknown classification scene directory")
                scene = parts[1]
        index = images if is_image else labels
        require(key not in index, source["id"], f"normalized filename collision: {path} and {index.get(key)}")
        index[key] = (path, split, scene, folder_class) if is_image else path
    require(bool(images), source["id"], "no supported images found")
    return local, images, labels, ignored


def read_label(path, source):
    """Đọc nhãn gốc và kiểm tra từng box; dùng chung cho kiểm kê và remap.

    Giữ nguyên nội dung TXT và số dòng để truy vết; dòng sai chỉ lưu trong nhãn
    gốc/lỗi, không biến thành box hợp lệ. Không sửa tọa độ hay xác nhận ảnh nền.
    """
    objects, errors = [], []
    if path is None:
        return "missing", None, objects, ["missing YOLO label"]
    try:
        original = path.read_bytes().decode("utf-8-sig")
    except (OSError, UnicodeError) as exc:
        return "invalid", None, objects, [f"label read error: {exc}"]
    for number, line in enumerate(original.splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split()
        try:
            if len(parts) != 5 or not re.fullmatch(r"[0-9]+", parts[0]):
                raise ValueError("expected class_id and four coordinates")
            class_id = int(parts[0])
            if not 0 <= class_id < len(source["class_names"]):
                raise ValueError("source class ID out of range")
            x, y, width, height = map(float, parts[1:])
            if not all(math.isfinite(v) for v in (x, y, width, height)):
                raise ValueError("non-finite coordinate")
            if not (0 <= x <= 1 and 0 <= y <= 1 and 0 < width <= 1 and 0 < height <= 1):
                raise ValueError("invalid normalized coordinate or box size")
            objects.append({"line_number": number, "source_class_id": class_id,
                            "bbox_xywh": [x, y, width, height]})
        except ValueError as exc:
            errors.append(f"label line {number}: {exc}")
    return ("invalid" if errors else "unreviewed" if objects else "empty_unverified"), original, objects, errors


def inspect_label(path, source):
    """Tổng hợp trạng thái, số box hợp lệ theo lớp và lỗi cho manifest bước 2."""
    status, _, objects, errors = read_label(path, source)
    return status, Counter(obj["source_class_id"] for obj in objects), errors


def inspect_image(path):
    """Kiểm tra file và giải mã đầy đủ ảnh bằng Pillow để phát hiện lỗi đọc.

    Trả về kích thước gốc, chế độ màu, EXIF orientation, trạng thái và cảnh báo/lỗi.
    Không xoay, resize hoặc ghi lại ảnh.
    """
    metadata, errors, status = {}, [], "ok"
    try:
        with image_warnings.catch_warnings(record=True) as caught:
            image_warnings.simplefilter("always")
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                image.load()
                metadata = {"width": image.width, "height": image.height, "mode": image.mode,
                            "exif_orientation": image.getexif().get(274, 1)}
            errors.extend(str(w.message) for w in caught)
            if errors:
                status = "decode_warning"
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as exc:
        status, errors = "decode_error", [f"image decode error: {exc}"]
    return metadata, status, errors


def run_inventory(config, warnings, *, project_root=PROJECT_ROOT):
    """Điều phối bước 2 cho mọi nguồn: ghép nhãn, đọc ảnh và tổng hợp thống kê.

    Tạo ID ổn định từ nguồn/đường dẫn; ghi cả ảnh lỗi, thiếu nhãn và nhãn mồ côi.
    Xuất manifest.csv và inventory-summary.json trong artifacts, thay kết quả cũ
    sau khi xử lý xong. Chưa làm sạch, dedup hoặc chia tập; giữ nguyên processed-data.
    """
    root = project_root.resolve()
    manifest = artifact_path(config, "manifest.csv", root)
    summary_path = artifact_path(config, "inventory-summary.json", root)
    # Kiểm tra xung đột tên trong tất cả nguồn trước khi ghi kết quả.
    indexed = [(source, index_source(source, root)) for source in config["sources"]]
    summary = {"schema_version": 1, "warnings": warnings, "sources": {},
               "scope": "Inventory only; no remap, deduplication, image transforms, split assignment or label approval.",
               "paths": "original_path and label_path are relative to each source local_root",
               "class_counts": "Source classes; YOLO counts include only labels with no syntax/range errors. Class IDs may be unverified."}
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".inventory-", dir=manifest.parent) as temporary:
        temp_manifest = Path(temporary) / "manifest.csv"
        with temp_manifest.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=MANIFEST_FIELDS)
            writer.writeheader()
            for source, (local, images, labels, ignored) in indexed:
                print(f"Inventory {source['id']}: {len(images)} images...", flush=True)
                counts = Counter({key: 0 for key in ("images", "paired_labels", "missing_labels", "empty_labels",
                    "invalid_labels", "orphan_labels", "needs_annotation", "decode_errors", "decode_warnings")})
                classes, objects, splits, scenes = Counter(), Counter(), Counter(), Counter()
                for number, (key, (path, split, scene, folder_class)) in enumerate(sorted(images.items()), 1):
                    relative = path.relative_to(local).as_posix()
                    label = labels.get(key)
                    row = dict.fromkeys(MANIFEST_FIELDS, "")
                    row.update(record_type="image", image_id=hashlib.sha256(f"{source['id']}\0{relative}".encode()).hexdigest(),
                               source_dataset=source["id"], original_path=relative, original_split=split, scene_type=scene,
                               annotation_type=source["annotation_type"], role=source["role"])
                    metadata, row["image_status"], errors = inspect_image(path)
                    row.update(metadata)
                    ids, source_classes = [], [folder_class] if folder_class else []
                    if folder_class:
                        row["annotation_status"] = "needs_annotation"
                        counts["needs_annotation"] += 1
                        classes[folder_class] += 1
                    else:
                        status, object_counts, label_errors = inspect_label(label, source)
                        row.update(annotation_status=status, label_path=label.relative_to(local).as_posix() if label else "")
                        errors.extend(label_errors)
                        counts["paired_labels" if label else "missing_labels"] += 1
                        if status in ("invalid", "empty_unverified"):
                            counts["invalid_labels" if status == "invalid" else "empty_labels"] += 1
                        ids = sorted(object_counts)
                        source_classes = [source["class_names"][i] for i in ids]
                        row["object_count"] = sum(object_counts.values())
                        if status == "unreviewed":
                            classes.update(source_classes)
                            objects.update({source["class_names"][i]: n for i, n in object_counts.items()})
                    row.update(source_classes=json.dumps(source_classes, ensure_ascii=False),
                               source_class_ids=json.dumps(ids), errors=json.dumps(errors, ensure_ascii=False))
                    writer.writerow(row)
                    counts["images"] += 1
                    counts["decode_errors"] += row["image_status"] == "decode_error"
                    counts["decode_warnings"] += row["image_status"] == "decode_warning"
                    splits[split or "unspecified"] += 1
                    scenes[scene or "unspecified"] += 1
                    if number % 1000 == 0:
                        print(f"  {source['id']}: {number}/{len(images)}", flush=True)
                for key in sorted(labels.keys() - images.keys()):
                    writer.writerow({"record_type": "orphan_label", "source_dataset": source["id"],
                                     "label_path": labels[key].relative_to(local).as_posix(),
                                     "original_split": key.split("/")[0] if source["annotation_type"] == "yolo_split" else "",
                                     "annotation_type": source["annotation_type"], "role": source["role"],
                                     "annotation_status": "orphan", "errors": '["label has no image"]'})
                    counts["orphan_labels"] += 1
                summary["sources"][source["id"]] = {**counts, "local_root": source["local_root"], "role": source["role"],
                    "label_files": len(labels), "ignored_files": ignored, "images_by_class": dict(sorted(classes.items())),
                    "objects_by_class": dict(sorted(objects.items())), "original_splits": dict(sorted(splits.items())),
                    "scene_types": dict(sorted(scenes.items()))}
        summary["totals"] = {key: sum(source[key] for source in summary["sources"].values())
                             for key in (*counts.keys(), "label_files", "ignored_files")}
        summary["manifest_sha256"] = hashlib.sha256(temp_manifest.read_bytes()).hexdigest()
        temp_summary = Path(temporary) / "inventory-summary.json"
        temp_summary.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        temp_manifest.replace(manifest)
        temp_summary.replace(summary_path)
    return manifest, summary_path
