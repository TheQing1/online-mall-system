#!/bin/sh
set -e

echo "==> 等待 MySQL 就绪..."
# 原来是无上限的 until 循环：MySQL 一直起不来容器就会永久挂住（既不退出也不报错）。
# 现在限制为最多 120 秒（60 次 × 2 秒），超时后明确报错并以非 0 退出，
# 交给 restart: unless-stopped 重新走一轮，日志里也能看出是数据库没起来。
# 密码通过 MYSQL_PWD 传递而不是命令行 -p"$MYSQL_PASSWORD"：
# 后者会出现在容器的 ps/argv 里，任何能执行 ps 的进程都能读到。
MYSQL_PWD="$MYSQL_PASSWORD"
export MYSQL_PWD

waited=0
max_wait=120
until mysqladmin ping -h"$MYSQL_HOST" -u"$MYSQL_USER" --silent >/dev/null 2>&1; do
  waited=$((waited + 2))
  if [ "$waited" -ge "$max_wait" ]; then
    echo "==> 错误：MySQL 在 ${max_wait} 秒内仍未就绪（host=${MYSQL_HOST} user=${MYSQL_USER}），放弃启动。" >&2
    exit 1
  fi
  sleep 2
done

# 后续步骤（alembic / seed / uvicorn）都不需要 MYSQL_PWD，清掉避免密码继续留在进程环境里。
unset MYSQL_PWD

echo "==> 执行数据库迁移..."
alembic -c /app/alembic.ini upgrade head

echo "==> 初始化种子数据（幂等，可重复执行）..."
python -m app.core.seed

# --proxy-headers + --forwarded-allow-ips：nginx 已经会带上 X-Forwarded-For/Proto，
# 不打开这两个开关 uvicorn 会把请求来源记成 nginx 容器的 IP。
# 用 '*' 信任任意来源，仅在 backend 不直接对外暴露时才安全（见报告：当前 compose 把
# 8000 直接映射到了宿主机，所以这层信任是打了折扣的）；最稳妥的生产做法是收紧成
# nginx 所在网段，例如 --forwarded-allow-ips='172.16.0.0/12'。
# 单 worker：app/core/tasks.py 的订单超时自动关单任务挂在 FastAPI lifespan 上，
# 每个 worker 进程都会各起一份，多 worker 会让同一批超时订单被并发重复处理。
echo "==> 启动 API 服务..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 \
  --proxy-headers --forwarded-allow-ips='*'
