#!/bin/sh
set -e

echo "==> 等待 MySQL 就绪..."
until mysqladmin ping -h"$MYSQL_HOST" -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" --silent >/dev/null 2>&1; do
  sleep 2
done

echo "==> 执行数据库迁移..."
alembic -c /app/alembic.ini upgrade head

echo "==> 初始化种子数据（幂等，可重复执行）..."
python -m app.core.seed

echo "==> 启动 API 服务..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
