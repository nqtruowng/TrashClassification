"""Fine-tune RT-DETR-L pretrained bằng Ultralytics, đọc trực tiếp dataset YOLO."""

import sys
from datetime import date
from pathlib import Path

sys.dont_write_bytecode = True

from ultralytics import RTDETR


def train(data=None, project=None, *, device=0, epochs=50, imgsz=640,
          batch=4, workers=2, amp=False, name=None):
    """Train local hoặc Kaggle; batch là tổng trên các GPU. Trả về thư mục run."""
    root = Path(__file__).resolve().parents[2]
    data = Path(data).resolve() if data is not None else root / "processed-data/data.yaml"
    if not data.is_file():
        raise FileNotFoundError(f"Chưa có dataset YOLO: {data}")

    model_dir = Path(project).resolve() if project is not None else root / "model"
    model_dir.mkdir(parents=True, exist_ok=True)
    weights = model_dir / "rtdetr-l.pt"
    model = RTDETR(str(weights))  # Tự tải pretrained COCO khi chưa có.
    model.train(
        data=str(data),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,        # Kaggle: batch=4, device=[0, 1] => 2 ảnh/GPU.
        workers=workers,    # Số worker trên mỗi GPU.
        device=device,
        amp=amp,            # Baseline FP32: RT-DETR có thể NaN khi dùng AMP.
        deterministic=False,  # grid_sample của RT-DETR không hỗ trợ deterministic backward.
        optimizer="AdamW",
        lr0=1e-4,
        weight_decay=1e-4,
        seed=42,
        cache=False,
        patience=15,
        save=True,
        save_period=5,
        project=str(model_dir),
        name=name or f"{date.today():%d-%m-%Y}-{weights.stem}",
        exist_ok=False,
    )
    return Path(model.trainer.save_dir)


if __name__ == "__main__":
    train()
