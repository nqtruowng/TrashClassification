"""Bước 6: chia ảnh sạch theo nhóm, cân đối nguồn/lớp, không tự duyệt nhãn."""

from collections import Counter, defaultdict
import csv
import hashlib
import json
import random
import tempfile
from pathlib import Path

from .step1_config import PROJECT_ROOT, artifact_path, require


SPLITS = ("train", "test", "val")
SPLIT_FIELDS = ("image_id", "source_dataset", "original_path", "original_split", "image_path",
                "group_id", "file_sha256", "pixel_sha256", "target_class_ids",
                "annotation_status", "ready_for_training", "split")


def assign_groups(rows, ratios, seed):
    """Chia nguyên nhóm; ưu tiên nhóm lớn, rồi lớp hiếm, phá hòa bằng seed.

    Làm tròn tổng ảnh bằng phần dư lớn nhất. Chọn tập còn chỗ và giảm sai lệch
    bình phương theo nguồn và nguồn × lớp (mỗi ảnh tính một lần mỗi lớp).
    Nếu nhóm không vừa tập nào, cho phép lệch số lượng thay vì tách nhóm.
    """
    totals, groups = Counter(), defaultdict(Counter)
    sizes = Counter()
    for row in rows:
        gid, source = row["group_id"], row["source_dataset"]
        features = [(source, None), *((source, c) for c in set(row["target_class_ids"]))]
        groups[gid].update(features)
        totals.update(features)
        sizes[gid] += 1
    targets = {s: int(len(rows) * ratios[s]) for s in SPLITS}
    remainder_order = sorted(SPLITS, key=lambda s: -(len(rows) * ratios[s] - targets[s]))
    for s in remainder_order[:len(rows) - sum(targets.values())]:
        targets[s] += 1
    rng = random.Random(seed)
    order = sorted(groups)
    rng.shuffle(order)
    order.sort(key=lambda gid: (-sizes[gid], -sum(n / totals[f] for f, n in groups[gid].items())))
    assigned, counts = {}, Counter()
    feature_counts = {s: Counter() for s in SPLITS}
    for gid in order:
        size, features = sizes[gid], groups[gid]
        candidates = [s for s in SPLITS if ratios[s] > 0 and counts[s] + size <= targets[s]]
        if not candidates:
            candidates = [s for s in SPLITS if ratios[s] > 0]
            overflow = min(counts[s] + size - targets[s] for s in candidates)
            candidates = [s for s in candidates if counts[s] + size - targets[s] == overflow]
        rng.shuffle(candidates)

        def score(split):
            """Độ tăng sai lệch chuẩn hóa; số nhỏ hơn giữ phân bố gần tỷ lệ đích hơn."""
            return sum((2 * (feature_counts[split][f] - totals[f] * ratios[split]) * n + n*n)
                       / max(totals[f] * ratios[split], 1) for f, n in features.items())

        chosen = min(candidates, key=score)
        assigned[gid] = chosen
        counts[chosen] += size
        feature_counts[chosen].update(features)
    return assigned, targets


def run_split(config, warnings, *, project_root=PROJECT_ROOT):
    """Đọc clean có checksum hợp lệ, kiểm tra leakage và ghi manifest chia tập.

    Dùng nhãn nguồn sẵn có theo yêu cầu; giữ trạng thái chưa duyệt. Không sao chép
    ảnh/box và không xuất dataset train: manifest liên kết tới clean qua image_id.
    """
    root = project_root.resolve()
    clean = artifact_path(config, "clean/annotations.jsonl", root)
    clean_summary = artifact_path(config, "clean/summary.json", root)
    output = artifact_path(config, "split-manifest.csv", root)
    summary_path = artifact_path(config, "split-summary.json", root)
    require(clean.is_file() and clean_summary.is_file(), "split", "run --stage clean first")
    previous = json.loads(clean_summary.read_text(encoding="utf-8"))
    data = clean.read_bytes()
    checksum = hashlib.sha256(data).hexdigest()
    require(checksum == previous["annotations_sha256"] and config == previous["configuration"],
            "split", "clean checksum/configuration mismatch; rerun remap and clean")
    rows = [json.loads(line) for line in data.decode("utf-8").splitlines()]
    require(bool(rows) and len(rows) == previous["kept"], "split", "empty or incomplete clean input")
    require(len({r["image_id"] for r in rows}) == len(rows), "split", "duplicate image IDs")
    sources = {s["id"] for s in config["sources"]}
    for row in rows:
        require(row["source_dataset"] in sources and row["group_id"] and row["objects"]
                and row["original_annotation_status"] == "unreviewed"
                and row["annotation_status"] in ("needs_review", "approved"),
                row["image_id"], "expected a clean image with valid source boxes and group_id")
        require(set(row["target_class_ids"]) == {o["target_class_id"] for o in row["objects"]}
                and all(type(c) is int and 0 <= c < len(config["classes"]) for c in row["target_class_ids"]),
                row["image_id"], "invalid target classes")
        require((root / row["image_path"]).is_file(), row["image_id"], "clean image is missing")
    # Hash giống nhau phải cùng nhóm trước khi chia, kể cả đầu vào được sửa bên ngoài.
    for key in ("file_sha256", "pixel_sha256"):
        groups_by_hash = {}
        for row in rows:
            value = row[key]
            require(bool(value), row["image_id"], f"missing {key}")
            require(groups_by_hash.setdefault(value, row["group_id"]) == row["group_id"],
                    "split", f"{key} occurs in different groups; rerun clean")
    assignments, targets = assign_groups(rows, config["split"], config["seed"])
    summary = {"schema_version": 1, "configuration": config, "warnings": list(warnings),
               "input_sha256": checksum, "images": len(rows), "groups": len(assignments),
               "target_images": targets, "splits": {},
               "method": "Seeded greedy whole-group allocation balancing source and source/class image counts; largest-remainder targets.",
               "scope": "Split assignment only; existing annotation status is preserved. No label approval or YOLO export."}
    for split in SPLITS:
        subset = [r for r in rows if assignments[r["group_id"]] == split]
        classes = Counter(c for r in subset for c in set(r["target_class_ids"]))
        boxes = Counter(o["target_class_id"] for r in subset for o in r["objects"])
        summary["splits"][split] = {
            "images": len(subset), "ratio": len(subset) / len(rows),
            "target_difference": len(subset) - targets[split],
            "groups": len({r["group_id"] for r in subset}),
            "sources": dict(sorted(Counter(r["source_dataset"] for r in subset).items())),
            "images_by_class": {name: classes[i] for i, name in enumerate(config["classes"])},
            "boxes_by_class": {name: boxes[i] for i, name in enumerate(config["classes"])},
            "annotation_statuses": dict(Counter(r["annotation_status"] for r in subset)),
        }
    # Đối chiếu ID, nhóm và cả hai loại hash giữa từng cặp tập trước khi ghi.
    overlaps = {}
    for key in ("image_id", "group_id", "file_sha256", "pixel_sha256"):
        values = {s: {r[key] for r in rows if assignments[r["group_id"]] == s} for s in SPLITS}
        overlaps[key] = {f"{a}/{b}": len(values[a] & values[b])
                         for i, a in enumerate(SPLITS) for b in SPLITS[i+1:]}
        require(not any(overlaps[key].values()), "split", f"cross-split overlap in {key}")
    summary["overlaps"] = overlaps
    if any(v["target_difference"] for v in summary["splits"].values()):
        summary["warnings"].append("Whole groups prevent exact target counts; see target_difference.")
    with tempfile.TemporaryDirectory(prefix=".split-", dir=output.parent) as temporary:
        manifest = Path(temporary) / output.name
        with manifest.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=SPLIT_FIELDS)
            writer.writeheader()
            for row in sorted(rows, key=lambda r: r["image_id"]):
                record = {key: row[key] for key in SPLIT_FIELDS if key != "split"}
                record.update(split=assignments[row["group_id"]],
                              target_class_ids=json.dumps(row["target_class_ids"]),
                              ready_for_training=json.dumps(row["ready_for_training"]))
                writer.writerow(record)
        summary["manifest_sha256"] = hashlib.sha256(manifest.read_bytes()).hexdigest()
        report = Path(temporary) / summary_path.name
        report.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        manifest.replace(output)
        report.replace(summary_path)
    print(f"Split {len(rows)} images: " + ", ".join(f"{s}={summary['splits'][s]['images']}" for s in SPLITS), flush=True)
    return output, summary_path
