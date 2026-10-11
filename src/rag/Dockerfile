# LIKELY NEEDS UPDATES

# Use a lightweight base
FROM python:3.13-slim

# Set work directory inside container
WORKDIR /rag

# Install curl (needed for Docker healthcheck)
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better caching)
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose FastAPI port
EXPOSE 9000

# Run FastAPI app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9000", "--reload"]
