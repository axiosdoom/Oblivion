from __future__ import annotations

from app.config import DEFAULT_INFLATION_PREMIUM, DEFAULT_REINVESTMENT_RATE, NDFL_TAX_RATE
from app.utils import get_risk_premium


def compute_discount_rate(
    key_rate: float,
    rating: str | None,
    inflation_premium: float = DEFAULT_INFLATION_PREMIUM,
) -> tuple[float, float]:
    rho = get_risk_premium(rating)
    r = key_rate + inflation_premium + rho
    return r, rho


def basic_dcf(C: float, N: float, T: float, r: float) -> float | None:
    if T <= 0 or r <= 0 or N <= 0:
        return None
    T_int = max(1, int(round(T)))
    s = sum(C / (1 + r) ** t for t in range(1, T_int + 1))
    s += N / (1 + r) ** T_int
    return s


def freq_adjusted_dcf(C: float, N: float, T: float, r: float, m: int) -> float | None:
    if T <= 0 or r <= 0 or N <= 0 or m <= 0:
        return None
    total_periods = max(1, int(round(T * m)))
    coupon_per_period = C / m
    r_per_period = r / m
    s = sum(coupon_per_period / (1 + r_per_period) ** t for t in range(1, total_periods + 1))
    s += N / (1 + r_per_period) ** total_periods
    return s


def reinvestment_dcf(
    C: float, N: float, T: float, r: float,
    e: float = DEFAULT_REINVESTMENT_RATE,
    k: int = 182, K: int = 365,
) -> float | None:
    if T <= 0 or r <= 0 or N <= 0:
        return None
    T_int = max(1, int(round(T)))
    s = sum(C * (1 + e * k / K) / (1 + r) ** t for t in range(1, T_int + 1))
    s += N / (1 + r) ** T_int
    return s


def tax_adjusted_dcf(C: float, N: float, T: float, r: float, tau: float = NDFL_TAX_RATE) -> float | None:
    if T <= 0 or r <= 0 or N <= 0:
        return None
    T_int = max(1, int(round(T)))
    s = sum(C * (1 - tau) / (1 + r) ** t for t in range(1, T_int + 1))
    s += N / (1 + r) ** T_int
    return s


def zero_coupon_value(N: float, T: float, r: float) -> float | None:
    if T <= 0 or r <= 0 or N <= 0:
        return None
    return N / (1 + r) ** T


def perpetual_value(C: float, r: float) -> float | None:
    if r <= 0 or C <= 0:
        return None
    return C / r


def compute_all_valuations(
    coupon_annual: float,
    nominal: float,
    years_to_maturity: float | None,
    frequency: int | None,
    discount_rate: float,
    is_perpetual: bool = False,
) -> dict[str, float | None]:
    results: dict[str, float | None] = {
        "calc_basic_dcf": None,
        "calc_freq_adjusted": None,
        "calc_reinvestment": None,
        "calc_tax_adjusted": None,
        "calc_zero_coupon": None,
        "calc_perpetual": None,
        "calc_primary": None,
        "formula_used": None,
    }

    C = coupon_annual
    N = nominal
    r = discount_rate
    T = years_to_maturity
    m = frequency or 1

    if is_perpetual or T is None:
        results["calc_perpetual"] = perpetual_value(C, r)
        results["calc_primary"] = results["calc_perpetual"]
        results["formula_used"] = "perpetual"
        return results

    if T <= 0:
        results["calc_primary"] = N
        results["formula_used"] = "matured"
        return results

    if C <= 0 or C is None:
        results["calc_zero_coupon"] = zero_coupon_value(N, T, r)
        results["calc_primary"] = results["calc_zero_coupon"]
        results["formula_used"] = "zero_coupon"
        return results

    results["calc_basic_dcf"] = basic_dcf(C, N, T, r)
    results["calc_tax_adjusted"] = tax_adjusted_dcf(C, N, T, r)
    results["calc_reinvestment"] = reinvestment_dcf(C, N, T, r)

    if m > 1:
        results["calc_freq_adjusted"] = freq_adjusted_dcf(C, N, T, r, m)
        results["calc_primary"] = results["calc_freq_adjusted"]
        results["formula_used"] = "freq_adjusted"
    else:
        results["calc_primary"] = results["calc_basic_dcf"]
        results["formula_used"] = "basic_dcf"

    return results
