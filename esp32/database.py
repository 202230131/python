import os
import threading
import importlib
from typing import Any

# 데이터베이스 서비스 클래스 정의
class DBService:
	def __init__(self) -> None:
		self.host = os.getenv("MYSQL_HOST", "127.0.0.1")
		self.port = int(os.getenv("MYSQL_PORT", "3306"))
		self.user = os.getenv("MYSQL_USER", "esp32")
		self.password = os.getenv("MYSQL_PASSWORD", "qwer1234")
		self.database = os.getenv("MYSQL_DATABASE", "esp32")
		self.charset = "utf8mb4"
		self._lock = threading.Lock()
 
    # 데이터베이스 연결을 생성하는 내부 메서드
	def _connect(self):
		pymysql = importlib.import_module("pymysql")
		dict_cursor = importlib.import_module("pymysql.cursors").DictCursor
		return pymysql.connect(
			host=self.host,
			port=self.port,
			user=self.user,
			password=self.password,
			database=self.database,
			charset=self.charset,
			autocommit=True,
			cursorclass=dict_cursor,
		)
    
    # play_request_table에 요청 정보를 삽입하는 메서드
	def insert_play_request(self, rand_num: str, member_name: str, member_no: str, topic_name: str) -> None:
		with self._lock:
			conn = self._connect()
			try:
				with conn.cursor() as cur:
					cur.execute(
						"""
						INSERT INTO play_request_table(rand_num, member_name, member_no, topic_name)
						VALUES(%s, %s, %s, %s)
						""",
						(rand_num, member_name, member_no, topic_name),
					)
			finally:
				conn.close()

    # play_result_table에 분류 결과를 삽입하거나 업데이트하는 메서드
	def insert_play_result(self, rand_num: str, result_value: int) -> None:
		with self._lock:
			conn = self._connect()
			try:
				with conn.cursor() as cur:
					cur.execute(
						"""
						INSERT INTO play_result_table(rand_num, result_value)
						VALUES(%s, %s)
						ON DUPLICATE KEY UPDATE result_value=VALUES(result_value)
						""",
						(rand_num, int(result_value)),
					)
			finally:
				conn.close()
    
    # rand_num을 기준으로 play_request_table과 play_result_table을 조인하여 관련 정보를 조회하는 메서드
	def get_play_relation(self, rand_num: str) -> dict[str, Any] | None:
		conn = self._connect()
		try:
			with conn.cursor() as cur:
				cur.execute(
					"""
					SELECT
						p.rand_num,
						p.member_name,
						p.member_no,
						p.topic_name,
						r.result_value
					FROM play_request_table p
					LEFT JOIN play_result_table r ON r.rand_num = p.rand_num
					WHERE p.rand_num = %s
					""",
					(rand_num,),
				)
				row = cur.fetchone()
				return row
		finally:
			conn.close()

# DBService 인스턴스를 생성하여 모듈 전체에서 사용할 수 있도록 한다.
db = DBService()

__all__ = ["db", "DBService"]
