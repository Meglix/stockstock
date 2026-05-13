# Base image: slim Python matching the project version
FROM python:3.13-slim

# Set working directory inside the container
WORKDIR /app

# Install dependencies first so rebuilds are faster when only code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Copy scripts so init_db.py and seed_data.py can be run inside the container
COPY scripts/ ./scripts/

# Copy database schema, needed by init_db.py
COPY database/schema.sql ./database/schema.sql

# Port the API listens on
EXPOSE 8000

# Start the API server. Override UVICORN_HOST/PORT when exposing the container.
ENV UVICORN_HOST=localhost
ENV PORT=8000
CMD ["sh", "-c", "uvicorn app.main:app --host ${UVICORN_HOST} --port ${PORT}"]
