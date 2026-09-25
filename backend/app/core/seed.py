"""种子数据：初始化管理员、演示用户、分类、商品(SKU)、Banner、知识库与评测用例。

运行方式: cd backend && python -m app.core.seed
"""

from app.core.database import SessionLocal
from app.models.content import Banner
from app.models.user import User, UserRole
from app.models.product import Category, Product, ProductStatus
from app.models.sku import ProductSku
from app.models.knowledge import KnowledgeDoc, KnowledgeCategory
from app.models.chat import EvalTestCase
from app.core.security import hash_password


IMG = {
    "phone_1": "/static/products/1bbf0016e05341dfb532bc012d20f9f1.jpg",
    "phone_2": "/static/products/282766e267ea43fea8737450c93bcf69.jpg",
    "phone_3": "/static/products/3467f6efba3c46299efdce473bcb59e9.jpg",
    "phone_4": "/static/products/8604cc2a928346529947db1ab40b30fb.jpg",
    "laptop_1": "/static/products/3d057aa0e0a346a582777e8db97ec2ae.jpg",
    "laptop_2": "/static/products/8d3ad574a9774bb28ec4b6ed4efcfed9.jpg",
    "earphone_1": "/static/products/6b1864ab81624232a944e3ee7dfcb4d8.png",
    "earphone_2": "/static/products/a6b35111b58440dd8b5ea67cdea386a8.png",
    "mouse": "/static/products/bb5b595f893d4b27ae770b2d9be66604.jpg",
    "watch": "/static/products/c6a95b0dc12242c59b9285ac7ae7ca68.jpg",
    "fridge": "/static/products/d0b6149cc80546d8bdc5100f177901bf.jpg",
    "shoes": "/static/products/d5642d094df94c42b1c5e4e2a27440be.jpg",
    "bag": "/static/products/dcdd1c9b08d7405bb718ecda182ea24c.jpg",
    "snack": "/static/products/e02bfeaabc5e45c2b3fffe313218d2ba.jpg",
    "tea": "/static/products/e7c943f4a6fa41fc94bfd27c9a6b62b9.jpg",
    "banner_1": "/static/products/ee2603dcdecb4903b7e863231dddae76.jpg",
    "banner_2": "/static/products/ef22839bbc2444daa01ee8fe3df1e6aa.png",
    "banner_3": "/static/products/f138bddac50a45d183944f1994b2f332.jpg",
    "banner_4": "/static/products/f1c230fd55224ac496c25c131d9dea8d.jpg",
}


def _cat_id(db, name):
    category = db.query(Category).filter(Category.name == name).first()
    return category.id if category else None


def seed(db):
    # === 管理员 ===
    if not db.query(User).filter(User.username == "admin").first():
        db.add(
            User(
                username="admin",
                password_hash=hash_password("admin123"),
                email="admin@mall.com",
                role=UserRole.ADMIN,
            )
        )
        db.commit()
        print("[OK] admin / admin123")

    # === 演示用户 ===
    if not db.query(User).filter(User.username == "demo").first():
        db.add(
            User(
                username="demo",
                password_hash=hash_password("demo123"),
                email="demo@mall.com",
                phone="13800138000",
            )
        )
        db.commit()
        print("[OK] demo / demo123")

    # === 分类（按名称幂等补齐，可在已有库上增量执行） ===
    roots = [
        ("手机数码", 1, ["手机", "平板", "耳机", "智能手表"]),
        ("电脑办公", 2, ["笔记本", "台式机", "键鼠外设"]),
        ("家用电器", 3, ["大家电", "厨房电器", "生活电器"]),
        ("服饰鞋包", 4, ["男装", "女装", "运动鞋", "箱包"]),
        ("食品生鲜", 5, ["休闲零食", "茗茶冲饮", "生鲜水果"]),
    ]
    added_categories = 0
    for root_name, root_sort, subs in roots:
        root = (
            db.query(Category)
            .filter(Category.name == root_name, Category.parent_id.is_(None))
            .first()
        )
        if not root:
            root = Category(name=root_name, sort=root_sort)
            db.add(root)
            db.flush()
            added_categories += 1
        existing_subs = {
            c.name for c in db.query(Category).filter(Category.parent_id == root.id)
        }
        for idx, sub_name in enumerate(subs, start=1):
            if sub_name not in existing_subs:
                db.add(Category(name=sub_name, parent_id=root.id, sort=idx))
                added_categories += 1
    if added_categories:
        db.commit()
        print(f"[OK] categories added: {added_categories}")

    # === 商品与 SKU ===
    added_products = 0
    existing_names = {p.name for p in db.query(Product).all()}
    products = [
            (
                "iPhone 15 Pro Max",
                "6.7 英寸超视网膜 XDR 屏，A17 Pro 芯片，钛金属边框，4800 万像素三摄，续航最长 29 小时。",
                9999,
                _cat_id(db, "手机"),
                [
                    ("原色钛金属 256GB", {"颜色": "原色钛金属", "容量": "256GB"}, 9999, 60),
                    ("原色钛金属 512GB", {"颜色": "原色钛金属", "容量": "512GB"}, 11999, 40),
                    ("深黑钛金属 256GB", {"颜色": "深黑钛金属", "容量": "256GB"}, 9999, 30),
                ],
                [IMG["phone_1"]],
                326,
            ),
            (
                "华为 Mate 60 Pro",
                "麒麟 9000S 芯片，6.82 英寸 OLED 曲面屏，卫星通话，超可靠玄武架构，IP68 防水防尘。",
                6999,
                _cat_id(db, "手机"),
                [
                    ("雅丹黑 12+512GB", {"颜色": "雅丹黑", "存储": "512GB"}, 6999, 80),
                    ("白沙银 12+512GB", {"颜色": "白沙银", "存储": "512GB"}, 6999, 50),
                ],
                [IMG["phone_2"]],
                218,
            ),
            (
                "小米 14 Ultra",
                "骁龙 8 Gen 3，徕卡光学全焦段四摄，2K 全等深微曲屏，专业影像旗舰。",
                5999,
                _cat_id(db, "手机"),
                [
                    ("黑色 16+512GB", {"颜色": "黑色", "存储": "512GB"}, 5999, 120),
                    ("白色 16+1TB", {"颜色": "白色", "存储": "1TB"}, 6999, 40),
                ],
                [IMG["phone_3"]],
                166,
            ),
            (
                "三星 Galaxy S24 Ultra",
                "2 亿像素主摄，钛金属边框，内置 S Pen，骁龙 8 Gen 3 for Galaxy。",
                9499,
                _cat_id(db, "手机"),
                [("钛灰 12+512GB", {}, 9499, 45)],
                [IMG["phone_4"]],
                98,
            ),
            (
                "MacBook Pro 14 英寸",
                "M3 Pro 芯片，18GB 统一内存，Liquid 视网膜 XDR 屏，适合高性能办公与创作。",
                14999,
                _cat_id(db, "笔记本"),
                [
                    ("深空黑 18+512GB", {"颜色": "深空黑", "存储": "512GB"}, 14999, 30),
                    ("银色 18+1TB", {"颜色": "银色", "存储": "1TB"}, 17499, 20),
                ],
                [IMG["laptop_1"]],
                88,
            ),
            (
                "联想 ThinkPad X1 Carbon",
                "i7-1365U，16GB+512GB，1.12kg 轻薄商务本，军工级可靠。",
                9999,
                _cat_id(db, "笔记本"),
                [("黑色 i7/16GB/512GB", {}, 9999, 30)],
                [IMG["laptop_2"]],
                55,
            ),
            (
                "华为 MatePad Pro 13.2",
                "13.2 英寸 144Hz OLED 屏，星闪连接，鸿蒙多设备协同，办公学习好帮手。",
                5199,
                _cat_id(db, "平板"),
                [("曜金黑 12+512GB", {}, 5199, 60)],
                [IMG["phone_4"]],
                72,
            ),
            (
                "Apple Watch Series 9",
                "Always-On 视网膜屏，心率/血氧/睡眠监测，双指互点交互，续航 18 小时。",
                2999,
                _cat_id(db, "智能手表"),
                [
                    ("午夜色 41mm", {"颜色": "午夜色", "尺寸": "41mm"}, 2999, 100),
                    ("星光色 45mm", {"颜色": "星光色", "尺寸": "45mm"}, 3199, 80),
                ],
                [IMG["watch"]],
                210,
            ),
            (
                "AirPods Pro 第二代",
                "H2 芯片，主动降噪提升 2 倍，自适应通透模式，USB-C 充电盒。",
                1899,
                _cat_id(db, "耳机"),
                [("白色 USB-C 版", {}, 1899, 200)],
                [IMG["earphone_1"]],
                350,
            ),
            (
                "索尼 WH-1000XM5",
                "行业标杆降噪，30 小时续航，多点连接，Hi-Res 高解析度音质。",
                2499,
                _cat_id(db, "耳机"),
                [("黑色", {"颜色": "黑色"}, 2499, 60)],
                [IMG["earphone_2"]],
                79,
            ),
            (
                "罗技 MX Master 3S",
                "8K DPI 传感器，静音按键，MagSpeed 电磁滚轮，USB-C 充电。",
                699,
                _cat_id(db, "键鼠外设"),
                [("石墨黑", {"颜色": "石墨黑"}, 699, 150)],
                [IMG["mouse"]],
                260,
            ),
            (
                "海尔 500 升对开门冰箱",
                "风冷无霜，双变频一级能效，92L 大冷冻室，节能静音。",
                3999,
                _cat_id(db, "大家电"),
                [("星蕴银", {"颜色": "星蕴银"}, 3999, 25)],
                [IMG["fridge"]],
                40,
            ),
            (
                "戴森 V12 无绳吸尘器",
                "激光探测微尘，230AW 强劲吸力，60 分钟续航，整机密封过滤。",
                4290,
                _cat_id(db, "生活电器"),
                [("紫色", {"颜色": "紫色"}, 4290, 35)],
                [IMG["banner_4"]],
                63,
            ),
            (
                "Nike Air Max 270",
                "气垫缓震运动鞋，透气网面，黑白经典配色，日常百搭。",
                1199,
                _cat_id(db, "运动鞋"),
                [
                    ("黑白色 42", {"颜色": "黑白", "尺码": "42"}, 1199, 30),
                    ("黑白色 43", {"颜色": "黑白", "尺码": "43"}, 1199, 30),
                    ("黑白色 44", {"颜色": "黑白", "尺码": "44"}, 1199, 30),
                ],
                [IMG["shoes"]],
                205,
            ),
            (
                "新秀丽双肩包",
                "商务通勤 15.6 英寸电脑包，防泼水面料，独立电脑隔层，USB 外接充电口。",
                599,
                _cat_id(db, "箱包"),
                [("黑色", {"颜色": "黑色"}, 599, 90)],
                [IMG["bag"]],
                130,
            ),
            (
                "三只松鼠每日坚果礼盒",
                "30 包混合每日坚果，科学配比，独立小包装，营养早餐加餐好选择。",
                89.9,
                _cat_id(db, "休闲零食"),
                [("750g 30 包", {}, 89.9, 500)],
                [IMG["snack"]],
                810,
            ),
            (
                "明前龙井茶礼盒",
                "杭州西湖产区明前龙井，手工采摘，豆香馥郁，送礼自饮两相宜。",
                268,
                _cat_id(db, "茗茶冲饮"),
                [("200g 礼盒装", {}, 268, 120)],
                [IMG["tea"]],
                95,
            ),
    ]
    for name, desc, price, cat_id, skus, images, sales in products:
        if name in existing_names:
            continue
        product = Product(
            name=name,
            description=desc,
            price=price,
            stock=sum(s[2] for s in skus),
            images=images,
            category_id=cat_id,
            status=ProductStatus.ON,
            sales=sales,
        )
        db.add(product)
        db.flush()
        for sku_name, specs, sku_price, sku_stock in skus:
            db.add(
                ProductSku(
                    product_id=product.id,
                    name=sku_name,
                    specs=specs,
                    price=sku_price,
                    stock=sku_stock,
                )
            )
        existing_names.add(name)
        added_products += 1
    if added_products:
        db.commit()
        print(f"[OK] products with SKUs added: {added_products}")

    # === 兼容旧数据：无 SKU 的商品补默认规格 ===
    backfilled = 0
    for product in db.query(Product).all():
        if not product.skus:
            db.add(
                ProductSku(
                    product_id=product.id,
                    name="默认规格",
                    specs={},
                    price=product.price,
                    stock=product.stock,
                )
            )
            backfilled += 1
    if backfilled:
        db.commit()
        print(f"[OK] backfilled {backfilled} default SKU(s)")

    # === Banner ===
    if db.query(Banner).count() == 0:
        db.add_all(
            [
                Banner(
                    title="618 数码狂欢节",
                    image=IMG["banner_1"],
                    link="/search?keyword=手机",
                    sort=1,
                ),
                Banner(
                    title="新品首发 · 钛金属旗舰",
                    image=IMG["banner_2"],
                    link="/product/1",
                    sort=2,
                ),
                Banner(
                    title="轻食生活节",
                    image=IMG["banner_3"],
                    link="/search?keyword=坚果",
                    sort=3,
                ),
            ]
        )
        db.commit()
        print("[OK] banners")

    # === 知识库 ===
    existing_titles = {d.title for d in db.query(KnowledgeDoc.title).all()}
    docs = [
            (
                "退换货政策",
                KnowledgeCategory.REFUND,
                "自收到商品之日起 7 日内，商品保持完好且不影响二次销售的情况下，可申请无理由退货，退货运费由买家承担。如商品存在质量问题，运费由商家承担；15 日内可申请换货。退货商品需包含全部配件、赠品和包装。退款将在收到退货商品后 3-5 个工作日内原路返回。",
            ),
            (
                "配送说明",
                KnowledgeCategory.ORDER,
                "全国大部分地区支持配送。省会城市 1-3 天送达，地级市 2-4 天，县城及乡镇 3-7 天。订单满 99 元包邮，不满 99 元收取 8 元运费。默认使用顺丰快递或京东物流配送。您可以在订单详情页面查看物流信息。",
            ),
            (
                "支付方式与支付时限",
                KnowledgeCategory.ORDER,
                "本商城支持模拟收银台支付，后续将支持微信支付和支付宝。下单后请在 30 分钟内完成支付，超时未支付订单将自动取消并释放库存。支付遇到问题时请检查网络连接后重试。支付金额以订单确认页显示的金额为准。",
            ),
            (
                "售后保障",
                KnowledgeCategory.REFUND,
                "所有商品均享受国家三包政策。电子产品类商品享受 1 年质保服务。质保期内非人为损坏可免费维修。如需售后服务，请在订单详情页申请售后，上传问题描述和凭证图片，客服会在 24 小时内处理。紧急问题可拨打客服热线 400-888-8888。",
            ),
            (
                "如何申请退款",
                KnowledgeCategory.REFUND,
                "在「我的订单」中找到已支付、已发货或已完成的订单，点击「申请退款」，填写退款原因并提交。系统会生成退款申请，商家在 1-3 个工作日内审核。审核通过后，库存与销量自动回滚，退款金额将在 3-5 个工作日内原路退回。审核不通过时可联系在线客服申诉。",
            ),
            (
                "iPhone 15 Pro Max 产品介绍",
                KnowledgeCategory.PRODUCT,
                "iPhone 15 Pro Max 采用钛金属设计，配备 6.7 英寸超视网膜 XDR 显示屏，支持 ProMotion 自适应刷新率。搭载 A17 Pro 芯片，支持硬件加速光线追踪；4800 万像素主摄支持多焦段，5 倍光学变焦。USB-C 接口支持 USB 3 速度。电池续航最长 29 小时，支持 5G 全网通、Wi-Fi 6E 和蓝牙 5.3。",
            ),
            (
                "华为 Mate 60 Pro 产品介绍",
                KnowledgeCategory.PRODUCT,
                "华为 Mate 60 Pro 搭载麒麟 9000S 芯片，6.82 英寸 OLED 曲面屏，支持 1-120Hz LTPO 自适应刷新率。支持卫星通话功能，超可靠玄武架构，第二代昆仑玻璃。5000 万像素超感光主摄，物理光圈十档可调。5000mAh 大电池，88W 有线快充 + 50W 无线快充，IP68 级防水防尘。",
            ),
            (
                "如何修改收货地址",
                KnowledgeCategory.ORDER,
                "下单前可以在「个人中心 - 地址管理」中新增、编辑或删除收货地址，也可设置默认地址。下单时会保存地址快照，订单生成后修改地址不会影响已下单的订单。如需更改收货信息，请在订单未发货前联系在线客服协助处理。",
            ),
            (
                "如何联系人工客服",
                KnowledgeCategory.OTHER,
                "AI 客服 7x24 小时在线。如需人工服务，可在 AI 客服对话框中输入「转人工」或在订单详情页提交售后工单，客服热线为 400-888-8888，服务时间为每日 9:00-21:00。",
            ),
            (
                "会员与优惠说明",
                KnowledgeCategory.OTHER,
                "注册即可成为商城会员。收藏商品可获得新品提醒，热门商品按销量实时更新。商城会不定期推出限时优惠活动，具体以活动页面说明为准。优惠活动与退换货政策同时适用，使用优惠后的实付金额参与退款计算。",
            ),
    ]
    added_docs = 0
    for title, category, content in docs:
        if title in existing_titles:
            continue
        db.add(KnowledgeDoc(title=title, content=content, category=category))
        existing_titles.add(title)
        added_docs += 1
    if added_docs:
        db.commit()
        print(f"[OK] knowledge docs added: {added_docs}")

    # === RAG 评测用例 ===
    if db.query(EvalTestCase).count() == 0:
        cases = [
            ("收到商品后多久可以无理由退货？", "退换货政策"),
            ("订单要多少钱才能包邮？", "配送说明"),
            ("下单后多久内需要完成支付？", "支付方式与支付时限"),
            ("电子产品质保期是多久？", "售后保障"),
            ("怎么申请退款？", "如何申请退款"),
            ("iPhone 15 Pro Max 电池续航有多长？", "iPhone 15 Pro Max 产品介绍"),
            ("华为 Mate 60 Pro 支持卫星通话吗？", "华为 Mate 60 Pro 产品介绍"),
            ("怎么转人工客服？", "如何联系人工客服"),
        ]
        for question, title in cases:
            db.add(EvalTestCase(question=question, expected_title=title))
        db.commit()
        print(f"[OK] eval cases: {len(cases)}")


def main():
    db = SessionLocal()
    try:
        seed(db)
        if db.query(KnowledgeDoc).count():
            try:
                from app.ai.indexer import sync_all_knowledge

                count = sync_all_knowledge(db)
                print(f"[OK] vector index synced ({count} chunks)")
            except Exception as e:
                print(f"[WARN] vector index sync skipped: {e}")
        print("[DONE] seed finished")
    finally:
        db.close()


if __name__ == "__main__":
    main()
