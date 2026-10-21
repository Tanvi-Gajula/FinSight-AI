import os,re,base64
from pathlib import Path
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from research import agent_answer,math_results
from investigation import investigate,format_investigation
from annual_reports import extract_pdf,evidence,reference_label
from financial_data import coverage
from model import Assumptions,workbook,dcf_inputs
ROOT=Path(__file__).resolve().parent;load_dotenv(ROOT/'.env')
st.set_page_config(page_title='FinSight AI',page_icon='🌷',layout='wide',initial_sidebar_state='expanded')
css=ROOT/'assets'/'theme.css'
if css.exists():st.markdown('<style>'+css.read_text(encoding='utf-8')+'</style>',unsafe_allow_html=True)

@st.cache_data(ttl=1800,show_spinner=False)
def fetch(ticker):
    import yfinance as yf
    s=yf.Ticker(ticker);r={'Income':s.income_stmt,'Balance':s.balance_sheet,'CashFlow':s.cashflow}
    if all(x is None or x.empty for x in r.values()):raise ValueError('No annual statements returned. Check the ticker or try another company.')
    return r
if 'companies' not in st.session_state:st.session_state.companies={}
if 'selected' not in st.session_state:st.session_state.selected=''
if 'messages' not in st.session_state:st.session_state.messages=[]
if 'reports' not in st.session_state:st.session_state.reports={}

with st.sidebar:
    st.title('🌷 FinSight AI');st.caption('Learn the numbers. Investigate the change. Test a valuation.')
    ticker=st.text_input('Company ticker','TCS.NS').strip().upper();go=st.button('Explore company',type='primary',use_container_width=True)
    if go:
        if not re.fullmatch(r'[A-Z0-9.^=_-]{1,25}',ticker):st.error('Invalid ticker.')
        else:
            try:
                with st.spinner('Loading annual statements...'):st.session_state.companies[ticker]=fetch(ticker)
                st.session_state.selected=ticker;st.session_state.messages=[]
            except Exception as e:st.error(str(e))
    if st.session_state.companies:
        st.session_state.selected=st.selectbox('Loaded company',list(st.session_state.companies),index=list(st.session_state.companies).index(st.session_state.selected) if st.session_state.selected in st.session_state.companies else 0)
    use_ai=st.toggle('Groq explanations',True);st.caption('Groq explains. Python calculates. Provider figures remain unverified until checked against filings.')

st.title('FinSight AI')
st.markdown('#### Financial research for learners — focused on **what changed, why it may have changed, and how to verify it.**')
active=st.session_state.selected if st.session_state.selected in st.session_state.companies else None
if not active:
    st.info('Enter a ticker in the sidebar to begin.');st.stop()
frames=st.session_state.companies[active];hist=math_results(active,frames)['historical'];latest=hist[-1] if hist else None
st.caption(f'{active} · Yahoo Finance/yfinance annual statement extraction · not independently filing-verified · raw provider units')
if latest:
    a,b,c=st.columns(3);a.metric('Latest revenue',f"{latest['revenue_raw']:,.0f}" if latest['revenue_raw'] is not None else 'N/A');b.metric('Revenue growth',f"{latest.get('revenue_growth_pct'):.2f}%" if latest.get('revenue_growth_pct') is not None else 'N/A');c.metric('Net margin',f"{latest.get('net_margin_pct'):.2f}%" if latest.get('net_margin_pct') is not None else 'N/A')
    st.warning('Do not read the revenue number as crore/billion until the reporting currency and scale are verified against the company filing.')

t_over,t_why,t_fin,t_reports,t_val=st.tabs(['🏠 Overview','🔎 Investigate WHY','📚 Financials','📄 Annual Reports','🧪 Valuation Playground'])
with t_over:
    st.subheader('Company snapshot')
    if hist:st.dataframe(pd.DataFrame(hist).rename(columns={'revenue_raw':'Revenue (raw units)','net_margin_pct':'Net margin %','operating_margin_pct':'Operating margin %','revenue_growth_pct':'Revenue growth %'}),use_container_width=True,hide_index=True)
    st.subheader('Ask FinSight')
    for m in st.session_state.messages:
        with st.chat_message(m['role']):st.markdown(m['content'])
    q=st.chat_input('Ask about revenue, margins, cash flow, debt or changes…')
    if q:
        with st.chat_message('user'):st.markdown(q)
        passages=[]
        for rep in st.session_state.reports.get(active,[]):passages+=evidence(rep,q,4)
        ans,calls=agent_answer(q,{active:frames},use_ai,sorted(passages,key=lambda x:x['relevance'],reverse=True)[:6])
        with st.chat_message('assistant'):st.markdown(ans)
        st.session_state.messages += [{'role':'user','content':q},{'role':'assistant','content':ans}]
with t_why:
    st.subheader('Investigate WHY')
    st.caption('FinSight first calculates the movement. It only treats a business reason as evidence-backed when the annual report supports it.')
    inc=frames.get('Income');years=sorted({pd.Timestamp(c).year for c in inc.columns}) if inc is not None and not inc.empty else []
    if len(years)>=2:
        end=st.selectbox('Ending financial year',years[1:],index=len(years)-2);start=years[years.index(end)-1]
        st.markdown(format_investigation(investigate(active,frames,[start,end])))
        reps=st.session_state.reports.get(active,[])
        if reps:
            search=st.text_input('Search uploaded annual report for possible evidence','revenue demand margin employee cost pricing')
            hits=sorted([h for r in reps for h in evidence(r,search,5)],key=lambda x:x['relevance'],reverse=True)[:6]
            for h in hits:st.markdown(f"**{reference_label(h)}** — {h['excerpt']}")
        else:st.info('Upload an annual report in the Annual Reports tab to add page-level evidence.')
with t_fin:
    st.subheader('Actual provider-extracted statements')
    st.caption('Missing stays missing. No zero substitution. Values remain in raw provider units until currency/scale verification.')
    cov=coverage(frames);st.dataframe(cov,use_container_width=True,hide_index=True)
    choice=st.radio('Statement',['Income','Balance','CashFlow'],horizontal=True);df=frames.get(choice)
    if df is not None and not df.empty:
        query=st.text_input('Filter accounts');view=df.loc[[i for i in df.index if query.casefold() in str(i).casefold()]] if query else df
        st.dataframe(view,use_container_width=True)
with t_reports:
    st.subheader('Annual-report evidence')
    st.write('Upload the company annual report PDF. FinSight searches extracted text and shows the PDF page so you can verify the explanation yourself.')
    files=st.file_uploader('Annual report PDF',type=['pdf'],accept_multiple_files=True)
    if files:
        st.session_state.reports[active]=[extract_pdf(x) for x in files];st.success(f'Loaded {len(files)} report(s) for this session.')
    st.caption('Automatic filing discovery is intentionally disabled in this reliability-focused version; explicit uploaded evidence is easier to audit.')
with t_val:
    st.subheader('Valuation Playground')
    st.info('This is a simple free-cash-flow scenario, not an automatic company forecast. It is disabled when essential FCF/debt/cash data is missing.')
    di=dcf_inputs(frames)
    if di['missing']:st.warning('Valuation unavailable for this company: '+', '.join(di['missing']))
    else:
        c1,c2=st.columns(2)
        growth=c1.slider('FCF growth assumption (%)',-10.0,25.0,6.0,.5)/100;years=c2.slider('Forecast years',3,10,5)
        wacc=c1.slider('WACC (%)',5.0,25.0,11.0,.5)/100;tg=c2.slider('Terminal growth (%)',0.0,7.0,4.0,.25)/100
        shares=st.number_input('Diluted shares outstanding — actual number of shares (0 if unknown)',min_value=0.0,value=0.0,step=1_000_000.0,format='%.0f')
        price=st.number_input('Market price per share — enter only after checking quote currency/date (0 if unknown)',min_value=0.0,value=0.0)
        if st.button('Run valuation scenario',type='primary'):
            try:
                blob,v=workbook(active,frames,Assumptions(growth,wacc,tg,years,shares or None,price or None));st.session_state['valuation']=(active,blob,v)
            except Exception as e:st.error(str(e))
        if st.session_state.get('valuation') and st.session_state['valuation'][0]==active:
            _,blob,v=st.session_state['valuation'];x,y,z=st.columns(3);x.metric('Enterprise value','Raw units '+f"{v['enterprise_value_raw']:,.0f}");y.metric('Intrinsic value / share',f"{v['intrinsic_value_per_share']:,.2f}" if v['intrinsic_value_per_share'] is not None else 'Need shares');z.metric('Difference vs entered price',f"{v['difference_vs_price']:.1%}" if v['difference_vs_price'] is not None else 'Need price')
            st.download_button('Download valuation Excel',blob,file_name=f'FinSight_{active.replace(".","_")}_Valuation.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            st.caption('Illustrative only. Verify financial statements, currency, shares, price, WACC and assumptions before using the output.')
