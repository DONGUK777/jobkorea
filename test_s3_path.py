import os
import json

# 로컬 JSON 파일이 있는 디렉토리 경로
json_directory = os.path.expanduser("~/code/crawling/jobkorea/20241122")  # 디렉토리 경로 설정

# s3_url을 임의로 생성하는 함수 (예시로 파일명 기반으로 URL 생성)
def generate_s3_url(file_name):
    return f"test/{file_name}"

# 디렉토리 내 모든 JSON 파일 처리
for file_name in os.listdir(json_directory):
    if file_name.endswith(".json"):
        file_path = os.path.join(json_directory, file_name)
        
        # JSON 파일 읽기
        with open(file_path, "r", encoding="utf-8") as json_file:
            data = json.load(json_file)
        
        # s3_url path 임의 추가 (예시로 파일명 기반 URL 사용)
        s3_url = generate_s3_url(file_name)
        
        # s3_url을 JSON 데이터에 추가
        data["s3 url path"] = s3_url

        # 변경된 데이터를 다시 파일에 저장
        with open(file_path, "w", encoding="utf-8") as json_file:
            json.dump(data, json_file, ensure_ascii=False, indent=4)
        
        print(f"Added 's3 url path' to {file_name}")
