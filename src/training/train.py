"""Train YOLOv8n pretrained. Chạy: uv run python -B src/training/train.py."""

import sys
from datetime import date
from pathlib import Path

sys.dont_write_bytecode = True

from ultralytics import YOLO


def train():
    """Đọc dataset, train pretrained và lưu kết quả theo ngày/tháng/năm-model."""
    root = Path(__file__).resolve().parents[2]
    data = root / "processed-data/data.yaml"
    if not data.is_file():
        raise FileNotFoundError(f"Chưa có dataset YOLO: {data}")

    artifacts = root / "artifacts"
    artifacts.mkdir(exist_ok=True)
    model = YOLO(str(artifacts / "yolov8n.pt"))  # Tự tải pretrained khi chưa có.
    model.train(
        data=str(data),
        epochs=10,       # Số vòng huấn luyện; chỉnh trực tiếp tại đây.
        imgsz=320,      # Kích thước ảnh đầu vào.
        batch=16,        # Số ảnh mỗi batch.
        workers=2,      # Đọc dữ liệu trong tiến trình chính, đơn giản trên Windows.
        project=str(artifacts / "train"),
        name=date.today().strftime("%d/%m/%Y-model"),  # Ngày bắt đầu train; / tạo thư mục con.
    )


if __name__ == "__main__":
    train()
