# Dockerfile
FROM python:3.9-slim

# Set working directory
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=America/Chicago

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    tzdata && \
    cp /usr/share/zoneinfo/America/Chicago /etc/localtime && \
    echo "America/Chicago" > /etc/timezone && \
    dpkg-reconfigure -f noninteractive tzdata
RUN apt-get update && \
    apt-get install -y iputils-ping curl net-tools && \
    rm -rf /var/lib/apt/lists/*

RUN apt-get update && \
    apt-get install -y ca-certificates && \
    update-ca-certificates
# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Create static directory if it doesn't exist
RUN mkdir -p /app/static

# Expose port
EXPOSE 8000

# Command to run the application using uvicorn with production settings
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--proxy-headers"]
