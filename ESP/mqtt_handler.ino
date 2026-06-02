    #include <WiFi.h>
    #include <PubSubClient.h>
    #include <stdio.h>
    #include <stdlib.h>
    #include <string.h>

    // # MQTT 설정값
    const char* mqtt_server = "192.168.137.1";
    const char* mqtt_user = "admin";
    const char* mqtt_password = "qwer1234";
    const char* mqtt_client_id = "ESP32Client-01";

    // # MQTT 클라이언트 객체 (WiFiClient 기반)
    extern WiFiClient espClient;
    PubSubClient client(espClient);

    // # MQTT 상태값
    char latestRandNum[33] = {0};

    // 구독할 토픽 3개 정의
    const char* topic1 = "esp32/motor";     // 모터 제어용 토픽 (0, 1, 2 수신)
    const char* topic2 = "esp32/sensor";    // 센서 발행 토픽 (필요 시 상태 수신 가능)
    const char* topic3 = "esp32/random";    // 상태 확인용 토픽 3


    // # 메인 루프(MQTT 흐름 + 센서 이벤트 발행)
    void loop() {
    // MQTT 연결 유지
    if (!client.connected()) {
        reconnect();
    }
    client.loop();

    // MQTT 처리 모듈에서 센서 감지 + 발행을 함께 처리한다.
    processUltrasonicAndPublish();
    }

    // # 양쪽 공백/개행을 제거한다.
    void trimInPlace(char* text) {
    if (text == NULL) {
        return;
    }

    size_t len = strlen(text);
    while (len > 0 && (text[len - 1] == ' ' || text[len - 1] == '\n' || text[len - 1] == '\r' || text[len - 1] == '\t')) {
        text[len - 1] = '\0';
        len--;
    }

    size_t start = 0;
    while (text[start] == ' ' || text[start] == '\n' || text[start] == '\r' || text[start] == '\t') {
        start++;
    }

    if (start > 0) {
        memmove(text, text + start, strlen(text + start) + 1);
    }
    }

    // # payload 바이트 배열을 C 문자열 버퍼에 복사한다.
    void payloadToBuffer(byte* payload, unsigned int length, char* out, size_t outSize) {
    if (out == NULL || outSize == 0) {
        return;
    }

    size_t copyLen = length;
    if (copyLen > outSize - 1) {
        copyLen = outSize - 1;
    }

    memcpy(out, payload, copyLen);
    out[copyLen] = '\0';
    trimInPlace(out);
    }

    // 초음파 감지를 확인하고, 감지 시 센서 토픽으로 JSON을 발행한다.
    void processUltrasonicAndPublish() {
    if (!checkUltrasonic()) {
        return;
    }

    // 서버(sensor.py)에서 기대하는 JSON 포맷으로 발행한다.
    char payload[96];
    snprintf(payload, sizeof(payload), "{\"sensor_status\":true,\"rand_num\":\"%s\"}", latestRandNum);
    Serial.print("Object detected within 10cm! Sending MQTT alert: ");
    Serial.println(payload);
    client.publish(topic2, payload, false);
    }

    // MQTT 메시지 수신 시 실행되는 콜백 함수
    void callback(char* topic, byte* payload, unsigned int length) {
    Serial.print("Message arrived [");
    Serial.print(topic);
    Serial.print("] ");

    char messageInfo[64];
    payloadToBuffer(payload, length, messageInfo, sizeof(messageInfo));
    Serial.println(messageInfo);

    // 서버가 발행한 난수 키를 저장해 센서 이벤트에 함께 보낸다.
    if (strcmp(topic, topic3) == 0) {
        strncpy(latestRandNum, messageInfo, sizeof(latestRandNum) - 1);
        latestRandNum[sizeof(latestRandNum) - 1] = '\0';
        Serial.print("Updated latest rand_num: ");
        Serial.println(latestRandNum);
        return;
    }

    // 모터 제어 토픽에서 온 메시지만 처리
    if (strcmp(topic, topic1) == 0) {
        int cmd = atoi(messageInfo);
        handleMotorCommand(cmd);
    }
    }

    // MQTT 브로커 재연결 및 토픽 구독
    void reconnect() {
    while (!client.connected()) {
        Serial.print("Attempting MQTT connection...");

        // Python 서버 모스키토 설정과 동일한 계정으로 접속한다.
        if (client.connect(mqtt_client_id, mqtt_user, mqtt_password)) {
        Serial.println("connected");

        // 토픽 3개 구독 신청
        client.subscribe(topic1);
        client.subscribe(topic2);
        client.subscribe(topic3);

        Serial.println("Subscribed to 3 topics.");
        } else {
        Serial.print("failed, rc=");
        Serial.print(client.state());
        Serial.println(" try again in 5 seconds");
        delay(5000);
        }
    }
    }
