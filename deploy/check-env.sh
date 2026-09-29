#!/usr/bin/env sh
# 生产部署前置检查：把「配置错了但服务照样起得来」的情况挡在启动之前。
#
# 为什么要单独一个脚本：docker compose 对几乎所有变量都给了能跑的默认值，
# 所以漏配不会报错，只会表现成「站点能打开，但认证形同虚设」或者
# 「接口文档挂在公网上」。这类问题在浏览器里完全看不出来，只能显式断言。
#
# 用法：
#   sh deploy/check-env.sh            # 检查基础配置
#   sh deploy/check-env.sh --tls      # 额外检查 HTTPS 相关配置
# 退出码非 0 表示有必须处理的问题。

set -eu

ENV_FILE="${ENV_FILE:-.env}"
TLS_MODE=0
[ "${1:-}" = "--tls" ] && TLS_MODE=1

errors=0
warnings=0

fail() {
  echo "  [错误] $1"
  errors=$((errors + 1))
}

warn() {
  echo "  [警告] $1"
  warnings=$((warnings + 1))
}

ok() {
  echo "  [通过] $1"
}

# 取 .env 里某个键的值：同名键以最后一次出现为准，顺手去掉两端引号。
env_value() {
  sed -n "s/^[[:space:]]*$1[[:space:]]*=[[:space:]]*//p" "$ENV_FILE" \
    | tail -n 1 \
    | sed -e 's/[[:space:]]*$//' -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'$/\1/"
}

echo "==> 检查 $ENV_FILE"

if [ ! -f "$ENV_FILE" ]; then
  echo "  [错误] 找不到 $ENV_FILE，先执行：cp .env.example .env"
  exit 1
fi

# ---- 数据库口令 ----
mysql_password="$(env_value MYSQL_ROOT_PASSWORD)"
case "$mysql_password" in
  "" | "mall_root_123" | "your_password" | "password")
    fail "MYSQL_ROOT_PASSWORD 还是空值或示例值。数据库只在内网，但那是纵深防御，不是不设密码的理由。生成：openssl rand -hex 16"
    ;;
  *)
    ok "MYSQL_ROOT_PASSWORD 已设置（长度 ${#mysql_password}）"
    ;;
esac

# ---- JWT 密钥 ----
jwt_secret="$(env_value JWT_SECRET_KEY)"
case "$jwt_secret" in
  "" | "change-me" | "change-me-in-production" | "your-secret-key-change-me")
    fail "JWT_SECRET_KEY 还是示例值，任何人都能自己签发管理员 token 登进后台。生成：openssl rand -hex 32"
    ;;
  *)
    if [ "${#jwt_secret}" -lt 32 ]; then
      fail "JWT_SECRET_KEY 只有 ${#jwt_secret} 个字符，HS256 至少给 32。生成：openssl rand -hex 32"
    else
      ok "JWT_SECRET_KEY 已设置（长度 ${#jwt_secret}）"
    fi
    ;;
esac

# ---- 对外端口 ----
api_bind="$(env_value API_BIND)"
[ -z "$api_bind" ] && api_bind="0.0.0.0"
if [ "$api_bind" = "0.0.0.0" ] || [ -z "$api_bind" ]; then
  # 不算致命错误：只是把 /docs 和 /metrics 一起摆到公网上，
  # 而 /metrics 会暴露业务量级，/docs 会暴露全部接口形状。
  warn "API_BIND=$api_bind：后端调试端口（/docs、/metrics）会暴露在公网。生产建议改 127.0.0.1"
else
  ok "API_BIND=$api_bind，调试端口不对外"
fi

if [ "$TLS_MODE" -eq 1 ]; then
  domain="$(env_value DOMAIN)"
  web_port="$(env_value WEB_HTTP_PORT)"
  web_bind="$(env_value WEB_BIND)"

  if [ -z "$domain" ]; then
    fail "开了 TLS 层但 DOMAIN 是空的。填一个已经解析到本机的域名（例如 mall.example.com）"
  else
    ok "DOMAIN=$domain"
  fi

  # 80/443 要留给 Caddy；nginx 若还占着 80，容器起不来（端口已被占用）
  if [ "$web_port" = "80" ]; then
    fail "开了 TLS 层但 WEB_HTTP_PORT=80，会和 Caddy 抢端口。改成 8080"
  else
    ok "WEB_HTTP_PORT=${web_port:-未设置}"
  fi

  if [ "$web_bind" = "0.0.0.0" ]; then
    warn "WEB_BIND=0.0.0.0：nginx 也会直接对外。建议改 127.0.0.1，让流量只从 Caddy 进来"
  else
    ok "WEB_BIND=${web_bind:-未设置}"
  fi
fi

# ---- AI 客服 ----
deepseek_key="$(env_value DEEPSEEK_API_KEY)"
if [ -z "$deepseek_key" ]; then
  warn "DEEPSEEK_API_KEY 为空：商城下单、支付、后台都能用，但 AI 客服会返回「请先在 .env 中配置 DEEPSEEK_API_KEY」。演示 AI 能力必须配。"
else
  ok "DEEPSEEK_API_KEY 已设置"
fi

echo
if [ "$errors" -gt 0 ]; then
  echo "==> 有 $errors 个必须处理的问题，另有 $warnings 个警告。修完再启动。"
  exit 1
fi
echo "==> 配置检查通过（$warnings 个警告）"
