import secrets
import paho.mqtt.client as mqtt
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from esp32.database import db

MQTT_HOST = "127.0.0.1"
MQTT_PORT = 1883
DEFAULT_RANDOM_TOPIC = "esp32/random"

app = FastAPI()

app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)


class ExecuteRequest(BaseModel):
	member_name: str
	member_id: str
	topic_name: str

# 난수 생성 함수
def new_rand_num() -> str:
	return str(secrets.randbelow(90000) + 10000)

# MQTT 클라이언트 설정
mqtt_client = mqtt.Client()
mqtt_client.username_pw_set("admin", "qwer1234")

# MQTT 연결 성공 시 토픽 구독을 시작한다.
@app.on_event("startup")
def startup_mqtt() -> None:
	mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
	mqtt_client.loop_start()

@app.on_event("shutdown")
def shutdown_mqtt() -> None:
	mqtt_client.loop_stop()
	mqtt_client.disconnect()


# 요청 토픽을 정리해 ESP32 기본 랜덤키 토픽으로 안전하게 보정한다.
def normalize_publish_topic(topic_name: str) -> str:
	topic = (topic_name or "").strip()
	if not topic:
		return DEFAULT_RANDOM_TOPIC
	if " " in topic:
		return DEFAULT_RANDOM_TOPIC
	return topic

# 웹에서 받은 회원정보와 토픽정보를 처리한다.
@app.post("/execute")
def handle_web_request(payload: ExecuteRequest) -> dict:
	random_key = new_rand_num()
	publish_topic = normalize_publish_topic(payload.topic_name)

	try:
		db.insert_play_request(
			rand_num=random_key,
			member_name=payload.member_name,
			member_no=payload.member_id,
			topic_name=publish_topic,
		)
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"database.py 전달 실패: {e}") from e
	
# MQTT로 난수 키와 토픽을 발행한다.
	try:
		mqtt_client.publish(publish_topic, random_key, qos=1)
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"MQTT 발행 실패: {e}") from e

	return {
		"status": "success",
		"generated_random_key": random_key,
	}

