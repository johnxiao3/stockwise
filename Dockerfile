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
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
    echo $TZ > /etc/timezone && \
    rm -rf /var/lib/apt/lists/*


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
