#!/usr/bin/env bash
# 把演示站的数据恢复到「刚部署完」的状态。
#
# 为什么需要它：公开的 demo 站点上，任何人都能注册账号、下单、传图、改后台。
# 演示前发现首页躺着几笔乱七八糟的订单是很正常的，与其手动删，不如一键重来。
#
#   sudo bash deploy/reset-demo.sh          # 问一句再动手
#   sudo bash deploy/reset-demo.sh -y       # 不问，直接重置
#
# 做法是**只删 MySQL 的数据卷**再重新迁移 + 播种，而不是清空所有卷：
# mall-data 卷里存着 100MB 的 Embedding 模型，删掉的话下次启动要重新下载。
#
# 注意：商品图上传目录（backend/static/products）是宿主机上的 bind mount，
# 不在卷里，所以这里不会清掉它。上传的垃圾图要手动删——故意不做自动清理，
# 因为种子商品的图片也在同一个目录里，脚本没法可靠区分哪些是「垃圾」。
#
# 脚本里的几个小函数刻意没有抽成公共库：运维脚本单独拷到服务器上也要能跑。

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

ASSUME_YES=0
for arg in "$@"; do
  case "$arg" in
    -y | --yes) ASSUME_YES=1 ;;
    -h | --help) sed -n '2,16p' "$0"; exit 0 ;;
    *) echo "未知参数：$arg" >&2; exit 2 ;;
  esac
done

log() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }

if [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1; then
  exec sudo -E bash "$0" "$@"
fi

[ -f .env ] || {
  echo "找不到 .env，先跑 deploy/bootstrap.sh" >&2
  exit 1
}

env_value() {
  sed -n "s/^[[:space:]]*$1[[:space:]]*=[[:space:]]*//p" .env \
    | tail -n 1 \
    | sed -e 's/[[:space:]]*$//' -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'$/\1/"
}

# 用 .env 里是否填了 DOMAIN 判断当前是不是 TLS 模式，和 bootstrap.sh 保持同一套判断
COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)
if [ -n "$(env_value DOMAIN)" ]; then
  COMPOSE+=(-f docker-compose.tls.yml)
fi

echo "将删除 MySQL 数据卷并重新播种初始数据。"
echo "（演示账号 demo/demo123、admin/admin123 会被恢复成初始密码）"
if [ "$ASSUME_YES" -ne 1 ]; then
  printf '继续？输入 yes: '
  read -r answer || answer=""
  [ "$answer" = "yes" ] || {
    echo "已取消。"
    exit 0
  }
fi

log "停止会写库的服务"
"${COMPOSE[@]}" stop backend worker web >/dev/null

log "定位 MySQL 数据卷"
mysql_cid="$("${COMPOSE[@]}" ps -aq mysql | head -n 1)"
[ -n "$mysql_cid" ] || {
  echo "找不到 mysql 容器，先跑 deploy/bootstrap.sh" >&2
  exit 1
}
volume="$(
  docker inspect --format \
    '{{range .Mounts}}{{if eq .Destination "/var/lib/mysql"}}{{.Name}}{{end}}{{end}}' \
    "$mysql_cid"
)"
[ -n "$volume" ] || {
  echo "没找到挂到 /var/lib/mysql 的卷" >&2
  exit 1
}
echo "数据卷：$volume"

"${COMPOSE[@]}" rm -sf mysql >/dev/null
docker volume rm "$volume" >/dev/null
echo "已删除旧数据"

log "重建数据库并播种"
"${COMPOSE[@]}" up -d mysql redis >/dev/null

waited=0
printf '等待 mysql 就绪'
until [ "$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' \
  "$("${COMPOSE[@]}" ps -q mysql)")" = "healthy" ]; do
  if [ "$waited" -ge 240 ]; then
    echo
    echo "mysql 在 240s 内没就绪" >&2
    exit 1
  fi
  printf '.'
  sleep 3
  waited=$((waited + 3))
done
echo " → 就绪"

# 这里只跑迁移和播种，不跑模型预热：模型在 mall-data 卷里没被动过，
# 播种时同步向量索引会直接命中缓存，不会重新下载。
"${COMPOSE[@]}" run --rm backend sh -c \
  'alembic -c /app/alembic.ini upgrade head && python -m app.core.seed'

log "恢复全部服务"
"${COMPOSE[@]}" up -d >/dev/null

web_port="$(env_value WEB_HTTP_PORT)"
[ -z "$web_port" ] && web_port=80
log "自检"
BASE_URL="http://127.0.0.1:${web_port}" sh deploy/smoke.sh
