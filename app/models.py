from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Bond(Base):
    __tablename__ = "bonds"

    id: Mapped[int] = mapped_column(primary_key=True)
    smartlab_slug: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(300))
    isin: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True, index=True)
    figi: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    ticker: Mapped[str | None] = mapped_column(String(20), nullable=True)

    years_to_maturity: Mapped[float | None] = mapped_column(Float, nullable=True)
    ytm_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    annual_coupon_yield: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_coupon_yield: Mapped[float | None] = mapped_column(Float, nullable=True)
    rating: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    volume_mln_rub: Mapped[float | None] = mapped_column(Float, nullable=True)
    coupon_rub: Mapped[float | None] = mapped_column(Float, nullable=True)
    frequency_per_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    nkd_rub: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_years: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    coupon_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    maturity_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    offer_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    nominal_rub: Mapped[float] = mapped_column(Float, default=1000.0)
    currency: Mapped[str] = mapped_column(String(5), default="RUB")
    is_floating_coupon: Mapped[bool] = mapped_column(Boolean, default=False)
    is_amortizing: Mapped[bool] = mapped_column(Boolean, default=False)

    market_price_rub: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_price_source: Mapped[str | None] = mapped_column(String(20), nullable=True)

    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    coupons: Mapped[list[Coupon]] = relationship(back_populates="bond", cascade="all, delete-orphan")
    basket_links: Mapped[list[BondBasketLink]] = relationship(back_populates="bond", cascade="all, delete-orphan")
    valuations: Mapped[list[Valuation]] = relationship(back_populates="bond", cascade="all, delete-orphan")


class Coupon(Base):
    __tablename__ = "coupons"

    id: Mapped[int] = mapped_column(primary_key=True)
    bond_id: Mapped[int] = mapped_column(ForeignKey("bonds.id", ondelete="CASCADE"), index=True)
    coupon_date: Mapped[date] = mapped_column(Date)
    pay_one_bond_rub: Mapped[float] = mapped_column(Float)
    coupon_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    coupon_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    bond: Mapped[Bond] = relationship(back_populates="coupons")


class Basket(Base):
    __tablename__ = "baskets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    rating_group: Mapped[str | None] = mapped_column(String(10), nullable=True)
    maturity_group: Mapped[str | None] = mapped_column(String(10), nullable=True)

    bond_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_price_rub: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ytm: Mapped[float | None] = mapped_column(Float, nullable=True)
    std_ytm: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_rating_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    bond_links: Mapped[list[BondBasketLink]] = relationship(back_populates="basket", cascade="all, delete-orphan")


class BondBasketLink(Base):
    __tablename__ = "bond_basket_links"

    bond_id: Mapped[int] = mapped_column(ForeignKey("bonds.id", ondelete="CASCADE"), primary_key=True)
    basket_id: Mapped[int] = mapped_column(ForeignKey("baskets.id", ondelete="CASCADE"), primary_key=True)

    bond: Mapped[Bond] = relationship(back_populates="basket_links")
    basket: Mapped[Basket] = relationship(back_populates="bond_links")


class Valuation(Base):
    __tablename__ = "valuations"

    id: Mapped[int] = mapped_column(primary_key=True)
    bond_id: Mapped[int] = mapped_column(ForeignKey("bonds.id", ondelete="CASCADE"), index=True)
    basket_id: Mapped[int | None] = mapped_column(ForeignKey("baskets.id", ondelete="SET NULL"), nullable=True)

    discount_rate: Mapped[float] = mapped_column(Float)
    key_rate_used: Mapped[float] = mapped_column(Float)
    inflation_premium_used: Mapped[float] = mapped_column(Float)
    risk_premium_used: Mapped[float] = mapped_column(Float)

    calc_basic_dcf: Mapped[float | None] = mapped_column(Float, nullable=True)
    calc_freq_adjusted: Mapped[float | None] = mapped_column(Float, nullable=True)
    calc_reinvestment: Mapped[float | None] = mapped_column(Float, nullable=True)
    calc_tax_adjusted: Mapped[float | None] = mapped_column(Float, nullable=True)
    calc_zero_coupon: Mapped[float | None] = mapped_column(Float, nullable=True)
    calc_perpetual: Mapped[float | None] = mapped_column(Float, nullable=True)

    calc_primary: Mapped[float | None] = mapped_column(Float, nullable=True)
    formula_used: Mapped[str | None] = mapped_column(String(30), nullable=True)

    market_price_rub: Mapped[float | None] = mapped_column(Float, nullable=True)
    delta_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    delta_yield: Mapped[float | None] = mapped_column(Float, nullable=True)
    delta_curve: Mapped[float | None] = mapped_column(Float, nullable=True)
    delta_curve_zscore: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_adjusted_yield: Mapped[float | None] = mapped_column(Float, nullable=True)

    color: Mapped[str | None] = mapped_column(String(10), nullable=True)
    yield_symbol: Mapped[str | None] = mapped_column(String(5), nullable=True)
    anomaly_code: Mapped[str | None] = mapped_column(String(10), nullable=True)

    calculated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    bond: Mapped[Bond] = relationship(back_populates="valuations")
    basket: Mapped[Basket | None] = relationship()


class MacroData(Base):
    __tablename__ = "macro_data"

    id: Mapped[int] = mapped_column(primary_key=True)
    indicator: Mapped[str] = mapped_column(String(50), index=True)
    value: Mapped[float] = mapped_column(Float)
    as_of_date: Mapped[date] = mapped_column(Date)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
