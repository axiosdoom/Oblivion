from __future__ import annotations

import logging
from datetime import date

import requests
from bs4 import BeautifulSoup

from app.config import CBR_KEY_RATE_URL

logger = logging.getLogger(__name__)


def fetch_key_rate() -> tuple[float, date] | None:
    try:
        resp = requests.get(CBR_KEY_RATE_URL, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (compatible; OblivionBot/1.0)"
        })
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table", class_="data")
        if not table:
            tables = soup.find_all("table")
            table = tables[-1] if tables else None

        if not table:
            logger.error("CBR: No table found on key rate page")
            return None

        rows = table.find_all("tr")
        for row in reversed(rows):
            cells = row.find_all("td")
            if len(cells) >= 2:
                date_str = cells[0].get_text(strip=True)
                rate_str = cells[1].get_text(strip=True).replace(",", ".")
                try:
                    from datetime import datetime
                    rate_date = datetime.strptime(date_str, "%d.%m.%Y").date()
                    rate_value = float(rate_str) / 100.0
                    logger.info(f"CBR key rate: {rate_value*100}% as of {rate_date}")
                    return (rate_value, rate_date)
                except (ValueError, TypeError):
                    continue

        logger.error("CBR: Could not parse any rate from table")
        return None

    except requests.RequestException as e:
        logger.error(f"CBR: Failed to fetch key rate: {e}")
        return None
