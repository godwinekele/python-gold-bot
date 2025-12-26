FROM python:3.11-slim

WORKDIR /app

# Install system dependencies required by MetaTrader5
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir \
    MetaTrader5 \
    pandas

# Copy application code
COPY . .

# Run the bot
CMD ["python", "XAUUSDm-break-even.py"]
