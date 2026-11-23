# Etapa 1: construcción de la SPA
FROM node:24-alpine AS construccion
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

# Etapa 2: nginx
FROM nginx:1.30-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=construccion /app/dist /usr/share/nginx/html
EXPOSE 80
