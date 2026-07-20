"""种子数据脚本 — 初始化管理员、分类、商品和知识库

运行方式: cd backend && python -m app.core.seed
"""

from sqlalchemy.orm import Session
from app.core.database import SessionLocal, engine
from app.models.base import Base
from app.models.user import User, UserRole
from app.models.product import Category, Product, ProductStatus
from app.models.knowledge import KnowledgeDoc, KnowledgeCategory
from app.core.security import hash_password

def seed(db: Session):
    # === 管理员 ===
    if not db.query(User).filter(User.username == "admin").first():
        admin = User(
            username="admin",
            password_hash=hash_password("admin123"),
            email="admin@mall.com",
            role=UserRole.ADMIN,
        )
        db.add(admin)
        db.commit()
        print("✅ 已创建管理员账号: admin / admin123")

    # === 分类 ===
    if db.query(Category).count() == 0:
        categories = [
            Category(id=1, name="手机数码", sort=1),
            Category(id=2, name="电脑办公", sort=2),
            Category(id=3, name="家用电器", sort=3),
            Category(id=4, name="服饰鞋包", sort=4),
            Category(id=5, name="食品生鲜", sort=5),
        ]
        # 手机数码子分类
        sub_categories = [
            Category(id=6, name="手机", parent_id=1, sort=1),
            Category(id=7, name="平板", parent_id=1, sort=2),
            Category(id=8, name="耳机", parent_id=1, sort=3),
            Category(id=9, name="智能手表", parent_id=1, sort=4),
            # 电脑办公子分类
            Category(id=10, name="笔记本", parent_id=2, sort=1),
            Category(id=11, name="台式机", parent_id=2, sort=2),
            Category(id=12, name="键盘鼠标", parent_id=2, sort=3),
        ]
        db.add_all(categories + sub_categories)
        db.commit()
        print(f"✅ 已创建 {len(categories) + len(sub_categories)} 个分类")

    # === 商品 ===
    if db.query(Product).count() == 0:
        products = [
            Product(name="iPhone 15 Pro Max", description="苹果智能手机 256GB 原色钛金属 支持5G全网通 A17 Pro芯片 高端旗舰手机", price=9999.00, stock=100, sales=256, category_id=6, images=[]),
            Product(name="华为 Mate 60 Pro", description="华为智能手机 12GB+512GB 雅丹黑 卫星通话 超可靠玄武架构 国产旗舰手机", price=6999.00, stock=80, sales=189, category_id=6, images=[]),
            Product(name="小米14 Ultra", description="小米智能手机 16GB+512GB 专业影像 骁龙8Gen3 徕卡光学 旗舰手机", price=5999.00, stock=120, sales=145, category_id=6, images=[]),
            Product(name="MacBook Pro 14英寸", description="苹果笔记本电脑 M3 Pro芯片 18GB+512GB 深空黑色 高性能办公电脑", price=14999.00, stock=50, sales=88, category_id=10, images=[]),
            Product(name="联想 ThinkPad X1 Carbon", description="联想笔记本电脑 i7-1365U 16GB+512GB 商务旗舰 轻薄便携电脑", price=9999.00, stock=30, sales=42, category_id=10, images=[]),
            Product(name="AirPods Pro 第二代", description="苹果蓝牙耳机 主动降噪 自适应音频 USB-C充电盒 无线耳机", price=1899.00, stock=200, sales=320, category_id=8, images=[]),
            Product(name="索尼 WH-1000XM5 头戴式耳机", description="索尼无线降噪头戴式耳机 30小时续航 黑色 高解析度音频", price=2499.00, stock=60, sales=67, category_id=8, images=[]),
            Product(name="罗技 MX Master 3S 鼠标", description="罗技无线蓝牙鼠标 8K DPI USB-C充电 静音按键 办公游戏两用", price=699.00, stock=150, sales=234, category_id=12, images=[]),
            Product(name="海尔 500升冰箱", description="海尔家用电器 500升冰箱 风冷无霜 双变频 一级能效 节能静音", price=3999.00, stock=25, sales=36, category_id=3, images=[]),
            Product(name="Nike Air Max 270", description="Nike男子运动鞋 气垫 黑白配色 休闲百搭 透气舒适", price=1199.00, stock=90, sales=178, category_id=4, images=[]),
        ]
        db.add_all(products)
        db.commit()
        print(f"✅ 已创建 {len(products)} 个商品")

    # === 知识库 ===
    if db.query(KnowledgeDoc).count() == 0:
        knowledge_docs = [
            KnowledgeDoc(
                title="退换货政策",
                content="自收到商品之日起7日内，商品保持完好且不影响二次销售的情况下，可申请无理由退货，退货运费由买家承担。如商品存在质量问题，运费由商家承担，15日内可申请换货。退货商品需包含全部配件、赠品和包装。退款将在收到退货商品后3-5个工作日原路返回。",
                category=KnowledgeCategory.REFUND,
            ),
            KnowledgeDoc(
                title="配送说明",
                content="全国大部分地区支持配送。省会城市1-3天送达，地级市2-4天，县城及乡镇3-7天。订单满99元包邮，不满99元收取8元运费。默认使用顺丰快递或京东物流配送。您可以在订单详情页面查看物流信息。",
                category=KnowledgeCategory.ORDER,
            ),
            KnowledgeDoc(
                title="支付方式",
                content="本商城支持微信支付和支付宝两种支付方式。下单后请在30分钟内完成支付，超时未支付订单将自动取消。如支付遇到问题，请检查网络连接后重试，或更换支付方式。支付金额以订单确认页显示的金额为准。",
                category=KnowledgeCategory.ORDER,
            ),
            KnowledgeDoc(
                title="售后保障",
                content="所有商品均享受国家三包政策。电子产品类商品享受1年质保服务。质保期内非人为损坏可免费维修。如需售后服务，请在订单详情页申请售后，上传问题描述和凭证图片，客服会在24小时内处理。紧急问题可拨打客服热线400-888-8888。",
                category=KnowledgeCategory.REFUND,
            ),
            KnowledgeDoc(
                title="iPhone 15 Pro Max 产品介绍",
                content="iPhone 15 Pro Max 采用钛金属设计，配备6.7英寸超视网膜XDR显示屏，支持ProMotion自适应刷新率技术。搭载A17 Pro芯片，支持硬件加速光线追踪。4800万像素主摄支持多种焦距，5倍光学变焦。USB-C接口，支持USB 3速度。电池续航最长29小时。支持5G全网通、Wi-Fi 6E和蓝牙5.3。",
                category=KnowledgeCategory.PRODUCT,
            ),
            KnowledgeDoc(
                title="华为 Mate 60 Pro 产品介绍",
                content="华为 Mate 60 Pro 搭载麒麟9000S芯片，6.82英寸OLED曲面屏，支持1-120Hz LTPO自适应刷新率。支持卫星通话功能，超可靠玄武架构，第二代昆仑玻璃。5000万像素超感知主摄，物理光圈十档可调。5000mAh大电池，88W有线快充+50W无线快充。IP68级防水防尘。",
                category=KnowledgeCategory.PRODUCT,
            ),
        ]
        db.add_all(knowledge_docs)
        db.commit()
        print(f"✅ 已创建 {len(knowledge_docs)} 个知识库文档")

def main():
    # 确保表已创建
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed(db)
        print("\n🎉 种子数据初始化完成！")
    finally:
        db.close()

if __name__ == "__main__":
    main()
