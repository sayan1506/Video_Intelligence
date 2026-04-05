FROM python:3.11-slim

# Install ffmpeg — required by the STT pipeline for MP4 → FLAC audio extraction.
# ffmpeg is not included in python:3.11-slim.
# --no-install-recommends keeps the image lean.
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first — better Docker layer caching.
# Only rebuilds this layer when requirements.txt changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Worker is a long-lived Pub/Sub subscriber — not an HTTP server.
# No PORT env var, no EXPOSE, no uvicorn.
CMD ["python", "main.py"]