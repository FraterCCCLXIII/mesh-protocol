FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn aiosqlite pydantic

COPY main.py .

RUN mkdir -p /app/data

EXPOSE 12006

CMD ["python", "main.py"]
