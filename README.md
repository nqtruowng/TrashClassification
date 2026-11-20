# GreenLens — Nhận diện và phân loại rác

GreenLens là ứng dụng web nhận diện vật thể rác bằng camera hoặc ảnh tải lên. Frontend React hiển thị kết quả, độ tin cậy và gợi ý xử lý; backend FastAPI chạy model Ultralytics YOLO. Dự án cũng có pipeline để kiểm kê, chuẩn hóa nhãn, làm sạch, chia tập và xuất dữ liệu YOLO.

## Tính năng

- Nhận diện một ảnh JPG/PNG, phân tích video bằng tối đa 8 khung hình lấy mẫu, hoặc bật camera trực tuyến để nhận diện định kỳ.
- Gửi ảnh tới API, hiển thị bounding box, lớp dự đoán, độ tin cậy và hướng dẫn xử lý.
- Theo dõi số lượt nhận diện và phân bố lớp trong phiên hiện tại.
- Trang Hướng dẫn phân loại giải thích ba nhóm model, ví dụ thường gặp và gợi ý xử lý; nhắc người dùng kiểm tra quy định thu gom tại địa phương.
- Giao diện dashboard theo bản duyệt [preview.html](src/frontend/preview.html), được chia thành component React; ba chế độ nhận diện đều có luồng hoạt động riêng và giao diện responsive cho màn hình máy tính.
- Pipeline dataset cấu hình được, có kiểm tra trùng ảnh, nhóm gần trùng và rò rỉ ảnh giữa các tập.
- Huấn luyện YOLO26n hoặc RT-DETR-L bằng Ultralytics.

## Chạy ứng dụng web

### Docker Compose

Yêu cầu Docker Compose và model checkpoint. Mặc định dự án dùng `model/11-11-2026-yolo26n/weights/best.pt`.

```powershell
docker compose up --build
```

Mở frontend tại [http://localhost:8080](http://localhost:8080). Backend API chạy ở cổng 8000; kiểm tra trạng thái tại [http://localhost:8000/health](http://localhost:8000/health).

Có thể chọn checkpoint khác bằng biến `MODEL_FILE`:

```powershell
$env:MODEL_FILE = ".\model\duong-dan\best.pt"
docker compose up --build
```

### Chạy frontend và backend riêng

Backend cần môi trường Python theo `pyproject.toml`, checkpoint YOLO và các dependency đã đồng bộ:

```powershell
uv sync --locked
uv run --locked uvicorn src.backend.main:app --host 0.0.0.0 --port 8000
```

Trong terminal khác:

```powershell
cd src/frontend
npm ci
npm run dev
```

Mở URL Vite được in trong terminal. Vite chuyển tiếp `/api` tới backend `localhost:8000`. Khi chạy frontend production sau Nginx, cấu hình proxy `/api/` đã có trong `src/frontend/nginx.conf`.

API chính:

| Phương thức | Đường dẫn | Mô tả |
|---|---|---|
| `GET` | `/health` | Trạng thái backend và model |
| `POST` | `/predict` | Nhận bytes ảnh dạng `application/octet-stream`, trả kết quả detection |

Có thể đặt đường dẫn checkpoint qua biến môi trường `MODEL_PATH`. Kích thước ảnh mặc định tối đa 20 MiB; có thể thay đổi bằng `MAX_IMAGE_BYTES`.

## Dataset hiện tại

Dataset huấn luyện chính là `processed-data/`, được tham chiếu bởi `src/training/train.py` và `src/training/train_rtdetr.py`. File `processed-data/data.yaml` khai báo ba lớp theo đúng thứ tự ID:

| ID | Lớp |
|---:|---|
| 0 | `Biodegradable` — rác phân hủy sinh học |
| 1 | `recyclable` — rác tái chế được |
| 2 | `non_recyclable` — rác không tái chế được |

### Số ảnh theo lớp

Số liệu lấy từ `artifacts/export-summary.json`, là đầu ra export hiện tại. “Ảnh chứa lớp” là số ảnh có ít nhất một box của lớp đó; một ảnh có thể chứa nhiều lớp. “Box” là số bounding box trong các nhãn YOLO.

| Lớp | Ảnh chứa lớp | Bounding box |
|---|---:|---:|
| `Biodegradable` | 24.097 | 85.540 |
| `recyclable` | 44.048 | 91.981 |
| `non_recyclable` | 12.765 | 31.256 |
| **Tổng lượt lớp/box** | **80.910** | **208.777** |

Tổng lượt ảnh chứa lớp lớn hơn tổng ảnh vì một ảnh có thể mang nhiều lớp. Tổng dataset xuất là **74.103 ảnh**, chia như sau:

| Tập | Số ảnh | Biodegradable | recyclable | non_recyclable |
|---|---:|---:|---:|---:|
| Train | 59.279 | 19.277 | 35.237 | 10.211 |
| Val | 7.409 | 2.411 | 4.402 | 1.277 |
| Test | 7.415 | 2.409 | 4.409 | 1.277 |
| **Tổng** | **74.103** | **24.097** | **44.048** | **12.765** |

Trước export có 74.413 ảnh trong split manifest; export loại **310 ảnh** do có ít nhất một box vượt biên ảnh. Dataset đã xuất nằm tại:

```text
processed-data/
  data.yaml
  images/{train,val,test}/
  labels/{train,val,test}/
```

`processed-data-20k/` là tập con 20.000 ảnh được lấy ngẫu nhiên theo split hiện có (16.000 train, 2.000 val, 2.000 test); luồng huấn luyện mặc định không dùng tập con này.

### Nguồn và mapping

Cấu hình tại `configs/dataset.yaml` đưa bốn nguồn YOLO vào cùng ba lớp đích:

| Nguồn | Mapping chính |
|---|---|
| `raw-data/Recyclable Waste` | `Non-Recyclable` → `non_recyclable`; `Recyclable` → `recyclable` |
| `raw-data/Waste management` | Thực phẩm/giấy → `Biodegradable`; quần áo → `non_recyclable`; thủy tinh, kim loại, nhựa, cao su → `recyclable` |
| `raw-data/Waste Management- Recyclingv1` | Ba lớp nguồn được map trực tiếp sang ba lớp đích |
| `raw-data/Waste Detection` | Rác bếp và gỗ → `Biodegradable`; quần áo → `non_recyclable`; vật liệu tái chế → `recyclable` |

Lớp nguy hại trong hai nguồn phù hợp được loại khỏi mapping. `raw-data/` được giữ làm dữ liệu gốc; chỉ bốn nguồn khai báo trong cấu hình được dùng trong pipeline.

### Trạng thái nhãn

Các con số trên mô tả phân bố kỹ thuật của nhãn, không phải kết quả kiểm định nội dung. Báo cáo export hiện đánh dấu `ready_for_training: 0`; nhãn vẫn ở trạng thái `needs_review`. Cần duyệt tính đúng đắn ngữ nghĩa, xác minh các trường hợp mâu thuẫn nhãn trước khi xem dataset là đã được kiểm định. Bước export kiểm tra định dạng, tọa độ và ranh giới box, nhưng không tự xác nhận vật thể được gán đúng lớp.

## Pipeline tiền xử lý

Các bước được gọi tuần tự từ thư mục gốc. Nếu cấu hình hoặc dữ liệu nguồn thay đổi, chạy lại các bước từ inventory để cập nhật artifact nhất quán.

```powershell
uv sync --locked
uv run --locked python -B main.py --report
uv run --locked python -B main.py --stage inventory
uv run --locked python -B main.py --stage remap
uv run --locked python -B main.py --stage clean
uv run --locked python -B main.py --stage split
uv run --locked python -B main.py --stage export
```

Không truyền `--stage` thì CLI chỉ kiểm tra cấu hình. Các stage:

1. `config` — kiểm tra cấu hình và số nguồn/lớp.
2. `inventory` — ghép ảnh/nhãn, ghi kiểm kê trong `artifacts/`.
3. `remap` — ánh xạ ID lớp nguồn sang lớp đích.
4. `clean` — loại nhãn/ảnh lỗi, tìm bản trùng và chuẩn hóa EXIF/RGB.
5. `split` — chia theo nhóm ảnh với seed 42, mục tiêu train/val/test là 80/10/10.
6. `export` — ghi ảnh, nhãn YOLO và `data.yaml` vào `processed-data/` sau kiểm tra.

Đường dẫn cấu hình mặc định là `configs/dataset.yaml`; có thể chọn YAML khác bằng `--config`. Kết quả trung gian và báo cáo nằm trong `artifacts/`. Export bảo vệ dataset hiện có: thư mục `processed-data/` cần chưa tồn tại hoặc đang rỗng khi tạo lại.

## Huấn luyện và đánh giá

### YOLO26n

```powershell
uv run --locked python -B src/training/train.py
```

Script đọc `processed-data/data.yaml`, dùng GPU NVIDIA số 0 và pretrained `yolo26n.pt`. Cấu hình hiện tại: 40 epoch tối đa, patience 12, ảnh 640 px, batch 16, 4 workers, AdamW, learning rate 0.00015. Kết quả được lưu vào `model/` theo ngày và tên model, gồm `best.pt`, `last.pt` và checkpoint định kỳ.

### RT-DETR-L

```powershell
uv run --locked python -B src/training/train_rtdetr.py
```

Trainer này dùng pretrained `rtdetr-l.pt`, mặc định 50 epoch, ảnh 640 px, batch 4 và GPU 0. Có thể truyền cấu hình khi gọi `train()` trong Python; tham số `batch` là tổng batch size trên các GPU được chọn. AMP tắt mặc định để tránh NaN đã biết với một số cấu hình RT-DETR.

### Đánh giá

`src/training/evaluate.py` chạy đánh giá trên split test bằng Ultralytics. Trước khi chạy, cập nhật `MODEL_PATH` trong file tới checkpoint cần đo:

```powershell
uv run --locked python -B src/training/evaluate.py
```

## Cấu trúc dự án

```text
configs/dataset.yaml          # Nguồn, lớp đích, mapping và tỷ lệ chia
raw-data/                     # Các bộ dữ liệu gốc
artifacts/                    # Manifest, báo cáo và dữ liệu trung gian
processed-data/               # Dataset YOLO chính dùng train
processed-data-20k/           # Tập con 20.000 ảnh
src/frontend/                 # React + Vite; UI trong App.jsx/components.jsx
src/backend/main.py           # FastAPI và endpoint nhận diện
src/preprocess/                # Các stage tiền xử lý
src/training/                  # Trainer YOLO/RT-DETR và đánh giá
model/                         # Checkpoint pretrained và kết quả train
tests/                         # Kiểm thử pipeline
main.py                        # CLI tiền xử lý
docker-compose.yml             # Frontend Nginx và backend API
```

## Kiểm thử

```powershell
uv run --locked python -B -m unittest discover -s tests -v
```

Frontend build:

```powershell
cd src/frontend
npm ci
npm run build
```
