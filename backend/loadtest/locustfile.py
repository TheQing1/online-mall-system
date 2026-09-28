"""商城读路径压测（locust）。

场景刻意贴近真实流量结构：**读多写少**——浏览商品列表、翻详情、拉分类与
Banner 占绝大多数，搜索占小头。

为什么压测里没有登录和下单：

1. 登录接口按 IP 限流（每分钟 10 次），压测会立刻撞上限流返回 429，
   量到的是限流器的性能而不是业务接口的性能；
2. 下单需要先准备地址、库存与购物车，属于有状态写路径，和读路径的性能特征
   完全不同——混在一起测出来的 QPS 没有解释力。

想压写路径的话，建议单独写一个 ``MallBuyer`` 用户类，并在服务端把
``RATE_LIMIT_ORDER`` 调大（或临时关掉 Redis），否则量到的同样是限流器。

用法（需要 API 已经跑起来）：

    locust -f loadtest/locustfile.py --headless -u 50 -r 10 -t 30s \
        --host http://127.0.0.1:8000

    # 或者打开 Web UI：locust -f loadtest/locustfile.py --host http://127.0.0.1:8000
"""

import random

from locust import HttpUser, between, task

# 分组名：让 locust 报表按「接口」聚合，而不是把 /products/1、/products/2
# 算成两条独立的记录（与 Prometheus 指标那边避免 label 基数爆炸是同一个道理）。
PRODUCTS = "/api/v1/products"


class MallBrowser(HttpUser):
    """模拟一个逛商城的用户：以列表页和详情页为主。"""

    wait_time = between(0.1, 0.5)

    def on_start(self):
        self.product_ids: list[int] = []
        res = self.client.get(PRODUCTS, params={"page_size": 20}, name=PRODUCTS)
        if res.ok:
            self.product_ids = [item["id"] for item in res.json().get("items", [])]

    @task(5)
    def browse_products(self):
        """首页/列表页：默认按创建时间倒序。"""
        page = random.randint(1, 3)
        self.client.get(
            PRODUCTS,
            params={"page": page, "page_size": 20},
            name=PRODUCTS,
        )

    @task(4)
    def view_product_detail(self):
        """商品详情页：命中 Redis 缓存后应该明显快于列表页。"""
        if not self.product_ids:
            return
        product_id = random.choice(self.product_ids)
        self.client.get(
            f"{PRODUCTS}/{product_id}",
            name=f"{PRODUCTS}/{{product_id}}",
        )

    @task(3)
    def search_products(self):
        """搜索与排序：这类请求的参数组合多，缓存命中率天然更低。"""
        keyword = random.choice(["手机", "耳机", "笔记本", "华为", "苹果"])
        self.client.get(
            PRODUCTS,
            params={"keyword": keyword, "sort_by": "price", "sort_order": "asc"},
            name=f"{PRODUCTS}?keyword",
        )

    @task(2)
    def list_categories(self):
        self.client.get(
            "/api/v1/products/categories",
            name="/api/v1/products/categories",
        )

    @task(1)
    def list_banners(self):
        self.client.get("/api/v1/banners", name="/api/v1/banners")
