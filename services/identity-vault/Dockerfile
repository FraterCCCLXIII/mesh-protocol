FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn aiosqlite argon2-cffi pydantic[email] httpx

COPY main.py .
COPY client.py .

RUN mkdir -p /app/data

EXPOSE 12003

CMD ["python", "main.py"]
