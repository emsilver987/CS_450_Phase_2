# Use official Python runtime as base image
FROM python:3.12-slim

# Set working directory in container
WORKDIR /app

# Install system dependencies if needed
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire application
COPY . .

# Expose the port your app runs on
EXPOSE 3000

# Set environment variables
ENV PORT=3000
ENV PYTHONUNBUFFERED=1

# AWS Configuration (can be overridden at runtime)
ENV AWS_REGION=us-east-1
ENV AWS_ACCOUNT_ID=838693051036
ENV S3_ACCESS_POINT_NAME=cs450-s3

# Command to run the application (wrapped entrypoint to attach JWT middleware)
CMD ["uvicorn", "src.entrypoint:app", "--host", "0.0.0.0", "--port", "3000"]