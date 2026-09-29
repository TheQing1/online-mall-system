# 固定到具体小版本线：node 22（LTS，满足 Vite 8 对 Node >= 22.12 的要求）
# 和 nginx 1.27 mainline-alpine。
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend
# 先只 COPY 依赖清单再 npm ci：源码改动不会让依赖安装层缓存失效。
# 这里不再用 package-lock.json* 通配：npm ci 必须有 lock 文件，缺失时应当直接构建失败。
COPY frontend/package.json frontend/package-lock.json ./
# NPM_REGISTRY 是给国内构建用的：
#   docker compose build --build-arg NPM_REGISTRY=https://registry.npmmirror.com
# 不传就用 npm 默认源，行为与以前一致。
ARG NPM_REGISTRY
RUN if [ -n "$NPM_REGISTRY" ]; then npm ci --registry="$NPM_REGISTRY"; else npm ci; fi
COPY frontend .
RUN npm run build

FROM node:22-alpine AS admin-builder
WORKDIR /app/admin
COPY admin/package.json admin/package-lock.json ./
ARG NPM_REGISTRY
RUN if [ -n "$NPM_REGISTRY" ]; then npm ci --registry="$NPM_REGISTRY"; else npm ci; fi
COPY admin .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=frontend-builder /app/frontend/dist /usr/share/nginx/html
COPY --from=admin-builder /app/admin/dist /usr/share/nginx/html/admin
COPY web/nginx.conf /etc/nginx/conf.d/default.conf

# nginx:alpine 自带 busybox wget，不需要装 curl。
# 探 / 而不是 /health：backend 有自己的 healthcheck，compose 的 depends_on 也已经
# 等到它 healthy 才起 web。这里只关心「nginx 自己在正常提供静态站点」，
# 否则 backend 一抖动 web 也会被标记 unhealthy，反而看不清是谁出了问题。
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1

EXPOSE 80
