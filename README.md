# Trash Classification

Đã triển khai bước 1 (kiểm tra cấu hình), bước 2 (kiểm kê 5 nguồn dữ liệu) và bước 3 (chuẩn hóa lớp, trạng thái nhãn). Kế hoạch tiếp theo: `docs/plans/dataset-preprocessing-plan.md`.

## Cấu trúc

```text
main.py                       # Nhận lệnh và gọi bước tương ứng
src/preprocess/
  step1_config.py             # Bước 1: kiểm tra cấu hình, báo cáo môi trường
  step2_inventory.py          # Bước 2: kiểm kê ảnh/nhãn và thống kê
  step3_remap.py              # Bước 3: remap lớp, giữ nhãn gốc và phân luồng xử lý
configs/dataset.yaml           # Cấu hình chung: lớp, split, nguồn, mapping
raw-data/                     # Dữ liệu gốc
processed-data/               # Chỉ dataset đã làm sạch, sẵn sàng train
artifacts/                    # Báo cáo và dữ liệu trung gian khi cần
tests/test_config.py          # Kiểm thử cấu hình, kiểm kê và remap
```

`processed-data/` hiện để trống vì chưa làm sạch dữ liệu. Khi xuất dataset, chỉ đặt ảnh, nhãn và YAML dùng để train ở đây. Manifest, log, báo cáo, ảnh lỗi, nhãn chờ duyệt và dữ liệu tạm nằm trong `artifacts/`.

Các hàm có chú thích tiếng Việt ngay trong file của bước tương ứng. Bước 2 dùng lại hàm kiểm tra đường dẫn và báo lỗi của bước 1, không sao chép logic.

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

## Kiểm kê dữ liệu — bước 2

```powershell
uv run --locked python -B main.py --stage inventory
```

Lệnh đọc toàn bộ ảnh trong 5 nguồn đã khai báo, ghép nhãn theo nguồn/thư mục/split và tên file không phân biệt hoa thường. Giữ lớp gốc, split gốc của Garbage, bối cảnh của Household và orientation EXIF; không xoay ảnh hay chuyển nhãn.

Chỉ xuất hai file, cập nhật cùng đường dẫn khi chạy lại:

- `artifacts/manifest.csv`: một dòng mỗi ảnh; nhãn không có ảnh có dòng riêng với `record_type=orphan_label`. Đường dẫn ảnh/nhãn tính từ `local_root` của nguồn; ID ảnh được tạo từ nguồn và đường dẫn tương đối.
- `artifacts/inventory-summary.json`: số ảnh/nhãn/lỗi, phân bố lớp nguồn, số box, split gốc, bối cảnh và SHA-256 của manifest.

Manifest lưu chiều rộng/cao gốc, chế độ màu, EXIF orientation, trạng thái giải mã và lỗi. Với YOLO, `source_classes`/`source_class_ids` là danh sách JSON để biểu diễn ảnh nhiều lớp. `object_count` đếm các dòng nhãn hợp lệ đã đọc; nếu có dòng sai, cả file vẫn mang trạng thái `invalid`. Thống kê lớp/box của YOLO trong báo cáo chỉ tính file không có lỗi cú pháp hoặc miền giá trị. Số ảnh theo lớp có thể cộng lớn hơn tổng ảnh vì một ảnh chứa nhiều lớp.

Trạng thái nhãn: `needs_annotation` (nhãn thư mục, chưa có box), `missing` (thiếu TXT), `empty_unverified` (TXT rỗng, chưa xác nhận ảnh nền), `invalid` (nhãn lỗi), `unreviewed` (nhãn đọc được nhưng chưa duyệt), `orphan` (TXT không có ảnh). Cấu trúc hoặc tên file xung đột làm lệnh dừng trước khi ghi kết quả; ảnh/nhãn lỗi được ghi vào manifest để xử lý sau. Lệnh không remap, loại ảnh, dedup, chia tập hay ghi vào `processed-data/`.

Kết quả kiểm kê toàn bộ, ngày 12/10/2026:

| Nguồn | Ảnh | File nhãn YOLO | Thiếu TXT | Nhãn lỗi | Không đọc được ảnh |
|---|---:|---:|---:|---:|---:|
| TrashNet | 2.527 | 0 | — | 0 | 0 |
| Drinking-waste | 4.829 | 4.811 | 18 | 13 | 8 |
| Garbage | 10.464 | 10.464 | 0 | 17 | 0 |
| Household | 15.000 | 0 | — | 0 | 0 |
| RealWaste | 4.752 | 0 | — | 0 | 0 |

Tổng 37.572 ảnh, 15.275 file nhãn, không có TXT rỗng hay nhãn mồ côi. 8 ảnh không đọc được đều là HEIC và cũng thuộc nhóm 18 ảnh thiếu TXT; 10 ảnh còn lại là `Glass664`–`Glass673`. 22.279 ảnh của ba nguồn classification chưa có box, được ghi `needs_annotation`, không tính là lỗi thiếu TXT. Số liệu này là kiểm kê, chưa phải số ảnh đủ điều kiện huấn luyện.

## Chuẩn hóa lớp và trạng thái nhãn — bước 3

Sau khi đã có kết quả bước 2:

```powershell
uv run --locked python -B main.py --stage remap
```

Lệnh kiểm tra checksum manifest, đối chiếu cấu hình và đọc nhãn gốc để ánh xạ sang 6 lớp đích. Khi dữ liệu nguồn thay đổi, chạy lại `--stage inventory` trước. Bước 3 dùng lại bộ đọc/kiểm tra nhãn của bước 2, không thêm dependency.

Chỉ thêm hai file trung gian, ghi đè cùng đường dẫn khi chạy lại:

- `artifacts/annotations.jsonl`: mỗi dòng là một ảnh hoặc nhãn mồ côi; giữ nguồn, đường dẫn, split gốc, role, EXIF, nội dung TXT gốc và các box đã đổi ID. Mỗi box giữ ID/tên lớp nguồn, số dòng gốc, tọa độ YOLO chưa biến đổi và kết quả mapping. Đối tượng `DROP` vẫn có metadata với `mapping_status=dropped`, ID đích là `null`.
- `artifacts/remap-summary.json`: thống kê trạng thái/lớp đích theo nguồn, lý do xử lý tiếp, cấu hình đã dùng, kiểm tra thứ tự lớp và checksum. Số box là số ứng viên đọc được, kể cả phần đọc được của nhãn lỗi; chưa phải số box đã duyệt.

Lọc `annotation_status` ngay trong JSONL để lấy hàng đợi, không tạo các bản sao danh sách:

| Trạng thái | Ý nghĩa |
|---|---|
| `needs_annotation` | Nhãn thư mục chưa có box, thiếu TXT hoặc TXT rỗng chưa xác nhận |
| `needs_review` | Có box chưa duyệt, nhãn lỗi, hoặc ảnh chứa cả lớp giữ và DROP |
| `out_of_scope` | Chỉ có lớp DROP; không dùng làm background |
| `excluded` | Ảnh không giải mã được hoặc nhãn không có ảnh; lý do được giữ để xử lý sau |

Tất cả bản ghi hiện có `ready_for_training=false`. Nhãn thư mục không được tạo box toàn ảnh; nhãn thiếu/rỗng không trở thành background. Vai trò RealWaste `test_only` được giữ nguyên, 4 nguồn còn lại vẫn `train_val`; chưa chia train/val ở bước này.

Kết quả chạy toàn bộ ngày 13/10/2026: 37.572 ảnh, gồm 20.339 `needs_annotation`, 15.275 `needs_review`, 1.950 `out_of_scope` và 8 `excluded` (HEIC lỗi giải mã, đồng thời thiếu TXT). Nhóm cần kiểm tra gồm 30 file nhãn lỗi. Giữ 32.820 ảnh với vai trò train/val và 4.752 ảnh RealWaste với vai trò test ở mức kiểm kê; các con số này chưa trừ dữ liệu bị loại và chưa phải kích thước dataset huấn luyện cuối cùng. Đã đối chiếu ID/lớp/role của mọi bản ghi, checksum hai đầu ra và xác nhận `processed-data/` vẫn trống.

Đã xem mẫu `AluCan1,000.jpg`, `Glass1.jpg`, `HDPEM1.jpg`, `PET1,000.jpg` và nhãn tương ứng ngày 13/10/2026: hình ảnh phù hợp lần lượt với lon, chai thủy tinh, chai nhựa đục và chai nhựa trong. Kiểm tra này hỗ trợ thứ tự dự kiến `[AluCan, Glass, HDPEM, PET]`, không xác nhận vật liệu của mọi ảnh. Chưa có metadata lớp chính thức nên `class_order_verified` vẫn là `false`; nhãn remap của drinking-waste còn tạm thời.

Đối chiếu tự động drinking-waste: 4.774 ảnh có ID hợp lệ khớp tiền tố lớp, 24 ảnh không có tiền tố lớp xác định và 31 ảnh không có box đọc hợp lệ. Không có mâu thuẫn trong nhóm đối chiếu được; 55 ảnh còn lại chưa được xác minh bằng phép đối chiếu tên này.

## Cấu hình

- ID đích: `organic, cardboard, glass, metal, paper, plastic`; seed 42, chia train/val 80/20 cho 4 nguồn ngoài RealWaste.
- `mapping` dùng tên lớp nguồn chính xác; `DROP` là loại khỏi tập, không phải ảnh nền. Classification đối chiếu mapping trực tiếp với thư mục, không khai báo lặp danh sách lớp.
- Chỉ YOLO khai báo `class_names` theo thứ tự ID bắt đầu từ 0; đối chiếu `native_data_yaml` nếu có.
- TrashNet, drinking-waste, Garbage và household có `role: train_val`. RealWaste có `role: test_only`, khớp `eval.test_source: realwaste`, dành riêng cho test cuối cùng. Không dùng RealWaste để chọn checkpoint.
- Tất cả nguồn có `cap: null`: không giới hạn 750 ảnh. Chỉ dữ liệu đủ điều kiện sau làm sạch/gán nhãn mới được xuất. Các split gốc của Garbage được ghi lại rồi chia lại train/val.
- Từ chối khóa lạ/trùng, mapping thiếu, đường dẫn sai, split không đủ 1, cap âm, thứ tự lớp và nguồn test mâu thuẫn.
- Drinking-waste chưa xác minh thứ tự ID. Cấu hình dùng trực tiếp `mapping` đã khai báo; cấu hình hợp lệ chưa có nghĩa ảnh/box đã được duyệt.
- RealWaste được giữ làm test; cần gán và duyệt box trước khi đánh giá detection. Ba nguồn classification đều cần gán box; đã remap lớp nhưng chưa làm sạch hoặc xuất YOLO.

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

Môi trường đã chạy: Python 3.14.7, PyYAML 6.0.3, Pillow 12.3.0. `uv.lock` cố định dependency. 28 kiểm thử cấu hình, kiểm kê và remap đạt. Chưa kiểm chứng môi trường model-assisted labeling.
