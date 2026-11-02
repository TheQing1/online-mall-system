#!/usr/bin/env bash
# 依赖漏洞扫描（CI 与本地都能跑）。
#
# 为什么不用 `pip-audit --strict` 直接卡住：
#   本项目有 80 条存量漏洞（118 条原始记录，去重后 80 个唯一 ID），
#   绝大多数在被锁定的间接依赖里（langchain 系、chromadb 系、aiohttp 系）。
#   真正该动作的几个 —— starlette / python-multipart / python-jose ——
#   受 FastAPI 0.115 的版本约束牵制，升级必须跨大版本，牵连面远超改个版本号。
#
#   一条 80 处红叉、且长期没人处理的检查，唯一的效果是让大家习惯性忽略它。
#   所以这里用**基线模式**：
#     - 当前已知漏洞集合做基线（security-baseline.json）；
#     - 扫描出现基线之外的新漏洞 → 非零退出，CI 变红；
#     - 存量漏洞照常打印，但不会让流水线永久红着。
#
#   「新引入一个带洞的依赖」会被立刻拦住，存量问题仍然可见、仍需单独排期。
#   取舍与解除条件见 scripts/BASELINE.md。
#
# 用法：
#   bash scripts/security-audit.sh            # 检查（有新增漏洞则失败）
#   bash scripts/security-audit.sh --update   # 重新生成基线（需人工 review diff）
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASELINE="$ROOT/scripts/security-baseline.json"
TARGET="$ROOT/backend/requirements.txt"

PYTHON="${PYTHON:-python}"
command -v "$PYTHON" >/dev/null 2>&1 || PYTHON=python3

# requirements.txt 里有中文注释；pip-audit 按平台默认编码读文件，
# 在非 UTF-8 环境（如 Windows 的 GBK）会解析失败。统一强制 UTF-8。
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

echo "== 扫描 $TARGET"
if ! "$PYTHON" -m pip_audit --version >/dev/null 2>&1; then
  echo "   未安装 pip-audit，正在安装到 $PYTHON ..."
  "$PYTHON" -m pip install --quiet pip-audit || {
    echo "!! pip-audit 安装失败。"
    echo "   请确认当前 python 有 pip，或先手动安装："
    echo "   $PYTHON -m pip install pip-audit"
    exit 2
  }
fi

TMP_JSON="$(mktemp)"
trap 'rm -f "$TMP_JSON"' EXIT

# 有漏洞时 pip-audit 会返回非零，这里忽略退出码，只看产出
"$PYTHON" -m pip_audit -r "$TARGET" -f json -o "$TMP_JSON" >/dev/null 2>&1 || true

if [ ! -s "$TMP_JSON" ]; then
  echo "!! 扫描没有产出结果，多半是 requirements.txt 解析失败。"
  echo "   手动复查：$PYTHON -m pip_audit -r backend/requirements.txt"
  exit 2
fi

extract_keys() {
  "$PYTHON" - "$1" <<'PY'
import json, sys

path = sys.argv[1]
with open(path, encoding="utf-8") as fh:
    data = json.load(fh)

# 基线文件是我们自己的精简格式：{包名: {version, ids[]}}
if isinstance(data, dict) and all(
    isinstance(v, dict) and "ids" in v for v in data.values()
):
    for name, info in sorted(data.items()):
        for vid in info["ids"]:
            print(f"{name}:{vid}")
    raise SystemExit(0)

# pip-audit 原始输出：{"dependencies": [{name, version, vulns:[{id, aliases}]}]}
deps = data.get("dependencies", data) if isinstance(data, dict) else data
for dep in deps or []:
    if not dep.get("vulns"):
        continue
    name = dep.get("name", "?")
    for vuln in dep["vulns"]:
        vid = vuln.get("id") or (vuln.get("aliases") or ["?"])[0]
        print(f"{name}:{vid}")
PY
}

extract_keys "$TMP_JSON" | sort -u > "$TMP_JSON.current"
CURRENT_COUNT="$(wc -l < "$TMP_JSON.current" | tr -d ' ')"
echo "== 当前已知漏洞：$CURRENT_COUNT 条"

if [ "${1:-}" = "--update" ]; then
  "$PYTHON" - "$TMP_JSON" "$BASELINE" <<'PY'
import json, sys

src, dst = sys.argv[1], sys.argv[2]
with open(src, encoding="utf-8") as fh:
    data = json.load(fh)

deps = data.get("dependencies", data) if isinstance(data, dict) else data
out = {}
for dep in deps or []:
    if not dep.get("vulns"):
        continue
    name = dep.get("name")
    ids = {
        (v.get("id") or (v.get("aliases") or ["?"])[0])
        for v in dep["vulns"]
    }
    out[name] = {"version": dep.get("version"), "ids": sorted(ids)}
out = dict(sorted(out.items()))

with open(dst, "w", encoding="utf-8") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=2)
    fh.write("\n")
print(f"   已写入 {len(out)} 个包 / {sum(len(v['ids']) for v in out.values())} 条漏洞")
PY
  echo "== 基线已更新：$BASELINE"
  echo "   请 git diff 检查增删，并在 scripts/BASELINE.md 里同步说明。"
  exit 0
fi

if [ ! -f "$BASELINE" ]; then
  echo "!! 没有基线文件，先跑一次：bash scripts/security-audit.sh --update"
  exit 2
fi

extract_keys "$BASELINE" | sort -u > "$TMP_JSON.baseline"

NEW="$(comm -13 "$TMP_JSON.baseline" "$TMP_JSON.current" || true)"
FIXED="$(comm -23 "$TMP_JSON.baseline" "$TMP_JSON.current" || true)"

if [ -n "$FIXED" ]; then
  echo "== 相比基线少了这些（可能已随依赖升级修掉）："
  echo "$FIXED" | sed 's/^/   - /'
fi

if [ -n "$NEW" ]; then
  echo ""
  echo "!! 发现基线之外的新漏洞 —— 这正是本检查要拦的情况："
  echo "$NEW" | sed 's/^/   + /'
  echo ""
  echo "处理方式："
  echo "  1) 升级或替换引入它的依赖（首选）；"
  echo "  2) 确认暂时无法升级时，跑 --update 记入基线，"
  echo "     并在 scripts/BASELINE.md 写明理由与解除条件。"
  exit 1
fi

echo "== 没有新增漏洞，通过。（存量 $CURRENT_COUNT 条见 scripts/BASELINE.md）"
