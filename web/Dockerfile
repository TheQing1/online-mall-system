FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend .
RUN npm run build

FROM node:20-alpine AS admin-builder
WORKDIR /app/admin
COPY admin/package.json admin/package-lock.json* ./
RUN npm install
COPY admin .
RUN npm run build

FROM nginx:alpine
COPY --from=frontend-builder /app/frontend/dist /usr/share/nginx/html
COPY --from=admin-builder /app/admin/dist /usr/share/nginx/html/admin
COPY web/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
