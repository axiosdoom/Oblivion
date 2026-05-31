# Oblivion — Bond Value Analysis Tool

Анализ стоимости облигаций и выявление рыночных неэффективностей на российском долговом рынке.

## Requirements

- Python 3.10+
- Tinkoff Invest API token ([получить здесь](https://www.tbank.ru/invest/settings/api/))

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Install Tinkoff SDK
pip install t-tech-investments --index-url https://opensource.tbank.ru/api/v4/projects/238/packages/pypi/simple

# Configure API token — create app_secrets.py in the project root:
echo 'TINKOFF_TOKEN = "your_token_here"' > app_secrets.py
```

## Run

```bash
python main.py
```

Open http://127.0.0.1:8000 in browser.

Click **Refresh Data** on the dashboard to run the full pipeline:
1. Scrape ~1000 bonds from SmartLab
2. Match with Tinkoff API by ISIN, fetch real-time prices
3. Fetch CBR key rate
4. Group bonds into baskets (rating × maturity)
5. Compute 6 DCF valuations per bond
6. Detect pricing anomalies (Δ price, Δ yield, Δ curve)

## Pages

| Route | Description |
|-------|-------------|
| `/` | Dashboard — sortable table with color-coded bonds, filters |
| `/bond/{id}` | Bond detail — all 6 valuations, market comparison |
| `/basket/{id}` | Basket view — yield curve chart, member bonds |
| `/anomalies` | Anomaly list — tabs by type (P+, Y+, C+, P+Y+, R) |

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/run` | POST | Run full pipeline |
| `/api/bonds` | GET | Filtered bond list with valuations |
| `/api/bonds/{id}` | GET | Single bond detail |
| `/api/baskets` | GET | All baskets with stats |
| `/api/yield-curve/{id}` | GET | Yield curve data for Chart.js |
| `/api/anomalies` | GET | Anomaly list |
| `/api/stats` | GET | Summary statistics |


