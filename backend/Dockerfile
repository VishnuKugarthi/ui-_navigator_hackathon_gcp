# Use the official Microsoft Playwright image which includes all browser dependencies
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Add essential utilities
RUN apt-get update && apt-get install -y wget gnupg jq

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared interfaces folder
COPY shared-core/ ./shared-core/

# Copy the backend files (FastAPI + ENV)
COPY main.py .
COPY .ENV .

# Cloud Run expects the app to bind to 0.0.0.0 and varying PORTs
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:=8080}
