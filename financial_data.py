import pandas as pd
from official_metrics import get_official

PROVIDER = "Yahoo Finance / yfinance"

def latest_value(df,label):
    if df is None or df.empty or label not in df.index:return None
    for c in sorted(df.columns,key=lambda x:pd.Timestamp(x),reverse=True):
        v=df.loc[label,c]
        if not isinstance(v,pd.Series) and pd.notna(v):return pd.Timestamp(c).year,float(v)
    return None

def provider_profile(ticker, stock=None):
    out={"ticker":ticker,"name":ticker,"quote_currency":None,"last_price":None,"shares_outstanding":None,"market_cap":None,"provider":PROVIDER}
    if stock is None:return out
    try:
        fi=stock.fast_info
        for src,dst in [("currency","quote_currency"),("last_price","last_price"),("market_cap","market_cap")]:
            try:out[dst]=fi.get(src)
            except Exception:pass
    except Exception:pass
    try:
        info=stock.info or {}
        out["name"]=info.get("longName") or info.get("shortName") or ticker
        out["quote_currency"]=out["quote_currency"] or info.get("currency")
        out["shares_outstanding"]=info.get("sharesOutstanding")
        out["last_price"]=out["last_price"] or info.get("currentPrice")
    except Exception:pass
    return out

def coverage(frames):
    labels={'Income':['Total Revenue','Operating Income','Net Income'],
            'Balance':['Total Assets','Total Debt','Cash And Cash Equivalents'],
            'CashFlow':['Operating Cash Flow','Capital Expenditure','Free Cash Flow']}
    rows=[]
    for kind,wanted in labels.items():
        df=frames.get(kind)
        for label in wanted:rows.append({'statement':kind,'account':label,'available':bool(df is not None and not df.empty and label in df.index)})
    return pd.DataFrame(rows)

def provider_history(ticker,frames):
    inc=frames.get('Income'); years=sorted({pd.Timestamp(c).year for c in inc.columns}) if inc is not None and not inc.empty else []
    out=[]
    for y in years:
        def at(label):
            cols=[c for c in inc.columns if pd.Timestamp(c).year==y]
            if not cols or label not in inc.index:return None
            v=inc.loc[label,cols[0]]
            return None if isinstance(v,pd.Series) or pd.isna(v) else float(v)
        rev,ni,op=at('Total Revenue'),at('Net Income'),at('Operating Income')
        out.append({'year':y,'revenue_raw':rev,'net_income_raw':ni,'operating_income_raw':op,
                    'provider_net_margin_pct':100*ni/rev if rev and ni is not None else None,
                    'provider_operating_margin_pct':100*op/rev if rev and op is not None else None})
    for i in range(1,len(out)):
        p,c=out[i-1]['revenue_raw'],out[i]['revenue_raw'];out[i]['revenue_growth_pct']=100*(c/p-1) if p and c is not None else None
    return out

def research_snapshot(ticker,frames):
    hist=provider_history(ticker,frames); official=get_official(ticker)
    latest=hist[-1] if hist else {}
    result={"ticker":ticker,"provider_history":hist,"official":official,"latest_provider":latest,
            "confidence":"Official metrics available" if official else "Provider-derived only"}
    if official:
        ys=sorted(official['years']); y=ys[-1]; result['latest_official']={"year":y,**official['years'][y]}
    else:result['latest_official']=None
    return result

def format_money(value,currency=None,scale=None):
    if value is None:return 'N/A'
    if currency=='INR' and scale=='crore':return f"₹{value:,.0f} crore"
    return f"{value:,.0f}"
