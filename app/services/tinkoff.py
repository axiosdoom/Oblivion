from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from app.utils import quotation_to_float, money_to_float

logger = logging.getLogger(__name__)

try:
    from t_tech.invest import Client  # type: ignore
    _SDK = "t-tech-investments"
except Exception:
    try:
        from tinkoff.invest import Client  # type: ignore
        _SDK = "tinkoff-investments"
    except Exception:
        Client = None  # type: ignore
        _SDK = "not-installed"


def sdk_name() -> str:
    return _SDK


@dataclass
class TinkoffBond:
    figi: str
    isin: str
    ticker: str
    name: str
    nominal: float
    currency: str
    coupon_quantity_per_year: int
    maturity_date: date | None
    floating_coupon_flag: bool
    amortization_flag: bool


@dataclass
class TinkoffCoupon:
    coupon_date: date
    pay_one_bond: float
    coupon_number: int
    coupon_type: str


def get_all_bonds(token: str) -> list[TinkoffBond]:
    if Client is None:
        logger.error("Tinkoff SDK not installed")
        return []

    result: list[TinkoffBond] = []
    try:
        with Client(token) as client:
            resp = client.instruments.bonds()
            for b in resp.instruments:
                mat_date = None
                if hasattr(b, "maturity_date") and b.maturity_date:
                    try:
                        mat_date = b.maturity_date.date() if hasattr(b.maturity_date, "date") else b.maturity_date
                    except Exception:
                        mat_date = None

                nominal = 1000.0
                if hasattr(b, "nominal"):
                    nominal = money_to_float(b.nominal)
                elif hasattr(b, "initial_nominal"):
                    nominal = money_to_float(b.initial_nominal)

                currency = "RUB"
                if hasattr(b, "currency"):
                    currency = str(b.currency).upper()

                result.append(TinkoffBond(
                    figi=b.figi,
                    isin=getattr(b, "isin", ""),
                    ticker=getattr(b, "ticker", ""),
                    name=getattr(b, "name", ""),
                    nominal=nominal if nominal > 0 else 1000.0,
                    currency=currency,
                    coupon_quantity_per_year=getattr(b, "coupon_quantity_per_year", 0),
                    maturity_date=mat_date,
                    floating_coupon_flag=getattr(b, "floating_coupon_flag", False),
                    amortization_flag=getattr(b, "amortization_flag", False),
                ))
    except Exception as e:
        logger.error(f"Failed to fetch bonds from Tinkoff: {e}")

    logger.info(f"Fetched {len(result)} bonds from Tinkoff API")
    return result


def get_last_prices(token: str, figis: list[str]) -> dict[str, float]:
    if Client is None or not figis:
        return {}

    prices: dict[str, float] = {}
    batch_size = 100

    try:
        with Client(token) as client:
            for i in range(0, len(figis), batch_size):
                batch = figis[i:i + batch_size]
                try:
                    resp = client.market_data.get_last_prices(
                        instrument_id=batch
                    )
                except TypeError:
                    resp = client.market_data.get_last_prices(
                        figi=batch
                    )

                for lp in resp.last_prices:
                    figi = getattr(lp, "figi", "") or getattr(lp, "instrument_uid", "")
                    price = quotation_to_float(lp.price)
                    if price > 0:
                        prices[figi] = price
    except Exception as e:
        logger.error(f"Failed to fetch prices from Tinkoff: {e}")

    logger.info(f"Fetched {len(prices)} prices from Tinkoff API")
    return prices


def get_bond_coupons(token: str, figi: str) -> list[TinkoffCoupon]:
    if Client is None:
        return []

    result: list[TinkoffCoupon] = []
    try:
        with Client(token) as client:
            from datetime import datetime, timezone
            resp = client.instruments.get_bond_coupons(
                figi=figi,
                from_=datetime(2020, 1, 1, tzinfo=timezone.utc),
                to=datetime(2040, 1, 1, tzinfo=timezone.utc),
            )
            for c in resp.events:
                c_date = c.coupon_date
                if hasattr(c_date, "date"):
                    c_date = c_date.date()

                pay = 0.0
                if hasattr(c, "pay_one_bond"):
                    pay = money_to_float(c.pay_one_bond)

                c_type = "UNKNOWN"
                if hasattr(c, "coupon_type"):
                    c_type = str(c.coupon_type)

                result.append(TinkoffCoupon(
                    coupon_date=c_date,
                    pay_one_bond=pay,
                    coupon_number=getattr(c, "coupon_number", 0),
                    coupon_type=c_type,
                ))
    except Exception as e:
        logger.error(f"Failed to fetch coupons for {figi}: {e}")

    return result
