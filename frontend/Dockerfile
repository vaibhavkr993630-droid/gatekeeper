FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
# a *.template file: the nginx image runs envsubst over it at startup, replacing
# only PORT + BACKEND_UPSTREAM (NGINX_ENVSUBST_FILTER) so nginx's own
# $host / $http_upgrade / etc. are left alone. PORT is the PaaS convention
# (Railway injects it); defaults to 80 locally.
COPY nginx.conf /etc/nginx/templates/default.conf.template
ENV PORT=80
ENV BACKEND_UPSTREAM=backend:8000
ENV NGINX_ENVSUBST_FILTER=^(PORT|BACKEND_UPSTREAM)$

EXPOSE 80

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
  CMD wget -qO- "http://127.0.0.1:${PORT}/" >/dev/null || exit 1
