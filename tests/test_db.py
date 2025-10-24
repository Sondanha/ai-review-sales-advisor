# test_db.py
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()  # .env 파일 로드

url = os.getenv("DATABASE_URL")
if not url:
    raise RuntimeError("DATABASE_URL not found")

engine = create_engine(url)
with engine.begin() as conn:
    result = conn.execute(text("select 1")).scalar()
    print("DB 연결 성공:", result == 1)
