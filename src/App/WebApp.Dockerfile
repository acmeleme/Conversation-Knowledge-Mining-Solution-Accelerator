FROM node:20-alpine AS build
WORKDIR /home/node/app
COPY ./package*.json ./

RUN npm ci --omit=dev

COPY . .

ARG REACT_APP_VERSION=dev
ENV REACT_APP_VERSION=$REACT_APP_VERSION

ARG FRONTEND_IMAGE_TAG=dev

RUN npm run build

FROM nginx:alpine
COPY --from=build /home/node/app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY env.sh /docker-entrypoint.d/env.sh
RUN chmod +x /docker-entrypoint.d/env.sh
RUN sed -i 's/\r$//' /docker-entrypoint.d/env.sh
EXPOSE 80
CMD ["/bin/sh", "-c", "/docker-entrypoint.d/env.sh && nginx -g 'daemon off;'"]