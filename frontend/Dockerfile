# B-roll Engine frontend image.
# Builds the Vite static bundle and serves it with nginx.
# nginx also reverse-proxies /api to the backend api service, so the browser
# only needs to reach one origin.

# ---- stage 1: build ----
FROM node:20-slim AS build

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --quiet
COPY . .
RUN npm run build

# ---- stage 2: serve ----
FROM nginx:stable-alpine AS runtime

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
