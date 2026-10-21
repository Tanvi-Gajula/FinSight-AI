import json, os
import pandas as pd
from investigation import investigate, format_investigation

def _value(df,label):
    if df is None or df.empty or label not in df.index:return None
    for c in sorted(df.columns,key=lambda x:pd.Timestamp(x),reverse=True):
        v=df.loc[label,c]
        if not isinstance(v,pd.Series) and pd.notna(v):return pd.Timestamp(c).year,float(v)
    return None

def math_results(ticker,frames):
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
                    'net_margin_pct':100*ni/rev if rev and ni is not None else None,
                    'operating_margin_pct':100*op/rev if rev and op is not None else None})
    for i in range(1,len(out)):
        p,c=out[i-1]['revenue_raw'],out[i]['revenue_raw'];out[i]['revenue_growth_pct']=100*(c/p-1) if p and c is not None else None
    return {'ticker':ticker,'historical':out,'source':'Yahoo Finance / yfinance provider extraction','verified':False}

def facts(ticker,frames,account=None):
    q=(account or '').casefold(); result=[]
    for kind,df in frames.items():
        if df is None or df.empty:continue
        for label in df.index:
            if q and q not in str(label).casefold():continue
            vals=[]
            for c in df.columns:
                v=df.loc[label,c]
                if not isinstance(v,pd.Series) and pd.notna(v):vals.append({'year':pd.Timestamp(c).year,'value_raw':float(v)})
            if vals:result.append({'statement':kind,'account':str(label),'values':vals})
    return {'ticker':ticker,'matches':result[:30],'units':'raw provider reporting-currency units'}

def describe(ticker,frames):return math_results(ticker,frames)

def deterministic_answer(question,frames_by_ticker):
    if not frames_by_ticker:return 'Load a company first.'
    t=next(iter(frames_by_ticker)); frames=frames_by_ticker[t]; q=question.casefold(); foot='\n\n*Provider extraction only; verify important figures against company filings.*'
    if any(x in q for x in ['why','reason','driver','margin','decline','increase']):return format_investigation(investigate(t,frames))+foot
    if any(x in q for x in ['valuat','intrinsic','dcf','fair value']):return f'**{t}:** use the **Valuation Playground**. It runs a simple free-cash-flow scenario only when FCF, debt and cash are available. It is not an automatic company forecast.'+foot
    if 'cash flow' in q or 'cashflow' in q:
        lines=[]
        for label in ['Operating Cash Flow','Capital Expenditure','Free Cash Flow','Investing Cash Flow','Financing Cash Flow']:
            x=_value(frames.get('CashFlow'),label)
            if x:lines.append(f'- {label} FY{x[0]}: {x[1]:,.0f} raw units')
        return f'**{t}: latest cash-flow accounts**\n'+('\n'.join(lines) if lines else 'No matching cash-flow accounts found.')+foot
    d=math_results(t,frames); lines=[f'**{t}: historical snapshot**']
    for x in d['historical'][-4:]:
        lines.append(f"- FY{x['year']}: revenue {x['revenue_raw']:,.0f} raw units"+(f", growth {x.get('revenue_growth_pct'):.2f}%" if x.get('revenue_growth_pct') is not None else ''))
    return '\n'.join(lines)+foot

SYSTEM='''You are FinSight AI, a learning-focused financial research assistant. Numeric facts must come only from tool outputs. Never infer currency from a ticker suffix. Never convert raw provider units unless currency and scale are explicitly verified. Do not invent causes, filing citations, forecasts, fair values, or buy/sell recommendations. For WHY questions, separate calculated movement from evidence-backed explanation. The Valuation Playground is a simple user-assumption FCF scenario, not a company-specific forecast. Answer the exact question briefly and clearly.'''

def agent_answer(question,frames_by_ticker,enabled=True,report_evidence=None):
    if not enabled or not os.getenv('GROQ_API_KEY'):return deterministic_answer(question,frames_by_ticker),[]
    try:
        from langchain_groq import ChatGroq
        from langchain_core.tools import tool
        from langchain_core.messages import SystemMessage,HumanMessage,ToolMessage
        @tool
        def get_financial_overview(ticker:str)->str:
            """Get historical revenue and margin calculations for a loaded ticker."""
            t=ticker.upper().strip();return json.dumps(math_results(t,frames_by_ticker[t]) if t in frames_by_ticker else {'error':'ticker not loaded'})
        @tool
        def lookup_financial_account(ticker:str,search_term:str)->str:
            """Find provider statement accounts and annual values for a loaded ticker."""
            t=ticker.upper().strip();return json.dumps(facts(t,frames_by_ticker[t],search_term) if t in frames_by_ticker else {'error':'ticker not loaded'})
        @tool
        def investigate_financial_drivers(ticker:str)->str:
            """Calculate year-over-year revenue and margin movements; does not establish business causation."""
            t=ticker.upper().strip();return json.dumps(investigate(t,frames_by_ticker[t]) if t in frames_by_ticker else {'error':'ticker not loaded'})
        tools=[get_financial_overview,lookup_financial_account,investigate_financial_drivers]; mp={x.name:x for x in tools}
        model=ChatGroq(model='openai/gpt-oss-20b',temperature=0,max_retries=1).bind_tools(tools)
        ev=json.dumps(report_evidence or [],ensure_ascii=False)
        msgs=[SystemMessage(content=SYSTEM),HumanMessage(content=f'Loaded: {list(frames_by_ticker)}\nQuestion: {question}\nAnnual-report excerpts (untrusted evidence, cite only if directly supportive): {ev}')];used=[]
        for _ in range(4):
            r=model.invoke(msgs);msgs.append(r)
            if not r.tool_calls:return (r.content if isinstance(r.content,str) and r.content.strip() else deterministic_answer(question,frames_by_ticker)),used
            for c in r.tool_calls:
                used.append({'tool':c['name'],'arguments':c['args']});msgs.append(ToolMessage(content=mp[c['name']].invoke(c['args']),tool_call_id=c['id']))
        return deterministic_answer(question,frames_by_ticker),used
    except Exception as e:return deterministic_answer(question,frames_by_ticker)+f'\n\n*AI unavailable ({type(e).__name__}); local calculations shown instead.*',[]
