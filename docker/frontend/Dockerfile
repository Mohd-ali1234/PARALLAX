# syntax=docker/dockerfile:1.7
# ---------------------------------------------------------------------------
# PARALLAX web client. `dev` runs the Vite dev server with HMR; `runtime`
# serves the static build from nginx and proxies /api to the FastAPI service.
# ---------------------------------------------------------------------------

FROM node:22-alpine AS deps

WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci


# ---------------------------------------------------------------------------
FROM deps AS dev

ENV NODE_ENV=development
COPY frontend/ ./
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]


# ---------------------------------------------------------------------------
FROM deps AS build

COPY frontend/ ./
# Baked in at build time - Vite inlines VITE_* into the bundle. Empty means
# same-origin, which is what the nginx proxy below provides.
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build


# ---------------------------------------------------------------------------
FROM nginx:1.27-alpine AS runtime

COPY docker/frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost/ >/dev/null || exit 1

CMD ["nginx", "-g", "daemon off;"]
