import json
import sys
from datetime import datetime
from pathlib import Path
import paho.mqtt.client as mqtt
import requests
from esp32.test import analyze_image_for_motor
from esp32.motor import handle_classification_result
from esp32.database import db

# MQTT 센서 구독기: 이미지를 캡처하고 test.py 분류 함수를 호출한다.
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
	sys.path.insert(0, str(BASE_DIR))

MQTT_HOST = "127.0.0.1"
MQTT_PORT = 1883
MQTT_TOPIC = "esp32/sensor"

CAM_URL = "http://192.168.137.240/capture"

LATEST_CAPTURE_PATH = BASE_DIR / "captured_image.jpg"
PHOTO_DATA_DIR = BASE_DIR / "photoData"

# MQTT 센서 구독기를 실행한다.
def main() -> None:
	client = mqtt.Client()
	client.username_pw_set("admin", "qwer1234")
	client.on_connect = on_connect
	client.on_message = on_message

	client.connect(MQTT_HOST, MQTT_PORT, 60)
	client.loop_forever()

# MQTT 연결 성공 시 센서 토픽 구독을 시작한다.
def on_connect(client, userdata, flags, rc):
	if rc == 0:
		client.subscribe(MQTT_TOPIC)


# MQTT 메시지 콜백에서 payload를 받아 처리 함수로 전달한다.
def on_message(client, userdata, msg):
	payload_str = msg.payload.decode("utf-8").strip()
	process_sensor_message(payload_str)


	# 센서 토픽 payload에서 상태값과 난수를 추출한다.
def parse_sensor_payload(payload_str: str) -> tuple[object, str]:
	payload = json.loads(payload_str)
	sensor_status = payload.get("sensor_status", payload.get("signal", False))
	raw_rand = payload.get("rand_num", payload.get("random_key", ""))
	rand_num = "" if raw_rand is None else str(raw_rand).strip()
	return sensor_status, rand_num


# 센서 상태값을 bool로 안전하게 해석한다.
def is_sensor_triggered(sensor_status: object) -> bool:
	if isinstance(sensor_status, bool):
		return sensor_status

	if isinstance(sensor_status, (int, float)):
		return int(sensor_status) == 1

	if isinstance(sensor_status, str):
		normalized = sensor_status.strip().lower()
		return normalized in {"1", "true", "on", "yes"}

	return False


# 센서 메시지를 처리하고, true일 때만 캡처/분류를 진행한다.
def process_sensor_message(payload_str: str) -> None:
	try:
		sensor_status, rand_num = parse_sensor_payload(payload_str)
	except Exception:
		# JSON 형식이 아니면 기존 문자열 규칙으로도 처리해본다.
		raw = payload_str.strip().lower()
		sensor_status = raw
		rand_num = ""

	if not is_sensor_triggered(sensor_status):
		return

	image_path = fetch_still_image(rand_num=rand_num)
	if image_path is None:
		return

	classify_and_forward(image_path=image_path, rand_num=rand_num)


# 캡처 파일명을 생성한다. (시간 + 선택적 rand_num)
def _build_capture_filename(rand_num: str) -> str:
	# 마이크로초까지 포함해 연속 캡처에서도 파일명 충돌을 줄인다.
	timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
	# 파일명에 안전한 영숫자만 남기고 길이를 제한한다.
	safe_rand = "".join(ch for ch in rand_num if ch.isalnum())[:32]
	if safe_rand:
		return f"capture_{timestamp}_{safe_rand}.jpg"
	return f"capture_{timestamp}.jpg"

# ESP32-CAM 정지 이미지를 받아 latest와 이력 파일로 함께 저장한다.
def fetch_still_image(rand_num: str = "") -> Path | None:
	response = requests.get(CAM_URL, timeout=12, headers={"Connection": "close"})
	if response.status_code != 200 or not response.content:
		return None

	PHOTO_DATA_DIR.mkdir(parents=True, exist_ok=True)
	# 이력 보관용 파일 경로(요청마다 새 파일)
	photo_data_path = PHOTO_DATA_DIR / _build_capture_filename(rand_num)
	# 누적 보관용 파일
	photo_data_path.write_bytes(response.content)
	# 최신 1장 참조용 고정 파일(분류는 이 파일을 사용)
	LATEST_CAPTURE_PATH.write_bytes(response.content)
	return LATEST_CAPTURE_PATH


# 캡처 이미지를 분류하고 결과 코드를 반환받아 DB에 저장한다.
def classify_and_forward(image_path: Path, rand_num: str) -> int:
	result = int(analyze_image_for_motor(str(image_path)))
	handle_classification_result(result)
	if rand_num:
		db.insert_play_result(rand_num=rand_num, result_value=result)
	return result


if __name__ == "__main__":
	main()
