import os
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from PIL import Image
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader, Dataset

# GPU 사용 가능 여부 확인
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"사용 디바이스: {device}\n")


# ============================================
# 1. CNN 모델 정의 (다중 분류, 원본 해상도 대응)
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

        # 입력 이미지 크기가 달라도 FC 입력 차원을 고정한다.
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
# 2. 이미지 전처리 함수 (원본 RGB 유지)
# ============================================
def preprocess_image(img_path: str):
    """
    흑백/리사이징 없이 원본 RGB 이미지를 그대로 텐서로 변환한다.
    반환 shape: (3, H, W)
    """
    try:
        img = Image.open(img_path).convert("RGB")
        img_array = np.array(img, dtype=np.float32) / 255.0
    except Exception:
        print(f"파일 읽기 실패: {os.path.basename(img_path)}")
        return None

    chw = np.transpose(img_array, (2, 0, 1))
    return torch.from_numpy(chw)


# ============================================
# 3. PyTorch Dataset 클래스
# ============================================
class CanPetDataset(Dataset):
    def __init__(self, images, labels):
        self.images = images
        self.labels = torch.LongTensor(labels)

    def __len__(self):
        return len(self.images)

    def __getitem__(self, idx):
        return self.images[idx], self.labels[idx]


# ============================================
# 4. 배치 패딩(collate)
# ============================================
def pad_collate_fn(batch):
    """
    서로 다른 해상도의 이미지를 같은 배치로 묶기 위해
    배치 내 최대 H/W 기준으로 0 패딩한다.
    """
    images, labels = zip(*batch)

    max_h = max(img.shape[1] for img in images)
    max_w = max(img.shape[2] for img in images)

    padded = []
    for img in images:
        c, h, w = img.shape
        canvas = torch.zeros((c, max_h, max_w), dtype=img.dtype)
        canvas[:, :h, :w] = img
        padded.append(canvas)

    return torch.stack(padded, dim=0), torch.stack(labels, dim=0)


# ============================================
# 5. 데이터 로드
# ============================================
def discover_class_dirs(base_path: Path):
    class_dirs = [p for p in base_path.iterdir() if p.is_dir()]
    class_dirs.sort(key=lambda p: p.name)
    return class_dirs


def load_data(base_path: Path):
    images = []
    labels = []

    class_dirs = discover_class_dirs(base_path)
    if not class_dirs:
        return None, None, None

    class_names = [p.name for p in class_dirs]
    class_to_idx = {name: idx for idx, name in enumerate(class_names)}

    print("클래스 매핑:")
    for name, idx in class_to_idx.items():
        print(f"  {idx} <- {name}")

    for class_dir in class_dirs:
        class_name = class_dir.name
        class_idx = class_to_idx[class_name]

        count = 0
        for filename in os.listdir(class_dir):
            if not filename.lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp")):
                continue

            filepath = str(class_dir / filename)
            img_tensor = preprocess_image(filepath)

            if img_tensor is not None:
                images.append(img_tensor)
                labels.append(class_idx)
                count += 1

        print(f"  {class_name}({class_idx}): {count}장 로드됨")

    if not images:
        return None, None, None

    return images, np.array(labels, dtype=np.int64), class_names


# ============================================
# 6. 학습 함수
# ============================================
def train_model(model, train_loader, val_loader, criterion, optimizer, num_epochs=20):
    for epoch in range(num_epochs):
        model.train()
        train_loss = 0.0
        train_correct = 0
        train_total = 0

        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)

            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)

            loss.backward()
            optimizer.step()

            train_loss += loss.item()
            predictions = torch.argmax(outputs, dim=1)
            train_correct += (predictions == labels).sum().item()
            train_total += labels.size(0)

        train_loss /= len(train_loader)
        train_acc = (train_correct / train_total) * 100 if train_total else 0.0

        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0

        with torch.no_grad():
            for images, labels in val_loader:
                images, labels = images.to(device), labels.to(device)

                outputs = model(images)
                loss = criterion(outputs, labels)

                val_loss += loss.item()
                predictions = torch.argmax(outputs, dim=1)
                val_correct += (predictions == labels).sum().item()
                val_total += labels.size(0)

        val_loss /= len(val_loader)
        val_acc = (val_correct / val_total) * 100 if val_total else 0.0

        if (epoch + 1) % 5 == 0 or epoch == 0:
            print(
                f"Epoch [{epoch + 1:2d}/{num_epochs}] | "
                f"Train Loss: {train_loss:.4f} Acc: {train_acc:.1f}% | "
                f"Val Loss: {val_loss:.4f} Acc: {val_acc:.1f}%"
            )


# ============================================
# 7. 메인 실행
# ============================================
if __name__ == "__main__":
    BASE_DIR = Path(__file__).resolve().parent
    DATASET_PATH = BASE_DIR / "dataset"

    print("=" * 60)
    print("다중 클래스 분류 모델 학습 - 원본 RGB 이미지")
    print("=" * 60)
    print(f"\n데이터셋 경로: {DATASET_PATH}\n")

    print("데이터 로드 중...\n")
    images, labels, class_names = load_data(DATASET_PATH)

    if images is None:
        print("\n에러: 데이터가 없습니다.")
        print(f"  {DATASET_PATH} 하위에 클래스별 폴더를 만들고 이미지를 넣어주세요.\n")
        raise SystemExit(1)

    class_count = len(class_names)
    if class_count < 2:
        print("\n에러: 클래스 수가 2개 이상이어야 학습할 수 있습니다.")
        raise SystemExit(1)

    print(f"\n총 {len(images)}장 로드됨")
    for idx, name in enumerate(class_names):
        count = int((labels == idx).sum())
        print(f"  클래스 {idx} ({name}): {count}장")
    print()

    indices = np.arange(len(images))
    train_idx, val_idx = train_test_split(
        indices,
        test_size=0.2,
        random_state=42,
        stratify=labels,
    )

    train_images = [images[i] for i in train_idx]
    val_images = [images[i] for i in val_idx]
    train_labels = labels[train_idx]
    val_labels = labels[val_idx]

    train_dataset = CanPetDataset(train_images, train_labels)
    val_dataset = CanPetDataset(val_images, val_labels)

    train_loader = DataLoader(train_dataset, batch_size=8, shuffle=True, collate_fn=pad_collate_fn)
    val_loader = DataLoader(val_dataset, batch_size=8, shuffle=False, collate_fn=pad_collate_fn)

    model = CanPetCNN(num_classes=class_count).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)

    print("모델 구조:")
    print(model)
    print()

    print("학습 시작...\n")
    train_model(model, train_loader, val_loader, criterion, optimizer, num_epochs=20)

    checkpoint = {
        "model_state_dict": model.state_dict(),
        "class_names": class_names,
    }
    model_path = BASE_DIR / "can_pet_model.pth"
    torch.save(checkpoint, model_path)

    print("\n" + "=" * 60)
    print(f"학습 완료! 모델 저장: {model_path}")
    print("=" * 60)
