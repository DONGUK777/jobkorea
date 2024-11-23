import os
import json
import time
from datetime import datetime
import re
import pymysql
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from collections import OrderedDict
from collections import defaultdict

# AWS MySQL 연결 설정
db = pymysql.connect(
    host='3.36.11.84',          # AWS 퍼블릭 IP
    user='user',                # MySQL 사용자
    password='1234',            # MySQL 비밀번호
    database='testdb',          # 데이터베이스 이름
    charset='utf8mb4'
)
cursor = db.cursor()

# Selenium 웹 드라이버 설정
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))

# 오늘 날짜 기반 파일 이름 및 디렉토리 설정 (형식: yyyymmdd)
today_date = datetime.now().strftime("%Y%m%d")
links_file = f"{today_date}.json"
output_dir = today_date

# JSON 파일 존재 여부 확인
if not os.path.exists(links_file):
    print(f"ERROR: {links_file} is not defined.")
    driver.quit()
    exit()

# JSON 파일 읽기
with open(links_file, "r", encoding="utf-8") as file:
    all_links_data = json.load(file)

# 크롤링 작업을 위한 준비
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

processed_count = 0
error_count = 0
error_types = defaultdict(int)
skipped_urls = []

# 회사 이름을 추출하는 함수
def extract_company(text):
    match = re.search(r"(.*?)(를 소개해요)", text)
    if match:
        return match.group(1).strip()
    return ""

# 크롤링 작업
for link_data in all_links_data:
    url = link_data["url"]
    search = link_data["search"]
    position_id = url.split('/')[-1].split('?')[0]
    output_file = os.path.join(output_dir, f"{position_id}.json")

    if os.path.exists(output_file):
        print(f"[INFO] {position_id}.json 파일은 이미 존재하므로 크롤링 SKIP")
        skipped_urls.append(url)
        continue

    try:
        driver.get(url)

        try:
            iframe = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#gib_frame"))
            )
            driver.switch_to.frame(iframe)
            iframe_body = driver.find_element(By.TAG_NAME, "body")
            iframe_text = iframe_body.text.strip()

            img_links = []
            if iframe_text == "":
                img_elements = iframe_body.find_elements(By.TAG_NAME, "img")
                img_links = list({img.get_attribute("src") for img in img_elements if img.get_attribute("src")})
        except Exception:
            iframe_text = ""
            img_links = []
            content_section = driver.find_element(By.CSS_SELECTOR, "section.section-content")
            article = content_section.find_element(By.CLASS_NAME, "view-content.view-detail")
            iframe_text = article.text.strip()
            img_elements = article.find_elements(By.TAG_NAME, "img")
            img_links = list({img.get_attribute("src") for img in img_elements if img.get_attribute("src")})

        driver.switch_to.default_content()
        deadline = None
        try:
            date_elements = driver.find_elements(By.CSS_SELECTOR, "dl.date .tahoma")
            if len(date_elements) > 1:
                deadline_text = date_elements[1].text.strip()
                deadline = re.search(r"(\d{4}\.\s*\d{2}\.\s*\d{2})", deadline_text).group(1).replace(".", "-").replace(" ", "")
        except Exception:
            print(f"ERROR: deadline is not defined. {url}")
            error_count += 1
            error_types["<deadline is not defined>"] += 1

        if not deadline:
            deadline = "상시채용"

        try:
            summary_section = driver.find_element(By.CLASS_NAME, "secReadSummary")
            company_name = summary_section.find_element(By.CLASS_NAME, "coName").text.strip()
        except Exception:
            company_name = extract_company(iframe_text)

        try:
            summary_section = driver.find_element(By.CLASS_NAME, "secReadSummary")
            post_title = summary_section.find_element(By.CLASS_NAME, "sumTit").text.strip()
        except Exception:
            post_title = "N/A"

        job_data = OrderedDict([
            ("s3 url path", None),
            ("site", "jobkorea"),
            ("id", position_id),
            ("collection_date", datetime.now().strftime("%Y-%m-%d")),
            ("deadline", deadline),
            ("search", search),
            ("company", company_name),
            ("post title", post_title),
            ("url", url),
            ("image", img_links),
            ("text", iframe_text),
        ])

        with open(output_file, "w", encoding="utf-8") as file:
            json.dump(job_data, file, ensure_ascii=False, indent=4)

        print(f"[INFO] {output_dir}/{position_id}.json 저장 완료")
        processed_count += 1

    except Exception as e:
        print(f"ERROR: {url} is not defined.")
        print(f"{e}")
        error_count += 1
        error_types["General"] += 1

driver.quit()

# JSON 데이터를 MySQL 데이터베이스에 삽입
for file_name in os.listdir(output_dir):
    if file_name.endswith(".json"):
        file_path = os.path.join(output_dir, file_name)
        with open(file_path, "r", encoding="utf-8") as json_file:
            data = json.load(json_file)

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
                s3_url = data.get("s3 url path")
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
                    ", ".join(data.get("image", [])),
                    data.get("text")
                ))
                db.commit()
                print(f"Inserted/Updated: {file_name}")
            except Exception as e:
                print(f"Error processing {file_name}: {e}")
                db.rollback()

cursor.close()
db.close()

print(f"[INFO] 크롤링 완료: 총 {processed_count}건 처리됨.")
print(f"[INFO] 총 에러 수: {error_count}")
