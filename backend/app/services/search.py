"""商品搜索的查询理解层：归一化、分词、同义词、匹配条件。

这层只干一件事：**把「用户敲进来的字」和「商品文案里写的字」对齐**。
不对齐的来源会不断增加，但只有三类：

1. **形式差异**——大小写、空格、连字符（用户敲 `mate60`，文案写 `Mate 60`；
   敲 `wh1000xm5`，文案写 `WH-1000XM5`）、全角半角、容量单位写法（`512G` / `512GB`）。
   解法是**统一的归一化管道**：查询侧和文案侧走同一套变换，差异自然消失。
2. **分词差异**——`华为手机` 必须拆成两个词分别匹配，而不是当一个整串。
3. **用词差异**——`鞋子` vs `运动鞋`、`苹果` vs `iPhone`。这类没有算法能推出来，
   只能靠**数据**（见 ``search_synonyms.py``）。

上一版把第 3 类当成特例写死在检索逻辑里（给「鞋子」加了一条「去掉名词后缀」的规则），
结果马上又需要一份「哪些词不该截断」的例外表。现在的分工是：
**代码里只有通用管道，所有词形/用词差异都是数据。**

还有一条兜底：多词查询里只要有一个词不认识，AND 就会一条不剩，
所以 AND 为空时会退化成 OR，并用「名称命中词数」把最贴合的排前面。

已知边界（诚实写在这里，别在外面吹）：

- 错别字、拼音输入（`huawEI` / `华威`）需要拼音索引或编辑距离，本层不做；
- 简繁转换需要 opencc 之类的词典，本层不做；
- LIKE `%x%` 用不到索引，数据量上来应换成物化的归一化搜索列或搜索引擎（ES/OpenSearch）。
"""

import re
import unicodedata
from typing import List, Optional, Sequence

import jieba
from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Query, Session

from app.models.product import Category, Product, ProductStatus
from app.models.sku import ProductSku
from app.services.search_synonyms import load_synonyms

# 词的分隔符：空白、中英文逗号/顿号/分号/斜杠等
_TERM_SPLIT = re.compile(r"[\s,，、;；/|+]+")
# 归一化时要抹掉的字符：空白、连字符、下划线、间隔号——用户几乎不会在意这些
_NOISE = re.compile(r"[\s\-_·]+")
_CJK_ONLY = re.compile(r"^[\u4e00-\u9fff]+$")
# 容量写法：512g / 512gb / 1t / 1tb —— 同一件事的四种写法
_SIZE = re.compile(r"^(\d+)(g|gb|t|tb)$")


def normalize(text: str) -> str:
    """把一段文本归一化成「比较用」的形式。

    NFKC（全角转半角、兼容字符归一）+ 小写 + 抹掉空白与连字符。
    **查询侧和文案侧必须用同一个函数**，否则归一化只会制造新的不一致。
    """
    if not text:
        return ""
    return _NOISE.sub("", unicodedata.normalize("NFKC", text).lower())


def _size_variants(term: str) -> List[str]:
    """容量写法的等价形：512g ↔ 512gb、1t ↔ 1tb。"""
    match = _SIZE.fullmatch(term)
    if not match:
        return []
    number, unit = match.group(1), match.group(2)
    if unit in ("g", "gb"):
        return [f"{number}g", f"{number}gb"]
    return [f"{number}t", f"{number}tb"]


def _dedupe(items: Sequence[str]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def variants_for(term: str) -> List[str]:
    """一个词的候选写法：自身 + 同义词 + 容量单位等价形。"""
    term = normalize(term)
    if not term:
        return []
    candidates = [term, *load_synonyms().get(term, ())]
    result: List[str] = []
    for candidate in candidates:
        normalized = normalize(candidate)
        result.append(normalized)
        # 同义词本身也可能带单位（用户配「1t」这种写法时）
        if _SIZE.fullmatch(normalized):
            result.extend(_size_variants(normalized))
    return _dedupe(result)


def parse_query(keyword: str) -> List[List[str]]:
    """把用户输入解析成「词分组」：组内是候选写法（OR），组间是 AND。

    ``"华为 手机"`` → ``[['华为'], ['手机']]``
    ``"鞋子"``     → ``[['鞋子', '鞋']]``
    ``"Mate 60"``  → ``[['mate'], ['60']]``
    """
    groups: List[List[str]] = []
    for chunk in _TERM_SPLIT.split(keyword.strip()):
        if not chunk:
            continue
        normalized = normalize(chunk)
        if not normalized:
            continue

        terms = [normalized]
        # 中文长词再切一层：「华为手机」→ 华为 + 手机。
        # 只切纯中文且长度 > 2 的片段；「鞋子」这种两字词交给同义词表处理，
        # 硬切只会得到没有意义的单字。
        if len(normalized) > 2 and _CJK_ONLY.match(normalized):
            tokens = [
                normalize(token)
                for token in jieba.lcut(normalized)
                if len(token) >= 2 and _CJK_ONLY.match(token)
            ]
            if len(tokens) > 1:
                terms = tokens

        for term in terms:
            variants = variants_for(term)
            if variants:
                groups.append(variants)
    return groups


def _normalized_column(column):
    """与 ``normalize()`` 等价的 SQL 表达式（小写 + 去空格 + 去连字符）。

    刻意用 SQL 表达式而不是新增一列物化的搜索文本：省掉一次迁移、一次回填，
    以及最麻烦的「改了商品/SKU/分类却忘了刷新索引」的维护负担。
    代价是每列多两次函数调用——反正 `%x%` 本来也用不到索引；
    数据量上来后应该改成物化列或搜索引擎（见模块文档的已知边界）。
    """
    return func.replace(func.replace(func.lower(column), " ", ""), "-", "")


def _sku_condition(db: Session, term: str):
    """该商品的任一 SKU 名称包含 term（用 EXISTS，避免 join 出重复行）。"""
    pattern = f"%{term}%"
    return (
        db.query(ProductSku.id)
        .filter(
            ProductSku.product_id == Product.id,
            _normalized_column(ProductSku.name).like(pattern),
        )
        .exists()
    )


def group_condition(db: Session, variants: Sequence[str]):
    """一个词分组的 SQL 条件：任一写法命中任一字段即可。"""
    conditions = []
    for term in variants:
        pattern = f"%{term}%"
        conditions.extend(
            [
                _normalized_column(Product.name).like(pattern),
                _normalized_column(Product.description).like(pattern),
                _normalized_column(Category.name).like(pattern),
                _sku_condition(db, term),
            ]
        )
    return or_(*conditions)


def name_relevance(groups: Sequence[Sequence[str]]):
    """相关度：名称命中了几个词。搜「手机」时名字里带「手机」的应该排在前面。"""
    return sum(
        case((_normalized_column(Product.name).like(f"%{term}%"), 1), else_=0)
        for variants in groups
        for term in variants
    )


def apply_product_search(db: Session, base_query: Query, keyword: Optional[str]):
    """给在售商品查询加上搜索条件，返回 ``(query, 相关度表达式或 None)``。

    - 正常：组间 AND（每个词都要命中）
    - 兜底：AND 一条结果都没有时退化成 OR——多词查询里只要有一个词不认识，
      AND 就会归零，此时给出部分匹配比给一个空页面有用
    """
    if not keyword:
        return base_query, None

    groups = parse_query(keyword)
    if not groups:
        return base_query, None

    joined = base_query.outerjoin(Category, Product.category_id == Category.id)
    strict = joined.filter(and_(*[group_condition(db, g) for g in groups]))

    if len(groups) > 1 and strict.count() == 0:
        relaxed = joined.filter(or_(*[group_condition(db, g) for g in groups]))
        if relaxed.count():
            return relaxed, name_relevance(groups)

    return strict, name_relevance(groups)


# --- 搜索建议（autocomplete）---
#
# 与真正的检索分开实现，因为两者的目标不同：
#   - 检索要「**找全**」：宁可多召回再由相关度排序，所以走同义词、AND→OR 兜底；
#   - 建议要「**补全**」：用户敲了前缀，就该看到以这个前缀开头的候选，
#     而不是一堆「因为近义才相关」的东西。给错候选比没候选更糟——
#     用户会顺着它去搜，然后得到莫名其妙的空结果。
#
# 因此这里的匹配规则刻意简单：**归一化后的前缀/子串匹配**，不做同义词扩展。
# 唯一用到同义词的地方是「反向」的：用户敲「鞋子」时，也把映射到「鞋」的
# 商品名候选带出来——这是补全该做的事，不是检索的事。


def _suggestion_candidates(db: Session, limit_titles: int = 200) -> List[dict]:
    """收集候选池：商品名 + 分类名 + SKU 名。

    候选池是有上限的（商品名取销量前 N），因为自动补全要「快」：
    数据量大了以后这里应该换成专门的补全索引（如 ES completion suggester），
    或者把候选物化成一张表。当前 59 个商品直接查库完全够用。
    """
    candidates: List[dict] = []

    for product in (
        db.query(Product.name, Product.id)
        .filter(Product.status == ProductStatus.ON)
        .order_by(Product.sales.desc(), Product.id.asc())
        .limit(limit_titles)
        .all()
    ):
        candidates.append(
            {"text": product.name, "type": "product", "product_id": product.id}
        )

    for category in db.query(Category.name, Category.id).all():
        candidates.append(
            {"text": category.name, "type": "category", "category_id": category.id}
        )

    # SKU 名里有「白色 16+1TB」这类，直接当前缀补全没有价值，
    # 但品牌/型号类词（如「钛灰」）偶尔会被用户当关键词敲，保留一部分。
    for (sku_name,) in (
        db.query(ProductSku.name).distinct().limit(limit_titles).all()
    ):
        if sku_name and sku_name != "默认规格":
            candidates.append({"text": sku_name, "type": "sku"})

    return candidates


def suggest(keyword: str, limit: int = 8, db: Optional[Session] = None) -> List[dict]:
    """按用户已输入的内容返回补全候选。

    排序规则（越靠前越该被选中）：

    1. **前缀命中**优先于中间命中——用户敲「手机」时，「手机数码」比
       「双卡双待手机」更可能是他想找的。
    2. 同类里**短词优先**——短词是更「通用」的概念。
    3. 商品名 > 分类名 > SKU 名：商品是最终目标，分类是导航。

    返回形如 ``[{"text": "手机数码", "type": "category"}, ...]``。
    """
    if db is None:
        raise ValueError("suggest() 需要 db 会话")

    query = normalize(keyword or "")
    if not query:
        return []

    # 同义词的反向查找：用户敲「鞋子」，把映射到「鞋」的候选也带出来。
    # 注意方向——是「这个词的同义词有哪些」，不是「把候选扩展成近义词」。
    synonym_terms = set(variants_for(keyword)) - {query}
    # 中文单字同义词是**有效**的（鞋 / 帽 / 袜 / 裤 / 裙 都在同义词表里），
    # 一开始写了 `len(t) >= 2` 想把噪音过滤掉，结果把「鞋子 → 鞋 → 运动鞋」
    # 这条链整段关掉了。噪音的正确处理方式是靠排序把它排到最后，
    # 而不是在匹配阶段就把候选排除掉——排除掉就再也回不来了。
    synonym_terms = {t for t in synonym_terms if t}

    ranked: List[tuple] = []
    seen_texts = set()
    for candidate in _suggestion_candidates(db):
        text = candidate["text"]
        if not text or text in seen_texts:
            continue
        normalized = normalize(text)
        if not normalized:
            continue

        if normalized.startswith(query):
            rank = (0, len(text))
        elif query in normalized:
            rank = (1, len(text))
        elif any(normalized.startswith(t) or t in normalized for t in synonym_terms):
            # 同义词命中的排最后：它是「可能相关」，不如字面命中可靠
            rank = (2, len(text))
        else:
            continue

        # 同 rank 内按类型加权：商品 > 分类 > SKU
        type_weight = {"product": 0, "category": 1, "sku": 2}.get(candidate["type"], 3)
        ranked.append((rank[0], type_weight, rank[1], candidate))
        seen_texts.add(text)

    ranked.sort(key=lambda item: (item[0], item[1], item[2]))

    results: List[dict] = []
    for *_, candidate in ranked[:limit]:
        item = {"text": candidate["text"], "type": candidate["type"]}
        if "product_id" in candidate:
            item["product_id"] = candidate["product_id"]
        if "category_id" in candidate:
            item["category_id"] = candidate["category_id"]
        results.append(item)
    return results
