from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class BondOut(BaseModel):
    id: int
    smartlab_slug: str
    name: str
    isin: str | None = None
    figi: str | None = None
    ticker: str | None = None
    years_to_maturity: float | None = None
    ytm_percent: float | None = None
    annual_coupon_yield: float | None = None
    last_coupon_yield: float | None = None
    rating: str | None = None
    volume_mln_rub: float | None = None
    coupon_rub: float | None = None
    frequency_per_year: int | None = None
    nkd_rub: float | None = None
    duration_years: float | None = None
    price_percent: float | None = None
    coupon_date: date | None = None
    issue_date: date | None = None
    maturity_date: date | None = None
    offer_date: date | None = None
    nominal_rub: float = 1000.0
    currency: str = "RUB"
    is_floating_coupon: bool = False
    is_amortizing: bool = False
    market_price_rub: float | None = None

    model_config = {"from_attributes": True}


class ValuationOut(BaseModel):
    id: int
    bond_id: int
    basket_id: int | None = None
    discount_rate: float
    key_rate_used: float
    inflation_premium_used: float
    risk_premium_used: float
    calc_basic_dcf: float | None = None
    calc_freq_adjusted: float | None = None
    calc_reinvestment: float | None = None
    calc_tax_adjusted: float | None = None
    calc_zero_coupon: float | None = None
    calc_perpetual: float | None = None
    calc_primary: float | None = None
    formula_used: str | None = None
    market_price_rub: float | None = None
    delta_price: float | None = None
    delta_yield: float | None = None
    delta_curve: float | None = None
    delta_curve_zscore: float | None = None
    risk_adjusted_yield: float | None = None
    color: str | None = None
    yield_symbol: str | None = None
    anomaly_code: str | None = None
    calculated_at: datetime | None = None

    model_config = {"from_attributes": True}


class BasketOut(BaseModel):
    id: int
    name: str
    rating_group: str | None = None
    maturity_group: str | None = None
    bond_count: int = 0
    avg_price_rub: float | None = None
    avg_ytm: float | None = None
    std_ytm: float | None = None
    avg_duration: float | None = None
    avg_rating_score: float | None = None

    model_config = {"from_attributes": True}


class BondWithValuation(BaseModel):
    bond: BondOut
    valuation: ValuationOut | None = None
    basket_name: str | None = None


class PipelineResult(BaseModel):
    bonds_scraped: int = 0
    bonds_matched: int = 0
    prices_fetched: int = 0
    key_rate: float | None = None
    baskets_formed: int = 0
    valuations_computed: int = 0
    comparisons_computed: int = 0
    anomalies_found: int = 0
    errors: list[str] = []
