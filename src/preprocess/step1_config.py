"""Bước 1: đọc, kiểm tra cấu hình dataset và ghi báo cáo môi trường khi được yêu cầu."""

import hashlib
import importlib.metadata
import json
import math
import re
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ConfigError(ValueError):
    """Lỗi cấu hình hoặc cấu trúc dataset, kèm vị trí để người dùng sửa."""


def require(condition, location, message):
    """Dừng bằng ConfigError khi điều kiện không đạt; ghi rõ vị trí và lý do lỗi."""
    if not condition:
        raise ConfigError(f"{location}: {message}")


class UniqueKeyLoader(yaml.SafeLoader):
    """Bộ đọc YAML an toàn, dùng unique_mapping để phát hiện khóa khai báo trùng."""


def unique_mapping(loader, node):
    """Đọc một mapping YAML và báo lỗi khóa trùng, tránh ghi đè giá trị âm thầm."""
    pairs = loader.construct_pairs(node)
    result = {}
    for key, value in pairs:
        require(isinstance(key, (str, int)), "YAML", "invalid mapping key")
        require(key not in result, f"YAML line {node.start_mark.line + 1}", f"duplicate key {key!r}")
        result[key] = value
    return result


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def read_yaml(path):
    """Đọc file YAML UTF-8; chuyển lỗi đọc file/cú pháp thành thông báo có đường dẫn."""
    try:
        return yaml.load(path.read_text(encoding="utf-8-sig"), Loader=UniqueKeyLoader)
    except (OSError, UnicodeError, yaml.YAMLError, ConfigError) as exc:
        raise ConfigError(f"{path}: {exc}") from exc


def fields(value, location, required, optional=()):
    """Kiểm tra một mục cấu hình: phải là dictionary, đủ khóa bắt buộc và không có khóa lạ."""
    require(isinstance(value, dict), location, "expected a mapping")
    for key in value:
        require(key in set(required) | set(optional), f"{location}.{key}", "unknown key")
    for key in required:
        require(key in value, f"{location}.{key}", "required field missing")


def names(value, location):
    """Kiểm tra danh sách tên lớp: không rỗng, không trùng, không có khoảng trắng thừa."""
    require(isinstance(value, list) and bool(value), location, "expected a list of names")
    require(all(isinstance(s, str) and s.strip() and s == s.strip() for s in value), location, "invalid name")
    require(len(value) == len(set(value)), location, "names must be unique")
    return value


def resolve_path(value, root, location):
    """Kiểm tra chuỗi đường dẫn rồi đổi thành đường dẫn tuyệt đối tính từ gốc project."""
    require(isinstance(value, str) and bool(value.strip()), location, "expected a path string")
    return (root / value).resolve()


def load_configuration(config_path="configs/dataset.yaml", *, project_root=PROJECT_ROOT):
    """Bước 1: kiểm tra nguồn YOLO, mapping và tỷ lệ train/test/val.

    Đối chiếu lớp với YAML gốc nếu có; trả về cấu hình và các cảnh báo.
    Chỉ xác nhận quy tắc hợp lệ, chưa kiểm kê ảnh hay chia dữ liệu.
    """
    root = project_root.resolve()
    config = read_yaml(root / config_path)
    fields(config, "config", ("schema_version", "classes", "seed", "split", "sources"))
    require(type(config["schema_version"]) is int and config["schema_version"] == 1, "config.schema_version", "expected version 1")
    classes = names(config["classes"], "config.classes")
    require(type(config["seed"]) is int and 0 <= config["seed"] < 2**32, "config.seed", "expected an integer in [0, 2**32)")
    fields(config["split"], "config.split", ("train", "test", "val"))
    for split, ratio in config["split"].items():
        require(type(ratio) in (int, float) and 0 <= ratio <= 1, f"config.split.{split}", "expected a finite number in [0, 1]")
    require(math.isclose(sum(config["split"].values()), 1, abs_tol=1e-9, rel_tol=0), "config.split", "ratios must sum to 1")
    require(isinstance(config["sources"], list) and bool(config["sources"]), "config.sources", "expected a nonempty list")
    ids, roots, warnings = set(), set(), []
    for index, source in enumerate(config["sources"]):
        loc = f"config.sources[{index}]"
        fields(source, loc, ("id", "local_root", "annotation_type", "mapping", "class_names", "class_order_verified"),
               ("native_data_yaml",))
        source_id = source["id"]
        require(isinstance(source_id, str) and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", source_id), f"{loc}.id", "invalid source ID")
        require(source_id not in ids, f"{loc}.id", "duplicate source ID")
        ids.add(source_id)
        local = resolve_path(source["local_root"], root, f"{loc}.local_root")
        require(local.is_dir(), f"{loc}.local_root", f"directory does not exist: {local}")
        require(local not in roots, f"{loc}.local_root", "duplicate source directory")
        roots.add(local)
        kind = source["annotation_type"]
        require(kind in ("yolo_flat", "yolo_split"), f"{loc}.annotation_type", "unsupported annotation type")
        source_names = names(source["class_names"], f"{loc}.class_names")
        require(type(source["class_order_verified"]) is bool, f"{loc}.class_order_verified", "expected an explicit boolean")
        if not source["class_order_verified"]:
            warnings.append(f"{source_id}: source class ID order is unverified; review before remapping")
        require(kind != "yolo_split" or "native_data_yaml" in source, f"{loc}.native_data_yaml", "required for yolo_split")
        if "native_data_yaml" in source:
            native = read_yaml(resolve_path(source["native_data_yaml"], root, f"{loc}.native_data_yaml"))
            require(isinstance(native, dict), f"{loc}.native_data_yaml", "expected a YAML mapping")
            native_names = native.get("names")
            if isinstance(native_names, dict):
                require(all(type(k) is int for k in native_names) and set(native_names) == set(range(len(source_names))),
                        f"{loc}.native_data_yaml.names", "source IDs must be contiguous integers starting at 0")
                native_names = [native_names[k] for k in range(len(source_names))]
            require(native_names == source_names, f"{loc}.class_names", "order/names differ from native data.yaml")
            require("nc" not in native or type(native["nc"]) is int and native["nc"] == len(source_names), f"{loc}.native_data_yaml.nc", "incorrect class count")
        fields(source["mapping"], f"{loc}.mapping", source_names)
        for name, target in source["mapping"].items():
            require(isinstance(target, str) and target in classes, f"{loc}.mapping.{name}", f"unknown target class {target!r}")
    return config, warnings


def artifact_path(config, name, root):
    """Xác định nơi ghi báo cáo trong artifacts; chặn ghi vào dữ liệu gốc hoặc processed-data."""
    output = (root / "artifacts" / name).resolve()
    protected = [(root / name).resolve() for name in ("raw-data", "processed-data")]
    protected += [(root / source["local_root"]).resolve() for source in config["sources"]]
    require(output.is_relative_to(root) and not any(output.is_relative_to(p) for p in protected),
            "report", "must stay outside raw-data, processed-data and source directories")
    return output


def write_report(config, warnings, config_path, *, project_root=PROJECT_ROOT):
    """Ghi kết quả bước 1, phiên bản môi trường và checksum vào config-check.json.

    Chỉ chạy khi có --report; cập nhật cùng file, không sao chép code hoặc dataset.
    """
    root = project_root.resolve()
    output = artifact_path(config, "config-check.json", root)
    inputs = [root / config_path, root / "main.py", root / "src/preprocess/step1_config.py",
              root / "src/preprocess/step2_inventory.py", root / "src/preprocess/step3_remap.py",
              root / "src/preprocess/step4_clean.py", root / "src/preprocess/step6_split.py", root / "uv.lock"]
    report = {
        "status": "valid", "source_count": len(config["sources"]), "classes": config["classes"],
        "warnings": warnings, "python": sys.version,
        "packages": {name: importlib.metadata.version(name) for name in ("PyYAML", "Pillow")},
        "sha256": {str(p.relative_to(root) if p.is_relative_to(root) else p): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in inputs if p.is_file()},
        "scope": "Configuration only; images and labels have not been validated.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output
