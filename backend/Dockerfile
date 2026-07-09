# syntax=docker/dockerfile:1
FROM python:3.12-slim

# System deps (scipy needs libgfortran, pyreadr needs libstdc++)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        libgfortran5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend

# Install Python dependencies first (cached unless requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source and the dataset
COPY . .

# Expose and run
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
