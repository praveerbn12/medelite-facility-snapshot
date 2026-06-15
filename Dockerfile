# Match your local Python so dev and prod behave the same
FROM python:3.14-slim

# System libraries WeasyPrint needs to render PDFs on Linux
# (the Linux equivalent of `brew install pango` on your Mac)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libharfbuzz0b \
        libharfbuzz-subset0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first so Docker caches this layer between rebuilds
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Now copy the app code
COPY . .

# Render assigns a port via $PORT; default to 8000 for local runs.
# --host 0.0.0.0 is required so the app is reachable from outside the container.
ENV PORT=8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]