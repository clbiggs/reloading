FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY src/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ .

# Ensure application files are readable and directories are traversable
# when the container runs as a non-root user (for example uid 1001 in Kubernetes).
# Also make the default SQLite data directory writable for arbitrary non-root UIDs.
RUN chmod -R a=rX /app && mkdir -p /data && chmod 0777 /data

# Expose port
EXPOSE 5000

# Set environment variables
ENV DATABASE_PATH=/data/reloading.db
ENV PYTHONUNBUFFERED=1

# Run with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "app:create_app()"]

