FROM python:3.11-slim

WORKDIR /app

# Install only runtime deps needed by lxml (libxml2/libxslt runtime libs)
# No need for gcc/g++ anymore — lxml ships pre-built wheels on linux/amd64.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libxml2 \
        libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy bot source
COPY . .

# Default command
CMD ["python", "bot.py"]
