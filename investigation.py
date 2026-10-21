import pandas as pd

def _val(df,label,year):
    if df is None or df.empty or label not in df.index:return None
    cols=[c for c in df.columns if pd.Timestamp(c).year==year]
    if not cols:return None
    v=df.loc[label,cols[0]]
    if isinstance(v,pd.Series) or pd.isna(v):return None
    return float(v)

def investigate(ticker,frames,years=None):
    inc=frames.get('Income')
    if inc is None or inc.empty:return {'ticker':ticker,'error':'Income statement unavailable'}
    available=sorted({pd.Timestamp(c).year for c in inc.columns})
    if len(available)<2:return {'ticker':ticker,'error':'At least two annual periods are required'}
    y0,y1=(years[-2],years[-1]) if years else (available[-2],available[-1])
    r0,r1=_val(inc,'Total Revenue',y0),_val(inc,'Total Revenue',y1)
    op0,op1=_val(inc,'Operating Income',y0),_val(inc,'Operating Income',y1)
    ni0,ni1=_val(inc,'Net Income',y0),_val(inc,'Net Income',y1)
    c0,c1=_val(inc,'Cost Of Revenue',y0),_val(inc,'Cost Of Revenue',y1)
    def margin(x,r):return 100*x/r if x is not None and r else None
    def delta(a,b):return b-a if a is not None and b is not None else None
    return {'ticker':ticker,'from_year':y0,'to_year':y1,
      'revenue_growth_pct':100*(r1/r0-1) if r0 and r1 is not None else None,
      'operating_margin_change_pp':delta(margin(op0,r0),margin(op1,r1)),
      'net_margin_change_pp':delta(margin(ni0,r0),margin(ni1,r1)),
      'cost_of_revenue_share_change_pp':delta(margin(c0,r0),margin(c1,r1)),
      'source':'Yahoo Finance / yfinance provider extraction; not filing-verified'}

def format_investigation(x):
    if x.get('error'):return '**Investigation unavailable:** '+x['error']
    def f(v):return 'N/A' if v is None else f'{v:+.2f}'
    return f'''### What changed for {x['ticker']}?
Comparing **FY{x['from_year']} → FY{x['to_year']}**

- **Revenue growth:** {f(x['revenue_growth_pct'])}%
- **Operating margin movement:** {f(x['operating_margin_change_pp'])} percentage points
- **Net margin movement:** {f(x['net_margin_change_pp'])} percentage points
- **Cost of revenue / sales movement:** {f(x['cost_of_revenue_share_change_pp'])} percentage points

**What we know:** these movements are calculated from the provider-extracted statements.  
**What we do not know yet:** the business cause. Use annual-report evidence before claiming why the change happened.

*Source: {x['source']}*'''
