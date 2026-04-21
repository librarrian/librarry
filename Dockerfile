# FROM python:3.12-alpine3.20

FROM sandreas/ffmpeg:5.0.1-3 as ffmpeg
FROM sandreas/tone:v0.2.4 as tone
FROM sandreas/mp4v2:2.1.1 as mp4v2
FROM sandreas/fdkaac:2.0.1 as fdkaac
FROM alpine:3.20.3 as alpine_stage

WORKDIR /app

# RUN apk add --no-cache git curl

RUN echo "---- INSTALL RUNTIME PACKAGES ----" && \
  apk add --no-cache --update --upgrade \
  libstdc++ \
  php83-cli \
  php83-curl \
  php83-dom \
  php83-xml \
  php83-mbstring \
  php83-openssl \
  php83-phar \
  php83-simplexml \
  php83-tokenizer \
  php83-xmlwriter \
  php83-zip \
  bash \
  python3 \
  py3-pip \
  git \
  curl \
  && echo "date.timezone = UTC" >> /etc/php83/php.ini \
  && ln -s /usr/bin/php83 /bin/php

# Setup python venv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py .
COPY __init__.py .
COPY utils ./utils

# Copy binaries
COPY --from=ffmpeg /usr/local/bin/ffmpeg /usr/local/bin/
COPY --from=tone /usr/local/bin/tone /usr/local/bin/
COPY --from=mp4v2 /usr/local/bin/mp4* /usr/local/bin/
COPY --from=mp4v2 /usr/local/lib/libmp4v2* /usr/local/lib/
COPY --from=fdkaac /usr/local/bin/fdkaac /usr/local/bin/

ENV PYTHONUNBUFFERED=1 \
  FLASK_ENV=production

# Expose the port
EXPOSE 8080

CMD [ "gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "4", "--timeout", "120", "app:app" ]