# Eleanor Backend Dockerfile

FROM python:3.14-slim

WORKDIR /app

# Install system dependencies including build tools for python-ldap
RUN apt-get update && apt-get install -y \
    libmagic1 \
    libldap2-dev \
    libsasl2-dev \
    gcc \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir -e .

# Copy application code
COPY . .

# Create evidence directory
RUN mkdir -p /app/evidence

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
