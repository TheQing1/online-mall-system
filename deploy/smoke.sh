#!/usr/bin/env sh
# 部署自检：从「用户真正访问的那个地址」出发，把关键链路全走一遍。
#
# 为什么不只在服务器上 curl /health：健康检查只证明进程活着。真正的演示
# 会踩到的是另一批东西——静态资源有没有被构建进镜像、nginx 的 SPA 回退
# 对不对、/api 反代通不通、种子数据在不在、登录能不能拿到 token。
# 这些每一条都能让站点「打开是白屏」却依然 health=ok。
#
# 用法：
#   sh deploy/smoke.sh                          # 默认测 http://localhost
#   BASE_URL=https://mall.example.com sh deploy/smoke.sh
#   BASE_URL=http://127.0.0.1:8080 sh deploy/smoke.sh
#
# 退出码非 0 表示有硬性检查没过。

set -u

BASE_URL="${BASE_URL:-http://localhost}"
BASE_URL="${BASE_URL%/}"
ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin123}"
DEMO_USER="${DEMO_USER:-demo}"
DEMO_PASSWORD="${DEMO_PASSWORD:-demo123}"

pass=0
fail=0
warn=0

TMP_DIR="$(mktemp -d 2>/dev/null || echo /tmp/mall-smoke)"
mkdir -p "$TMP_DIR"
BODY="$TMP_DIR/body"
cleanup() { rm -rf "$TMP_DIR"; }
trap cleanup EXIT

if ! command -v curl >/dev/null 2>&1; then
  echo "缺少 curl，无法自检。Debian/Ubuntu: apt-get install -y curl"
  exit 1
fi

ok() {
  pass=$((pass + 1))
  echo "  [通过] $1"
}

bad() {
  fail=$((fail + 1))
  echo "  [失败] $1"
}

soft() {
  warn=$((warn + 1))
  echo "  [警告] $1"
}

# GET 并断言状态码；状态码对了再按需断言响应体里的关键字。
# 用法: expect_get "名称" "/path" 200 "关键字（可省略）"
expect_get() {
  name="$1"
  path="$2"
  want_code="$3"
  want_text="${4:-}"
  code="$(curl -sS -o "$BODY" -w '%{http_code}' --max-time 20 "${BASE_URL}${path}" 2>/dev/null || echo 000)"
  if [ "$code" != "$want_code" ]; then
    bad "$name：期望 HTTP $want_code，实际 $code（${BASE_URL}${path}）"
    return 1
  fi
  if [ -n "$want_text" ] && ! grep -q "$want_text" "$BODY"; then
    bad "$name：HTTP $code 但响应体里没有「$want_text」"
    return 1
  fi
  ok "$name"
  return 0
}

echo "==> 自检目标：$BASE_URL"
echo

# ---- 1. 后端存活 ----
expect_get "后端 /health" "/health" 200 '"status":"ok"'

# ---- 2. 两个前端确实被打进了镜像 ----
# Vue 应用挂载点。只有 index.html 在、JS 产物没进镜像时这里照样通过，
# 所以下面还会专门去要一次构建产物里的 JS。
expect_get "商城首页（SPA 挂载点）" "/" 200 'id="app"'
expect_get "管理后台首页（/admin/ 子路径）" "/admin/" 200 'id="app"'

# 从首页 HTML 里抠出构建产物的地址，再确认它真能取到 —— 这一步才真正验证
# 「前端产物进了镜像」，而不是「nginx 里有份 index.html」。
curl -sS --max-time 20 "${BASE_URL}/" -o "$BODY" 2>/dev/null || true
asset="$(grep -o '/assets/[A-Za-z0-9._-]*\.js' "$BODY" | head -n 1 || true)"
if [ -n "$asset" ]; then
  expect_get "商城 JS 构建产物（$asset）" "$asset" 200
else
  soft "没在首页 HTML 里找到 /assets/*.js，跳过产物检查（构建方式可能变了）"
fi

# 后台的产物在 /admin/assets/ 下，同样要真的取一次
curl -sS --max-time 20 "${BASE_URL}/admin/" -o "$BODY" 2>/dev/null || true
admin_asset="$(grep -o '/admin/assets/[A-Za-z0-9._-]*\.js' "$BODY" | head -n 1 || true)"
if [ -n "$admin_asset" ]; then
  expect_get "后台 JS 构建产物（$admin_asset）" "$admin_asset" 200
else
  soft "没在后台 HTML 里找到 /admin/assets/*.js，跳过产物检查"
fi

# ---- 3. 接口与种子数据 ----
if expect_get "商品列表接口" "/api/v1/products" 200 '"items"'; then
  if grep -q '"items":\[\]' "$BODY" || grep -q '"total":0' "$BODY"; then
    bad "商品列表是空的：种子数据没跑成功，商城首页会是空的"
  else
    ok "种子商品存在"
  fi
fi

# 搜索走的是「查询理解 + 同义词 + AND→OR 兜底」那条链路，
# 这里用口语化的「鞋子」（库里的商品名是「运动鞋」）当探针：
# 它是历史上真出过问题的那一类查询，放进部署自检里防止回归。
if expect_get "中文模糊搜索（关键词：鞋子）" "/api/v1/products?keyword=%E9%9E%8B%E5%AD%90" 200; then
  if grep -q '"items":\[\]' "$BODY" || grep -q '"total":0' "$BODY"; then
    bad "搜「鞋子」没有结果：搜索归一化/同义词链路有问题（这是历史回归点）"
  else
    ok "搜「鞋子」能命中「运动鞋」"
  fi
fi

# ---- 4. 认证 ----
login() { # user, password  -> 成功时把 token 打到 stdout
  curl -sS --max-time 20 -X POST "${BASE_URL}/api/v1/auth/login" \
    -H 'Content-Type: application/json' \
    -d "{\"username\":\"$1\",\"password\":\"$2\"}" 2>/dev/null
}

demo_resp="$(login "$DEMO_USER" "$DEMO_PASSWORD")"
if printf '%s' "$demo_resp" | grep -q '"access_token"'; then
  ok "普通用户登录（$DEMO_USER）"
  demo_token="$(printf '%s' "$demo_resp" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')"
  me_code="$(curl -sS -o "$BODY" -w '%{http_code}' --max-time 20 \
    -H "Authorization: Bearer $demo_token" "${BASE_URL}/api/v1/auth/me" 2>/dev/null || echo 000)"
  [ "$me_code" = "200" ] && ok "带 token 取用户信息" || bad "带 token 取用户信息：HTTP $me_code"
else
  bad "普通用户登录失败（$DEMO_USER）：$(printf '%s' "$demo_resp" | head -c 200)"
fi

admin_resp="$(login "$ADMIN_USER" "$ADMIN_PASSWORD")"
if printf '%s' "$admin_resp" | grep -q '"access_token"'; then
  ok "管理员登录（$ADMIN_USER）"
  admin_token="$(printf '%s' "$admin_resp" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')"
  dash_code="$(curl -sS -o "$BODY" -w '%{http_code}' --max-time 20 \
    -H "Authorization: Bearer $admin_token" "${BASE_URL}/api/v1/admin/dashboard" 2>/dev/null || echo 000)"
  if [ "$dash_code" = "200" ]; then
    ok "管理后台数据看板"
  else
    bad "管理后台数据看板：HTTP $dash_code"
  fi
else
  bad "管理员登录失败（$ADMIN_USER）：$(printf '%s' "$admin_resp" | head -c 200)"
fi

# ---- 5. AI 客服（SSE）----
# 这一段是项目的主打能力，单独探测。没有配 DeepSeek Key 时不算硬性失败
# （商城本身是完整的），但要明确说出来，避免「以为配了其实没配」。
chat_resp="$(curl -sS --max-time 90 -X POST "${BASE_URL}/api/v1/ai-chat/chat" \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"smoke-test-0001","message":"你们支持七天无理由退货吗？"}' 2>/dev/null || true)"

# 注意 `[ERROR]` 要写成 `[[]ERROR]`：case 的模式是 glob，`[ERROR]` 会被当成
# 「匹配 E/R/O 里任意一个字符」的字符集，几乎什么都能匹配上。
case "$chat_resp" in
  *'"type": "text"'* | *'"type":"text"'*)
    ok "AI 客服流式应答（检索 + 大模型都在工作）"
    ;;
  *DEEPSEEK_API_KEY*)
    soft "AI 客服未配置 DEEPSEEK_API_KEY：接口本身是通的，但只会返回配置提示。演示 AI 能力必须补上这个 Key"
    ;;
  *'[[]ERROR]'*)
    bad "AI 客服返回错误：$(printf '%s' "$chat_resp" | head -c 200)"
    ;;
  *)
    bad "AI 客服没有返回可识别的内容：$(printf '%s' "$chat_resp" | head -c 200)"
    ;;
esac

echo
echo "==> 自检结果：通过 $pass 项，失败 $fail 项，警告 $warn 项"
if [ "$fail" -gt 0 ]; then
  echo "==> 有失败项，站点还没到可以给人看的状态。"
  exit 1
fi
echo "==> 关键链路全部可用。"
