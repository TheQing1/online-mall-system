from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.orm import sessionmaker

from app.services import cart_service, order_service

from tests.conftest import create_address, create_product


def test_sequential_oversell_blocked(client, db, user):
    product = create_product(db, "限量商品", skus=[("S", {}, 100, 3)])
    sku = product.skus[0]
    addr = create_address(db, user)
    headers = {"Authorization": "unused"}
    # 直接用服务层，走真实的原子扣减 SQL
    created = 0
    for _ in range(4):
        try:
            cart_service.add_cart_item(db, user, product.id, 1, sku.id)
        except Exception:
            break
        try:
            order_service.create_order(db, user, addr.id)
            created += 1
        except Exception:
            pass
        # 清空购物车便于下一轮尝试
        db.expire_all()
        from app.services import cart_service as cs

        for item in cs.get_cart_items(db, user):
            db.delete(item)
        db.commit()

    assert created == 3
    db.refresh(product)
    assert product.stock == 0


def test_concurrent_orders_no_oversell(db, user):
    """多线程并发下单：原子条件更新保证 8 个用户只能抢到 3 件。"""
    from app.core.security import hash_password
    from app.models.user import User

    product = create_product(db, "并发商品", skus=[("S", {}, 100, 3)])
    sku = product.skus[0]

    users = [user]
    for i in range(7):
        u = User(username=f"race_{i}", password_hash=hash_password("123456"))
        db.add(u)
        db.flush()
        users.append(u)

    targets = []
    for u in users:
        addr = create_address(db, u)
        cart_service.add_cart_item(db, u, product.id, 1, sku.id)
        targets.append((u.id, addr.id))
    db.commit()

    engine = db.get_bind()
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def place_order(target):
        uid, addr_id = target
        s = Session()
        try:
            from app.models.user import User as UserModel

            u = s.query(UserModel).filter(UserModel.id == uid).first()
            order_service.create_order(s, u, addr_id)
            return True
        except Exception:
            s.rollback()
            return False
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(place_order, targets))

    assert sum(results) == 3

    from app.models.product import Product

    final_product = db.query(Product).filter(Product.id == product.id).first()
    assert final_product.stock == 0
