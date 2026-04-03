FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8080

# Worker doesn't serve HTTP — it runs as a long-lived Pub/Sub subscriber
CMD ["python", "main.py"]