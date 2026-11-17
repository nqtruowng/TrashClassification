"""Evaluate a trained YOLO model on the project's test split."""

from pathlib import Path

from ultralytics import YOLO


ROOT = Path(__file__).resolve().parents[2]
# Sửa đường dẫn model tại đây (tính từ thư mục dự án).
MODEL_PATH = "model/yolo26n.pt"
TEST_DATA = ROOT / "processed-data" / "data.yaml"


def main():
    weights = (ROOT / MODEL_PATH).resolve()
    for path, description in ((weights, "Model weights"), (TEST_DATA, "Dataset YAML")):
        if not path.is_file():
            raise FileNotFoundError(f"Không tìm thấy {description}: {path}")

    model = YOLO(str(weights))
    metrics = model.val(
        data=str(TEST_DATA),
        split="test",
        imgsz=640,
        plots=True,
        project=str(ROOT / "model" / "evaluation"),
        name=weights.stem,
    )

    print(f"Precision: {metrics.box.mp:.4f}")
    print(f"Recall:    {metrics.box.mr:.4f}")
    print(f"mAP@0.5:   {metrics.box.map50:.4f}")
    print(f"mAP@0.5:0.95: {metrics.box.map:.4f}")
    print(f"Kết quả và biểu đồ: {metrics.save_dir}")


if __name__ == "__main__":
    main()
