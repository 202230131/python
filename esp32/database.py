import os
import threading
import importlib

# 데이터베이스 서비스 클래스 정의
class DBService:
	def __init__(self) -> None:
		self.host = os.getenv("MYSQL_HOST", "127.0.0.1")
		self.port = int(os.getenv("MYSQL_PORT", "3306"))
		self.user = os.getenv("MYSQL_USER", "root")
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

	# rand_num 기준 조인 결과를 play_join_table에 upsert 저장만 수행한다.
	def _upsert_play_join_row(self, cur, rand_num: str) -> None:
		cur.execute(
			"""
			INSERT INTO play_join_table(rand_num, member_name, member_no, topic_name, result_value)
			SELECT
				p.rand_num,
				p.member_name,
				p.member_no,
				p.topic_name,
				r.result_value
			FROM play_request_table p
			LEFT JOIN play_result_table r ON r.rand_num = p.rand_num
			WHERE p.rand_num = %s
			ON DUPLICATE KEY UPDATE
				member_name = VALUES(member_name),
				member_no = VALUES(member_no),
				topic_name = VALUES(topic_name),
				result_value = VALUES(result_value)
			""",
			(rand_num,),
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
					self._upsert_play_join_row(cur, rand_num)
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
					self._upsert_play_join_row(cur, rand_num)
			finally:
				conn.close()

	# play_join_table에서 회원의 result_value를 집계해 포인트를 계산한다.
	# 규칙: result_value가 1 또는 2면 true(1점), 0 또는 NULL이면 false(0점)
	def get_member_points(self, member_no: str) -> int:
		with self._lock:
			conn = self._connect()
			try:
				with conn.cursor() as cur:
					cur.execute(
						"""
						SELECT COALESCE(
							SUM(CASE WHEN result_value IN (1, 2) THEN 1 ELSE 0 END),
							0
						) AS points
						FROM play_join_table
						WHERE member_no = %s OR member_name = %s
						""",
						(member_no, member_no),
					)
					row = cur.fetchone() or {}
					return int(row.get("points") or 0)
			finally:
				conn.close()

# DBService 인스턴스를 생성하여 모듈 전체에서 사용할 수 있도록 한다.
db = DBService()

__all__ = ["db", "DBService"]
