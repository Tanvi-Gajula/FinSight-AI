# FinSight AI

FinSight AI is a **learning-first financial research workspace** built around one disciplined flow:

**Snapshot → Investigate WHY → Verify evidence → Test valuation assumptions**

## Why it is different
FinSight does not treat a data-provider ratio, an official company KPI, and an AI explanation as the same thing.

- **Official KPI layer:** curated company-reported metrics override provider-derived headline KPIs when available.
- **Provider transparency:** Yahoo Finance/yfinance statements stay visible in raw units and are never silently relabelled as crore/billion.
- **Investigate WHY:** separates numerical movement from evidence-backed business explanation.
- **Evidence desk:** uploaded annual reports are searchable with PDF page references.
- **Groq study buddy:** explains tool outputs; Python performs calculations.
- **Valuation Playground:** transparent FCF scenarios, scenario/sensitivity lenses, and Excel download. It is not an automatic company forecast.

## Currently curated official KPI profiles
- TCS.NS — FY2025/FY2026
- INFY.NS — FY2025/FY2026

Other tickers still work for provider-based research, but headline metrics remain explicitly provider-derived until an official profile is curated or evidence is uploaded.

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

Optional `.env`:
```text
GROQ_API_KEY=YOUR_KEY_HERE
```
Never commit a real key.

## Important
FinSight is educational. It does not provide buy/sell recommendations. Financial statements, currency/scale, shares outstanding, market price and valuation assumptions should be independently verified before investment use.
