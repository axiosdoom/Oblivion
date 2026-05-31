from __future__ import annotations

import os
import sys

TINKOFF_TOKEN: str = ""

try:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app_secrets import TINKOFF_TOKEN as _token  # type: ignore
    TINKOFF_TOKEN = _token
except Exception:
    TINKOFF_TOKEN = os.environ.get("TINKOFF_TOKEN", "")

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///oblivion.db")

# Пороги ценовой аномалии (в %) — при какой недооценке считать P+
PRICE_ANOMALY_BY_RATING = {
    "AAA": 8.0,
    "AA": 9.0,
    "A": 10.0,
    "BBB": 12.0,
    "BB": 14.0,
    "B": 16.0,
    "CCC": 20.0,
    "CC": 25.0,
    "C": 30.0,
    "D": 40.0,
}

# Пороги доходностной аномалии (в %) — превышение доходности над средней по корзине
YIELD_ANOMALY_BY_RATING = {
    "AAA": 1.5,
    "AA": 2.0,
    "A": 2.8,
    "BBB": 4.0,
    "BB": 5.5,
    "B": 7.5,
    "CCC": 10.0,
    "CC": 13.0,
    "C": 16.0,
    "D": 20.0,
}

CURVE_ANOMALY_ZSCORE = 2.0   # остаётся без изменений
NDFL_TAX_RATE = 0.13
DEFAULT_REINVESTMENT_RATE = 0.08
DEFAULT_INFLATION_PREMIUM = 0.0  # CB key rate already includes inflation expectations
DEFAULT_NOMINAL = 1000.0

SMARTLAB_BASE_URL = "https://smart-lab.ru/q/bonds/"
SMARTLAB_MAX_PAGES = 10
SMARTLAB_DELAY = 1.5

CBR_KEY_RATE_URL = "https://www.cbr.ru/hd_base/KeyRate/"
