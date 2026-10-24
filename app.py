import os,re
from pathlib import Path
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from research import agent_answer
from investigation import investigate,format_investigation
from annual_reports import extract_pdf,evidence,reference_label
from financial_data import coverage,provider_profile,research_snapshot,format_money
from official_metrics import get_official
from model import Assumptions,workbook,dcf_inputs

ROOT=Path(__file__).resolve().parent;load_dotenv(ROOT/'.env')
st.set_page_config(page_title='FinSight AI',page_icon='🌷',layout='wide',initial_sidebar_state='expanded')
css=ROOT/'assets'/'theme.css'
if css.exists():st.markdown('<style>'+css.read_text(encoding='utf-8')+'</style>',unsafe_allow_html=True)

@st.cache_data(ttl=1800,show_spinner=False)
def fetch_company(ticker):
    import yfinance as yf
    s=yf.Ticker(ticker);frames={'Income':s.income_stmt,'Balance':s.balance_sheet,'CashFlow':s.cashflow}
    if all(x is None or x.empty for x in frames.values()):raise ValueError('No annual statements returned. Check the ticker or try another company.')
    return frames,provider_profile(ticker,s)

for key,default in [('companies',{}),('profiles',{}),('selected',''),('messages',{}),('reports',{})]:
    if key not in st.session_state:st.session_state[key]=default

with st.sidebar:
    st.markdown('## 🌷 FinSight AI')
    st.caption('Understand → investigate → verify → value')
    ticker=st.text_input('Company ticker','TCS.NS',help='Examples: TCS.NS, INFY.NS, AAPL').strip().upper()
    if st.button('Explore company',type='primary',use_container_width=True):
        if not re.fullmatch(r'[A-Z0-9.^=_-]{1,25}',ticker):st.error('Invalid ticker format.')
        else:
            try:
                with st.spinner('Loading annual statements...'):frames,profile=fetch_company(ticker)
                st.session_state.companies[ticker]=frames;st.session_state.profiles[ticker]=profile;st.session_state.selected=ticker
                st.session_state.messages.setdefault(ticker,[])
            except Exception as e:st.error(str(e))
    if st.session_state.companies:
        keys=list(st.session_state.companies);idx=keys.index(st.session_state.selected) if st.session_state.selected in keys else 0
        st.session_state.selected=st.selectbox('Research shelf',keys,index=idx)
    use_ai=st.toggle('Groq study buddy',True)
    st.caption('Python calculates. Official filings override provider-derived KPIs when curated. Groq explains; it does not create financial numbers.')
    st.divider();st.caption('Educational research only · no buy/sell recommendations')

st.markdown('<div class="hero"><div class="eyebrow">FINANCIAL RESEARCH FOR LEARNERS</div><h1>FinSight AI</h1><p>See what changed, understand what the numbers can and cannot prove, verify the story, then test your own valuation assumptions.</p></div>',unsafe_allow_html=True)
active=st.session_state.selected if st.session_state.selected in st.session_state.companies else None
if not active:
    st.info('Enter a ticker in the sidebar to begin. Try TCS.NS or INFY.NS.');st.stop()
frames=st.session_state.companies[active];profile=st.session_state.profiles.get(active,{})
snap=research_snapshot(active,frames);official=snap['official'];latestp=snap['latest_provider'];latesto=snap['latest_official']

# Trust banner and top metrics
if official:
    st.markdown(f'<div class="trust good"><b>✓ Official KPI layer available</b> · {official["source_name"]} · provider statements remain visible for traceability.</div>',unsafe_allow_html=True)
    m1,m2,m3,m4=st.columns(4)
    m1.metric('Revenue',format_money(latesto['revenue'],official['currency'],official['scale']))
    m2.metric('Operating margin',f"{latesto['operating_margin']:.1f}%")
    m3.metric('Net margin',f"{latesto['net_margin']:.1f}%")
    prev=official['years'].get(latesto['year']-1);growth=100*(latesto['revenue']/prev['revenue']-1) if prev else None
    m4.metric('Revenue growth',f'{growth:.1f}%' if growth is not None else 'N/A')
    st.caption(f"FY{latesto['year']} company-reported metrics · {official['currency']} {official['scale']} · official source linked below")
else:
    st.markdown('<div class="trust caution"><b>Provider-derived view</b> · no curated official KPI profile yet. Raw statement units and accounting definitions require filing verification.</div>',unsafe_allow_html=True)
    m1,m2,m3=st.columns(3)
    m1.metric('Latest revenue · raw',f"{latestp.get('revenue_raw'):,.0f}" if latestp.get('revenue_raw') is not None else 'N/A')
    m2.metric('Revenue growth',f"{latestp.get('revenue_growth_pct'):.2f}%" if latestp.get('revenue_growth_pct') is not None else 'N/A')
    m3.metric('Provider-derived net margin',f"{latestp.get('provider_net_margin_pct'):.2f}%" if latestp.get('provider_net_margin_pct') is not None else 'N/A')

# Simpler four-step navigation
t_over,t_why,t_evidence,t_val=st.tabs(['① Snapshot & Ask','② Investigate WHY','③ Verify & Financials','④ Valuation Playground'])

with t_over:
    left,right=st.columns([1.35,1])
    with left:
        st.subheader('At a glance')
        if official:
            rows=[]
            for y,v in sorted(official['years'].items()):rows.append({'FY':y,'Revenue':v['revenue'],'Operating margin %':v['operating_margin'],'Net margin %':v['net_margin']})
            odf=pd.DataFrame(rows).set_index('FY');st.line_chart(odf[['Revenue']],height=230)
            st.caption(f"Revenue chart uses verified {official['currency']} {official['scale']} values from the official KPI layer.")
            with st.expander('Why provider ratios may look different'):
                po=latestp.get('provider_operating_margin_pct');pn=latestp.get('provider_net_margin_pct')
                st.write(f"Yahoo/yfinance-derived latest operating margin: **{po:.2f}%**" if po is not None else 'Provider operating margin unavailable.')
                st.write(f"Yahoo/yfinance-derived latest net margin: **{pn:.2f}%**" if pn is not None else 'Provider net margin unavailable.')
                st.write(f"Company-reported latest operating margin: **{latesto['operating_margin']:.1f}%**; net margin: **{latesto['net_margin']:.1f}%**.")
                st.info('Different provider account mappings or KPI definitions can produce different ratios. FinSight does not silently merge them.')
            st.markdown(f"**Official source:** [{official['source_name']}]({official['source_url']})")
        else:
            pdf=pd.DataFrame(snap['provider_history'])
            if not pdf.empty:st.line_chart(pdf.set_index('year')[['revenue_raw']],height=230)
            st.warning('This chart is in raw provider units. Do not label it INR/USD/crore/billion until the filing establishes the statement currency and scale.')
    with right:
        st.subheader('Data confidence')
        st.markdown('**Official KPIs:** '+('Available ✓' if official else 'Not curated yet'))
        st.markdown('**Provider statements:** Available ✓')
        st.markdown('**Uploaded annual report:** '+('Available ✓' if st.session_state.reports.get(active) else 'Not uploaded'))
        if profile.get('quote_currency'):st.markdown(f"**Quote currency:** {profile['quote_currency']} *(market quote metadata only; not statement currency)*")
        st.caption('A stock quote currency does not prove the currency used in extracted financial statements.')

    st.divider();st.subheader('Ask FinSight')
    qcols=st.columns(3);quick=None
    if qcols[0].button('Why did operating margin change?',use_container_width=True,key=f'q1{active}'):quick='Why did operating margin change?'
    if qcols[1].button('Explain latest cash flow',use_container_width=True,key=f'q2{active}'):quick='Explain the latest operating cash flow'
    if qcols[2].button('How do I value this stock?',use_container_width=True,key=f'q3{active}'):quick='Do stock valuation'
    for m in st.session_state.messages.setdefault(active,[]):
        with st.chat_message(m['role']):st.markdown(m['content'],unsafe_allow_html=True)
    typed=st.chat_input('Ask about revenue, margins, cash flow, debt, changes or valuation…');q=quick or typed
    if q:
        with st.chat_message('user'):st.markdown(q)
        passages=[]
        for rep in st.session_state.reports.get(active,[]):passages+=evidence(rep,q,4)
        ans,calls=agent_answer(q,{active:frames},use_ai,sorted(passages,key=lambda x:x['relevance'],reverse=True)[:6])
        with st.chat_message('assistant'):st.markdown(ans,unsafe_allow_html=True)
        st.session_state.messages[active]+=[{'role':'user','content':q},{'role':'assistant','content':ans}]

with t_why:
    st.subheader('Investigate WHY')
    st.write('FinSight separates **measurement** from **explanation**. That prevents a numerical relationship from being presented as a business cause.')
    inc=frames.get('Income');years=sorted({pd.Timestamp(c).year for c in inc.columns}) if inc is not None and not inc.empty else []
    if len(years)>=2:
        end=st.selectbox('Ending financial year',years[1:],index=len(years)-2,key='whyyear');start=years[years.index(end)-1]
        result=investigate(active,frames,[start,end]);st.markdown(format_investigation(result),unsafe_allow_html=True)
        if official and result.get('official'):
            st.success('This comparison uses curated company-reported KPI definitions for the headline margins.')
        st.markdown('#### Evidence desk')
        reps=st.session_state.reports.get(active,[])
        if reps:
            search=st.text_input('Search your uploaded annual report','operating margin productivity pricing costs currency',key='whysearch')
            hits=sorted([h for r in reps for h in evidence(r,search,5)],key=lambda x:x['relevance'],reverse=True)[:6]
            for h in hits:
                with st.expander(reference_label(h)):st.write(h['excerpt'])
        else:st.info('Upload the annual report in “Verify & Financials” to add page-level evidence to your investigation.')

with t_evidence:
    c1,c2=st.columns([1,1.25])
    with c1:
        st.subheader('Annual-report evidence')
        st.write('Upload the official annual report PDF. FinSight keeps the page number with each evidence excerpt so you can check the source yourself.')
        files=st.file_uploader('Annual report PDF',type=['pdf'],accept_multiple_files=True,key=f'upload{active}')
        if files:
            with st.spinner('Reading report pages...'):st.session_state.reports[active]=[extract_pdf(x) for x in files]
            st.success(f"Loaded {len(files)} report(s), {sum(r['page_count'] for r in st.session_state.reports[active])} PDF pages.")
        if official:st.markdown(f"**Curated official KPI source:** [{official['source_name']}]({official['source_url']})")
        st.caption('FinSight does not claim an explanation is filing-backed unless a company source or uploaded report supports it.')
    with c2:
        st.subheader('Statement coverage')
        cov=coverage(frames);st.dataframe(cov,use_container_width=True,hide_index=True,height=300)
    st.divider();st.subheader('Provider-extracted financial statements')
    st.caption('These are useful for exploration, but account mappings and units can differ from company-reported KPIs. Missing values remain missing.')
    choice=st.radio('Statement',['Income','Balance','CashFlow'],horizontal=True,key='statement');df=frames.get(choice)
    if df is not None and not df.empty:
        query=st.text_input('Filter accounts',key='accountfilter');view=df.loc[[i for i in df.index if query.casefold() in str(i).casefold()]] if query else df
        st.dataframe(view,use_container_width=True,height=500)

with t_val:
    st.subheader('Valuation Playground')
    st.write('A transparent **FCF scenario**, not an automatic prediction of the company. Change assumptions and see how sensitive estimated value is.')
    di=dcf_inputs(frames)
    if di['missing']:st.warning('Valuation unavailable because the provider data is missing: '+', '.join(di['missing']))
    else:
        st.caption(f"Starting FCF: {di['fcf'][1]:,.0f} raw provider units · method: {di['fcf_method']}. Verify statement currency/scale before interpreting enterprise value.")
        a1,a2,a3=st.columns(3)
        growth=a1.slider('FCF growth (%)',-10.0,25.0,6.0,.5)/100
        wacc=a2.slider('WACC (%)',5.0,25.0,11.0,.5)/100
        tg=a3.slider('Terminal growth (%)',0.0,7.0,4.0,.25)/100
        years=st.slider('Forecast period (years)',3,10,5)
        suggested_shares=float(profile.get('shares_outstanding') or 0);suggested_price=float(profile.get('last_price') or 0)
        i1,i2=st.columns(2)
        shares=i1.number_input('Shares outstanding · actual number of shares',min_value=0.0,value=suggested_shares,step=1_000_000.0,format='%.0f',help='Provider suggestion may be prefilled. Verify it against the latest filing before relying on per-share value.')
        price=i2.number_input('Market price / share',min_value=0.0,value=suggested_price,help='Provider quote may be prefilled. Verify quote currency and time.')
        if suggested_shares or suggested_price:st.caption('Prefilled market inputs, when available, come from Yahoo/yfinance metadata and are **not independently verified**.')
        if st.button('Run valuation scenario',type='primary',use_container_width=True):
            try:
                blob,v,sc,sens=workbook(active,frames,Assumptions(growth,wacc,tg,years,shares or None,price or None));st.session_state['valuation']=(active,blob,v,sc,sens)
            except Exception as e:st.error(str(e))
        if st.session_state.get('valuation') and st.session_state['valuation'][0]==active:
            _,blob,v,sc,sens=st.session_state['valuation'];x,y,z=st.columns(3)
            x.metric('Enterprise value','Raw '+f"{v['enterprise_value_raw']:,.0f}")
            y.metric('Illustrative value / share',f"{v['intrinsic_value_per_share']:,.2f}" if v['intrinsic_value_per_share'] is not None else 'Need shares')
            z.metric('Vs entered market price',f"{v['difference_vs_price']:.1%}" if v['difference_vs_price'] is not None else 'Need price')
            if v['terminal_value_share'] is not None and v['terminal_value_share']>0.8:st.warning(f"Terminal value contributes {v['terminal_value_share']:.0%} of enterprise value. The result is highly assumption-sensitive.")
            st.markdown('#### Scenario lens')
            sdf=pd.DataFrame(sc);show=['scenario','growth','wacc','terminal_growth','intrinsic_value_per_share','equity_value_raw'];st.dataframe(sdf[show],use_container_width=True,hide_index=True)
            st.markdown('#### Sensitivity lens')
            sen=pd.DataFrame(sens)
            if shares>0:
                pivot=sen.pivot(index='wacc',columns='terminal_growth',values='intrinsic_value_per_share');pivot.index=[f'{x:.1%}' for x in pivot.index];pivot.columns=[f'{x:.1%}' for x in pivot.columns];st.dataframe(pivot,use_container_width=True)
            else:st.caption('Enter shares outstanding to see per-share sensitivity.')
            st.download_button('Download transparent valuation workbook',blob,file_name=f'FinSight_{active.replace(".","_")}_Valuation.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',use_container_width=True)
            st.caption('Illustrative only. FinSight intentionally does not issue buy/sell recommendations.')

if len(st.session_state.companies)>1:
    with st.expander('Compare companies on my research shelf'):
        rows=[]
        for t,fr in st.session_state.companies.items():
            s=research_snapshot(t,fr);o=s['latest_official'];p=s['latest_provider']
            rows.append({'Ticker':t,'Data layer':'Official' if o else 'Provider-derived','Revenue growth %':(100*(o['revenue']/s['official']['years'][o['year']-1]['revenue']-1) if o and o['year']-1 in s['official']['years'] else p.get('revenue_growth_pct')),'Operating margin %':o.get('operating_margin') if o else p.get('provider_operating_margin_pct'),'Net margin %':o.get('net_margin') if o else p.get('provider_net_margin_pct')})
        st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
