# Build stage
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci
COPY . .
# VITE_API_URL is embedded at build time by Vite (browser-side env var).
# Pass it as a build argument: docker build --build-arg VITE_API_URL=https://your-api
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL
ARG VITE_ACCOUNT_SERVICE_URL=http://localhost:8001
ENV VITE_ACCOUNT_SERVICE_URL=$VITE_ACCOUNT_SERVICE_URL
ARG VITE_PAYMENTS_SERVICE_URL=http://localhost:8002
ENV VITE_PAYMENTS_SERVICE_URL=$VITE_PAYMENTS_SERVICE_URL
ARG VITE_TRANSACTIONS_SERVICE_URL=http://localhost:8003
ENV VITE_TRANSACTIONS_SERVICE_URL=$VITE_TRANSACTIONS_SERVICE_URL
RUN npm run build

# Production stage
FROM nginx:alpine AS production
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
