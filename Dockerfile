# toryOrderBackend/Dockerfile

# 1. 파이썬 3.10 버전 사용
FROM python:3.10-slim

# 2. 작업 폴더 설정
WORKDIR /app

# 3. 필요한 파일 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. 소스 코드 복사
COPY . .

# 5. 실행 명령어 (포트 8000번)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]