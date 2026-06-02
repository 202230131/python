const int dirPin = 17;
const int stepPin = 21;
const int enPin = 22;             
const bool useEnablePin = true;   

// # 스텝 설정 (150도 회전 스텝 적용)
const int stepsPerRevolution = 200;       
const int rotate150Steps = 83;            // 200 * 150 / 360 = 83.3 -> 83 스텝
const unsigned int stepPulseUs = 25000;   // 펄스 주기 (속도)

// # 동작 타이밍
const unsigned long holdAtTargetMs = 700;  // 목표 지점 대기 시간
const unsigned long settleDelayMs = 90;    // 복귀 후 안정화 시간

// # A4988 활성/비활성
void enableDriver() {
  if (useEnablePin) {
    digitalWrite(enPin, LOW);
    delay(10); // 드라이버가 완전히 켜지는 시간 확보
  }
}

void disableDriver() {
  if (useEnablePin) {
    digitalWrite(enPin, HIGH);
  }
}

// # 모터 핀 초기화
void initMotorControl() {
  pinMode(dirPin, OUTPUT);
  pinMode(stepPin, OUTPUT);

  if (useEnablePin) {
    pinMode(enPin, OUTPUT);
    disableDriver();
  }

  digitalWrite(dirPin, LOW);
  digitalWrite(stepPin, LOW);
}

void stopMotor() {
  disableDriver();
}

// # direction=true : 정방향, false : 역방향
void rotateMotorSteps(bool direction, int stepCount) {
  enableDriver();
  digitalWrite(dirPin, direction ? HIGH : LOW);
  
  delay(10);

  for (int i = 0; i < stepCount; i++) {
    digitalWrite(stepPin, HIGH);
    delayMicroseconds(stepPulseUs);
    digitalWrite(stepPin, LOW);
    delayMicroseconds(stepPulseUs);
  }
}

// # 지정 방향으로 동작 후 원점(0도)으로 복귀
void runAndReturnHome(bool direction, int stepCount) {
  // 1) 목표 방향으로 이동
  Serial.println("-> Moving to target position...");
  rotateMotorSteps(direction, stepCount);

  // 2) 목표 위치 잠깐 유지
  delay(holdAtTargetMs);

  // 3) 역방향(!direction)으로 같은 스텝만큼 복귀
  Serial.println("<- Returning to home position...");
  rotateMotorSteps(!direction, stepCount);
  
  // 4) 복귀 후 안정화 및 정지
  delay(settleDelayMs);
  stopMotor();
  Serial.println("   Arrived at home.");
}

// # MQTT 모터 명령(0/1/2) 처리 함수
void handleMotorCommand(int cmd) {
  if (cmd == 0) {
    Serial.println("Action: 0 - Stop (No movement)");
    stopMotor();
  } 
  else if (cmd == 1) {
    Serial.println("Action: 1 - Rotate +150 deg and return home");
    // true(정방향)로 갔다가 false(역방향)로 돌아옴
    runAndReturnHome(true, rotate150Steps);
  } 
  else if (cmd == 2) {
    Serial.println("Action: 2 - Rotate -150 deg and return home");
    // false(역방향)로 갔다가 true(정방향)로 돌아옴
    runAndReturnHome(false, rotate150Steps);
  } 
  else {
    Serial.print("Unknown motor command: ");
    Serial.println(cmd);
  }
}