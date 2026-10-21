# FinSight AI
A learning-first financial research app: **What changed → Why might it have changed → What evidence supports it → What if assumptions change?**

## Main features
- Historical financial statements from Yahoo Finance/yfinance (provider extraction; not filing-verified)
- Investigate WHY: deterministic revenue/margin movement calculations
- Annual-report PDF evidence search with PDF page references
- Groq explanations grounded in tool outputs
- Optional simple FCF Valuation Playground; no automatic three-statement forecast
- Excel valuation download

## Run
```bash
pip install -r requirements.txt
streamlit run app.py
```
Optional `.env`: `GROQ_API_KEY=...` (never commit the real key).

## Important
FinSight is educational. Provider data, currency/scale, share count, market price and valuation assumptions must be verified before investment use. No buy/sell recommendation is produced.
