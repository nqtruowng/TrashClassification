# Trash Classification

Pipeline tiền xử lý YOLO Detection chỉ dùng **Drinking-waste** và **Garbage**, với nhãn bounding box có sẵn. Bộ lớp đích giữ nguyên: `organic, cardboard, glass, metal, paper, plastic` (ID 0–5).

Đã triển khai kiểm tra cấu hình, kiểm kê, remap, làm sạch (bước 1–4) và chia train/test/val (bước 6). Đã thêm xuất YOLO (bước 7); duyệt nội dung nhãn và train chưa hoàn tất. Kế hoạch: [dataset-preprocessing-plan.md](docs/plans/dataset-preprocessing-plan.md).

## Train YOLOv8n pretrained

```powershell
uv run --locked python -B src/training/train.py
```

`src/training/train.py` đọc `processed-data/data.yaml`, tự tải trọng số pretrained `yolov8n.pt` vào `artifacts/` khi chưa có và huấn luyện với 50 epoch, ảnh 320, batch 8. Chỉnh ba giá trị này trực tiếp trong file; không cần tham số CLI. Đường dẫn được tính từ thư mục gốc project.

Hàm `train()` lưu kết quả trong `artifacts/train/dd/mm/yyyy-model/` theo ngày bắt đầu chạy trên máy, ví dụ `artifacts/train/15/10/2026-model/weights/best.pt`. Dấu `/` tạo thư mục con; trọng số vẫn mang tên `best.pt` và `last.pt`. Các lần chạy cùng ngày được Ultralytics thêm số vào thư mục cuối để giữ kết quả cũ. Train dùng tập train, đánh giá trong quá trình huấn luyện bằng val theo YAML. API theo [tài liệu YOLOv8 của Ultralytics](https://docs.ultralytics.com/models/yolov8/).

## Nguồn và cấu hình

| Nguồn | Đường dẫn | Lớp đích |
|---|---|---|
| Drinking-waste | `raw-data/Images_of_Waste/YOLO_imgs/` | glass, metal, plastic |
| Garbage | `raw-data/Garbage/GARBAGE CLASSIFICATION/` | Đủ 6 lớp |

Chỉ hai nguồn trong `configs/dataset.yaml` được đọc. Các thư mục dữ liệu khác trên máy không tham gia pipeline. `raw-data/` giữ nguyên để truy vết; không cộng thêm ảnh từ `Images_of_Waste/rawimgs/`.

- Hai nguồn dùng chung seed 42 và tỷ lệ mục tiêu train/test/val 80/10/10, không giới hạn số ảnh.
- Test được tách từ hai nguồn theo nhóm; chỉ dùng để đánh giá sau khi chốt mô hình. Split gốc train/valid/test của Garbage được lưu trong metadata, không dùng làm split cuối.
- ID đích là vị trí trong `classes`. Mapping Drinking-waste: AluCan → metal, Glass → glass, HDPEM/PET → plastic. Garbage remap từ tên lớp trong YAML gốc.
- Thứ tự Drinking-waste `[AluCan, Glass, HDPEM, PET]` khớp kiểm tra tiền tố tên ảnh và các mẫu đã xem, nhưng chưa có metadata chính thức; `class_order_verified` vẫn false.

## Cấu trúc

```text
main.py                       # CLI gọi bước được chọn
src/preprocess/
  step1_config.py             # Kiểm tra cấu hình, báo cáo môi trường
  step2_inventory.py          # Ghép ảnh/nhãn và thống kê
  step3_remap.py              # Ánh xạ lớp, giữ nhãn nguồn và lý do cần duyệt
  step4_clean.py              # Lọc lỗi/trùng và nhãn không hợp lệ, chuẩn hóa ảnh
  step5_split.py              # Bước 6: chia theo nhóm và cân đối nguồn/lớp
  step7_export.py             # Xuất và kiểm tra dataset YOLO
configs/dataset.yaml           # Hai nguồn, lớp, mapping và tỷ lệ chia
raw-data/                     # Dữ liệu gốc
artifacts/                    # Báo cáo và dữ liệu trung gian
processed-data/               # Chỉ ảnh, TXT và YAML đúng định dạng YOLO
tests/test_config.py          # Kiểm thử pipeline
```

`processed-data/` chỉ chứa ảnh, nhãn TXT và `data.yaml` do bước 7 xuất. Báo cáo, checksum, danh sách loại và dữ liệu trung gian đều nằm trong `artifacts/`. Việc xuất định dạng YOLO không tự xác nhận nhãn đã được duyệt.

## Chạy

```powershell
uv sync --locked
uv run --locked python -B main.py --report
uv run --locked python -B main.py --stage inventory
uv run --locked python -B main.py --stage remap
uv run --locked python -B main.py --stage clean
uv run --locked python -B main.py --stage split
```

Chạy theo thứ tự trên sau khi thay đổi nguồn. Nếu không có `--stage`/`--report`, CLI chỉ kiểm tra cấu hình, không ghi file. `--config` chọn YAML khác; đường dẫn tương đối tính từ gốc project. `-B` tránh tạo bytecode cache. Không cần tải model hoặc cài dependency autobox.

## Kiểm kê — bước 2

Đọc toàn bộ ảnh của hai nguồn để đối chiếu tổng số và lỗi. Ghép TXT theo nguồn/split/stem không phân biệt hoa thường; xung đột tên làm lệnh dừng. Giữ ID ổn định, split gốc Garbage, kích thước, màu và EXIF.

| Nguồn | Ảnh gốc | File nhãn | Thiếu TXT | Nhãn lỗi | Ảnh lỗi giải mã |
|---|---:|---:|---:|---:|---:|
| Drinking-waste | 4.829 | 4.811 | 18 | 13 | 8 |
| Garbage | 10.464 | 10.464 | 0 | 17 | 0 |
| **Tổng** | **15.293** | **15.275** | **18** | **30** | **8** |

8 HEIC lỗi giải mã cũng nằm trong 18 ảnh thiếu TXT; 10 ảnh thiếu TXT còn lại là `Glass664`–`Glass673`. Không có TXT rỗng hoặc nhãn mồ côi trong dữ liệu hiện tại. Số kiểm kê chưa phải số ảnh đưa vào huấn luyện.

Đầu ra:

- `artifacts/manifest.csv`: một dòng mỗi ảnh; nhãn mồ côi có dòng riêng. Đường dẫn ảnh/nhãn tính từ `local_root` của nguồn.
- `artifacts/inventory-summary.json`: thống kê theo nguồn/lớp, số box, split gốc, lỗi và checksum manifest.

Trạng thái nhãn nguồn: `unreviewed` đọc được, `missing` thiếu TXT, `empty_unverified` rỗng chưa xác nhận, `invalid` lỗi, `orphan` không có ảnh. File có một dòng sai vẫn được đánh dấu invalid toàn bộ. Thống kê lớp/box chỉ tính nhãn không có lỗi cú pháp/miền giá trị.

## Chuẩn hóa lớp — bước 3

Kiểm tra checksum manifest và cấu hình trước khi remap. Giữ nguyên nội dung TXT gốc cùng nguồn, đường dẫn, split gốc và từng box sau đổi ID.

- `artifacts/annotations.jsonl`: các bản ghi kiểm kê đã remap, gồm cả lỗi để truy vết.
- `artifacts/remap-summary.json`: thống kê trạng thái/lớp đích, cấu hình, kiểm tra thứ tự ID và checksum.

Nhãn đọc được mang `needs_review`; thiếu/rỗng mang `needs_annotation`; ảnh hỏng bị `excluded`. Bước 4 loại các ảnh không có nhãn nguồn hợp lệ; không tạo box mới hay coi nhãn thiếu là ảnh nền. Toàn bộ bản ghi vẫn `ready_for_training=false`.

## Làm sạch — bước 4

Chỉ giữ ảnh có nhãn bounding box nguồn hợp lệ về định dạng. Loại ảnh lỗi, nhãn mồ côi, bản trùng, thiếu TXT, TXT rỗng và nhãn lỗi. Không dùng phần box đọc được của một file invalid.

- Đọc ảnh bằng 4 luồng; dùng SHA-256 file và pixel RGB sau EXIF để tìm bản trùng chính xác.
- Tìm gần trùng bằng dHash 64 bit cách tối đa 4 bit, tỷ lệ ảnh lệch tối đa 1% và MAE thumbnail RGB tối đa 8/255. Chỉ xóa bản sao sau đối chiếu pixel toàn ảnh: MAE <= 2/255, RMS <= 4/255 và tối đa 1% mẫu kênh màu lệch quá 16/255.
- Resize chỉ phục vụ đối chiếu; giữ kích thước/tỷ lệ ảnh đầu ra. Cặp tương tự chưa đủ bằng chứng xóa vẫn cùng `group_id` để không chia chéo train/test/val.
- Chọn đại diện theo chất lượng nhãn, có box, độ phân giải và ID ổn định; nhãn mâu thuẫn giữa các bản sao được ghi `duplicate_label_conflict` để duyệt.
- Chuẩn hóa RGB và 8 hướng EXIF, đổi tọa độ box tương ứng. Chỉ ghi PNG mới nếu thực sự đổi màu/hướng; ảnh khác tham chiếu nguồn.

| Đầu ra trong `artifacts/clean/` | Nội dung |
|---|---|
| `annotations.jsonl` | Chỉ ảnh được giữ, box, group ID, hash và image_path |
| `decisions.jsonl` | Quyết định giữ/loại và bằng chứng cặp trùng/gần trùng |
| `summary.json` | Thống kê nguồn, lý do loại, ngưỡng, cấu hình và checksum |
| `images/` | Chỉ ảnh được giữ cần chuẩn hóa |

`image_path` trỏ tới ảnh nguồn tuyệt đối hoặc ảnh chuẩn hóa tương đối với gốc project; box tương ứng đúng ảnh này. `original_label` giữ nhãn trước biến đổi. Kết quả cũ được thay khi bước clean hoàn tất thành công.

Nhãn thiếu/rỗng/lỗi được lọc sau chọn đại diện. Mỗi ảnh bị loại có một lý do chính; nhãn lỗi đã bị loại dưới dạng bản trùng không được đếm lần nữa vào lý do invalid_label.

## Kết quả chạy lại ngày 13/10/2026

Từ 15.293 ảnh gốc, giữ **15.164 ảnh có nhãn nguồn hợp lệ về định dạng**:

| Nguồn | Giữ lại | Loại |
|---|---:|---:|
| Drinking-waste | 4.723 | 106 |
| Garbage | 10.441 | 23 |
| **Tổng** | **15.164** | **129** |

129 ảnh bị loại gồm 82 bản trùng, 8 ảnh lỗi giải mã, 10 ảnh thiếu TXT và 29 ảnh có nhãn lỗi. Một trong 30 nhãn lỗi ban đầu đã bị loại dưới dạng bản trùng. Cách đếm lý do loại thay đổi khi chỉ đối chiếu hai nguồn; đây là kết quả của lần chạy hiện tại.

| Lớp | Drinking-waste | Garbage | Tổng ảnh chứa lớp |
|---|---:|---:|---:|
| organic | 0 | 2.275 | 2.275 |
| cardboard | 0 | 1.499 | 1.499 |
| glass | 1.224 | 2.683 | 3.907 |
| metal | 1.079 | 1.898 | 2.977 |
| paper | 0 | 1.760 | 1.760 |
| plastic | 2.442 | 1.463 | 3.905 |

Một ảnh có thể chứa nhiều lớp nên tổng các dòng vượt 15.164. Đầu ra có 15.100 nhóm, 1 ảnh cần lưu bản chuẩn hóa và 80 ảnh đại diện có mâu thuẫn nhãn giữa các bản sao. Nhãn vẫn còn `needs_review`; kết quả chia bước 6 nằm trong manifest riêng; số liệu xuất sau kiểm tra bổ sung ở phần bước 7 bên dưới.

Đã đối chiếu checksum, số giữ/loại, ID duy nhất, hash file/pixel không trùng, đường dẫn ảnh và lớp đích. Manifest/remap/clean chỉ chứa đúng hai nguồn được chọn; mọi ảnh clean có box nguồn và không có nhãn thiếu/rỗng/invalid.

## Chia train/test/val — bước 6

```powershell
uv run --locked python -B main.py --stage split
```

Đọc `artifacts/clean/annotations.jsonl`, kiểm tra checksum và cấu hình rồi chia toàn bộ ảnh sạch theo tỷ lệ **train 80%, test 10%, val 10%**, seed 42. Theo yêu cầu thực hiện bước 6 trước khi duyệt nhãn, trạng thái `needs_review` và `ready_for_training=false` được giữ nguyên.

- Giữ nguyên `group_id` trong một tập; ưu tiên nhóm lớn, sau đó lớp hiếm. Dùng seed phá hòa và cân đối số ảnh theo nguồn và nguồn × lớp; mỗi ảnh nhiều lớp được tính một lần cho từng lớp.
- Làm tròn số ảnh bằng phần dư lớn nhất, hòa phần dư ưu tiên train → test → val. Nếu kích thước nhóm ngăn đạt đúng số ảnh mục tiêu, giữ nhóm và báo độ lệch thay vì tách nhóm.
- Kiểm tra không giao nhau theo image ID, group ID, SHA-256 file và SHA-256 pixel giữa cả ba tập trước khi ghi.
- `artifacts/split-manifest.csv`: mỗi ảnh một dòng có split, đường dẫn, nguồn, split gốc, hash, nhóm và trạng thái nhãn. Lấy box đã remap/chuẩn hóa từ clean bằng image_id, không dùng trực tiếp TXT nguồn.
- `artifacts/split-summary.json`: số ảnh/nhóm, nguồn, số ảnh và box từng lớp, trạng thái duyệt, tỷ lệ thực tế, chênh lệch mục tiêu, kết quả kiểm tra giao nhau và checksum.

Chạy lại cùng dữ liệu/cấu hình/seed cho cùng kết quả; ghi đè hai file cùng đường dẫn, không nhân bản ảnh. Đổi cấu hình thì chạy lại remap và clean trước split để các báo cáo khớp nhau. Xuất ảnh/TXT/data.yaml thuộc bước 7.

Kết quả trên 15.164 ảnh, seed 42:

| Tập | Ảnh | Drinking-waste | Garbage |
|---|---:|---:|---:|
| Train | 12.131 | 3.779 | 8.352 |
| Test | 1.517 | 472 | 1.045 |
| Val | 1.516 | 472 | 1.044 |

Cả ba tập có đủ 6 lớp. Số ảnh đạt đúng mục tiêu sau làm tròn; không giao nhau theo ID, nhóm, hash file hoặc hash pixel trong dữ liệu đã kiểm tra. Tổng 15.100 nhóm được giữ nguyên. Đã đối chiếu toàn bộ ID, nguồn, split gốc, đường dẫn, lớp, số box và checksum đầu ra với clean.

## Xuất YOLO — bước 7

```powershell
uv run --locked python -B main.py --stage export
```

`src/preprocess/step7_export.py` lấy split từ manifest bước 6 và box từ clean. Kiểm tra checksum/cấu hình, đối chiếu metadata và kiểm tra không giao nhau theo nhóm/hash giữa các tập trước khi xuất. Tên ảnh và TXT dùng cùng image ID ổn định. Nhãn dùng ID đích 0–5 và tọa độ ứng với đúng ảnh đã chuẩn hóa; không đọc lại TXT gốc để bỏ qua remap hoặc EXIF.

Loại cả ảnh khi có bất kỳ box sai ID, giá trị không hữu hạn, kích thước không dương hoặc cạnh vượt ngoài ảnh (dung sai số thực 1e-9). Không cắt box hoặc xuất riêng các dòng đúng của một nhãn lỗi. Giữ nguyên split của ảnh còn lại, không chia lại sau khi loại.

Ảnh được sao chép vào thư mục tạm trong `artifacts/`, kiểm tra checksum, giải mã đầy đủ, RGB, EXIF, kích thước và hash pixel so với clean. Đọc lại nhãn đã ghi, kiểm tra cặp ảnh/TXT rồi mới đưa dataset vào `processed-data/`. Nếu ảnh nguồn thay đổi, dừng để chạy lại clean/split. Thư mục đích phải chưa có hoặc rỗng; chạy lại khi đã có dữ liệu sẽ dừng để bảo vệ dataset hiện tại.

```text
processed-data/
  data.yaml
  images/train/   images/test/   images/val/
  labels/train/   labels/test/   labels/val/
```

`data.yaml` chứa names theo cấu hình và đường dẫn tuyệt đối tới dataset hiện tại; khi di chuyển thư mục cần cập nhật `path`. `artifacts/export-summary.json` chứa checksum từng file, phân bố ảnh/box/lớp/nguồn, trạng thái duyệt và ID/nguồn/đường dẫn/split/lý do của từng ảnh bị loại. Không đặt báo cáo hoặc cache trong dataset.

Kết quả ngày 14/10/2026: **14.992 ảnh và 14.992 TXT**, loại thêm **172 ảnh Drinking-waste chứa 174 box vượt biên**. Loại toàn bộ 185 box thuộc những ảnh này, kể cả 11 box không vượt biên nằm cùng ảnh, để không dùng nhãn thiếu vật thể.

| Tập | Ảnh xuất | Ảnh loại thêm |
|---|---:|---:|
| Train | 11.995 | 136 |
| Test | 1.506 | 11 |
| Val | 1.491 | 25 |

Đã kiểm tra độc lập toàn bộ 29.985 file sau khi xuất: checksum khớp, ảnh/TXT ghép đủ, box đúng clean và trong biên, mỗi split đủ 6 lớp, không giao nhau theo nhóm/hash. Thư mục tạm của lần xuất đã được dọn.

Trạng thái `needs_review` và `ready_for_training=false` trong clean/split được giữ nguyên. 72 ảnh xuất còn mang cảnh báo mâu thuẫn nhãn giữa các bản sao; thứ tự lớp Drinking-waste vẫn chưa xác minh chính thức. Bước 7 xác nhận tính hợp lệ kỹ thuật của ảnh/TXT; bước duyệt nội dung và bước 8 vẫn cần thực hiện trước khi kết luận chất lượng huấn luyện.

## Chất lượng nhãn và bước tiếp theo

Có đủ 6 lớp không đồng nghĩa mọi box đã chính xác. Bộ đọc hiện kiểm tra ID, số hữu hạn, tâm trong [0,1] và kích thước trong (0,1]; bước 7 bổ sung kiểm tra toàn bộ cạnh box và loại cả ảnh có box vượt biên. Theo yêu cầu thực hiện bước 7, xuất nhãn nguồn hiện có, giữ nguyên trạng thái chưa duyệt. Vẫn cần xác minh ID Drinking-waste, xử lý mâu thuẫn nhãn và duyệt nội dung trước khi xác nhận chất lượng dataset.

Phạm vi hiện tại chỉ dùng nhãn sẵn có; không cần luồng Grounding DINO/BiRefNet hay tạo box cho nguồn classification. Dataset xuất chỉ có `images/train`, `images/test`, `images/val`, `labels/train`, `labels/test`, `labels/val` và `data.yaml`.

## Thông tin nguồn cục bộ

Drinking-waste không có README/LICENSE/class names được tìm thấy trong bản dữ liệu đang dùng. Garbage có metadata trong `raw-data/Garbage/GARBAGE CLASSIFICATION/data.yaml`: CC BY 4.0, workspace `material-identification`, project `garbage-classification-3`, version 2. Đây là thông tin từ bản dữ liệu cục bộ.

## Kiểm thử

```powershell
uv run --locked python -B -m unittest discover -s tests -v
```

41 kiểm thử đạt, gồm hai dạng YOLO, loại nhãn thiếu/rỗng/lỗi, remap, EXIF, lọc trùng, chia theo nhóm, tỷ lệ, tính tái lập và bảo vệ đầu ra khi dữ liệu/cấu hình thay đổi, xuất YOLO đúng ảnh/box sau EXIF, loại box vượt biên, kiểm tra checksum và không để lại dataset dở dang khi lỗi. Không thêm dependency; `uv.lock` giữ nguyên.

Các file step chỉ xử lý nguồn YOLO. Đã bỏ nhánh classification, bối cảnh thư mục, mapping DROP và ưu tiên nguồn test riêng; bỏ các trường cấu hình `role`, `cap`, `eval` cùng metadata `scene_type` và `mapping_status`. Cấu hình có trường cũ bị từ chối để tránh âm thầm bỏ qua yêu cầu. Manifest cũ không đúng danh sách cột phải được tạo lại bằng inventory trước khi remap.
