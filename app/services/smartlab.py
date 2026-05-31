from __future__ import annotations

import logging
import re
import time

import requests
from bs4 import BeautifulSoup

from app.config import SMARTLAB_BASE_URL, SMARTLAB_DELAY, SMARTLAB_MAX_PAGES
from app.utils import parse_date, parse_float

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}

EXPECTED_COLUMNS = [
    "№", "Имя", "Лет до погаш", "Доходн", "Год.куп", "Куп.дох",
    "Рейтинг", "Объем", "Купон", "Частота", "НКД", "Дюр",
    "Цена", "Дата купона", "Размещение", "Погашение", "Оферта",
]


def _validate_headers(header_row) -> bool:
    cells = header_row.find_all(["th", "td"])
    header_text = " ".join(c.get_text(strip=True) for c in cells).lower()
    required = ["имя", "доходн", "рейтинг", "купон", "цена"]
    return all(kw in header_text for kw in required)


def _extract_slug(cell) -> str | None:
    a_tag = cell.find("a")
    if not a_tag or not a_tag.get("href"):
        return None
    href = a_tag["href"]
    match = re.search(r"/q/bonds/([^/]+)/", href)
    if match:
        return match.group(1)
    parts = [p for p in href.strip("/").split("/") if p]
    return parts[-1] if parts else None


def _extract_name(cell) -> str:
    a_tag = cell.find("a")
    if a_tag:
        return a_tag.get_text(strip=True)
    return cell.get_text(strip=True)


def _parse_int(val: str | None) -> int | None:
    f = parse_float(val)
    if f is None:
        return None
    return int(f)


def _parse_row(cells) -> dict | None:
    # SmartLab table: 20 columns
    # [0]=№, [1]=name(ISIN link), [2]=company link, [3]=years, [4]=ytm%,
    # [5]=annual_coupon%, [6]=last_coupon%, [7]=rating, [8]=volume,
    # [9]=coupon_rub, [10]=frequency, [11]=nkd, [12]=duration,
    # [13]=price, [14]=coupon_date, [15]=issue_date, [16]=maturity_date,
    # [17]=offer_date, [18..19]=extra
    if len(cells) < 17:
        return None

    slug = _extract_slug(cells[1])
    name = _extract_name(cells[1])

    if not slug or not name:
        return None

    return {
        "smartlab_slug": slug,
        "name": name,
        "years_to_maturity": parse_float(cells[3].get_text(strip=True)),
        "ytm_percent": parse_float(cells[4].get_text(strip=True)),
        "annual_coupon_yield": parse_float(cells[5].get_text(strip=True)),
        "last_coupon_yield": parse_float(cells[6].get_text(strip=True)),
        "rating": cells[7].get_text(strip=True) or None,
        "volume_mln_rub": parse_float(cells[8].get_text(strip=True)),
        "coupon_rub": parse_float(cells[9].get_text(strip=True)),
        "frequency_per_year": _parse_int(cells[10].get_text(strip=True)),
        "nkd_rub": parse_float(cells[11].get_text(strip=True)),
        "duration_years": parse_float(cells[12].get_text(strip=True)),
        "price_percent": parse_float(cells[13].get_text(strip=True)),
        "coupon_date": parse_date(cells[14].get_text(strip=True)),
        "issue_date": parse_date(cells[15].get_text(strip=True)),
        "maturity_date": parse_date(cells[16].get_text(strip=True)),
        "offer_date": parse_date(cells[17].get_text(strip=True)) if len(cells) > 17 else None,
    }


def scrape_all_bonds() -> list[dict]:
    bonds: list[dict] = []
    seen_slugs: set[str] = set()

    for page_num in range(1, SMARTLAB_MAX_PAGES + 1):
        if page_num == 1:
            url = SMARTLAB_BASE_URL
        else:
            url = f"{SMARTLAB_BASE_URL}order_by_val_to_day/desc/page{page_num}/"

        logger.info(f"Scraping SmartLab page {page_num}: {url}")

        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch page {page_num}: {e}")
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table")
        if not table:
            logger.warning(f"No table found on page {page_num}, stopping")
            break

        rows = table.find_all("tr")
        if not rows:
            break

        if page_num == 1 and len(rows) > 0:
            if not _validate_headers(rows[0]):
                logger.error("SmartLab table headers don't match expected format")
                break

        data_rows = rows[1:]
        if not data_rows:
            break

        page_bonds = 0
        for row in data_rows:
            cells = row.find_all("td")
            bond = _parse_row(cells)

            # Skip bonds with maturity less than 1 day (0.01 years)
            if bond and bond.get("years_to_maturity") is not None and bond["years_to_maturity"] < 0.1:
                continue

            # После парсинга bond, проверяем YTM
            if bond.get("ytm_percent") is not None and bond["ytm_percent"] > 40.0:
                continue  # не добавляем в базу

            if bond and bond["smartlab_slug"] not in seen_slugs:
                seen_slugs.add(bond["smartlab_slug"])
                bonds.append(bond)
                page_bonds += 1

        logger.info(f"Page {page_num}: parsed {page_bonds} bonds (total: {len(bonds)})")

        if page_bonds == 0:
            break

        if page_num < SMARTLAB_MAX_PAGES:
            time.sleep(SMARTLAB_DELAY)

    logger.info(f"SmartLab scraping complete: {len(bonds)} bonds total")
    return bonds
