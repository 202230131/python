// # 초음파 핀 설정
const int trigPin = 5;
const int echoPin = 18;

unsigned long lastDetectionTime = 0;
const unsigned long cooldownPeriod = 10000; // 10초 대기 시간 (밀리초)
const unsigned long echoTimeoutUs = 30000;  // 에코 대기 최대 시간
const float minValidDistanceCm = 2.0f;
const float detectThresholdCm = 10.0f;

// # 초음파 핀을 초기화한다.
void initUltrasonic() {
  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT_PULLDOWN);
  digitalWrite(trigPin, LOW);
}

// # 초음파 센서 거리(cm)를 측정한다. 실패 시 -1을 반환한다.
float measureDistanceCm() {
  // 초음파 신호 발사
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  // 에코 신호 수신 시간 측정
  long duration = pulseIn(echoPin, HIGH, echoTimeoutUs);
  if (duration == 0) {
    return -1.0;
  }

  return (duration * 0.034f) / 2.0f;
}

bool checkUltrasonic() {
  unsigned long currentMillis = millis();
  
  // 10초 대기 시간이 지나지 않았으면 작동하지 않음
  if (currentMillis - lastDetectionTime < cooldownPeriod) {
    return false; 
  }

  // 거리 측정
  float distance = measureDistanceCm();
  if (distance < 0) {
    return false;
  } 

  // 유효 범위를 벗어난 값(노이즈/미연결 오탐)을 제외한다.
  if (distance < minValidDistanceCm || distance > 400.0f) {
    return false;
  }

  // 10cm 이내 감지 시
  if (distance <= detectThresholdCm) {
    lastDetectionTime = currentMillis; // 마지막 감지 시간 업데이트 (10초 쿨타임 시작)
    Serial.print("Distance: ");
    Serial.print(distance, 2);
    Serial.println(" cm");
    return true;
  }

  return false;
}
