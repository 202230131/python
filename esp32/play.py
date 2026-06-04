import secrets
import paho.mqtt.client as mqtt
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
# 💡 [추가] 브라우저 차단(CORS)을 막기 위한 패키지 가져오기
from fastapi.middleware.cors import CORSMiddleware 
from esp32.database import db

MQTT_HOST = "127.0.0.1"
MQTT_PORT = 1883

app = FastAPI()

# 💡 [추가] 내 HTML 대시보드 웹페이지가 접근할 수 있도록 보안 허용 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 주소의 접근을 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


class ExecuteRequest(BaseModel):
    member_name: str
    member_id: str
    topic_name: str

# 웹에서 받은 회원정보와 토픽정보를 처리한다.
@app.post("/execute")
def handle_web_request(req: ExecuteRequest) -> dict:
    member_name = req.member_name
    member_id = req.member_id
    topic_name = req.topic_name
    random_key = new_rand_num()

    try:
        db.insert_play_request(
            rand_num=random_key,
            member_name=member_name,
            member_no=member_id,
            topic_name=topic_name,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"database.py 전달 실패: {e}") from e
   
    # MQTT로 난수 키와 토픽을 발행한다.
    try:
        mqtt_client.publish(topic_name, random_key, qos=1)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MQTT 발행 실패: {e}") from e

    return {
        "status": "success",
        "generated_random_key": random_key,
    }


# 💡 [올바른 위치로 정렬] 로그인한 회원의 포인트를 데이터베이스에서 조회하는 API
@app.get("/member/{member_id}/points")
def get_member_points(member_id: str) -> dict:
    try:
        # DB에서 이 회원의 포인트를 가져오는 함수 실행
        points = db.get_member_points(member_no=member_id) 
        if points is None: 
            points = 0
        return {"status": "success", "points": points}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))