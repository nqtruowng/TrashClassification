"""Tiền xử lý YOLO: cấu hình, kiểm kê, remap, làm sạch và chia train/test/val."""

import sys

sys.dont_write_bytecode = True

import argparse

from src.preprocess.step1_config import ConfigError, load_configuration, write_report
from src.preprocess.step2_inventory import run_inventory
from src.preprocess.step3_remap import run_remap
from src.preprocess.step4_clean import run_clean
from preprocess.step5_split import run_split


def main(argv=None):
    """Nhận tham số CLI, kiểm tra cấu hình rồi chạy stage được chọn.

    Mặc định chỉ kiểm tra cấu hình; --stage inventory chạy kiểm kê, --report ghi
    thêm báo cáo bước 1; --stage remap chuẩn hóa lớp; --stage clean lọc lỗi/trùng.
    --stage split chia ảnh sạch theo nhóm, giữ trạng thái duyệt nhãn hiện có.
    Trả mã 0 khi hoàn tất, mã 2 khi lỗi cấu hình/đọc ghi file.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/dataset.yaml", help="YAML path relative to the project root")
    parser.add_argument("--report", action="store_true", help="Update artifacts/config-check.json")
    parser.add_argument("--stage", choices=("config", "inventory", "remap", "clean", "split"), default="config")
    args = parser.parse_args(argv)
    try:
        config, warnings = load_configuration(args.config)
        print(f"Configuration valid: {len(config['sources'])} sources, {len(config['classes'])} target classes.")
        for warning in warnings:
            print(f"REVIEW: {warning}")
        if args.report:
            print(f"Report: {write_report(config, warnings, args.config)}")
        if args.stage == "inventory":
            manifest, summary = run_inventory(config, warnings)
            print(f"Manifest: {manifest}\nSummary: {summary}")
        elif args.stage == "remap":
            annotations, summary = run_remap(config, warnings)
            print(f"Annotations: {annotations}\nSummary: {summary}")
        elif args.stage == "clean":
            annotations, summary = run_clean(config, warnings)
            print(f"Clean annotations: {annotations}\nSummary: {summary}")
        elif args.stage == "split":
            manifest, summary = run_split(config, warnings)
            print(f"Split manifest: {manifest}\nSummary: {summary}")
    except (ConfigError, OSError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
