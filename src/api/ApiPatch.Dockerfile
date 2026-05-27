# Patch Dockerfile: usa imagem base já compilada, só substitui os agents PT-BR
FROM ckmcc0522172320.azurecr.io/km-api:app-only-20260524140241
WORKDIR /app
COPY ./agents /app/agents/
