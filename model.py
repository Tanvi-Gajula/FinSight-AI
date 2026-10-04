"""Auditable educational three-statement projections. All money INR crore."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import io
import math
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

RUPEES_PER_CRORE=10_000_000
SOURCE_MAP={
 'revenue':('Income','Total Revenue'), 'cogs':('Income','Cost Of Revenue'),
 'ebit':('Income','Operating Income'), 'ni':('Income','Net Income'),
 'tax':('Income','Tax Provision'), 'pretax':('Income','Pretax Income'),
 'da':('CashFlow','Depreciation And Amortization'), 'capex':('CashFlow','Capital Expenditure'),
 'cfo':('CashFlow','Operating Cash Flow'), 'cfi':('CashFlow','Investing Cash Flow'),
 'cff':('CashFlow','Financing Cash Flow'), 'cash_begin':('CashFlow','Beginning Cash Position'),
 'cash_end':('CashFlow','End Cash Position'), 'fx':('CashFlow','Effect Of Exchange Rate Changes'),
 'cash_bs':('Balance','Cash And Cash Equivalents'), 'assets':('Balance','Total Assets'),
 'liabilities':('Balance','Total Liabilities Net Minority Interest'),
 'equity':('Balance','Total Equity Gross Minority Interest'),
 'debt':('Balance','Total Debt'), 'ar':('Balance','Accounts Receivable'),
 'inventory':('Balance','Inventory'), 'ap':('Balance','Accounts Payable'),
 'ppe':('Balance','Net PPE'), 'dividends':('CashFlow','Cash Dividends Paid'),
}
@dataclass
class Assumptions:
 growth:float=.058
 wacc:float=.11
 terminal_growth:float=.04
 n:int=3
 min_cash:float=0.0
 shares:float|None=None  # actual shares, not crore shares
 market_price:float|None=None  # INR/share; user verified


def extract(df, account, year):
    cols=[c for c in df.columns if pd.Timestamp(c).year == year]
    if len(cols)!=1 or account not in df.index:
        return None
    v=df.loc[account,cols[0]]
    if isinstance(v,pd.Series) or pd.isna(v):return None
    return float(v)/RUPEES_PER_CRORE


def history(frames):
    years=sorted(set(pd.Timestamp(c).year for c in frames['Income'].columns))
    result={}
    for year in years:
        row={key:extract(frames[kind], account, year) for key,(kind,account) in SOURCE_MAP.items()}
        if row['revenue'] is not None:result[year]=row
    return result


def historical_checks(h):
    rows=[]
    for year,row in sorted(h.items()):
        def diff(*items):return sum(items) if all(v is not None for v in items) else None
        bs=diff(row['assets'], -row['liabilities'] if row['liabilities'] is not None else None, -row['equity'] if row['equity'] is not None else None)
        cf=diff(row['cash_begin'],row['cfo'],row['cfi'],row['cff'],row['fx'], -row['cash_end'] if row['cash_end'] is not None else None)
        difference=diff(row['cash_end'],-row['cash_bs'] if row['cash_bs'] is not None else None)
        rows.append({'year':year,'bs_diff':bs,'bs_status':'PASS' if bs is not None and abs(bs)<.01 else 'REVIEW',
                     'cf_diff':cf,'cf_status':'PASS' if cf is not None and abs(cf)<.01 else 'REVIEW',
                     'cash_definition_difference':difference})
    return rows


def projections(h, a:Assumptions):
    if not (1<=a.n<=10):raise ValueError('Forecast years must be 1–10')
    if a.wacc<=a.terminal_growth:raise ValueError('WACC must exceed terminal growth')
    base_year=max(h)
    x=h[base_year]
    required=['revenue','cogs','ebit','ni','tax','pretax','da','capex','cash_bs','assets','liabilities','equity','debt','ar','inventory','ap','ppe','dividends']
    missing=[k for k in required if x[k] is None]
    if missing:raise ValueError('Last actual period lacks: '+', '.join(missing))
    if x['revenue']<=0 or x['pretax']==0:raise ValueError('Invalid base revenue or pretax income')
    if abs(x['assets']-x['liabilities']-x['equity'])>.01:raise ValueError('Historical balance sheet does not balance')
    rev=x['revenue']; ratios={k:x[k]/rev for k in ['cogs','ebit','ni','da','ar','inventory','ap']}
    ratios['capex']=abs(x['capex'])/rev
    ratios['dividends']=abs(x['dividends'])/rev
    tax=max(0,min(1,x['tax']/x['pretax']))
    other_assets=x['assets']-x['cash_bs']-x['ar']-x['inventory']-x['ppe']
    other_liabilities=x['liabilities']-x['debt']-x['ap']
    if other_assets < -0.01 or other_liabilities < -0.01: raise ValueError('Simplified balance sheet component classification invalid; inspect liabilities/debt overlap')
    prev={'year':base_year,'revenue':rev,'ar':x['ar'],'inventory':x['inventory'],'ap':x['ap'],'ppe':x['ppe'],
          'debt':x['debt'],'equity':x['equity'],'cash':x['cash_bs'],'other_assets':other_assets,'other_liabilities':other_liabilities}
    records=[]
    for i in range(1,a.n+1):
        revenue=prev['revenue']*(1+a.growth)
        cogs=revenue*ratios['cogs'];ebit=revenue*ratios['ebit'];ni=revenue*ratios['ni'];da=revenue*ratios['da']
        capex=revenue*ratios['capex']; dividends=revenue*ratios['dividends']
        ar=revenue*ratios['ar']; inventory=revenue*ratios['inventory'];ap=revenue*ratios['ap']
        delta_nwc=(ar+inventory-ap)-(prev['ar']+prev['inventory']-prev['ap'])
        ppe=prev['ppe']+capex-da
        equity=prev['equity']+ni-dividends
        cfo=ni+da-delta_nwc
        cfi=-capex
        cash_pre_finance=prev['cash']+cfo+cfi-dividends
        # Explicit financing policy: borrow only if pre-financing cash is below the minimum;
        # do not assume debt repayment automatically. This can lead to cash accumulation.
        borrowing=max(0.0,a.min_cash-cash_pre_finance)
        debt=prev['debt']+borrowing
        cff=borrowing-dividends
        cash=prev['cash']+cfo+cfi+cff
        assets=cash+ar+inventory+ppe+other_assets
        liabilities=debt+ap+other_liabilities
        bs_diff=assets-liabilities-equity
        cash_diff=cash-(prev['cash']+cfo+cfi+cff)
        fcff=ebit*(1-tax)+da-capex-delta_nwc
        row={'year':base_year+i,'revenue':revenue,'cogs':cogs,'gross_profit':revenue-cogs,'ebit':ebit,'ni':ni,'da':da,
             'capex':capex,'dividends':dividends,'ar':ar,'inventory':inventory,'ap':ap,'delta_nwc':delta_nwc,
             'ppe':ppe,'equity':equity,'debt':debt,'new_borrowing':borrowing,'cash':cash,'opening_cash':prev['cash'],
             'cfo':cfo,'cfi':cfi,'cff':cff,'assets':assets,'liabilities':liabilities,
             'other_assets':other_assets,'other_liabilities':other_liabilities,'bs_diff':bs_diff,'cash_diff':cash_diff,'fcff':fcff}
        records.append(row);prev=row
    if any(abs(r['bs_diff'])>.01 or abs(r['cash_diff'])>.01 for r in records):raise ArithmeticError('Forecast statements did not reconcile')
    terminal=records[-1]['fcff']*(1+a.terminal_growth)/(a.wacc-a.terminal_growth)
    pv_flows=sum(r['fcff']/(1+a.wacc)**i for i,r in enumerate(records,1))
    pv_terminal=terminal/(1+a.wacc)**a.n
    ev=pv_flows+pv_terminal
    equity_value=ev-x['debt']+x['cash_bs']
    valuation={'enterprise_value':ev,'equity_value':equity_value,'pv_flows':pv_flows,'terminal_value':terminal,
               'pv_terminal':pv_terminal,'tax_rate':tax,'base_year':base_year,'base_debt':x['debt'],'base_cash':x['cash_bs']}
    return records,valuation,ratios


def workbook(ticker, frames, assumptions):
    h=history(frames); f,v,ratios=projections(h,assumptions);checks=historical_checks(h)
    wb=Workbook();hist=wb.active;hist.title='Historical';ass=wb.create_sheet('Assumptions');inc=wb.create_sheet('Forecast IS');bs=wb.create_sheet('Forecast BS');cf=wb.create_sheet('Forecast CF');dcf=wb.create_sheet('DCF');valid=wb.create_sheet('Validation');sources=wb.create_sheet('Sources')
    years=sorted(h)
    hist.append(['INR crore | provider source']+[f'FY{y}A' for y in years])
    for key in SOURCE_MAP:hist.append([key]+[h[y][key] for y in years])
    ass.append(['Forecast assumption','Value','Basis'])
    assumptions_rows=[('Revenue growth',assumptions.growth,'User assumption'),('COGS as revenue fraction',ratios['cogs'],'Latest actual'),('EBIT margin',ratios['ebit'],'Latest actual'),('Net profit margin',ratios['ni'],'Latest actual; held fixed, not independently linked to debt interest'),('D&A / revenue',ratios['da'],'Latest actual'),('CAPEX / revenue',ratios['capex'],'Latest actual'),('Accounts receivable / revenue',ratios['ar'],'Latest actual'),('Inventory / revenue',ratios['inventory'],'Latest actual'),('Accounts payable / revenue',ratios['ap'],'Latest actual'),('Dividends / revenue',ratios['dividends'],'Latest actual'),('Effective tax rate',v['tax_rate'],'Latest actual'),('Minimum cash (INR crore)',assumptions.min_cash,'User assumption, incremental borrowing if necessary'),('WACC',assumptions.wacc,'User assumption, not independently estimated'),('Terminal growth',assumptions.terminal_growth,'User assumption; below WACC')]
    for row in assumptions_rows:ass.append(row)
    ac={label:i for i,(label,_,_) in enumerate(assumptions_rows,2)}
    columns=['FY'+str(v['base_year'])+'A']+[f'FY{r["year"]}E' for r in f]
    in_items=['revenue','cogs','gross_profit','ebit','ni','da']
    bs_items=['cash','ar','inventory','ppe','other_assets','assets','ap','debt','other_liabilities','liabilities','equity','bs_diff']
    cf_items=['opening_cash','ni','da','delta_nwc','cfo','capex','dividends','new_borrowing','cfi','cff','cash','cash_diff']
    base=h[v['base_year']]
    for sheet,items in [(inc,in_items),(bs,bs_items),(cf,cf_items)]:
        sheet.append([sheet.title+' | INR crore']+columns)
        for key in items:sheet.append([key])
    positions={name:{key:i+2 for i,key in enumerate(items)} for name,items in [('Forecast IS',in_items),('Forecast BS',bs_items),('Forecast CF',cf_items)]}
    ir=positions['Forecast IS'];br=positions['Forecast BS'];cr=positions['Forecast CF']
    base_nwc=base['ar']+base['inventory']-base['ap']
    base_items={'gross_profit':base['revenue']-base['cogs'],'other_assets':base['assets']-base['cash_bs']-base['ar']-base['inventory']-base['ppe'],
                'other_liabilities':base['liabilities']-base['debt']-base['ap'],'bs_diff':base['assets']-base['liabilities']-base['equity'],
                'opening_cash':base['cash_begin'],'delta_nwc':None,'new_borrowing':None,'cash_diff':None,'cash':base['cash_bs']}
    for sheet,items in [(inc,in_items),(bs,bs_items),(cf,cf_items)]:
        for key in items:
            value=base_items.get(key,base.get(key))
            sheet.cell(positions[sheet.title][key],2,value)
    for i,r in enumerate(f,3):
        col=get_column_letter(i);prev=get_column_letter(i-1)
        formulas_is={
            'revenue':f"={prev}{ir['revenue']}*(1+Assumptions!$B${ac['Revenue growth']})",
            'cogs':f"={col}{ir['revenue']}*Assumptions!$B${ac['COGS as revenue fraction']}",
            'gross_profit':f"={col}{ir['revenue']}-{col}{ir['cogs']}",
            'ebit':f"={col}{ir['revenue']}*Assumptions!$B${ac['EBIT margin']}",
            'ni':f"={col}{ir['revenue']}*Assumptions!$B${ac['Net profit margin']}",
            'da':f"={col}{ir['revenue']}*Assumptions!$B${ac['D&A / revenue']}"}
        for key,formula in formulas_is.items():inc.cell(ir[key],i,formula)
        formulas_bs={
          'cash':f"='Forecast CF'!{col}{cr['cash']}",
          'ar':f"='Forecast IS'!{col}{ir['revenue']}*Assumptions!$B${ac['Accounts receivable / revenue']}",
          'inventory':f"='Forecast IS'!{col}{ir['revenue']}*Assumptions!$B${ac['Inventory / revenue']}",
          'ppe':f"={prev}{br['ppe']}+'Forecast CF'!{col}{cr['capex']}-'Forecast IS'!{col}{ir['da']}",
          'other_assets':f"={prev}{br['other_assets']}",
          'assets':f"=SUM({col}{br['cash']}:{col}{br['other_assets']})",
          'ap':f"='Forecast IS'!{col}{ir['revenue']}*Assumptions!$B${ac['Accounts payable / revenue']}",
          'debt':f"={prev}{br['debt']}+'Forecast CF'!{col}{cr['new_borrowing']}",
          'other_liabilities':f"={prev}{br['other_liabilities']}",
          'liabilities':f"=SUM({col}{br['ap']}:{col}{br['other_liabilities']})",
          'equity':f"={prev}{br['equity']}+'Forecast IS'!{col}{ir['ni']}-'Forecast CF'!{col}{cr['dividends']}",
          'bs_diff':f"={col}{br['assets']}-{col}{br['liabilities']}-{col}{br['equity']}"}
        for key,formula in formulas_bs.items():bs.cell(br[key],i,formula)
        formulas_cf={
          'opening_cash':f"={prev}{cr['cash']}",
          'ni':f"='Forecast IS'!{col}{ir['ni']}",
          'da':f"='Forecast IS'!{col}{ir['da']}",
          'delta_nwc':f"=('Forecast BS'!{col}{br['ar']}+'Forecast BS'!{col}{br['inventory']}-'Forecast BS'!{col}{br['ap']})-('Forecast BS'!{prev}{br['ar']}+'Forecast BS'!{prev}{br['inventory']}-'Forecast BS'!{prev}{br['ap']})",
          'cfo':f"=SUM({col}{cr['ni']}:{col}{cr['da']})-{col}{cr['delta_nwc']}",
          'capex':f"='Forecast IS'!{col}{ir['revenue']}*Assumptions!$B${ac['CAPEX / revenue']}",
          'dividends':f"='Forecast IS'!{col}{ir['revenue']}*Assumptions!$B${ac['Dividends / revenue']}",
          'new_borrowing':f"=MAX(0,Assumptions!$B${ac['Minimum cash (INR crore)']}-({col}{cr['opening_cash']}+{col}{cr['cfo']}-{col}{cr['capex']}-{col}{cr['dividends']}))",
          'cfi':f"=-{col}{cr['capex']}",
          'cff':f"={col}{cr['new_borrowing']}-{col}{cr['dividends']}",
          'cash':f"={col}{cr['opening_cash']}+{col}{cr['cfo']}+{col}{cr['cfi']}+{col}{cr['cff']}",
          'cash_diff':f"={col}{cr['cash']}-({col}{cr['opening_cash']}+{col}{cr['cfo']}+{col}{cr['cfi']}+{col}{cr['cff']})"}
        for key,formula in formulas_cf.items():cf.cell(cr[key],i,formula)
    dcf.append(['Discounted cash flow | INR crore','Amount'])
    dcf.append(['Tax rate',f"=Assumptions!B{ac['Effective tax rate']}"])
    dcf.append(['WACC',f"=Assumptions!B{ac['WACC']}"])
    dcf.append(['Terminal growth',f"=Assumptions!B{ac['Terminal growth']}"])
    dcf.append(['Period']+[r['year'] for r in f])
    dcf.append(['FCFF'])
    dcf.append(['Discount factor'])
    dcf.append(['Present value FCFF'])
    for idx,r in enumerate(f,3):
        col=get_column_letter(idx-1); fc=get_column_letter(idx)
        # FCFF = EBIT*(1-tax)+DA-CAPEX-deltaNWC
        dcf.cell(6,idx-1,f"='Forecast IS'!{fc}{ir['ebit']}*(1-$B$2)+'Forecast IS'!{fc}{ir['da']}-'Forecast CF'!{fc}{cr['capex']}-'Forecast CF'!{fc}{cr['delta_nwc']}")
        dcf.cell(7,idx-1,f'=1/(1+$B$3)^{idx-2}')
        dcf.cell(8,idx-1,f'={col}6*{col}7')
    last=get_column_letter(len(f)+2);last_dcf=get_column_letter(len(f)+1)
    # replace valuation summary rows explicitly (avoid off-by-one references)
    for row,(title,value) in enumerate([
       ('PV forecast FCFF',f'=SUM(B8:{last_dcf}8)'),
       ('Terminal value',f'={last_dcf}6*(1+$B$4)/($B$3-$B$4)'),
       ('PV terminal value',f'=B10/(1+$B$3)^{len(f)}'),
       ('Enterprise value','=B9+B11'),
       ('Base-year total debt',v['base_debt']),('Base-year BS cash',v['base_cash']),('Illustrative equity value','=B12-B13+B14')],9):
        dcf.cell(row,1,title);dcf.cell(row,2,value)
    valid.append(['Historical FY','BS difference','BS status','CF difference','CF status','CF cash - BS cash'])
    for z in checks:valid.append([f"FY{z['year']}",z['bs_diff'],z['bs_status'],z['cf_diff'],z['cf_status'],z['cash_definition_difference']])
    valid.append([]);valid.append(['Forecast FY','BS difference','BS status','CF difference','CF status','Borrowing'])
    for idx,row in enumerate(f,3):
        col=get_column_letter(idx)
        valid.append([f"FY{row['year']}",f"='Forecast BS'!{col}{br['bs_diff']}",f'=IF(ABS(B{valid.max_row+1})<0.01,"PASS","REVIEW")',f"='Forecast CF'!{col}{cr['cash_diff']}",f'=IF(ABS(D{valid.max_row+1})<0.01,"PASS","REVIEW")',f"='Forecast CF'!{col}{cr['new_borrowing']}"])
    sources.append(['Source','Yahoo Finance / yfinance (NOT verified against official annual reports)'])
    sources.append(['Ticker',ticker]);sources.append(['Fetched UTC',datetime.now(timezone.utc).isoformat()])
    sources.append(['Units','INR crore; assumes source monetary amounts in INR'])
    sources.append(['Forecast policy','Constant profit margins, working capital ratios and other asset/liability balances'])
    sources.append(['Funding','Positive debt borrowing only when cash < minimum cash; no debt repayment modeled'])
    sources.append(['FX effects forecast','Zero'])
    sources.append(['Historical CF cash versus BS cash','Definitions differ; explicit open review item'])
    sources.append(['Forecast equity','Total equity (incl. minority interests) increases by net income less dividends; simplifying assumption'])
    sources.append(['Model purpose','Educational scenario model; not audited, no investment recommendation'])
    # Per-share stock valuation. Never guess shares or a live market quote.
    stock=wb.create_sheet('Stock Valuation')
    stock.append(['FINSIGHT | STOCK VALUATION','Value','Notes'])
    stock.append(['Company ticker',ticker,'Confirm quote/share class against reporting entity'])
    stock.append(['Enterprise value (INR crore)', '=DCF!B12', 'Scenario-based FCFF DCF'])
    stock.append(['Equity value (INR crore)', '=DCF!B15', 'EV - model debt + model cash; simplifying assumption'])
    stock.append(['Diluted shares (actual shares)',assumptions.shares,'Required: latest diluted shares, not in crores'])
    stock.append(['Model value per share (INR)', '=IF(OR(NOT(ISNUMBER(B5)),B5<=0),"",B4*10000000/B5)', 'Only if source/reporting currency is independently verified as INR'])
    stock.append(['Market share price (INR)',assumptions.market_price,'User-supplied quote; verify date and share class'])
    stock.append(['Model difference vs price','=IF(OR(NOT(ISNUMBER(B6)),NOT(ISNUMBER(B7)),B7<=0),"",B6/B7-1)','Not a trade recommendation'])
    stock.append(['Result status','=IF(OR(NOT(ISNUMBER(B5)),B5<=0,NOT(ISNUMBER(B7)),B7<=0),"INPUTS MISSING","ILLUSTRATIVE — SOURCE REVIEW")'])
    stock.append(['WACC sensitivity / terminal growth','-1%','Base','+1%'])
    for i, delta in enumerate((-.01,0,.01),2):stock.cell(11,i,f'=DCF!B4{delta:+.2f}')
    for j, delta in enumerate((-.01,0,.01),12):
        stock.cell(j,1,f'=DCF!B3{delta:+.2f}')
        for i in (2,3,4):
            col=get_column_letter(i)
            pv='+'.join(f'DCF!{get_column_letter(k+1)}6/(1+$A{j})^{k}' for k in range(1,len(f)+1))
            last_col=get_column_letter(len(f)+1)
            expr=f'{pv}+(DCF!{last_col}6*(1+{col}$11)/($A{j}-{col}$11))/(1+$A{j})^{len(f)}-DCF!B13+DCF!B14'
            stock.cell(j,i,f'=IF(OR(NOT(ISNUMBER($B$5)),$B$5<=0,$A{j}<={col}$11),"",({expr})*10000000/$B$5)')
    stock['B8'].number_format='0.00%'
    for c in stock[11][1:4]:c.number_format='0.0%'
    for j in range(12,15):stock.cell(j,1).number_format='0.0%'
    stock.column_dimensions['C'].width=80
    sources.append(['Stock valuation','Per-share values only when the user supplies verified diluted shares and market price'])
    sources.append(['Market price freshness','User-supplied; quote timestamp not fetched automatically'])
    for sheet in wb:
        sheet.freeze_panes='B2';sheet.column_dimensions['A'].width=44
        for ci in range(2,max(sheet.max_column+1,7)):sheet.column_dimensions[get_column_letter(ci)].width=22
        for cell in sheet[1]:cell.fill=PatternFill('solid',fgColor='183153');cell.font=Font(bold=True,color='FFFFFF')
        for row in sheet.iter_rows(min_row=2,min_col=2):
            for cell in row:
                if cell.data_type=='f' or isinstance(cell.value,(int,float)):cell.number_format='#,##0.00;[Red](#,##0.00)'
    for i in list(range(2,13))+[14,15]:ass.cell(i,2).number_format='0.00%'
    ass.cell(13,2).number_format='#,##0.00'
    dcf['B2'].number_format='0.00%';dcf['B3'].number_format='0.00%';dcf['B4'].number_format='0.00%'
    bio=io.BytesIO();wb.save(bio)
    return bio.getvalue(),h,f,v,checks
