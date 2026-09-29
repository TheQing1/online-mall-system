#!/usr/bin/env bash
# 在一台全新的 Linux 服务器上把这个项目跑起来。
#
#   git clone https://github.com/TheQing1/online-mall-system.git
#   cd online-mall-system
#   sudo bash deploy/bootstrap.sh
#
# 它会依次做完：装 Docker → 生成随机密钥写进 .env → 校验配置 → 构建镜像 →
# 起 MySQL/Redis → 跑迁移和种子数据 → 预热 Embedding 模型（首次约 100MB）→
# 起全部服务 → 跑一遍部署自检。
#
# 全程可以无人值守：把答案放进环境变量即可。
#   DOMAIN=mall.example.com DEEPSEEK_API_KEY=sk-xxx sudo -E bash deploy/bootstrap.sh
# 不设 DOMAIN 就是纯 HTTP 模式（用 http://服务器IP 访问，浏览器会提示不安全）。
#
# 关于顺序：模型预热刻意放在 `up -d` 之前。放到之后的话，第一个访问的人
# 会替我们把 100MB 模型下载完，而且 backend 在这期间一直是 unhealthy，
# 连带 web 服务（depends_on: service_healthy）根本不会启动——看起来就像
# 「部署失败」，但日志里什么都看不出来。

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="$ROOT_DIR/.env"
ASSUME_YES=0
for arg in "$@"; do
  case "$arg" in
    -y | --yes) ASSUME_YES=1 ;;
    -h | --help)
      sed -n '2,20p' "$0"
      exit 0
      ;;
    *)
      echo "未知参数：$arg（支持 -y / --yes / -h）" >&2
      exit 2
      ;;
  esac
done

log() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }
die() {
  echo "错误：$1" >&2
  exit 1
}

# ---------------------------------------------------------------- 1. 权限

if [ "$(id -u)" -ne 0 ]; then
  if command -v sudo >/dev/null 2>&1; then
    echo "需要 root 权限（装 Docker、开端口），改用 sudo 重新执行…"
    exec sudo -E bash "$0" "$@"
  fi
  die "请用 root 运行，或先安装 sudo"
fi

# ---------------------------------------------------------------- 2. Docker

log "检查 Docker"
if ! command -v docker >/dev/null 2>&1; then
  echo "没装 Docker，使用官方脚本安装（get.docker.com）…"
  if ! command -v curl >/dev/null 2>&1; then
    apt-get update && apt-get install -y curl
  fi
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker
else
  echo "Docker 已安装：$(docker --version)"
fi

if ! docker compose version >/dev/null 2>&1; then
  die "缺少 docker compose 插件（v2）。Debian/Ubuntu: apt-get install -y docker-compose-plugin"
fi

# 首次装完 Docker，当前 shell 里的 docker 仍然可用（我们是 root），
# 但 socket 权限如果被策略改过就会在下面构建时炸得莫名其妙，提前探一下。
docker info >/dev/null 2>&1 || die "docker 守护进程不可用，先确认 systemctl status docker"

# ---------------------------------------------------------------- 3. .env

log "准备 .env（数据库口令与 JWT 密钥用随机值，不再用示例默认值）"

random_hex() {
  # $1 = 字节数；openssl 更通用，没有就退回 /dev/urandom
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex "$1"
  else
    head -c "$1" /dev/urandom | od -An -tx1 | tr -d ' \n'
  fi
}

# 改 .env 里的某一项；不存在就追加。用 awk 重写而不是 sed -i，
# 避免值里出现 / & 之类的字符时被当成 sed 的分隔符或反向引用。
set_env() {
  key="$1"
  value="$2"
  if grep -q "^${key}=" "$ENV_FILE"; then
    awk -v k="$key" -v v="$value" \
      'index($0, k "=") == 1 { print k "=" v; next } { print }' \
      "$ENV_FILE" >"$ENV_FILE.tmp"
    mv "$ENV_FILE.tmp" "$ENV_FILE"
  else
    printf '%s=%s\n' "$key" "$value" >>"$ENV_FILE"
  fi
}

env_value() {
  sed -n "s/^[[:space:]]*$1[[:space:]]*=[[:space:]]*//p" "$ENV_FILE" \
    | tail -n 1 \
    | sed -e 's/[[:space:]]*$//' -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'$/\1/"
}

if [ ! -f "$ENV_FILE" ]; then
  cp .env.example "$ENV_FILE"
  echo "已从 .env.example 生成 .env"
else
  echo ".env 已存在，只补齐缺失项（不会覆盖你已经填好的值）"
fi

# 只替换「空值或示例值」，已填过的一律不动——重跑 bootstrap 不该把密钥换掉，
# 那会让之前签发的 token 全部失效。
current="$(env_value MYSQL_ROOT_PASSWORD)"
case "$current" in
  "" | "mall_root_123" | "your_password")
    set_env MYSQL_ROOT_PASSWORD "$(random_hex 16)"
    echo "已生成随机数据库口令"
    ;;
esac

current="$(env_value JWT_SECRET_KEY)"
case "$current" in
  "" | "change-me" | "change-me-in-production" | "your-secret-key-change-me")
    set_env JWT_SECRET_KEY "$(random_hex 32)"
    echo "已生成随机 JWT 密钥"
    ;;
esac

# ---- 交互式补问：域名与 DeepSeek Key ----
# 非交互（管道、CI）时直接跳过，用已有的环境变量 / .env 值。
interactive=0
[ -t 0 ] && interactive=1

domain="${DOMAIN:-$(env_value DOMAIN)}"
if [ "$interactive" -eq 1 ] && [ -z "$domain" ]; then
  echo
  echo "有域名的话填一个（用它自动配 HTTPS，需要先把这个域名解析到本机公网 IP）。"
  echo "没有域名直接回车，走 HTTP 模式，用 http://本机IP 访问。"
  printf '域名（可留空）: '
  read -r domain || domain=""
fi
set_env DOMAIN "$domain"

deepseek_key="${DEEPSEEK_API_KEY:-$(env_value DEEPSEEK_API_KEY)}"
if [ "$interactive" -eq 1 ] && [ -z "$deepseek_key" ]; then
  echo
  echo "AI 客服需要 DeepSeek API Key（https://platform.deepseek.com 申请）。"
  echo "不填也能部署：商城、下单、支付、管理后台都正常，只有 AI 对话会提示未配置。"
  printf 'DEEPSEEK_API_KEY（可留空）: '
  read -r deepseek_key || deepseek_key=""
fi
set_env DEEPSEEK_API_KEY "$deepseek_key"

# ---- 端口规划 ----
set_env MALL_ENV production
# 后端调试端口只留宿主机可访问：公网上扫不到 /docs 和 /metrics
set_env API_BIND 127.0.0.1
set_env API_PORT 8000

TLS_MODE=0
if [ -n "$domain" ]; then
  TLS_MODE=1
  # 80/443 交给 Caddy，nginx 退到回环的 8080（方便在本机直接排查 nginx 那一层）
  set_env WEB_BIND 127.0.0.1
  set_env WEB_HTTP_PORT 8080
  echo "HTTPS 模式：https://$domain（Caddy 自动申请并续期证书）"
else
  set_env WEB_BIND 0.0.0.0
  set_env WEB_HTTP_PORT 80
  echo "HTTP 模式：http://<本机公网 IP>"
fi

# ---------------------------------------------------------------- 4. 选文件

COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)
if [ "$TLS_MODE" -eq 1 ]; then
  COMPOSE+=(-f docker-compose.tls.yml)
fi
LOCAL_URL="http://127.0.0.1:$(env_value WEB_HTTP_PORT)"
[ "$TLS_MODE" -eq 0 ] && LOCAL_URL="http://127.0.0.1"

# ---------------------------------------------------------------- 5. 校验

log "校验配置"
if [ "$TLS_MODE" -eq 1 ]; then
  bash deploy/check-env.sh --tls
else
  bash deploy/check-env.sh
fi

# ---------------------------------------------------------------- 6. 构建

log "构建镜像（首次会下载依赖，约 5-15 分钟）"
"${COMPOSE[@]}" build

# ---------------------------------------------------------------- 7. 起依赖

log "启动数据库与 Redis"
"${COMPOSE[@]}" up -d mysql redis

wait_service_healthy() {
  service="$1"
  timeout="${2:-180}"
  waited=0
  printf '等待 %s 就绪' "$service"
  while :; do
    cid="$("${COMPOSE[@]}" ps -q "$service" 2>/dev/null || true)"
    if [ -n "$cid" ]; then
      status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$cid" 2>/dev/null || echo unknown)"
      if [ "$status" = "healthy" ] || [ "$status" = "none" ]; then
        echo " → 就绪"
        return 0
      fi
    fi
    if [ "$waited" -ge "$timeout" ]; then
      echo
      echo "超时：$service 在 ${timeout}s 内没有就绪，日志如下" >&2
      "${COMPOSE[@]}" logs --tail 40 "$service" >&2 || true
      return 1
    fi
    printf '.'
    sleep 3
    waited=$((waited + 3))
  done
}

wait_service_healthy mysql 240
wait_service_healthy redis 60

# ---------------------------------------------------------------- 8. 初始化

log "初始化数据库并预热模型（首次要下载约 100MB 的 BGE，请耐心等）"
"${COMPOSE[@]}" run --rm backend sh -c \
  'alembic -c /app/alembic.ini upgrade head && python -m app.core.seed && python -m app.ai.warmup'

# ---------------------------------------------------------------- 9. 起飞

log "启动全部服务"
"${COMPOSE[@]}" up -d

echo
"${COMPOSE[@]}" ps

# ---------------------------------------------------------------- 10. 自检

log "本地自检（绕过 Caddy，直接测 nginx）"
if ! BASE_URL="$LOCAL_URL" sh deploy/smoke.sh; then
  echo
  echo "本地自检没全过。最近的日志：" >&2
  "${COMPOSE[@]}" logs --tail 30 backend web >&2 || true
  exit 1
fi

PUBLIC_URL="$LOCAL_URL"
if [ "$TLS_MODE" -eq 1 ]; then
  PUBLIC_URL="https://$domain"
  log "等待 HTTPS 证书（Let's Encrypt 校验域名所有权，通常几秒到一分钟）"
  waited=0
  until curl -sSf -o /dev/null --max-time 10 "$PUBLIC_URL/health" 2>/dev/null; do
    if [ "$waited" -ge 180 ]; then
      echo "证书没在 180 秒内就绪。常见原因：" >&2
      echo "  1) 域名没解析到本机公网 IP；2) 防火墙/安全组没放行 80 或 443；" >&2
      echo "  3) 同一域名短期签发次数过多（Let's Encrypt 限制每周 5 次）。" >&2
      echo "Caddy 日志：" >&2
      "${COMPOSE[@]}" logs --tail 40 caddy >&2 || true
      exit 1
    fi
    printf '.'
    sleep 5
    waited=$((waited + 5))
  done
  echo " → 证书就绪"

  log "公网自检（走真实域名和证书）"
  BASE_URL="$PUBLIC_URL" sh deploy/smoke.sh
fi

# ---------------------------------------------------------------- 完成

cat <<EOF

==> 部署完成

    商城前台   ${PUBLIC_URL}
    管理后台   ${PUBLIC_URL}/admin/login
    演示账号   demo / demo123
    管理账号   admin / admin123   （部署后请立刻改掉）

    本机调试   ${LOCAL_URL}                  （nginx 那一层）
               http://127.0.0.1:8000/docs    （接口文档，仅本机可访问）

    常用命令   ${COMPOSE[*]} ps
               ${COMPOSE[*]} logs -f backend
               ${COMPOSE[*]} restart
               sh deploy/reset-demo.sh        # 演示数据被别人改乱后重置

    想再加监控面板（Prometheus + Grafana）：
               ${COMPOSE[*]} --profile observability up -d

EOF
