import os
import json
import pymysql
from datetime import datetime

# AWS MySQL 연결 설정
db = pymysql.connect(
    host='3.36.11.84',          # AWS 퍼블릭 IP
    user='user',                # MySQL 사용자
    password='1234',            # MySQL 비밀번호
    database='testdb',          # 데이터베이스 이름
    charset='utf8mb4'
)

cursor = db.cursor()

# JSON 파일 경로
# 오늘 날짜 기반으로 디렉토리 경로 설정 (예: 20241123)
today_date = datetime.today().strftime("%Y%m%d")
json_directory = os.path.expanduser(f"~/code/crawling/jobkorea/{today_date}")  # 동적으로 오늘 날짜 디렉토리


# 디렉토리 내 모든 JSON 파일 처리
for file_name in os.listdir(json_directory):
    if file_name.endswith(".json"):
        file_path = os.path.join(json_directory, file_name)
        
        with open(file_path, "r", encoding="utf-8") as json_file:
            data = json.load(json_file)

            # 데이터베이스에 삽입 쿼리
            insert_query = """
            INSERT INTO jobkorea (s3_url, site, id, collectiondate, deadline, search, company, post_title, url, image, text)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                collectiondate = VALUES(collectiondate),
                deadline = VALUES(deadline),
                search = VALUES(search),
                company = VALUES(company),
                post_title = VALUES(post_title),
                url = VALUES(url),
                image = VALUES(image),
                text = VALUES(text);
            """
            try:
                # 데이터 변환 및 삽입
                s3_url = data.get("s3 url path") if data.get("s3 url path") else None  # NULL 처리
                cursor.execute(insert_query, (
                    s3_url,
                    data.get("site"),
                    data.get("id"),
                    datetime.strptime(data.get("collection_date"), "%Y-%m-%d").date() if data.get("collection_date") else None,
                    data.get("deadline"),
                    data.get("search"),
                    data.get("company"),
                    data.get("post title"),
                    data.get("url"),
                    ", ".join(data.get("image", [])),  # 리스트 데이터를 문자열로 변환
                    data.get("text")
                ))
                db.commit()
                print(f"Inserted/Updated: {file_name}")
            except Exception as e:
                print(f"Error processing {file_name}: {e}")
                db.rollback()

# MySQL 연결 종료
cursor.close()
db.close()
