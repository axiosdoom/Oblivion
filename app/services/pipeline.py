from __future__ import annotations

import logging
from datetime import date

from sqlalchemy.orm import Session

from app.config import DEFAULT_INFLATION_PREMIUM, TINKOFF_TOKEN
from app.models import Bond, Coupon, MacroData, Valuation

logger = logging.getLogger(__name__)


def run_full_pipeline(db: Session, token: str | None = None) -> dict:
    token = token or TINKOFF_TOKEN
    stats: dict = {
        "bonds_scraped": 0,
        "bonds_matched": 0,
        "prices_fetched": 0,
        "key_rate": None,
        "baskets_formed": 0,
        "valuations_computed": 0,
        "comparisons_computed": 0,
        "anomalies_found": 0,
        "errors": [],
    }

    # 1. Scrape SmartLab
    try:
        from app.services.smartlab import scrape_all_bonds
        raw_bonds = scrape_all_bonds()
        stats["bonds_scraped"] = len(raw_bonds)
        _upsert_bonds(db, raw_bonds)
        db.commit()
    except Exception as e:
        logger.error(f"SmartLab scraping failed: {e}")
        stats["errors"].append(f"SmartLab: {e}")
        db.rollback()

    # 2. Enrich from Tinkoff (match ISIN, get FIGI)
    if token:
        try:
            from app.services.tinkoff import get_all_bonds
            tinkoff_bonds = get_all_bonds(token)
            matched = _match_tinkoff_bonds(db, tinkoff_bonds)
            stats["bonds_matched"] = matched
            db.commit()
        except Exception as e:
            logger.error(f"Tinkoff bond matching failed: {e}")
            stats["errors"].append(f"Tinkoff match: {e}")
            db.rollback()

        # 3. Fetch prices
        try:
            from app.services.tinkoff import get_last_prices
            figis = [b.figi for b in db.query(Bond).filter(Bond.figi.isnot(None)).all()]
            if figis:
                prices = get_last_prices(token, figis)
                updated = _update_prices(db, prices)
                stats["prices_fetched"] = updated
                db.commit()
        except Exception as e:
            logger.error(f"Tinkoff price fetch failed: {e}")
            stats["errors"].append(f"Tinkoff prices: {e}")
            db.rollback()

    # 4. Fetch CBR key rate
    key_rate = 0.21  # fallback
    try:
        from app.services.cbr import fetch_key_rate
        result = fetch_key_rate()
        if result:
            key_rate, rate_date = result
            stats["key_rate"] = key_rate
            existing = db.query(MacroData).filter_by(indicator="key_rate").first()
            if existing:
                existing.value = key_rate
                existing.as_of_date = rate_date
            else:
                db.add(MacroData(indicator="key_rate", value=key_rate, as_of_date=rate_date))
            db.commit()
    except Exception as e:
        logger.error(f"CBR key rate fetch failed: {e}")
        stats["errors"].append(f"CBR: {e}")

    # 5. Build baskets
    try:
        from app.services.baskets import build_baskets
        baskets = build_baskets(db)
        stats["baskets_formed"] = len(baskets)
        db.commit()
    except Exception as e:
        logger.error(f"Basket building failed: {e}")
        stats["errors"].append(f"Baskets: {e}")
        db.rollback()

    # 6. Run valuations
    try:
        computed = _run_valuations(db, key_rate)
        stats["valuations_computed"] = computed
        db.commit()
    except Exception as e:
        logger.error(f"Valuation failed: {e}")
        stats["errors"].append(f"Valuation: {e}")
        db.rollback()

    # 7. Compute comparisons
    try:
        from app.services.comparison import compute_comparisons
        compared = compute_comparisons(db, key_rate)
        stats["comparisons_computed"] = compared
        db.commit()
    except Exception as e:
        logger.error(f"Comparison failed: {e}")
        stats["errors"].append(f"Comparison: {e}")
        db.rollback()

    # 8. Count anomalies
    anomaly_count = db.query(Valuation).filter(Valuation.anomaly_code.isnot(None)).count()
    stats["anomalies_found"] = anomaly_count

    logger.info(f"Pipeline complete: {stats}")
    return stats


def _upsert_bonds(db: Session, raw_bonds: list[dict]) -> None:
    for raw in raw_bonds:
        slug = raw["smartlab_slug"]
        bond = db.query(Bond).filter_by(smartlab_slug=slug).first()
        if bond:
            for key, value in raw.items():
                if key != "smartlab_slug" and value is not None:
                    setattr(bond, key, value)
        else:
            bond = Bond(**raw)
            db.add(bond)
    db.flush()


def _match_tinkoff_bonds(db: Session, tinkoff_bonds) -> int:
    isin_map = {}
    for tb in tinkoff_bonds:
        if tb.isin:
            isin_map[tb.isin] = tb

    matched = 0
    bonds = db.query(Bond).all()
    for bond in bonds:
        if bond.smartlab_slug and bond.smartlab_slug in isin_map:
            tb = isin_map[bond.smartlab_slug]
            bond.isin = bond.smartlab_slug
            bond.figi = tb.figi
            bond.ticker = tb.ticker
            bond.nominal_rub = tb.nominal
            bond.currency = tb.currency
            bond.is_floating_coupon = tb.floating_coupon_flag
            bond.is_amortizing = tb.amortization_flag
            matched += 1
            continue

        if bond.isin and bond.isin in isin_map:
            tb = isin_map[bond.isin]
            bond.figi = tb.figi
            bond.ticker = tb.ticker
            bond.nominal_rub = tb.nominal
            bond.currency = tb.currency
            bond.is_floating_coupon = tb.floating_coupon_flag
            bond.is_amortizing = tb.amortization_flag
            matched += 1

    db.flush()
    return matched


def _update_prices(db: Session, prices: dict[str, float]) -> int:
    updated = 0
    figi_bond_map = {
        b.figi: b for b in db.query(Bond).filter(Bond.figi.isnot(None)).all()
    }
    for figi, price in prices.items():
        bond = figi_bond_map.get(figi)
        if bond and price > 0:
            # Tinkoff returns price as % of nominal, convert to rubles
            bond.market_price_rub = price / 100.0 * bond.nominal_rub
            bond.market_price_source = "tinkoff"
            updated += 1
    db.flush()
    return updated


def _run_valuations(db: Session, key_rate: float) -> int:
    from app.services.valuation import compute_all_valuations, compute_discount_rate

    db.query(Valuation).delete()
    db.flush()

    bonds = db.query(Bond).all()
    computed = 0

    for bond in bonds:
        if bond.years_to_maturity is None and bond.maturity_date is None:
            is_perpetual = True
        else:
            is_perpetual = False

        T = bond.years_to_maturity
        if T is None and not is_perpetual:
            continue

        coupon_annual = 0.0
        if bond.coupon_rub and bond.frequency_per_year:
            coupon_annual = bond.coupon_rub * bond.frequency_per_year
        elif bond.coupon_rub:
            coupon_annual = bond.coupon_rub

        nominal = bond.nominal_rub or 1000.0
        freq = bond.frequency_per_year or 1

        r, rho = compute_discount_rate(key_rate, bond.rating)

        results = compute_all_valuations(
            coupon_annual=coupon_annual,
            nominal=nominal,
            years_to_maturity=T,
            frequency=freq,
            discount_rate=r,
            is_perpetual=is_perpetual,
        )

        val = Valuation(
            bond_id=bond.id,
            discount_rate=r,
            key_rate_used=key_rate,
            inflation_premium_used=DEFAULT_INFLATION_PREMIUM,
            risk_premium_used=rho,
            calc_basic_dcf=results["calc_basic_dcf"],
            calc_freq_adjusted=results["calc_freq_adjusted"],
            calc_reinvestment=results["calc_reinvestment"],
            calc_tax_adjusted=results["calc_tax_adjusted"],
            calc_zero_coupon=results["calc_zero_coupon"],
            calc_perpetual=results["calc_perpetual"],
            calc_primary=results["calc_primary"],
            formula_used=results["formula_used"],
        )
        db.add(val)
        computed += 1

    db.flush()
    return computed
