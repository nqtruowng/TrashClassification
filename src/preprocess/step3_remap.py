"""Bước 3: chuẩn hóa lớp, giữ nhãn gốc và phân luồng xử lý trước khi làm sạch."""

from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import tempfile

from .step1_config import PROJECT_ROOT, artifact_path, require
from .step2_inventory import read_label


def source_path(local, relative):
    """Đọc đường dẫn từ manifest, chặn đường dẫn tuyệt đối hoặc thoát khỏi nguồn."""
    path = (local / relative).resolve()
    require(bool(relative) and not Path(relative).is_absolute() and path.is_relative_to(local),
            relative, "manifest path must stay inside source local_root")
    return path


def audit_class_order(rows, sources):
    """Đối chiếu ID trong manifest với tiền tố tên ảnh của nguồn YOLO chưa xác minh.

    Đây là kiểm tra tính nhất quán, không thay thế việc xem ảnh hoặc metadata gốc.
    Dừng nếu tên lớp trong cấu hình đổi hoặc tiền tố rõ ràng mâu thuẫn ID nhãn.
    """
    audit = {sid: {"class_names": s["class_names"], "matched": 0, "unmatched_filename": 0,
                   "without_valid_objects": 0, "examples": {}}
             for sid, s in sources.items() if s["annotation_type"] != "folder_classification"
             and not s["class_order_verified"]}
    for row in rows:
        source = sources[row["source_dataset"]]
        if row["record_type"] != "image" or source["annotation_type"] == "folder_classification":
            continue
        ids = json.loads(row["source_class_ids"])
        require(all(0 <= i < len(source["class_names"]) for i in ids)
                and [source["class_names"][i] for i in ids] == json.loads(row["source_classes"]),
                source["id"], "class order differs from inventory; rerun inventory")
        if source["id"] not in audit:
            continue
        entry = audit[source["id"]]
        prefix = [i for i, name in enumerate(source["class_names"])
                  if Path(row["original_path"]).stem.casefold().startswith(name.casefold())]
        if not ids:
            entry["without_valid_objects"] += 1
        elif len(prefix) != 1:
            entry["unmatched_filename"] += 1
        else:
            require(ids == prefix, row["original_path"], "filename/class ID mismatch; verify source class order")
            entry["matched"] += 1
            entry["examples"].setdefault(source["class_names"][prefix[0]], row["original_path"])
    return audit


def remap_record(row, source, classes, root):
    """Ánh xạ một ảnh/nhãn, giữ cả đối tượng DROP và lý do phải xử lý tiếp.

    Nhãn thư mục chỉ có lớp ảnh, không tạo box giả. Nhãn thiếu/rỗng không trở
    thành background; ảnh có lớp giữ lẫn DROP phải kiểm tra toàn bộ trước khi dùng.
    """
    local = (root / source["local_root"]).resolve()
    record = {**row, "original_annotation_status": row["annotation_status"],
              "source_classes": json.loads(row["source_classes"] or "[]"),
              "source_class_ids": json.loads(row["source_class_ids"] or "[]"),
              "errors": json.loads(row["errors"] or "[]"), "objects": [],
              "original_label": None, "target_classes": [], "target_class_ids": [],
              "reasons": [], "ready_for_training": False}
    for key in ("width", "height", "exif_orientation", "object_count"):
        record[key] = int(row[key]) if row[key] else None
    reasons = record["reasons"]
    folder = source["annotation_type"] == "folder_classification"
    if row["record_type"] == "image":
        require(source_path(local, row["original_path"]).is_file(), row["original_path"],
                "image missing since inventory; rerun inventory")
    if folder:
        names = record["source_classes"]
        require(len(names) == 1 and names[0] in source["mapping"], source["id"], "unknown folder class")
        target = source["mapping"][names[0]]
        targets = [] if target == "DROP" else [target]
        status = "out_of_scope" if target == "DROP" else "needs_annotation"
        reasons.append("all_classes_dropped" if target == "DROP" else "folder_label_has_no_boxes")
    else:
        path = source_path(local, row["label_path"]) if row["label_path"] else None
        label_status, original, objects, errors = read_label(path, source)
        record["original_label"] = original
        record["class_order_verified"] = source["class_order_verified"]
        if row["record_type"] == "image":
            require(label_status == row["annotation_status"]
                    and len(objects) == int(row["object_count"])
                    and sorted({obj["source_class_id"] for obj in objects}) == record["source_class_ids"],
                    row["label_path"] or row["original_path"], "labels changed since inventory; rerun inventory")
        record["errors"] = list(dict.fromkeys(record["errors"] + errors))
        for obj in objects:
            name = source["class_names"][obj["source_class_id"]]
            target = source["mapping"][name]
            obj.update(source_class_name=name, target_class_name=None if target == "DROP" else target,
                       target_class_id=classes.index(target) if target != "DROP" else None,
                       mapping_status="dropped" if target == "DROP" else "mapped")
        record["objects"] = objects
        targets = sorted({obj["target_class_name"] for obj in objects if obj["mapping_status"] == "mapped"},
                         key=classes.index)
        dropped = any(obj["mapping_status"] == "dropped" for obj in objects)
        status = "needs_review"
        if label_status in ("missing", "empty_unverified"):
            status = "needs_annotation"
            reasons.append("missing_label" if label_status == "missing" else "empty_label_unverified")
        elif label_status == "invalid":
            reasons.append("invalid_label")
        elif dropped and not targets:
            status = "out_of_scope"
            reasons.append("all_classes_dropped")
        else:
            reasons.append("mixed_kept_and_dropped_objects" if dropped else "boxes_not_reviewed")
        if not source["class_order_verified"]:
            reasons.append("source_class_order_unverified")
    if row["record_type"] == "orphan_label" or row["image_status"] == "decode_error":
        status = "excluded"
        reasons.append("orphan_label" if row["record_type"] == "orphan_label" else "image_decode_error")
    elif row["image_status"] == "decode_warning":
        reasons.append("image_decode_warning")
        if status != "out_of_scope":
            status = "needs_review"
    record.update(annotation_status=status, target_classes=targets,
                  target_class_ids=[classes.index(name) for name in targets])
    return record


def run_remap(config, warnings, *, project_root=PROJECT_ROOT):
    """Đọc manifest bước 2, remap vào một JSONL và xuất thống kê cùng checksum.

    Các hàng đợi được lọc bằng annotation_status trong cùng file để tránh bản sao.
    Giữ role train_val/test_only và split gốc; chưa chia tập hoặc xuất dữ liệu train.
    """
    root = project_root.resolve()
    manifest = artifact_path(config, "manifest.csv", root)
    inventory_path = artifact_path(config, "inventory-summary.json", root)
    output = artifact_path(config, "annotations.jsonl", root)
    summary_path = artifact_path(config, "remap-summary.json", root)
    require(manifest.is_file() and inventory_path.is_file(), "remap", "run --stage inventory first")
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    checksum = hashlib.sha256(manifest.read_bytes()).hexdigest()
    require(checksum == inventory["manifest_sha256"], "manifest", "checksum mismatch; rerun inventory")
    sources = {source["id"]: source for source in config["sources"]}
    require(sources.keys() == inventory["sources"].keys(), "remap", "sources changed; rerun inventory")
    for sid, source in sources.items():
        require(all(source[key] == inventory["sources"][sid][key] for key in ("local_root", "role")),
                sid, "source root/role changed; rerun inventory")
    with manifest.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        require(row["source_dataset"] in sources, "manifest", "unknown source")
        source = sources[row["source_dataset"]]
        require(row["record_type"] in ("image", "orphan_label")
                and row["annotation_type"] == source["annotation_type"] and row["role"] == source["role"],
                source["id"], "source type/role differs from inventory; rerun inventory")
    audit = audit_class_order(rows, sources)
    summary = {"schema_version": 1, "classes": config["classes"], "warnings": warnings,
               "manifest_sha256": checksum, "configuration": config, "class_order_audit": audit,
               "scope": "Provisional remapping only; no label approval, image transform or split assignment.",
               "sources": {}, "statuses": Counter(), "reasons": Counter()}
    with tempfile.TemporaryDirectory(prefix=".remap-", dir=output.parent) as temporary:
        temp_output = Path(temporary) / output.name
        with temp_output.open("w", encoding="utf-8", newline="\n") as stream:
            for row in rows:
                source = sources[row["source_dataset"]]
                record = remap_record(row, source, config["classes"], root)
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
                counts = summary["sources"].setdefault(source["id"], {
                    "role": source["role"], "images": 0, "orphan_labels": 0, "statuses": Counter(),
                    "images_by_target_class": Counter(), "candidate_objects_by_target_class": Counter(),
                    "dropped_objects": 0})
                counts["images" if row["record_type"] == "image" else "orphan_labels"] += 1
                counts["statuses"][record["annotation_status"]] += 1
                if row["record_type"] == "image":
                    counts["images_by_target_class"].update(record["target_classes"])
                counts["candidate_objects_by_target_class"].update(
                    obj["target_class_name"] for obj in record["objects"] if obj["mapping_status"] == "mapped")
                counts["dropped_objects"] += sum(obj["mapping_status"] == "dropped" for obj in record["objects"])
                summary["statuses"][record["annotation_status"]] += 1
                summary["reasons"].update(record["reasons"])
        summary["records"] = len(rows)
        summary["annotations_sha256"] = hashlib.sha256(temp_output.read_bytes()).hexdigest()
        temp_summary = Path(temporary) / summary_path.name
        temp_summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp_output.replace(output)
        temp_summary.replace(summary_path)
    print(f"Remapped {len(rows)} records: {dict(summary['statuses'])}", flush=True)
    return output, summary_path
