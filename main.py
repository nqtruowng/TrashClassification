"""Validate dataset configuration. Write a single report only with --report."""

import sys

sys.dont_write_bytecode = True

import argparse
import hashlib
import importlib.metadata
import json
import math
import re
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent


class ConfigError(ValueError):
    pass


def require(condition, location, message):
    if not condition:
        raise ConfigError(f"{location}: {message}")


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node):
    pairs = loader.construct_pairs(node)
    result = {}
    for key, value in pairs:
        require(isinstance(key, (str, int)), "YAML", "invalid mapping key")
        require(key not in result, f"YAML line {node.start_mark.line + 1}", f"duplicate key {key!r}")
        result[key] = value
    return result


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def read_yaml(path):
    try:
        return yaml.load(path.read_text(encoding="utf-8-sig"), Loader=UniqueKeyLoader)
    except (OSError, UnicodeError, yaml.YAMLError, ConfigError) as exc:
        raise ConfigError(f"{path}: {exc}") from exc


def fields(value, location, required, optional=()):
    require(isinstance(value, dict), location, "expected a mapping")
    for key in value:
        require(key in set(required) | set(optional), f"{location}.{key}", "unknown key")
    for key in required:
        require(key in value, f"{location}.{key}", "required field missing")


def names(value, location):
    require(isinstance(value, list) and bool(value), location, "expected a list of names")
    require(all(isinstance(s, str) and s.strip() and s == s.strip() for s in value), location, "invalid name")
    require(len(value) == len(set(value)), location, "names must be unique")
    return value


def resolve_path(value, root, location):
    require(isinstance(value, str) and bool(value.strip()), location, "expected a path string")
    return (root / value).resolve()


def load_configuration(config_path="configs/dataset.yaml", *, project_root=PROJECT_ROOT):
    root = project_root.resolve()
    config = read_yaml(root / config_path)
    fields(config, "config", ("schema_version", "classes", "seed", "split", "eval", "sources"))
    require(type(config["schema_version"]) is int and config["schema_version"] == 1, "config.schema_version", "expected version 1")
    classes = names(config["classes"], "config.classes")
    require("DROP" not in classes, "config.classes", "DROP is reserved for excluded classes")
    require(type(config["seed"]) is int and 0 <= config["seed"] < 2**32, "config.seed", "expected an integer in [0, 2**32)")
    fields(config["split"], "config.split", ("train", "val"))
    for split, ratio in config["split"].items():
        require(type(ratio) in (int, float) and 0 <= ratio <= 1, f"config.split.{split}", "expected a finite number in [0, 1]")
    require(math.isclose(sum(config["split"].values()), 1, abs_tol=1e-9, rel_tol=0), "config.split", "ratios must sum to 1")
    fields(config["eval"], "config.eval", ("test_source",))
    test_source = config["eval"]["test_source"]
    require(test_source is None or isinstance(test_source, str), "config.eval.test_source", "expected a source ID or null")
    require(isinstance(config["sources"], list) and bool(config["sources"]), "config.sources", "expected a nonempty list")
    ids, roots, test_sources, warnings = set(), set(), set(), []
    for index, source in enumerate(config["sources"]):
        loc = f"config.sources[{index}]"
        fields(source, loc, ("id", "local_root", "annotation_type", "role", "cap", "mapping"),
               ("class_names", "native_data_yaml", "class_order_verified"))
        source_id = source["id"]
        require(isinstance(source_id, str) and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", source_id), f"{loc}.id", "invalid source ID")
        require(source_id not in ids, f"{loc}.id", "duplicate source ID")
        ids.add(source_id)
        local = resolve_path(source["local_root"], root, f"{loc}.local_root")
        require(local.is_dir(), f"{loc}.local_root", f"directory does not exist: {local}")
        require(local not in roots, f"{loc}.local_root", "duplicate source directory")
        roots.add(local)
        kind, role, cap = source["annotation_type"], source["role"], source["cap"]
        require(kind in ("folder_classification", "yolo_flat", "yolo_split"), f"{loc}.annotation_type", "unsupported annotation type")
        require(role in ("train_val", "test_only"), f"{loc}.role", "unsupported role")
        if role == "test_only":
            test_sources.add(source_id)
        require(cap is None or type(cap) is int and cap >= 0, f"{loc}.cap", "expected a nonnegative integer or null")
        require(role == "train_val" or cap is None, f"{loc}.cap", "cap applies only to train")
        if kind == "folder_classification":
            require(not {"class_names", "native_data_yaml", "class_order_verified"} & source.keys(), loc, "folder classes come from mapping; YOLO metadata is not applicable")
            source_names = sorted(p.name for p in local.iterdir() if p.is_dir() and p.name != "__MACOSX" and not p.name.startswith("."))
            require(bool(source_names), f"{loc}.local_root", "no class directories found")
        else:
            source_names = names(source.get("class_names"), f"{loc}.class_names")
            require(type(source.get("class_order_verified")) is bool, f"{loc}.class_order_verified", "expected an explicit boolean")
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
            require(isinstance(target, str) and target in [*classes, "DROP"], f"{loc}.mapping.{name}", f"unknown target class {target!r}")
    require(test_source is None or test_source in ids, "config.eval.test_source", "unknown source")
    require(test_sources == ({test_source} if test_source is not None else set()), "config.eval.test_source", "conflicts with source role=test_only declarations")
    return config, warnings


def write_report(config, warnings, config_path, *, project_root=PROJECT_ROOT):
    """Overwrite one small report; never copy code, configuration or raw data."""
    root = project_root.resolve()
    output = (root / "artifacts/config-check.json").resolve()
    protected = [(root / name).resolve() for name in ("raw-data", "processed-data")]
    protected += [(root / source["local_root"]).resolve() for source in config["sources"]]
    require(output.is_relative_to(root) and not any(output.is_relative_to(p) for p in protected),
            "report", "must stay outside raw-data, processed-data and source directories")
    inputs = [root / config_path, root / "main.py", root / "uv.lock"]
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/dataset.yaml", help="YAML path relative to the project root")
    parser.add_argument("--report", action="store_true", help="Update artifacts/config-check.json")
    args = parser.parse_args(argv)
    try:
        config, warnings = load_configuration(args.config)
        print(f"Configuration valid: {len(config['sources'])} sources, {len(config['classes'])} target classes.")
        for warning in warnings:
            print(f"REVIEW: {warning}")
        if args.report:
            print(f"Report: {write_report(config, warnings, args.config)}")
    except (ConfigError, OSError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
