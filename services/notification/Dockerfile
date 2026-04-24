FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn aiosqlite pydantic

COPY main.py .

RUN mkdir -p /app/data

EXPOSE 12004

CMD ["python", "main.py"]
