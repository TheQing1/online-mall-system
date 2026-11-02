#!/usr/bin/env bash
# 数据库恢复到指定备份（回滚）。
#
# 与 backup.sh 配套。两者合起来才构成「可回滚的部署」——
# 只有备份没有恢复脚本，出事时照样要手敲一堆命令，慌乱中更容易出错。
#
# 用法：
#   bash deploy/rollback.sh                      # 列出可用备份
#   bash deploy/rollback.sh backups/xxx.sql.gz   # 从指定备份恢复
#   bash deploy/rollback.sh --latest             # 恢复最近一份
#   bash deploy/rollback.sh --latest --dry-run   # 只看会做什么
#
# 恢复策略说明：
#   本脚本恢复的是**数据库内容**。代码/镜像的回滚需要配合 git checkout +
#   重新 build，见文末提示。两者是两件事，不要混为一谈。
set -euo pipefail

cd "$(dirname "$0")/.."

BACKUP_DIR="${BACKUP_DIR:-./backups}"
DRY_RUN=0
TARGET=""

while [ $# -gt 0 ]; do
  case "$1" in
    --latest)
      TARGET="$(ls -1t "$BACKUP_DIR"/mall-*.sql.gz 2>/dev/null | head -1 || true)"
      shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help)
      sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    -*) echo "未知参数：$1" >&2; exit 1 ;;
    *) TARGET="$1"; shift ;;
  esac
done

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*" >&2; }
fail() { printf '\033[1;31m!!\033[0m %s\n' "$*" >&2; exit 1; }

COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)
if [ -f docker-compose.tls.yml ] && grep -qE '^DOMAIN=.+' .env 2>/dev/null; then
  COMPOSE+=(-f docker-compose.tls.yml)
fi

# 没给目标就列出现有备份
if [ -z "$TARGET" ]; then
  log "可用的备份（$BACKUP_DIR）"
  if ! ls -1 "$BACKUP_DIR"/mall-*.sql.gz >/dev/null 2>&1; then
    echo "  （没有备份）先执行：bash deploy/backup.sh"
    exit 1
  fi
  printf '  %-52s %8s  %s\n' "文件" "大小" "时间"
  while IFS= read -r f; do
    printf '  %-52s %8s  %s\n' \
      "$(basename "$f")" \
      "$(du -h "$f" | cut -f1)" \
      "$(date -r "$f" '+%Y-%m-%d %H:%M' 2>/dev/null || stat -c %y "$f" 2>/dev/null | cut -d. -f1)"
  done < <(ls -1t "$BACKUP_DIR"/mall-*.sql.gz)
  echo
  echo "恢复：bash deploy/rollback.sh --latest"
  echo "      bash deploy/rollback.sh $BACKUP_DIR/<文件>"
  exit 0
fi

[ -f "$TARGET" ] || fail "找不到备份文件：$TARGET"

# --- 恢复前先校验备份完整性 ---
# 「备份了但恢复不了」比没有备份更糟，因为它给了你错误的信心。
log "校验备份完整性"
if ! gzip -t "$TARGET" 2>/dev/null; then
  fail "备份文件已损坏（gzip -t 失败），拒绝恢复"
fi
if [ -f "$TARGET.sha256" ]; then
  if ! (cd "$(dirname "$TARGET")" && sha256sum -c "$(basename "$TARGET").sha256" >/dev/null 2>&1); then
    fail "校验和不匹配——备份文件可能被截断或改动过，拒绝恢复"
  fi
  log "校验和匹配"
else
  warn "没有 .sha256 校验文件，跳过校验和检查（继续，但请留意）"
fi

SIZE="$(wc -c < "$TARGET" | tr -d ' ')"
log "准备恢复：$(basename "$TARGET")（${SIZE} 字节）"

# --- 安全闸门：默认要交互确认 ---
if [ "$DRY_RUN" -eq 1 ]; then
  cat <<EOF

[DRY RUN] 实际会做的事：
  1. 先给**当前**数据库做一份安全备份（万一恢复错了还能回来）
  2. 停掉 backend / worker（避免恢复过程中有写入）
  3. 把 $(basename "$TARGET") 导入 mysql
  4. 重启 backend / worker
  5. 跑 smoke.sh 自检

没有做任何改动。
EOF
  exit 0
fi

if [ -z "${MALL_FORCE:-}" ]; then
  cat <<EOF

即将用备份覆盖当前数据库。**这不可撤销**（当前数据会被这份备份替换）。
备份文件：$(basename "$TARGET")

继续输入 yes：\c
EOF
  read -r REPLY
  [ "$REPLY" = "yes" ] || { echo "已取消"; exit 1; }
fi

# --- 1. 恢复前先保存现状 ---
# 这一步很关键：如果选错了备份、或者备份本身有问题，还能回到操作前的状态。
log "先备份当前数据库（回滚的回滚）"
if ! BACKUP_DIR="$BACKUP_DIR" bash deploy/backup.sh >/dev/null 2>&1; then
  warn "当前库备份失败。是否继续？输 yes 继续，其他键取消：\c"
  read -r REPLY2
  [ "$REPLY2" = "yes" ] || { echo "已取消"; exit 1; }
fi

# --- 2. 停写 ---
log "停止 backend / worker（避免恢复过程中有写入）"
"${COMPOSE[@]}" stop backend worker >/dev/null 2>&1 || true

# --- 3. 恢复 ---
log "导入备份到 mysql"
# 备份是 --databases 格式，自带 CREATE DATABASE / USE，不需要额外指定库名。
# 用 --init-command 关掉外键检查：转储里的表顺序未必满足外键依赖，
# 恢复时临时关闭最稳妥（mysqldump 默认也会在文件里写 SET FOREIGN_KEY_CHECKS=0，
# 这里显式加一层，防止老版本转储漏写）。
if ! gzip -dc "$TARGET" | "${COMPOSE[@]}" exec -T mysql sh -c \
  'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot \
     --init-command="SET FOREIGN_KEY_CHECKS=0; SET UNIQUE_CHECKS=0"'; then
  fail "恢复失败。数据库可能处于中间状态，请检查 mysql 日志后重试：
    docker compose logs --tail 50 mysql"
fi

log "恢复完成"

# --- 4. 重新起飞 ---
log "重启 backend / worker"
"${COMPOSE[@]}" start backend worker >/dev/null 2>&1 || \
  "${COMPOSE[@]}" up -d backend worker

# 等后端 healthy 再自检，否则 smoke 会连不上
waited=0
printf '等待 backend 就绪'
while :; do
  cid="$("${COMPOSE[@]}" ps -q backend 2>/dev/null || true)"
  if [ -n "$cid" ]; then
    st="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$cid" 2>/dev/null || echo unknown)"
    [ "$st" = "healthy" ] || [ "$st" = "none" ] && { echo " → 就绪"; break; }
  fi
  if [ "$waited" -ge 120 ]; then
    echo
    warn "backend 120s 内未就绪，跳过自检。手动确认：docker compose logs --tail 50 backend"
    exit 1
  fi
  printf '.'
  sleep 3
  waited=$((waited + 3))
done

# --- 5. 自检 ---
log "自检"
if command -v sh >/dev/null 2>&1 && [ -f deploy/smoke.sh ]; then
  BASE_URL="${BASE_URL:-http://localhost}" sh deploy/smoke.sh || {
    warn "自检未全过。数据已恢复，但服务可能还有问题，请看上面的失败项。"
    exit 1
  }
else
  warn "没找到 deploy/smoke.sh，跳过自检"
fi

cat <<EOF

\033[1;32m恢复完成\033[0m

提醒：本脚本只恢复**数据**。如果这次事故的起因是**代码**（而不是数据），
还需要把代码回滚到上一个可用版本再重新构建：

  git log --oneline -10            # 找到上一个正常的提交
  git checkout <commit>
  docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

EOF
