FROM node:20-slim AS build

WORKDIR /app

# VITE_WS_URL: Optional WebSocket backend URL override for Cloud Run deployments
# where the frontend and backend are on different Cloud Run services.
# If not provided, the frontend auto-connects to the same host via nginx proxy
# (suitable for docker-compose local setups).
# Example: --build-arg VITE_WS_URL=wss://tejas-backend-abc123-uc.a.run.app/ws/stream
ARG VITE_WS_URL=""
ENV VITE_WS_URL=${VITE_WS_URL}

# Install dependencies
COPY package.json package-lock.json* ./
RUN npm ci

# Copy source and build
COPY . .
RUN npm run build

# Serve with a lightweight static server
FROM nginx:alpine

# Copy nginx config as a template — BACKEND_URL is substituted at container
# startup via envsubst so the image works across different Cloud Run deployments
# without a rebuild.
COPY nginx.conf /etc/nginx/templates/default.conf.template

# Copy built assets
COPY --from=build /app/dist /usr/share/nginx/html

# Default backend URL for local docker-compose (service name "backend" resolves
# within the compose network). Override in Cloud Run with the backend service URL:
#   gcloud run deploy tejas-frontend --set-env-vars=BACKEND_URL=https://tejas-backend-...
ENV BACKEND_URL=http://backend:8080

EXPOSE 80

# envsubst substitutes only $BACKEND_URL, leaving nginx variables like
# $uri, $host, $http_upgrade, etc. untouched (single-quoted list).
CMD ["/bin/sh", "-c", \
  "envsubst '$BACKEND_URL' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]
