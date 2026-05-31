from __future__ import annotations

import logging

import numpy as np
from sqlalchemy.orm import Session

from app.config import CURVE_ANOMALY_ZSCORE, PRICE_ANOMALY_BY_RATING, YIELD_ANOMALY_BY_RATING
from app.models import Basket, Bond, BondBasketLink, Valuation
from app.utils import get_risk_premium

logger = logging.getLogger(__name__)


def compute_comparisons(db: Session, key_rate: float) -> int:
    baskets = db.query(Basket).all()
    total = 0

    for basket in baskets:
        links = db.query(BondBasketLink).filter_by(basket_id=basket.id).all()
        bond_ids = [lnk.bond_id for lnk in links]
        if not bond_ids:
            continue

        bonds = db.query(Bond).filter(Bond.id.in_(bond_ids)).all()

        yield_curve = _fit_yield_curve(bonds)

        for bond in bonds:
            val = (
                db.query(Valuation)
                .filter_by(bond_id=bond.id, basket_id=basket.id)
                .first()
            )
            if not val:
                val = db.query(Valuation).filter_by(bond_id=bond.id).order_by(Valuation.id.desc()).first()

            if not val:
                continue



            market_price = bond.market_price_rub
            if not market_price and bond.price_percent and bond.nominal_rub:
                market_price = bond.price_percent / 100.0 * bond.nominal_rub

            val.market_price_rub = market_price
            val.basket_id = basket.id

            if val.calc_primary and market_price and market_price > 0:
                val.delta_price = abs(val.calc_primary - market_price) / market_price * 100.0
            else:
                val.delta_price = None

            if bond.ytm_percent is not None and basket.avg_ytm is not None:
                val.delta_yield = bond.ytm_percent - basket.avg_ytm
            else:
                val.delta_yield = None

            if yield_curve is not None and bond.duration_years is not None and bond.ytm_percent is not None:
                try:
                    fitted_ytm = float(np.polyval(yield_curve["coeffs"], bond.duration_years))
                    val.delta_curve = bond.ytm_percent - fitted_ytm
                    if yield_curve["std"] and yield_curve["std"] > 0:
                        val.delta_curve_zscore = val.delta_curve / yield_curve["std"]
                    else:
                        val.delta_curve_zscore = None
                except Exception:
                    val.delta_curve = None
                    val.delta_curve_zscore = None
            else:
                val.delta_curve = None
                val.delta_curve_zscore = None

            rho = get_risk_premium(bond.rating)
            if bond.ytm_percent is not None and rho > 0:
                val.risk_adjusted_yield = (bond.ytm_percent / 100.0 - key_rate) / rho
            else:
                val.risk_adjusted_yield = None

            val.color = _classify_color(val, bond)
            val.yield_symbol = _classify_yield_symbol(val.delta_yield)
            # Передаём рейтинг облигации в _classify_anomaly
            val.anomaly_code = _classify_anomaly(val, bond.rating, bond.ytm_percent)

            total += 1

    db.flush()
    logger.info(f"Computed comparisons for {total} bonds")
    return total


def _fit_yield_curve(bonds: list[Bond]) -> dict | None:
    points = [
        (b.duration_years, b.ytm_percent)
        for b in bonds
        if b.duration_years is not None and b.ytm_percent is not None and b.duration_years > 0
    ]
    if len(points) < 5:
        return None

    durations = np.array([p[0] for p in points])
    ytms = np.array([p[1] for p in points])

    try:
        coeffs = np.polyfit(durations, ytms, min(2, len(points) - 1))
        fitted = np.polyval(coeffs, durations)
        residuals = ytms - fitted
        std = float(np.std(residuals)) if len(residuals) > 1 else 0.0
        return {"coeffs": coeffs, "std": std, "durations": durations, "ytms": ytms}
    except Exception:
        return None


def _classify_color(val: Valuation, bond: Bond) -> str:
    price_threshold_for_color = 10.0

    # Особые случаи
    if bond.offer_date or bond.is_floating_coupon or bond.is_amortizing:
        return "conditions"

    # Если нет данных для сравнения
    if val.delta_price is None or val.calc_primary is None or val.market_price_rub is None:
        return "neutral"

    # Только если отклонение превышает порог
    if val.delta_price > price_threshold_for_color:
        if val.calc_primary > val.market_price_rub:
            return "undervalued"  # недооценена — сигнал к покупке
        else:
            return "overvalued"  # переоценена — сигнал не покупать

    return "fair"  # справедливая цена


def _classify_yield_symbol(delta_yield: float | None) -> str:
    if delta_yield is None:
        return "→"
    if delta_yield > 1.0:
        return "↑↑"
    if delta_yield > 0.5:
        return "↑"
    if delta_yield < -1.0:
        return "↓↓"
    if delta_yield < -0.5:
        return "↓"
    return "→"


def _classify_anomaly(val: Valuation, rating: str | None = None, bond_ytm: float | None = None) -> str | None:
    # Если YTM = 0.0 или None — не даём аномалию (бескупонные, дефолтные, мусор)
    if bond_ytm is None or bond_ytm <= 0.01:
        return None

    # Если YTM слишком высокий (>40%) — артефакт/дефолт, не даём аномалию
    if bond_ytm > 40.0:
        return None

    # Выбираем пороги по рейтингу (по умолчанию как для B)
    price_threshold = PRICE_ANOMALY_BY_RATING.get(rating, PRICE_ANOMALY_BY_RATING["B"])
    yield_threshold = YIELD_ANOMALY_BY_RATING.get(rating, YIELD_ANOMALY_BY_RATING["B"])

    # Ценовая аномалия: только если расчётная цена > рыночной (недооценка) и delta_price > порога
    price_anom = False
    if (val.calc_primary is not None and val.market_price_rub is not None and
            val.calc_primary > val.market_price_rub and
            val.delta_price is not None and val.delta_price > price_threshold):
        price_anom = True

    # Доходностная аномалия: только если доходность выше средней по корзине на > порога
    yield_anom = val.delta_yield is not None and val.delta_yield > yield_threshold

    # Кривая аномалия: только если облигация выше кривой (положительный z-score) и > порога
    curve_anom = val.delta_curve_zscore is not None and val.delta_curve_zscore > CURVE_ANOMALY_ZSCORE

    if price_anom and yield_anom:
        return "P+Y+"
    if price_anom:
        return "P+"
    if yield_anom:
        return "Y+"
    if curve_anom:
        return "C+"

    return None


def get_yield_curve_data(db: Session, basket_id: int) -> dict | None:
    links = db.query(BondBasketLink).filter_by(basket_id=basket_id).all()
    bond_ids = [lnk.bond_id for lnk in links]
    if not bond_ids:
        return None

    bonds = db.query(Bond).filter(Bond.id.in_(bond_ids)).all()
    points = [
        {
            "duration": b.duration_years,
            "ytm": b.ytm_percent,
            "name": b.name,
            "bond_id": b.id,
        }
        for b in bonds
        if b.duration_years is not None and b.ytm_percent is not None
    ]

    if len(points) < 3:
        return {"points": points, "curve": []}

    durations = np.array([p["duration"] for p in points])
    ytms = np.array([p["ytm"] for p in points])

    try:
        coeffs = np.polyfit(durations, ytms, min(2, len(points) - 1))
        d_min, d_max = float(durations.min()), float(durations.max())
        d_range = np.linspace(d_min, d_max, 50)
        fitted = np.polyval(coeffs, d_range)
        curve = [{"duration": float(d), "ytm": float(y)} for d, y in zip(d_range, fitted)]
    except Exception:
        curve = []

    return {"points": points, "curve": curve}