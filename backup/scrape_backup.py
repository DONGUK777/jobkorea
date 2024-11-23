import os
import json
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from collections import OrderedDict

# Selenium 웹 드라이버 설정
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))

# 오늘 날짜 기반 파일 이름 (형식: yyyymmdd.json)
today_date = datetime.now().strftime("%Y%m%d")
links_file = f"{today_date}.json"

# JSON 파일 존재 여부 확인 및 읽기
if not os.path.exists(links_file):
    print(f"File {links_file} does not exist.")
    driver.quit()
    exit()

with open(links_file, "r", encoding="utf-8") as file:
    all_links_data = json.load(file)

# 오늘 날짜 기반 디렉토리 생성 (형식: yyyymmdd)
output_dir = today_date
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# 각 링크 처리
for link_data in all_links_data:
    url = link_data["url"]
    search = link_data["search"]
    try:
        # 페이지 열기
        driver.get(url)

        # iframe 전환
        iframe = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#gib_frame"))
        )
        driver.switch_to.frame(iframe)

        # iframe 내부 텍스트 가져오기
        iframe_body = driver.find_element(By.TAG_NAME, "body")
        iframe_text = iframe_body.text.strip()

        # 기본 정보 수집
        position_id = url.split('/')[-1].split('?')[0]
        collection_date = datetime.now().strftime("%Y-%m-%d")

        # 이미지 링크를 가져오기 전에 텍스트가 있는지 확인
        img_links = []  # 기본값을 빈 배열로 설정
        if iframe_text == "":  # 텍스트가 없을 경우에만 이미지 링크 추출
            # iframe 내부 이미지 링크 가져오기 (중복 제거)
            img_elements = iframe_body.find_elements(By.TAG_NAME, "img")
            img_links_set = set()  # 중복 제거를 위한 set 사용
            for img in img_elements:
                src = img.get_attribute("src")
                if src:
                    img_links_set.add(src)  # set에 추가
            img_links = list(img_links_set)  # 중복 제거된 리스트 생성

        # 마감일 정보 수집
        driver.switch_to.default_content()
        deadline = None
        try:
            date_elements = driver.find_elements(By.CSS_SELECTOR, "dl.date .tahoma")
            if len(date_elements) > 1:  # 시작일과 마감일 둘 다 존재하는 경우
                deadline_text = date_elements[1].text.strip()  # 두 번째 <span class="tahoma">
                deadline = deadline_text.replace(".", "-")  # 2024.12.07 -> 2024-12-07
            elif "상시채용" in deadline_text:
                deadline = "상시"
        except Exception as e:
            print(f"Error fetching deadline for URL {url}: {e}")
        
        # deadline이 None일 경우 "상시채용"으로 설정
        if deadline is None:
            deadline = "상시채용"

        # 회사 이름 및 게시물 제목 수집
        company_name = None
        post_title = None
        try:
            summary_section = driver.find_element(By.CLASS_NAME, "secReadSummary")
            company_name = summary_section.find_element(By.CLASS_NAME, "coName").text.strip()
            post_title = summary_section.find_element(By.CLASS_NAME, "sumTit").text.strip()
        except Exception:
            pass  # 회사 이름과 게시물 제목이 없을 경우

        # JSON 데이터 생성 (컬럼 순서 보장)
        job_data = OrderedDict([
            ("s3 url path", None),
            ("site", "jobkorea"),
            ("id", position_id),
            ("collection time", collection_date),
            ("deadline", deadline),
            ("search", search),
            ("company", company_name),
            ("post title", post_title),
            ("url", url),
            ("image", img_links),
            ("text", iframe_text),
        ])

        # 오늘 날짜 디렉토리 안에 개별 파일로 저장
        output_file = os.path.join(output_dir, f"{position_id}.json")
        with open(output_file, "w", encoding="utf-8") as file:
            json.dump(job_data, file, ensure_ascii=False, indent=4)

        print(f"Processed job: {position_id}")

        # 크롤링 간격을 10초로 설정
        time.sleep(3)

    except Exception as e:
        print(f"Error processing URL {url}: {e}")

# 브라우저 종료
driver.quit()
