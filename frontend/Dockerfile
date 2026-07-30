FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Baked in at build time — Vite env vars aren't available at runtime in a static build,
# so these must be set as build args (see docker-compose.yml), not container env vars.
ARG VITE_API_BASE
ARG VITE_MASTER_API_BASE
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
