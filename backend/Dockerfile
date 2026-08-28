FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
ENV DB_PATH=/app/data/scans.db
ENV OPENRAG_MODEL_PATH=/app/models
ENV DEEPSEEK_HARNESS_PLUGINS=database,web

RUN mkdir -p /app/data /app/models

EXPOSE 5001

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5001", "--reload"]
