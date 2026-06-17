FROM python:3.11-slim

ARG APP_VERSION=dev
ENV APP_VERSION=$APP_VERSION

ARG BACKEND_IMAGE_TAG=dev
ENV BACKEND_IMAGE_TAG=$BACKEND_IMAGE_TAG

# Install system dependencies and Microsoft ODBC Driver 18 for SQL Server.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        gnupg \
        ca-certificates \
        unixodbc \
        unixodbc-dev \
        libpq-dev \
        libffi-dev \
        libssl-dev \
        libopus-dev \
        libvpx-dev \
    && curl -sSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/microsoft-prod.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY ./requirements.txt .

RUN pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt && rm -rf /root/.cache

COPY ./ .

EXPOSE 80

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "80"]