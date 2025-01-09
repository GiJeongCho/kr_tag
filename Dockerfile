# Base image
FROM python:3.11-slim

# 작업 디렉토리 설정
WORKDIR /app

# 소스 코드 복사
COPY ./src /app/src
COPY ./pyproject.toml /app/pyproject.toml
COPY ./poetry.lock /app/poetry.lock

# Poetry 설치
RUN pip install poetry 
RUN pip install poetry 
# petry에서 가상환경 만드는 옵션을 꺼야 설치가 제대로 됨.
RUN pip install poetry
# petry에서 가상환경 만드는 옵션을 꺼야 설치가 제대로 됨.
RUN poetry config virtualenvs.create false
RUN poetry install --no-root

# 추가 패키지 설치
RUN pip install uvicorn fastapi

# 환경 변수 설정
ENV PYTHONPATH=/app/src
ENV RESOURCE_DIR=/app/src/v1

# 포트 노출
EXPOSE 80

# 헬스체크 설정
HEALTHCHECK --start-period=60s CMD curl -f http://localhost/v1/kr-tag/docs || exit 1


# 애플리케이션 실행
ENTRYPOINT ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "80", "--reload"]
