import pandas as pd

def metadata(ticker,stock=None):
    info={}
    try:
        info=(stock.fast_info if stock is not None else {}) or {}
    except Exception:pass
    currency=None
    try:currency=info.get('currency')
    except Exception:pass
    return {'ticker':ticker,'quote_currency':currency,'provider':'Yahoo Finance / yfinance','verified':False}

def latest_value(df,label):
    if df is None or df.empty or label not in df.index:return None
    for c in sorted(df.columns,key=lambda x:pd.Timestamp(x),reverse=True):
        v=df.loc[label,c]
        if not isinstance(v,pd.Series) and pd.notna(v):return pd.Timestamp(c).year,float(v)
    return None

def coverage(frames):
    labels={'Income':['Total Revenue','Operating Income','Net Income'],
            'Balance':['Total Assets','Total Debt','Cash And Cash Equivalents'],
            'CashFlow':['Operating Cash Flow','Capital Expenditure','Free Cash Flow']}
    rows=[]
    for kind,wanted in labels.items():
        df=frames.get(kind)
        for label in wanted:rows.append({'statement':kind,'account':label,'available':bool(df is not None and not df.empty and label in df.index)})
    return pd.DataFrame(rows)
