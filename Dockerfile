FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for better performance
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ .

# Create data directory
RUN mkdir -p /app/data /app/models

# Expose port
EXPOSE 5001

# Run the application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5001"]
