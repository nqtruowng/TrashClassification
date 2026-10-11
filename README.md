# Trash Classification

Đã triển khai bước 1: kiểm tra cấu hình 5 nguồn dữ liệu. Kế hoạch tiếp theo: `docs/plans/dataset-preprocessing-plan.md`.

## Cấu trúc

```text
main.py                       # Toàn bộ code bước 1 và lệnh chạy
configs/dataset.yaml           # Cấu hình chung: lớp, split, nguồn, mapping
raw-data/                     # Dữ liệu gốc
processed-data/               # Chỉ dataset đã làm sạch, sẵn sàng train
artifacts/                    # Báo cáo và dữ liệu trung gian khi cần
tests/test_config.py          # Kiểm thử cấu hình
```

`processed-data/` hiện để trống vì chưa làm sạch dữ liệu. Khi xuất dataset, chỉ đặt ảnh, nhãn và YAML dùng để train ở đây. Manifest, log, báo cáo, ảnh lỗi, nhãn chờ duyệt và dữ liệu tạm nằm trong `artifacts/`.

## Chạy

```powershell
uv sync --locked
uv run --locked python -B main.py
```

Dùng `-B` để Python không sinh `__pycache__`, kể cả trong `.venv`. Mặc định chỉ kiểm tra, không tạo file kết quả. Muốn lưu môi trường, checksum và kết quả kiểm tra:

```powershell
uv run --locked python -B main.py --report
```

Lệnh cập nhật duy nhất `artifacts/config-check.json`, không tạo thư mục theo lần chạy, không sao chép code/YAML/lockfile. Đường dẫn tương đối tính từ gốc project; dùng `--config` để chọn YAML khác.

## Cấu hình

- ID đích: `organic, cardboard, glass, metal, paper, plastic`; seed 42, chia train/val 80/20 cho 4 nguồn ngoài RealWaste.
- `mapping` dùng tên lớp nguồn chính xác; `DROP` là loại khỏi tập, không phải ảnh nền. Classification đối chiếu mapping trực tiếp với thư mục, không khai báo lặp danh sách lớp.
- Chỉ YOLO khai báo `class_names` theo thứ tự ID bắt đầu từ 0; đối chiếu `native_data_yaml` nếu có.
- TrashNet, drinking-waste, Garbage và household có `role: train_val`. RealWaste có `role: test_only`, khớp `eval.test_source: realwaste`, dành riêng cho test cuối cùng. Không dùng RealWaste để chọn checkpoint.
- Tất cả nguồn có `cap: null`: không giới hạn 750 ảnh. Chỉ dữ liệu đủ điều kiện sau làm sạch/gán nhãn mới được xuất. Các split gốc của Garbage được ghi lại rồi chia lại train/val.
- Từ chối khóa lạ/trùng, mapping thiếu, đường dẫn sai, split không đủ 1, cap âm, thứ tự lớp và nguồn test mâu thuẫn.
- Drinking-waste chưa xác minh thứ tự ID. Cấu hình dùng trực tiếp `mapping` đã khai báo; cấu hình hợp lệ chưa có nghĩa ảnh/box đã được duyệt.
- RealWaste được giữ làm test; cần gán và duyệt box trước khi đánh giá detection. Ba nguồn classification đều cần gán box; chưa triển khai inventory, remap, làm sạch hoặc xuất YOLO.

## Nguồn và ghi công

Đối chiếu tài liệu cục bộ ngày 11/10/2026. YAML đề xuất ban đầu không có trong workspace; cấu hình dựng từ kế hoạch và thư mục thực tế. Thông tin sau là khai báo trong bản dữ liệu đang có, chưa xác minh trực tuyến.

| Nguồn | Bằng chứng và thông tin ghi nhận |
|---|---|
| TrashNet | Không tìm thấy README/LICENSE trong bản giải nén; chưa xác minh giấy phép/phiên bản. |
| Drinking-waste | Không tìm thấy README/LICENSE/class names; thứ tự `[AluCan, Glass, HDPEM, PET]` lấy từ kế hoạch, cần xác minh. |
| Garbage | `raw-data/Garbage/GARBAGE CLASSIFICATION/data.yaml`: CC BY 4.0, workspace `material-identification`, project `garbage-classification-3`, version 2. |
| Household | `raw-data/Recyclable and Household Waste/README.txt`: v1.0, 18/05/2024; giáo dục/nghiên cứu/phi thương mại, ghi công Alistair King. Thư mục thực tế dùng snake_case khác ví dụ trong README. |
| RealWaste | `raw-data/realwaste/realwaste-main/README.md`: CC BY-NC-SA 4.0; trích dẫn “RealWaste: A Novel Real-Life Data Set for Landfill Waste Classification Using Deep Learning”, Information 14(12), 633. |

Địa chỉ ghi công do tài liệu gốc cung cấp:

- Garbage: https://universe.roboflow.com/material-identification/garbage-classification-3/dataset/2
- Household: https://www.kaggle.com/datasets/alistairking/recyclable-and-household-waste-classification
- RealWaste: https://www.mdpi.com/2078-2489/14/12/633

## Kiểm tra

```powershell
uv run --locked python -B -m unittest discover -s tests -v
```

Môi trường đã chạy: Python 3.14.7, PyYAML 6.0.3, Pillow 12.3.0. `uv.lock` cố định dependency. 20 kiểm thử đạt; Pillow đọc một ảnh mẫu mỗi nguồn thành công (5/5), chưa kiểm tra toàn bộ ảnh. Chưa kiểm chứng môi trường model-assisted labeling.
