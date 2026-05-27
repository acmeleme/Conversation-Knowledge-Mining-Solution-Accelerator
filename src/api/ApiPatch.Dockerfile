# Patch Dockerfile: usa imagem base já compilada, substitui agents, helpers e auth PT-BR/FinanceiraX
FROM ckmcc0522172320.azurecr.io/km-api:app-only-20260524140241
WORKDIR /app
COPY ./agents /app/agents/
COPY ./helpers /app/helpers/
COPY ./auth /app/auth/
COPY ./services /app/services/
COPY ./api /app/api/
COPY ./common /app/common/
COPY ./app.py /app/app.py
