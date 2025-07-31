FROM python:3.12-alpine
LABEL authors="github@amlor.at"

WORKDIR /app

COPY ./ /app
RUN ["apk", "add", "bash", "make"]
RUN ["python3", "-m", "venv", "venv"]
RUN ["bash", "-c", "source venv/bin/activate"]
RUN ["pip", "install", "--upgrade", "pip"]
RUN ["pip", "install", "-r", "requirements.txt"]

ENTRYPOINT ["make", "run"]
