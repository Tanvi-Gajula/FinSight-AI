"""Deterministic driver analysis. No claimed causal explanation without external evidence."""
from datetime import datetime, timezone
import pandas as pd

def _get(frames, kind, account, year):
    df=frames.get(kind)
    if df is None or df.empty or account not in df.index:return None
    cols=[c for c in df.columns if pd.Timestamp(c).year==int(year)]
    if len(cols)!=1:return None
    val=df.loc[account,cols[0]]
    if isinstance(val,pd.Series) or pd.isna(val):return None
    return float(val)

def investigate(ticker,frames,metric='operating',years=None):
    """Decompose margin changes exactly where data supports it; report residuals honestly."""
    inc=frames.get('Income')
    if inc is None or inc.empty:return {'error':'No income statement available'}
    available=sorted({pd.Timestamp(c).year for c in inc.columns})
    if years is None: years=available[-2:]
    if len(years)!=2: return {'error':'Need two financial years'}
    earlier,later=sorted(years)
    rev=[_get(frames,'Income','Total Revenue',y) for y in (earlier,later)]
    if any(v is None or v<=0 for v in rev):return {'error':'Missing or invalid revenue'}
    cogs=[_get(frames,'Income','Cost Of Revenue',y) for y in (earlier,later)]
    operating=[_get(frames,'Income','Operating Income',y) for y in (earlier,later)]
    net=[_get(frames,'Income','Net Income',y) for y in (earlier,later)]
    data={'ticker':ticker,'periods':[earlier,later],'source':'Yahoo Finance via yfinance, provider-extracted and not independently verified', 'retrieved_utc':datetime.now(timezone.utc).isoformat(), 'currency':'raw source reporting-currency units; margin contributions in percentage points','supported_findings':[], 'unverified_causes':[], 'filing_evidence':[], 'status':'calculation-only; cause not verified'}
    data['supported_findings'].append({'metric':'revenue_growth_pct','value':100*(rev[1]/rev[0]-1),'formula':'100 × (new revenue / prior revenue - 1)','source_account':'Income Statement > Total Revenue'})
    if all(x is not None for x in operating):
        before,after=[100*v/r for v,r in zip(operating,rev)]
        data['supported_findings'].append({'metric':'operating_margin_change_pp','value':after-before,'before_pct':before,'after_pct':after,'formula':'100 × (new operating income / new revenue - prior operating income / prior revenue)','source_account':'Income Statement > Operating Income, Total Revenue'})
    if all(x is not None for x in cogs):
        b,a=[100*v/r for v,r in zip(cogs,rev)]
        data['supported_findings'].append({'metric':'cost_of_revenue_ratio_change_pp','value':a-b,'before_pct':b,'after_pct':a,'formula':'100 × (new cost of revenue / new revenue - prior cost of revenue / prior revenue)','source_account':'Income Statement > Cost Of Revenue, Total Revenue'})
        if all(x is not None for x in operating):
            overhead=[r-c-o for r,c,o in zip(rev,cogs,operating)]
            b,a=[100*v/r for v,r in zip(overhead,rev)]
            data['supported_findings'].append({'metric':'other_operating_costs_residual_ratio_change_pp','value':a-b,'before_pct':b,'after_pct':a,'formula':'100 × ((revenue - cost of revenue - operating income) / revenue change)','source_account':'Derived residual, not identified expense line'})
            data['supported_findings'].append({'metric':'operating_margin_decomposition_check_pp','value':(before-after)-((100*cogs[1]/rev[1]-100*cogs[0]/rev[0])+(a-b)),'formula':'negative margin change minus cost-ratio changes; should be ~0','source_account':'Derived'})
    if all(x is not None for x in net):
        b,a=[100*v/r for v,r in zip(net,rev)]
        data['supported_findings'].append({'metric':'net_margin_change_pp','value':a-b,'before_pct':b,'after_pct':a,'formula':'100 × (new net income / new revenue - prior net income / prior revenue)','source_account':'Income Statement > Net Income, Total Revenue'})
    data['unverified_causes']=['The calculations identify changes but do not prove business causation.','Official annual reports, management commentary and segment disclosures must be separately retrieved and cited to substantiate reasons.']
    return data

def format_investigation(result):
    if 'error' in result:return result['error']
    ys=result['periods']
    lines=[f"### What changed for {result['ticker']}?", f"Comparing FY{ys[0]} with FY{ys[1]}. **Source:** Yahoo Finance extracted statements (not independently filing-verified).",'', '**Calculated findings**']
    labels={'revenue_growth_pct':'Revenue growth','operating_margin_change_pp':'Operating margin movement','cost_of_revenue_ratio_change_pp':'Cost of revenue / sales movement','other_operating_costs_residual_ratio_change_pp':'Other operating cost residual / sales movement','net_margin_change_pp':'Net margin movement'}
    for item in result['supported_findings']:
        if item['metric'] not in labels:continue
        unit='%' if item['metric']=='revenue_growth_pct' else 'percentage points'
        lines.append(f"- **{labels[item['metric']]}:** {item['value']:+.2f} {unit}. Account: {item['source_account']}.")
    lines+=['','**Why?** The relative movements are calculated, but the *underlying business causes are not established* by these statements alone. Verify explanations against official filings before asserting them.','', '**How to verify:** Check annual-report management discussion and notes for both financial years. This app does not claim to have read those reports.']
    return '\n'.join(lines)
