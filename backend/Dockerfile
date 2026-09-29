# 固定到 bookworm 发行版，避免 python:3.11-slim 随上游滚动（3.11.x 补丁 / trixie 切换）导致构建不可复现。
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# default-mysql-client 供 docker-entrypoint.sh 里的 mysqladmin 就绪等待使用。
RUN apt-get update \
    && apt-get install -y --no-install-recommends default-mysql-client \
    && rm -rf /var/lib/apt/lists/*

# 依赖层：只 COPY requirements.txt，之后再改源码不会让 pip 安装层缓存失效。
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# 源码层：放在 pip 之后，源码变更只影响这一层及其后的层。
COPY backend/app /app/app
COPY backend/alembic /app/alembic
COPY backend/alembic.ini /app/alembic.ini
COPY backend/static /app/static
COPY backend/docker-entrypoint.sh /app/docker-entrypoint.sh

# 非 root 运行。uid/gid 1000 只是「一个固定的非特权编号」，不要求宿主机配合。
#
# /app/data 与 /app/static/products 分别是 mall-data、mall-uploads 两个命名卷的
# 挂载点。命名卷首次创建时，Docker 会用镜像里这两个目录的内容**与属主**做初始化，
# 所以必须在这里 chown，否则容器首次下载 BGE 模型、或者后台传商品图时会因为
# 没有写权限失败。
# 商品图目录以前是 bind mount 到仓库里的，容器能不能写取决于宿主机那个目录归谁
# （用 root clone 再 sudo 部署就是 root:root，写不进去），改成命名卷之后这一类
# 问题整体消失了——这也是为什么镜像里要带上种子商品图（约 0.5MB）。
RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid 1000 --home-dir /app/data --shell /usr/sbin/nologin appuser \
    && chmod +x /app/docker-entrypoint.sh \
    && mkdir -p /app/data /app/static/products \
    && chown -R appuser:appuser /app/data /app/static/products

# HOME 指向 /app/data：该目录由 mall-data 卷挂载且归属 appuser，这样 modelscope /
# huggingface 等库若回落到 $HOME/.cache 也不会因无写权限而失败。
# 必须放在上面那条 RUN 之后 —— 此时 /app/data 才存在，且 apt/pip 层仍在默认 HOME 下执行。
ENV HOME=/app/data

USER appuser

EXPOSE 8000

# 不额外安装 curl：用标准库 urllib 请求 app/main.py 提供的 GET /health。
# start-period 覆盖 alembic 迁移 + 种子数据初始化的时间。
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status == 200 else 1)"

CMD ["/app/docker-entrypoint.sh"]
