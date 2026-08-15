FROM python:3.14-slim

WORKDIR /app

# Install build deps for compiled Python packages if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure the model exists before starting. If MODEL_URL is provided, download it.
# Otherwise the start script will train one on first boot (slow but free).
RUN chmod +x start.sh

EXPOSE 8000
CMD ["./start.sh"]
