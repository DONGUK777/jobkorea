import os
import json
import time
from datetime import datetime
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from collections import OrderedDict
from collections import defaultdict

# Selenium 웹 드라이버 설정
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))

# 오늘 날짜 기반 파일 이름 (형식: yyyymmdd.json)
today_date = datetime.now().strftime("%Y%m%d")
links_file = f"{today_date}.json"

# JSON 파일 존재 여부 확인 및 읽기
if not os.path.exists(links_file):
    print(f"ERROR: {links_file} is not defined.")
    driver.quit()
    exit()

with open(links_file, "r", encoding="utf-8") as file:
    all_links_data = json.load(file)

# 오늘 날짜 기반 디렉토리 생성 (형식: yyyymmdd)
output_dir = today_date
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

processed_count = 0  # 처리된 파일 수 카운트
error_count = 0  # 에러 총 수 카운트
error_types = defaultdict(int)  # 에러 종류별 카운트
skipped_urls = []  # 크롤링하지 않은 URL 리스트

# 회사 이름을 추출하는 함수
def extract_company(text):
    match = re.search(r"(.*?)(를 소개해요)", text)
    if match:
        return match.group(1).strip()  # "를 소개해요" 앞의 텍스트
    return ""  # "를 소개해요"가 없으면 빈 문자열

# 각 링크 처리
for link_data in all_links_data:
    url = link_data["url"]
    search = link_data["search"]
    position_id = url.split('/')[-1].split('?')[0]
    
    # 이미 처리된 job 파일이 있는지 확인
    output_file = os.path.join(output_dir, f"{position_id}.json")
    if os.path.exists(output_file):
        print(f"[INFO] {position_id}.json 파일은 이미 존재하므로 크롤링 SKIP")
        skipped_urls.append(url)  # 크롤링을 건너뛴 URL을 저장
        continue

    try:
        # 페이지 열기
        driver.get(url)

        # iframe 전환
        try:
            iframe = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#gib_frame"))
            )
            driver.switch_to.frame(iframe)

            # iframe 내부 텍스트 가져오기
            iframe_body = driver.find_element(By.TAG_NAME, "body")
            iframe_text = iframe_body.text.strip()

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

        except Exception as e:
            # iframe이 없으면 section > article에서 텍스트 추출
            iframe_text = ""
            img_links = []
            content_section = driver.find_element(By.CSS_SELECTOR, "section.section-content")
            article = content_section.find_element(By.CLASS_NAME, "view-content.view-detail")
            iframe_text = article.text.strip()

            # 이미지 링크 추출 (중복 제거)
            img_elements = article.find_elements(By.TAG_NAME, "img")
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
                deadline_match = re.search(r"(\d{4}\.\s*\d{2}\.\s*\d{2})", deadline_text)
                if deadline_match:
                    deadline = deadline_match.group(1).replace(".", "-").replace(" ", "")  # 2024. 12. 07 -> 2024-12-07

        except Exception as e:
            # deadline이 None일 경우 "상시채용"으로 설정
            print(f"ERROR: deadline is not defined. {url}")
            print(f"{e}")
            error_count += 1
            error_types["<deadline is not defined>"] += 1

        # "상시채용"으로 설정 (deadline이 None일 경우)
        if not deadline:
            deadline = "상시채용"

        # 회사 이름 및 게시물 제목 수집
        company_name = None
        try:
            summary_section = driver.find_element(By.CLASS_NAME, "secReadSummary")
            company_name = summary_section.find_element(By.CLASS_NAME, "coName").text.strip()
            if not company_name:
                summary_section = driver.find_element(By.CLASS_NAME, "iew-subtitle dev-wrap-subtitle")
        except Exception as e:
            # 회사 이름을 "를 소개해요" 이전 텍스트로 추출
            company_name = extract_company(iframe_text) if company_name == None else company_name

        post_title = None
        try:
            summary_section = driver.find_element(By.CLASS_NAME, "secReadSummary")
            post_title = summary_section.find_element(By.CLASS_NAME, "sumTit").text.strip()
        except Exception as e:
            try:
                # 두 번째 시도: section class="view-title dev-wrap-title"에서 제목 추출
                title_section = driver.find_element(By.CSS_SELECTOR, "section.view-title.dev-wrap-title")
                post_title = title_section.text.strip()
            except Exception as e2:
                print(f"ERROR: post title is not defined. {url}")
                error_count += 1
                error_types["post_title_not_found"] += 1  # 게시물 제목을 찾을 수 없을 경우 에러 추가
                post_title = "N/A"  # 게시물 제목을 찾을 수 없으면 'N/A'로 설정

        

        # JSON 데이터 생성 (컬럼 순서 보장)
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

        # 오늘 날짜 디렉토리 안에 개별 파일로 저장
        with open(output_file, "w", encoding="utf-8") as file:
            json.dump(job_data, file, ensure_ascii=False, indent=4)

        print(f"[INFO] {output_dir}/{position_id}.json 저장 완료")
        processed_count += 1

        # 크롤링 간격을 x초로 설정
        # time.sleep(3)

    except Exception as e:
        print(f"ERROR: {url} is not defined.")
        print(f"{e}")
        error_count += 1
        error_types["General"] += 1

# 브라우저 종료
driver.quit()

# 처리된 파일 수 출력
print(f"[INFO] 크롤링 중 발생한 총 에러 수: {error_count}")
print(f"[INFO] 에러 종류별 개수:")
for error_type, count in error_types.items():
    print(f"  {error_type}: {count}")
print(f"[INFO] 전체 URL 수: {len(all_links_data)}")
print(f"[INFO] 크롤링한 총 채용공고 수: {processed_count}개")
