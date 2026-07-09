# ── Stage 1: build ────────────────────────────────────────────────────────────
FROM node:22-alpine AS build

WORKDIR /app

# Install deps (cached unless package-lock changes)
COPY package.json package-lock.json ./
RUN npm ci

# Copy source and build
COPY . .
# VITE_API_BASE_URL is baked into the bundle at build time.
# In Compose we pass it as a build-arg so the bundle points to the right host.
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

# ── Stage 2: serve ────────────────────────────────────────────────────────────
FROM nginx:1.27-alpine AS serve

# Copy built assets
COPY --from=build /app/dist /usr/share/nginx/html

# SPA routing config (handles /player/:id, /compare, /chat without 404)
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
