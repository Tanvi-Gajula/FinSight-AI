import json, os
import pandas as pd
from investigation import investigate, format_investigation
from financial_data import provider_history
from official_metrics import get_official

def _value(df,label):
    if df is None or df.empty or label not in df.index:return None
    for c in sorted(df.columns,key=lambda x:pd.Timestamp(x),reverse=True):
        v=df.loc[label,c]
        if not isinstance(v,pd.Series) and pd.notna(v):return pd.Timestamp(c).year,float(v)
    return None

def math_results(ticker,frames):
    return {'ticker':ticker,'historical':provider_history(ticker,frames),'source':'Yahoo Finance / yfinance provider extraction','verified':False,'official':get_official(ticker)}

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

def valuation_guidance(ticker):
    return f'''### Valuation for {ticker}\nFinSight can run an **illustrative free-cash-flow DCF** in the **Valuation Playground**.\n\nYou control:\n- FCF growth assumption\n- WACC / discount rate\n- terminal growth\n- forecast period\n- shares outstanding\n- market price (optional comparison)\n\nFinSight calculates the result in Python. Groq only explains it. The app will not invent missing assumptions or call the result a buy/sell recommendation.'''

def deterministic_answer(question,frames_by_ticker):
    if not frames_by_ticker:return 'Load a company first.'
    t=next(iter(frames_by_ticker)); frames=frames_by_ticker[t]; q=question.casefold(); foot='\n\n*Provider extraction should be checked against company filings before investment use.*'
    if any(x in q for x in ['valuat','intrinsic','dcf','fair value']):return valuation_guidance(t)+foot
    if any(x in q for x in ['why','reason','driver','margin','decline','increase']):return format_investigation(investigate(t,frames))+foot
    if 'cash flow' in q or 'cashflow' in q:
        lines=[]
        for label in ['Operating Cash Flow','Capital Expenditure','Free Cash Flow','Investing Cash Flow','Financing Cash Flow']:
            x=_value(frames.get('CashFlow'),label)
            if x:lines.append(f'- {label} FY{x[0]}: {x[1]:,.0f} raw provider units')
        return f'**{t}: latest cash-flow accounts**\n'+('\n'.join(lines) if lines else 'No matching cash-flow accounts found.')+foot
    d=provider_history(t,frames);lines=[f'**{t}: provider snapshot**']
    for x in d[-4:]:lines.append(f"- FY{x['year']}: revenue {x['revenue_raw']:,.0f} raw units"+(f", growth {x.get('revenue_growth_pct'):.2f}%" if x.get('revenue_growth_pct') is not None else ''))
    off=get_official(t)
    if off:
        y=max(off['years']);m=off['years'][y];lines+=['',f"**Official FY{y}:** revenue {m['revenue']:,.0f} {off['currency']} {off['scale']}; operating margin {m['operating_margin']:.1f}%; net margin {m['net_margin']:.1f}%.",f"Source: {off['source_url']}"]
    return '\n'.join(lines)+foot

SYSTEM='''You are FinSight AI, a learning-focused financial research assistant. Numeric facts must come only from tool outputs or supplied annual-report excerpts. Never infer currency from a ticker suffix. Never convert raw provider units unless currency and scale are explicitly verified. Company-reported KPIs and provider-derived ratios are different definitions: prefer curated official metrics when available and label provider-derived metrics clearly. Do not invent causes, filing citations, forecasts, fair values, or buy/sell recommendations. For WHY questions, separate calculated movement from company-supported explanation. The Valuation Playground is a user-assumption FCF scenario, not a company-specific forecast. If asked for valuation, direct the user to the Valuation Playground rather than asking them to type assumptions into chat. Answer the exact question briefly and clearly.'''

def agent_answer(question,frames_by_ticker,enabled=True,report_evidence=None):
    if not frames_by_ticker:return 'Load a company first.',[]
    t=next(iter(frames_by_ticker));q=question.casefold()
    # Product routing stays deterministic so the LLM cannot turn a valuation request into a generic summary.
    if any(x in q for x in ['valuat','intrinsic','dcf','fair value']):return valuation_guidance(t),[]
    if not enabled or not os.getenv('GROQ_API_KEY'):return deterministic_answer(question,frames_by_ticker),[]
    try:
        from langchain_groq import ChatGroq
        from langchain_core.tools import tool
        from langchain_core.messages import SystemMessage,HumanMessage,ToolMessage
        @tool
        def get_financial_overview(ticker:str)->str:
            """Get provider history plus curated official metrics when available."""
            k=ticker.upper().strip();return json.dumps(math_results(k,frames_by_ticker[k]) if k in frames_by_ticker else {'error':'ticker not loaded'})
        @tool
        def lookup_financial_account(ticker:str,search_term:str)->str:
            """Find provider statement accounts and annual raw values."""
            k=ticker.upper().strip();return json.dumps(facts(k,frames_by_ticker[k],search_term) if k in frames_by_ticker else {'error':'ticker not loaded'})
        @tool
        def investigate_financial_drivers(ticker:str)->str:
            """Get verified official KPI changes where curated, otherwise provider-derived movements."""
            k=ticker.upper().strip();return json.dumps(investigate(k,frames_by_ticker[k]) if k in frames_by_ticker else {'error':'ticker not loaded'})
        tools=[get_financial_overview,lookup_financial_account,investigate_financial_drivers]; mp={x.name:x for x in tools}
        model=ChatGroq(model='openai/gpt-oss-20b',temperature=0,max_retries=1).bind_tools(tools)
        ev=json.dumps(report_evidence or [],ensure_ascii=False)
        msgs=[SystemMessage(content=SYSTEM),HumanMessage(content=f'Loaded: {list(frames_by_ticker)}\nQuestion: {question}\nUploaded annual-report excerpts (use only if directly supportive): {ev}')];used=[]
        for _ in range(4):
            r=model.invoke(msgs);msgs.append(r)
            if not r.tool_calls:return (r.content if isinstance(r.content,str) and r.content.strip() else deterministic_answer(question,frames_by_ticker)),used
            for c in r.tool_calls:
                used.append({'tool':c['name'],'arguments':c['args']});msgs.append(ToolMessage(content=mp[c['name']].invoke(c['args']),tool_call_id=c['id']))
        return deterministic_answer(question,frames_by_ticker),used
    except Exception as e:return deterministic_answer(question,frames_by_ticker)+f'\n\n*AI unavailable ({type(e).__name__}); verified/local calculations shown instead.*',[]
