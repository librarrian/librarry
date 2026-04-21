FROM python:3.12-alpine3.20

WORKDIR /app

RUN apk add --no-cache git curl
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py .
COPY __init__.py .
COPY utils ./utils

ENV PYTHONUNBUFFERED=1 \
  FLASK_ENV=production

# Expose the port
EXPOSE 8080

CMD [ "gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--timeout", "120", "app:app" ]
