from __future__ import annotations


def quotation_to_float(q) -> float:
    units = getattr(q, "units", 0)
    nano = getattr(q, "nano", 0)
    try:
        return float(units) + float(nano) / 1_000_000_000.0
    except Exception:
        return float(units)


def money_to_float(m) -> float:
    return quotation_to_float(m)


RATING_SCORES: dict[str, int] = {
    "AAA": 21, "AA+": 20, "AA": 19, "AA-": 18,
    "A+": 17, "A": 16, "A-": 15,
    "BBB+": 14, "BBB": 13, "BBB-": 12,
    "BB+": 11, "BB": 10, "BB-": 9,
    "B+": 8, "B": 7, "B-": 6,
    "CCC+": 5, "CCC": 4, "CC": 3, "C": 2, "D": 1,
}

RISK_PREMIUM: dict[str, float] = {
    "AAA": 0.0030,   # 0.3% — минимальная премия за кредитный риск (эталон)
    "AA+": 0.0045, "AA": 0.0060, "AA-": 0.0075,
    "A+": 0.0090, "A": 0.0105, "A-": 0.0125,
    "BBB+": 0.0150, "BBB": 0.0175, "BBB-": 0.0200,
    "BB+": 0.0250, "BB": 0.0300, "BB-": 0.0375,
    "B+": 0.0475, "B": 0.0600, "B-": 0.0750,
    "CCC+": 0.0950, "CCC": 0.1200, "CC": 0.1500,
    "C": 0.2000, "D": 0.3000,
}

RATING_GROUPS: dict[str, list[str]] = {
    "AAA": ["AAA"],
    "AA": ["AA+", "AA", "AA-"],
    "A": ["A+", "A", "A-"],
    "BBB": ["BBB+", "BBB", "BBB-"],
    "BB": ["BB+", "BB", "BB-"],
    "B": ["B+", "B", "B-"],
    "CCC+": ["CCC+", "CCC", "CC", "C", "D"],
}

MATURITY_GROUPS: dict[str, tuple[float, float]] = {
    "<6m": (0.0, 0.5),
    "6-12m": (0.5, 1.0),
    "1-2y": (1.0, 2.0),
    "2-3y": (2.0, 3.0),
    ">3y": (3.0, float("inf")),
}


def rating_to_score(rating: str | None) -> int | None:
    if not rating:
        return None
    return RATING_SCORES.get(rating.strip().upper())


def rating_to_group(rating: str | None) -> str | None:
    if not rating:
        return None
    r = rating.strip().upper()
    for group, members in RATING_GROUPS.items():
        if r in members:
            return group
    return None


def maturity_to_group(years: float | None) -> str | None:
    if years is None:
        return None
    for group, (lo, hi) in MATURITY_GROUPS.items():
        if lo <= years < hi:
            return group
    return None


def get_risk_premium(rating: str | None) -> float:
    if not rating:
        return 0.10
    return RISK_PREMIUM.get(rating.strip().upper(), 0.10)


def parse_float(val: str | None) -> float | None:
    if val is None:
        return None
    val = val.strip().replace("\xa0", "").replace(" ", "").replace("%", "")
    if not val or val == "-" or val == "—":
        return None
    val = val.replace(",", ".")
    try:
        return float(val)
    except ValueError:
        return None


def parse_date(val: str | None):
    if val is None:
        return None
    val = val.strip()
    if not val or val == "-" or val == "—":
        return None
    from datetime import datetime
    for fmt in ("%d.%m.%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            continue
    return None
