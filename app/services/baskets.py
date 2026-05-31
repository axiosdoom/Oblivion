from __future__ import annotations

import logging
import statistics
from collections import defaultdict

from sqlalchemy.orm import Session

from app.models import Basket, Bond, BondBasketLink
from app.utils import maturity_to_group, rating_to_group, rating_to_score

logger = logging.getLogger(__name__)

MIN_BASKET_SIZE = 3


def build_baskets(db: Session) -> list[Basket]:
    db.query(BondBasketLink).delete()
    db.query(Basket).delete()
    db.flush()

    bonds = db.query(Bond).all()
    groups: dict[tuple[str, str], list[Bond]] = defaultdict(list)

    for bond in bonds:
        # Skip bonds with extremely short maturity or duration (< 0.1 years ≈ 36 days)
        if bond.years_to_maturity is not None and bond.years_to_maturity < 0.1:
            continue
        if bond.duration_years is not None and bond.duration_years < 0.1:
            continue

        rg = rating_to_group(bond.rating)
        mg = maturity_to_group(bond.years_to_maturity)
        if rg and mg:
            groups[(rg, mg)].append(bond)

    created_baskets: list[Basket] = []

    for (rg, mg), group_bonds in groups.items():
        if len(group_bonds) < MIN_BASKET_SIZE:
            continue

        basket_name = f"{rg} / {mg}"
        basket = Basket(
            name=basket_name,
            rating_group=rg,
            maturity_group=mg,
        )
        _compute_stats(basket, group_bonds)
        db.add(basket)
        db.flush()

        for bond in group_bonds:
            link = BondBasketLink(bond_id=bond.id, basket_id=basket.id)
            db.add(link)

        created_baskets.append(basket)

    db.flush()
    logger.info(f"Built {len(created_baskets)} baskets from {len(bonds)} bonds")
    return created_baskets


def _compute_stats(basket: Basket, bonds: list[Bond]) -> None:
    basket.bond_count = len(bonds)

    prices = [b.market_price_rub or (b.price_percent / 100 * b.nominal_rub if b.price_percent else None) for b in bonds]
    prices = [p for p in prices if p is not None]
    basket.avg_price_rub = statistics.mean(prices) if prices else None

    # Исключаем бескупонные (<=0.5%) и артефакты (>40%)
    ytms = [
        b.ytm_percent for b in bonds
        if b.ytm_percent is not None
           and 0.5 < b.ytm_percent <= 40.0
    ]

    if ytms:
        basket.avg_ytm = statistics.mean(ytms)
        basket.std_ytm = statistics.stdev(ytms) if len(ytms) > 1 else 0.0
    else:
        basket.avg_ytm = None
        basket.std_ytm = None

    durations = [b.duration_years for b in bonds if b.duration_years is not None]
    basket.avg_duration = statistics.mean(durations) if durations else None

    scores = [rating_to_score(b.rating) for b in bonds]
    scores = [s for s in scores if s is not None]
    basket.avg_rating_score = statistics.mean(scores) if scores else None