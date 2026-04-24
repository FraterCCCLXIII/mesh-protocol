FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn aiosqlite pydantic stripe

COPY main.py .

RUN mkdir -p /app/data

EXPOSE 12007

CMD ["python", "main.py"]
