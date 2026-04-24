FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn aiosqlite pydantic httpx pynacl

COPY main.py .
COPY discovery.py .

RUN mkdir -p /app/data

EXPOSE 12000

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "12000"]
