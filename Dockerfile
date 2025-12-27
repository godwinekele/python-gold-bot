FROM ubuntu:22.04

# Prevent interactive prompts during installation
ENV DEBIAN_FRONTEND=noninteractive
ENV DISPLAY=:0

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    software-properties-common \
    gnupg2 \
    xvfb \
    x11vnc \
    wine64 \
    winetricks \
    python3.10 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Set up Wine prefix
ENV WINEPREFIX=/root/.wine
ENV WINEARCH=win64

# Initialize Wine
RUN wine wineboot --init && \
    winetricks -q vcrun2015 corefonts && \
    wineserver -w

# Install Python packages
RUN pip3 install --no-cache-dir \
    MetaTrader5==5.0.45 \
    pandas==2.0.3 \
    flask==3.0.0 \
    python-dotenv==1.0.0

# Create app directory
WORKDIR /app

# Copy application files
COPY bot.py /app/
COPY web_ui.py /app/
COPY templates/ /app/templates/
COPY .env /app/

# Expose port for web UI
EXPOSE 4000

# Create startup script
RUN echo '#!/bin/bash\n\
Xvfb :0 -screen 0 1024x768x24 &\n\
sleep 2\n\
python3 web_ui.py &\n\
python3 bot.py\n\
' > /app/start.sh && chmod +x /app/start.sh

CMD ["/app/start.sh"]
