#!/usr/bin/env bash
# 数据库备份。
#
# 为什么需要它：`bootstrap.sh` 第 8 步会执行 `alembic upgrade head`，
# 而本项目的迁移里有真实的 `DROP COLUMN` / `DROP TABLE`（见
# alembic/versions/2026_09_07_mall_upgrade.py）。一旦升级出问题，
# **数据本身不可恢复**——这个事实在 docs/interview-qa.md 里承认过，
# 但当时脚本并没有实现「升级前先备份」这句承诺。
#
# 用法：
#   bash deploy/backup.sh                      # 备份到 ./backups/
#   BACKUP_DIR=/var/backups/mall bash deploy/backup.sh
#   bash deploy/backup.sh --keep 5             # 只保留最近 5 份
#
# 依赖：docker compose（与 bootstrap.sh 用同一套 COMPOSE 选择逻辑）
set -euo pipefail

cd "$(dirname "$0")/.."

BACKUP_DIR="${BACKUP_DIR:-./backups}"
KEEP="${KEEP:-10}"

while [ $# -gt 0 ]; do
  case "$1" in
    --keep) KEEP="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) echo "未知参数：$1" >&2; exit 1 ;;
  esac
done

# 与 bootstrap.sh 完全一致的 compose 选择：有 DOMAIN 就带上 tls 层，
# 否则只跑 base + prod。用错文件会导致连到不同的 mysql 容器/卷。
COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)
if [ -f docker-compose.tls.yml ] && grep -qE '^DOMAIN=.+' .env 2>/dev/null; then
  COMPOSE+=(-f docker-compose.tls.yml)
fi

log() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m!!\033[0m %s\n' "$*" >&2; exit 1; }

# 从 .env 读库名；容器里的 MYSQL_DATABASE 由 compose 注入，优先用它
DB_NAME="$("${COMPOSE[@]}" exec -T mysql sh -c 'printf %s "$MYSQL_DATABASE"' 2>/dev/null | tr -d '\r')"
[ -n "$DB_NAME" ] || fail "读不到 MYSQL_DATABASE，mysql 容器可能没起。先执行：docker compose up -d mysql"

# 确认 mysql 已就绪，否则 mysqldump 会拿到空文件
if ! "${COMPOSE[@]}" exec -T mysql sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqladmin ping -uroot --silent' >/dev/null 2>&1; then
  fail "mysql 还没有就绪，等它 healthy 后再试"
fi

mkdir -p "$BACKUP_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$BACKUP_DIR/mall-${DB_NAME}-${STAMP}.sql.gz"

log "备份数据库 ${DB_NAME} → ${OUT}"

# --single-transaction：InnoDB 下拿到一致性快照，不锁表（线上也能跑）
# --routines --triggers：迁移可能用到，漏了恢复出来是残缺的
# --set-gtid-purged=OFF：避免 GTID 信息导致在别的实例上恢复失败
# 直接 gzip 管道而非先落盘再压：大库时省一半磁盘和 IO
if ! "${COMPOSE[@]}" exec -T mysql sh -c \
  'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqldump -uroot \
     --single-transaction --quick --routines --triggers \
     --set-gtid-purged=OFF \
     --databases "$MYSQL_DATABASE"' | gzip -9 > "$OUT"; then
  rm -f "$OUT"
  fail "备份失败"
fi

# 空文件/极小文件基本等于失败（比如库不存在时 mysqldump 仍可能返回 0）
SIZE="$(wc -c < "$OUT" | tr -d ' ')"
if [ "$SIZE" -lt 1024 ]; then
  rm -f "$OUT"
  fail "备份产物只有 ${SIZE} 字节，视为失败"
fi

# 校验它能被 gzip 正常解开、且含 CREATE TABLE —— 避免「备份了但恢复不了」。
# SQL 转储比二进制备份脆弱，这一步很便宜但很值。
if ! gzip -t "$OUT" 2>/dev/null; then
  fail "备份文件损坏（gzip -t 失败）：$OUT"
fi
if ! gzip -dc "$OUT" | grep -q 'CREATE TABLE'; then
  fail "备份里没有 CREATE TABLE，内容不完整：$OUT"
fi

# 写一个校验和，恢复前可以验证文件没被截断/改动
sha256sum "$OUT" > "$OUT.sha256" 2>/dev/null || shasum -a 256 "$OUT" > "$OUT.sha256"

log "备份完成：$(du -h "$OUT" | cut -f1)"

# 只保留最近 KEEP 份（连同 .sha256），避免磁盘被慢慢吃满
if [ "$KEEP" -gt 0 ]; then
  mapfile -t OLD < <(ls -1t "$BACKUP_DIR"/mall-*.sql.gz 2>/dev/null | tail -n +$((KEEP + 1)) || true)
  if [ "${#OLD[@]}" -gt 0 ]; then
    for f in "${OLD[@]}"; do
      rm -f "$f" "$f.sha256"
    done
    log "清理了 ${#OLD[@]} 份旧备份（保留最近 ${KEEP} 份）"
  fi
fi

echo "$OUT"
