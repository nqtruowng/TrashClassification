"""FastAPI backend for the trash classification frontend."""

import os
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from PIL import Image, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool
from ultralytics import YOLO
from sqlalchemy.orm import Session

from src.backend.auth import (
    AUTH_COOKIE_NAME,
    AUTH_COOKIE_SECURE,
    JWT_ACCESS_TOKEN_MINUTES,
    JWT_SECRET_KEY,
    Base,
    Credentials,
    User,
    authenticate_user,
    create_access_token,
    engine,
    get_current_user,
    get_session,
    public_user,
    register_user,
)


ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = Path(os.environ.get(
    "MODEL_PATH",
    str(ROOT / "model" / "11-11-2026-yolo26n" / "weights" / "best.pt"),
))
MAX_IMAGE_BYTES = int(os.environ.get("MAX_IMAGE_BYTES", str(20 * 1024 * 1024)))


def category_for(class_name: str) -> tuple[str, str, str]:
    name = class_name.casefold()
    if "biodegradable" in name:
        return "organic", "Phân hủy sinh học", "Có thể cho vào thùng rác hữu cơ hoặc ủ compost."
    if "recyclable" in name and "non_recyclable" not in name:
        return "recycle", "Tái chế được", "Làm sạch vật dụng và bỏ vào thùng tái chế."
    if "non_recyclable" in name:
        return "non_recyclable", "Không tái chế được", "Bỏ vào thùng rác còn lại. Kiểm tra hướng dẫn tại địa phương."
    return "other", class_name, "Kiểm tra hướng dẫn phân loại rác tại địa phương."


@asynccontextmanager
async def lifespan(app: FastAPI):
    if len(JWT_SECRET_KEY) < 32:
        raise RuntimeError("JWT_SECRET_KEY phải có ít nhất 32 ký tự. Hãy cấu hình biến môi trường trước khi chạy backend.")
    if JWT_ACCESS_TOKEN_MINUTES < 1:
        raise RuntimeError("JWT_ACCESS_TOKEN_MINUTES phải lớn hơn 0.")
    await run_in_threadpool(Base.metadata.create_all, engine)
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(f"Không tìm thấy model: {MODEL_PATH}")
    print(f"Đang tải model: {MODEL_PATH}")
    app.state.model = YOLO(str(MODEL_PATH))
    yield


app = FastAPI(title="Trash Classification API", version="1.0.0", lifespan=lifespan)


@app.get("/health")
def health(request: Request):
    return {"status": "ready", "model": MODEL_PATH.name, "loaded": hasattr(request.app.state, "model")}


def set_auth_cookie(response: Response, user: User) -> None:
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=create_access_token(user),
        httponly=True,
        secure=AUTH_COOKIE_SECURE,
        samesite="lax",
        max_age=JWT_ACCESS_TOKEN_MINUTES * 60,
        path="/",
    )


@app.post("/auth/register", status_code=status.HTTP_201_CREATED)
def register(credentials: Credentials, response: Response, session: Session = Depends(get_session)):
    user = register_user(session, credentials)
    set_auth_cookie(response, user)
    return {"user": public_user(user)}


@app.post("/auth/login")
def login(credentials: Credentials, response: Response, session: Session = Depends(get_session)):
    user = authenticate_user(session, credentials)
    set_auth_cookie(response, user)
    return {"user": public_user(user)}


@app.get("/auth/me")
def current_user(user: User = Depends(get_current_user)):
    return {"user": public_user(user)}


@app.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie(AUTH_COOKIE_NAME, httponly=True, secure=AUTH_COOKIE_SECURE, samesite="lax", path="/")
    return {"message": "Đã đăng xuất."}


@app.post("/predict")
async def predict(request: Request, _user: User = Depends(get_current_user)):
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_IMAGE_BYTES:
                return JSONResponse(status_code=413, content={"error": "Ảnh phải có dung lượng nhỏ hơn 20 MB."})
        except ValueError:
            return JSONResponse(status_code=400, content={"error": "Kích thước ảnh không hợp lệ."})

    # The frontend sends the image bytes directly as application/octet-stream.
    image_chunks = []
    image_size = 0
    async for chunk in request.stream():
        image_size += len(chunk)
        if image_size > MAX_IMAGE_BYTES:
            return JSONResponse(status_code=413, content={"error": "Ảnh phải có dung lượng nhỏ hơn 20 MB."})
        image_chunks.append(chunk)
    if image_size == 0:
        return JSONResponse(status_code=400, content={"error": "Ảnh phải có dung lượng nhỏ hơn 20 MB."})
    image_bytes = b"".join(image_chunks)

    try:
        with Image.open(BytesIO(image_bytes)) as source:
            source.load()
            image = source.convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        return JSONResponse(status_code=400, content={"error": "Không đọc được ảnh. Hãy thử ảnh JPG hoặc PNG."})

    result = await run_in_threadpool(request.app.state.model.predict, image, imgsz=640, conf=0.25, verbose=False)
    prediction = result[0]
    if prediction.boxes is None or len(prediction.boxes) == 0:
        return {
            "found": False,
            "message": "Model không phát hiện vật thể với ngưỡng tin cậy hiện tại.",
            "image_size": [image.width, image.height],
            "detections": [],
        }

    boxes = prediction.boxes
    confidences = boxes.conf.cpu().tolist()
    class_ids = boxes.cls.cpu().tolist()
    coordinates = boxes.xyxy.cpu().tolist()
    detections = []
    for class_id, confidence, xyxy in zip(class_ids, confidences, coordinates):
        class_name = prediction.names[int(class_id)]
        key, label, advice = category_for(class_name)
        detections.append({
            "class_name": class_name,
            "label": label,
            "category": key,
            "confidence": round(confidence, 4),
            "box": [round(value, 1) for value in xyxy],
            "advice": advice,
        })
    detections.sort(key=lambda item: item["confidence"], reverse=True)
    return {"found": True, "detections": detections, "image_size": [image.width, image.height]}
