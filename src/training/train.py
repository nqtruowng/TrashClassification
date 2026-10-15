"""Train YOLOv8n pretrained. Chạy: uv run python -B src/training/train.py."""

import sys
from datetime import date
from pathlib import Path

sys.dont_write_bytecode = True

from ultralytics import YOLO


def train():
    """Đọc dataset, train trên GPU và lưu theo ngày-tháng-năm-tên_model."""
    root = Path(__file__).resolve().parents[2]
    data = root / "processed-data/data.yaml"
    if not data.is_file():
        raise FileNotFoundError(f"Chưa có dataset YOLO: {data}")

    model_dir = root / "model"
    model_dir.mkdir(exist_ok=True)
    weights = model_dir / "yolov8n.pt"
    model = YOLO(str(weights))  # Tự tải pretrained khi chưa có.
    model.train(
        data=str(data),
        epochs=5,       # Số vòng huấn luyện; chỉnh trực tiếp tại đây.
        imgsz=320,      # Kích thước ảnh đầu vào.
        batch=64,        # Số ảnh mỗi batch.
        workers=8,      # Số tiến trình phụ đọc và chuẩn bị dữ liệu.
        device=0,       # Bắt buộc dùng GPU NVIDIA đầu tiên; báo lỗi nếu CUDA không sẵn sàng.
        project=str(model_dir),
        name=f"{date.today():%d-%m-%Y}-{weights.stem}",  # Ví dụ: 15-10-2026-yolov8n.
    )


if __name__ == "__main__":
    train()
