from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import json
import time
from datetime import datetime

# 셀레니움 웹 드라이버 설정
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))

# 시작 URL (첫 페이지 URL)
base_url = "https://www.jobkorea.co.kr/Search/?stext=%EB%8D%B0%EC%9D%B4%ED%84%B0%20%EC%97%94%EC%A7%80%EB%8B%88%EC%96%B4&tabType=recruit&Page_No="

# 오늘 날짜로 JSON 파일 이름 설정
today_date = datetime.now().strftime("%Y%m%d")
file_name = f"{today_date}.json"

# 이미 저장된 JSON 데이터를 불러오기 (중복 방지)
def load_existing_links():
    try:
        with open(file_name, "r", encoding="utf-8") as file:
            existing_data = json.load(file)
            existing_links = {entry["url"] for entry in existing_data}
    except FileNotFoundError:
        existing_data = []
        existing_links = set()
    return existing_data, existing_links

# JSON 파일에 새 데이터를 저장하기
def save_to_json(new_data):
    existing_data, _ = load_existing_links()
    combined_data = existing_data + new_data
    with open(file_name, "w", encoding="utf-8") as file:
        json.dump(combined_data, file, ensure_ascii=False, indent=4)

# 페이지 크롤링 함수
def scrape_links():
    new_data = []  # 새로 크롤링한 데이터 저장
    _, existing_links = load_existing_links()  # 기존 링크 불러오기

    page_number = 1  # 첫 페이지 번호
    while True:
        # 페이지 열기
        url = f"{base_url}{page_number}"
        driver.get(url)
        time.sleep(3)  # 페이지 로딩 대기

        # 검색 결과가 없으면 종료
        try:
            no_results_message = driver.find_element(By.CLASS_NAME, "list-empty-result")
            if "검색결과가 없습니다" in no_results_message.text:
                print(f"No results on page {page_number}. Stopping.")
                break  # 검색결과가 없으면 종료
        except Exception:
            # 검색결과 메시지가 없으면 정상적으로 진행
            print(f"Page {page_number}: Results available. Continuing...")

        # 검색어 가져오기
        try:
            search_value = driver.find_element(By.CSS_SELECTOR, "div.header-search input").get_attribute("value")
        except Exception as e:
            print(f"Could not retrieve search value on page {page_number}: {e}")
            search_value = ""

        # article class="list" 내부의 링크 가져오기
        page_links = []  # 해당 페이지에서 새로 수집한 링크 저장
        try:
            article_list = driver.find_element(By.CLASS_NAME, "list")  # article class="list" 선택
            links = article_list.find_elements(By.TAG_NAME, "a")  # 해당 article 내부의 <a> 태그 찾기

            for link in links:
                href = link.get_attribute("href")
                if href and href.startswith("https://www.jobkorea.co.kr/Recruit") and href not in existing_links:
                    # 'PageGbn=HH'가 포함된 링크는 제외
                    if "PageGbn=HH" not in href:
                        page_links.append(href)  # 새 링크를 리스트에 추가
                        existing_links.add(href)  # 중복 방지
        except Exception as e:
            print(f"Could not retrieve links from page {page_number}: {e}")

        # 해당 페이지의 데이터를 저장
        if page_links:
            new_data.extend([{"search": search_value, "url": link} for link in page_links])

        # 페이지 번호 증가
        page_number += 1

    # 크롤링한 데이터 출력
    print(f"Found {len(new_data)} new links.")

    # JSON 파일에 새 데이터 저장
    if new_data:
        save_to_json(new_data)
        print(f"Saved {len(new_data)} new entries to '{file_name}'.")
    else:
        print("No new links to save.")

# 크롤링 실행
scrape_links()

# 브라우저 종료
driver.quit()
