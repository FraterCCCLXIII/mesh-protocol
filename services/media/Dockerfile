FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn aiosqlite pydantic pillow

COPY main.py .

RUN mkdir -p /app/data/storage/original /app/data/storage/thumb

EXPOSE 12005

CMD ["python", "main.py"]
