"""Simple educational FCFF DCF. No automatic three-statement forecast."""
from dataclasses import dataclass
import io, math
import pandas as pd
from openpyxl import Workbook

@dataclass
class Assumptions:
    growth:float=.06; wacc:float=.11; terminal_growth:float=.04; n:int=5
    shares:float|None=None; market_price:float|None=None

def _latest(df,label):
    if df is None or df.empty or label not in df.index:return None
    for c in sorted(df.columns,key=lambda x:pd.Timestamp(x),reverse=True):
        v=df.loc[label,c]
        if not isinstance(v,pd.Series) and pd.notna(v):return pd.Timestamp(c).year,float(v)
    return None

def dcf_inputs(frames):
    cf=frames.get('CashFlow'); bs=frames.get('Balance')
    fcf=_latest(cf,'Free Cash Flow')
    if fcf is None:
        cfo=_latest(cf,'Operating Cash Flow'); capex=_latest(cf,'Capital Expenditure')
        if cfo and capex: fcf=(cfo[0],cfo[1]+capex[1]) # capex usually negative in provider data
    debt=_latest(bs,'Total Debt'); cash=_latest(bs,'Cash And Cash Equivalents')
    missing=[]
    if fcf is None:missing.append('free cash flow (or operating cash flow + capex)')
    if debt is None:missing.append('total debt')
    if cash is None:missing.append('cash and cash equivalents')
    return {'fcf':fcf,'debt':debt,'cash':cash,'missing':missing}

def value_company(frames,a:Assumptions):
    if not 1<=a.n<=10:raise ValueError('Forecast years must be 1–10')
    if a.wacc<=a.terminal_growth:raise ValueError('WACC must be greater than terminal growth')
    x=dcf_inputs(frames)
    if x['missing']:raise ValueError('Valuation unavailable: missing '+', '.join(x['missing']))
    year,fcf=x['fcf']; flows=[]; cur=fcf
    for i in range(1,a.n+1):
        cur*=1+a.growth; flows.append({'year':year+i,'fcf_raw':cur,'pv_raw':cur/(1+a.wacc)**i})
    terminal=cur*(1+a.terminal_growth)/(a.wacc-a.terminal_growth)
    ev=sum(r['pv_raw'] for r in flows)+terminal/(1+a.wacc)**a.n
    equity=ev-x['debt'][1]+x['cash'][1]
    per_share=equity/a.shares if a.shares and a.shares>0 else None
    diff=per_share/a.market_price-1 if per_share is not None and a.market_price and a.market_price>0 else None
    return {'base_year':year,'base_fcf_raw':fcf,'flows':flows,'enterprise_value_raw':ev,'equity_value_raw':equity,
            'intrinsic_value_per_share':per_share,'difference_vs_price':diff,'debt_raw':x['debt'][1],'cash_raw':x['cash'][1]}

def workbook(ticker,frames,a):
    v=value_company(frames,a); wb=Workbook(); ws=wb.active;ws.title='Valuation'
    ws.append(['FinSight AI — Educational Valuation Playground',ticker]);ws.append([])
    ws.append(['Input','Value']); ws.append(['Base free cash flow (raw provider units)',v['base_fcf_raw']]);ws.append(['Growth',a.growth]);ws.append(['WACC',a.wacc]);ws.append(['Terminal growth',a.terminal_growth]);ws.append(['Forecast years',a.n]);ws.append(['Shares outstanding',a.shares]);ws.append(['Market price / share',a.market_price])
    ws.append([]);ws.append(['Output','Value']);ws.append(['Enterprise value (raw provider units)',v['enterprise_value_raw']]);ws.append(['Equity value (raw provider units)',v['equity_value_raw']]);ws.append(['Illustrative intrinsic value / share',v['intrinsic_value_per_share']]);ws.append(['Difference vs entered market price',v['difference_vs_price']]);
    ws.append([]);ws.append(['Important','This is an educational scenario, not a company forecast or investment recommendation. Verify source currency, shares, price and filings.'])
    f=wb.create_sheet('FCF Forecast');f.append(['Year','FCF raw units','PV raw units']);[f.append([r['year'],r['fcf_raw'],r['pv_raw']]) for r in v['flows']]
    s=wb.create_sheet('Source Notes');s.append(['Provider','Yahoo Finance / yfinance']);s.append(['Status','Provider extraction; not independently filing-verified']);s.append(['Model','Simple FCFF growth scenario; no automatic three-statement projection'])
    out=io.BytesIO();wb.save(out);return out.getvalue(),v
