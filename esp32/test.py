import os
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn as nn
from fastapi import FastAPI, HTTPException
from PIL import Image
from pydantic import BaseModel, Field

# GPU 확인
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = str(BASE_DIR / "can_pet_model.pth")
loaded_bundle = None
app = FastAPI(title="ESP32 AI Inference Service")


class PredictRequest(BaseModel):
    image_path: str = Field(..., description="분류할 이미지 경로")


# ============================================
# 1. CNN 모델 정의 (학습 스크립트와 동일)
# ============================================
class CanPetCNN(nn.Module):
    def __init__(self, num_classes: int):
        super().__init__()

        self.conv1 = nn.Conv2d(3, 32, kernel_size=3, padding=1)
        self.pool1 = nn.MaxPool2d(2, 2)

        self.conv2 = nn.Conv2d(32, 64, kernel_size=3, padding=1)
        self.pool2 = nn.MaxPool2d(2, 2)

        self.conv3 = nn.Conv2d(64, 128, kernel_size=3, padding=1)
        self.pool3 = nn.MaxPool2d(2, 2)

        self.adaptive_pool = nn.AdaptiveAvgPool2d((8, 8))

        self.fc1 = nn.Linear(128 * 8 * 8, 128)
        self.dropout = nn.Dropout(0.5)
        self.fc2 = nn.Linear(128, num_classes)
        self.relu = nn.ReLU()

    def forward(self, x):
        x = self.relu(self.conv1(x))
        x = self.pool1(x)

        x = self.relu(self.conv2(x))
        x = self.pool2(x)

        x = self.relu(self.conv3(x))
        x = self.pool3(x)

        x = self.adaptive_pool(x)
        x = x.view(x.size(0), -1)
        x = self.relu(self.fc1(x))
        x = self.dropout(x)
        x = self.fc2(x)
        return x


# ============================================
# 2. 모델 로드
# ============================================
def get_model_bundle():
    global loaded_bundle
    if loaded_bundle is not None:
        return loaded_bundle

    if not os.path.exists(MODEL_PATH):
        return None

    checkpoint = torch.load(MODEL_PATH, map_location=device)

    # 이전 형식(state_dict만 저장)도 호환한다.
    if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
        class_names = checkpoint.get("class_names") or ["0", "1"]
        state_dict = checkpoint["model_state_dict"]
    else:
        class_names = ["0", "1"]
        state_dict = checkpoint

    model = CanPetCNN(num_classes=len(class_names)).to(device)
    model.load_state_dict(state_dict)
    model.eval()

    loaded_bundle = {
        "model": model,
        "class_names": class_names,
    }
    return loaded_bundle


# ============================================
# 3. 이미지 전처리 (원본 RGB 유지)
# ============================================
def preprocess_image_for_test(img_path: str):
    """
    흑백/리사이징 없이 원본 RGB 이미지를 그대로 사용한다.
    반환 shape: (1, 3, H, W)
    """
    try:
        img = Image.open(img_path).convert("RGB")
        img_array = np.array(img, dtype=np.float32) / 255.0
    except Exception:
        return None

    chw = np.transpose(img_array, (2, 0, 1))
    input_data = torch.from_numpy(chw).unsqueeze(0)
    return input_data.to(device)


# ============================================
# 4. 추론 함수
# ============================================
def class_name_to_service_code(class_name: str, default_idx: int) -> int:
    """
    클래스 폴더명이 숫자("0","1","2")면 그 값을 서비스 코드로 사용한다.
    숫자가 아니면 분류 인덱스를 그대로 반환한다.
    """
    text = str(class_name).strip()
    if text.isdigit():
        return int(text)
    return int(default_idx)


def classify_image(model, class_names, img_path: str):
    input_data = preprocess_image_for_test(img_path)
    if input_data is None:
        return 0, 0.0

    with torch.no_grad():
        logits = model(input_data)
        probs = torch.softmax(logits, dim=1)

    pred_idx = int(torch.argmax(probs, dim=1).item())
    confidence = float(probs[0, pred_idx].item())

    if pred_idx < len(class_names):
        service_code = class_name_to_service_code(class_names[pred_idx], pred_idx)
    else:
        service_code = pred_idx

    return service_code, confidence


def predict_now(img_path: str) -> int:
    bundle = get_model_bundle()
    if bundle is None:
        return 0

    model = bundle["model"]
    class_names = bundle["class_names"]

    label, _confidence = classify_image(model, class_names, img_path)
    return int(label)


def analyze_image_for_motor(img_path: str) -> int:
    if not os.path.exists(img_path):
        return 0
    return int(predict_now(img_path))


# FastAPI 엔드포인트 정의
@app.post("/predict")
def predict(req: PredictRequest) -> dict[str, int]:
    try:
        return {"result": int(analyze_image_for_motor(req.image_path))}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"predict failed: {exc}") from exc


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True}
