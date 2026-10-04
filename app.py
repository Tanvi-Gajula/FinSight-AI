"""FinSight AI: company-agnostic conversational financial research and optional financial modeling."""
import os
import re
import base64
from pathlib import Path
import pandas as pd
import streamlit as st
from model import Assumptions, workbook
from research import agent_answer, facts, math_results, describe
from investigation import investigate, format_investigation
from annual_reports import extract_pdf, evidence, reference_label
from auto_reports import discover, fetch_official_pdf

ROOT=Path(__file__).resolve().parent
st.set_page_config(page_title='FinSight AI · Your cozy finance copilot',page_icon=str(ROOT/'assets'/'finsight-logo.svg'),layout='wide',initial_sidebar_state='expanded')
from dotenv import load_dotenv
load_dotenv(ROOT/'.env')
css=(ROOT/'assets'/'theme.css').read_text(encoding='utf-8')
st.markdown('<style>'+css+'</style>',unsafe_allow_html=True)
logo_b64=base64.b64encode((ROOT/'assets'/'finsight-logo.svg').read_bytes()).decode('ascii')
logo_url='data:image/svg+xml;base64,'+logo_b64

@st.cache_data(ttl=3600,show_spinner=False)
def fetch(ticker,demo):
    if demo:
        if ticker!='TCS.NS':raise ValueError('Offline demonstration contains TCS.NS only.')
        p=ROOT/'data'/'TCS_Financial_Data.xlsx'
        return {'Income':pd.read_excel(p,sheet_name='Income Statement',index_col=0),
                'Balance':pd.read_excel(p,sheet_name='Balance Sheet',index_col=0),
                'CashFlow':pd.read_excel(p,sheet_name='Cash Flow',index_col=0)}
    import yfinance as yf
    stock=yf.Ticker(ticker)
    result={'Income':stock.income_stmt,'Balance':stock.balance_sheet,'CashFlow':stock.cashflow}
    if all(df.empty for df in result.values()):raise ValueError(f'Yahoo Finance returned no statements for {ticker}. Verify ticker and retry.')
    return result

@st.cache_data(ttl=3600,show_spinner=False)
def build(ticker,demo,growth,wacc,terminal,years,min_cash,shares,market_price):
    frames=fetch(ticker,demo)
    return workbook(ticker,frames,Assumptions(growth,wacc,terminal,years,min_cash,shares,market_price))

if 'companies' not in st.session_state:st.session_state.companies={}
if 'messages' not in st.session_state:st.session_state.messages=[]
if 'selected' not in st.session_state:st.session_state.selected=''
if 'reports' not in st.session_state:st.session_state.reports={}

with st.sidebar:
    st.markdown(f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px"><img src="{logo_url}" width="48" height="48" style="border-radius:14px"><div><div style="font-size:1.38rem;font-weight:850;color:#59449D">FinSight AI</div><div style="font-size:.77rem;color:#8C78A0">your friendly finance companion ✿</div></div></div>',unsafe_allow_html=True)
    st.caption('Pick a company and let the research begin!')
    ticker=st.text_input('🔎 Company ticker',value='INFY.NS',help='Try INFY.NS, TCS.NS, RELIANCE.NS, MSFT, AAPL, HDFCBANK.NS').strip().upper()
    demo=st.toggle('Use offline TCS sample',value=False)
    load=st.button('✦ Explore company',type='primary',use_container_width=True)
    if st.session_state.companies:
        st.divider()
        st.markdown('**📁 My research shelf**')
        selected=st.selectbox('Active company',list(st.session_state.companies),index=list(st.session_state.companies).index(st.session_state.selected) if st.session_state.selected in st.session_state.companies else 0)
        st.session_state.selected=selected
    st.divider()
    st.markdown('**✨ AI study buddy**')
    use_ai=st.toggle('Groq-powered tool-using agent',value=True)
    if use_ai and not os.getenv('GROQ_API_KEY'):
        st.caption('Add GROQ_API_KEY to private .env for agent answers.')
    st.caption('🌿 Yahoo Finance is a data provider, not an audited filing. Numbers and units must be checked before investment use.')

if load:
    if not re.fullmatch(r'[A-Z0-9.^=_-]{1,25}',ticker):st.error('Invalid ticker symbol. Example: INFY.NS')
    else:
        with st.spinner(f'Fetching available annual statements for {ticker}...'):
            try:
                frames=fetch(ticker,demo)
                st.session_state.companies[ticker]={'frames':frames,'demo':demo}
                st.session_state.selected=ticker
                st.session_state.messages=[]
                st.success(f'{ticker} loaded. Ask a question or review its statements below.')
            except Exception as e:st.error(str(e))

st.markdown(f"""<div class="fs-hero"><img class="fs-logo" src="{logo_url}" alt="FinSight AI logo"><div><div class="fs-eyebrow">✦ YOUR RESEARCH SPACE</div><h1>Hey there, I'm FinSight! 🌷</h1><p>Curious about a company? Let's explore its numbers together, ask thoughtful questions, and make finance feel a little less complicated.</p></div></div>""",unsafe_allow_html=True)

active=st.session_state.selected if st.session_state.selected in st.session_state.companies else None
if active:
    frames=st.session_state.companies[active]['frames']
    d=math_results(active,frames); hist=d['historical']; latest=hist[-1] if hist else None
    st.caption(f"Loaded: **{active}** · Annual statements · Yahoo Finance provider extraction · Not independently filing-verified")
    if latest:
        k1,k2,k3=st.columns(3)
        k1.metric(f'FY{latest["year"]} revenue',f'{latest["revenue_raw"]:,.0f}' if latest['revenue_raw'] is not None else 'N/A')
        k2.metric('Revenue growth',f'{latest["revenue_growth_pct"]:.2f}%' if latest.get('revenue_growth_pct') is not None else 'N/A')
        k3.metric('Net profit margin',f'{latest["net_margin_pct"]:.2f}%' if latest.get('net_margin_pct') is not None else 'N/A')
        st.caption('Monetary figures above use raw reporting-currency units; the ticker alone does not establish currency.')
else:
    st.markdown('<div class="fs-section">A little something for every question ✨</div>',unsafe_allow_html=True)
    feature_cols=st.columns(3)
    cards=[('💬','Ask anything','Wondering about revenue, debt or margins? Start a conversation grounded in the available data.'),('🕵️','Investigate the numbers','Explore actual statement accounts, spot missing values, and inspect reconciliation checks.'),('🧁','Model what-ifs','Try transparent assumptions and export an Excel scenario when the company supports one.')]
    for col,(emoji,heading,description) in zip(feature_cols,cards):
        with col:st.markdown(f'<div class="fs-feature"><strong>{emoji} {heading}</strong><p>{description}</p></div>',unsafe_allow_html=True)
    st.info('🌼 Start by entering a ticker in the left sidebar. Try INFY.NS, TCS.NS, or MSFT. You can research a company even when forecasting is unavailable.')

tab_chat,tab_why,tab_reports,tab_data,tab_compare,tab_model=st.tabs(['💬 Ask FinSight','🔎 Investigate WHY','📄 Annual reports','📚 Explore statements','🌸 Compare companies','📈 Model & download'])
with tab_chat:
    st.markdown('#### What are you curious about today? 💭')
    st.caption('Examples: “Show Infosys revenue growth”, “How did operating margin change?”, “What cash-flow accounts are available?”, “Compare INFY.NS and TCS.NS”.')
    if active:
        suggestions=['Summarize revenue growth and net profit margins','Explain the latest operating cash flow','What information is missing from this company data?']
        cols=st.columns(3)
        for i,suggestion in enumerate(suggestions):
            if cols[i].button(suggestion,key='prompt_'+str(i),use_container_width=True):st.session_state.pending=suggestion
    for m in st.session_state.messages:
        with st.chat_message(m['role']):st.markdown(m['content'])
    question=st.chat_input('Ask me anything about your company… ✨')
    if not question and st.session_state.get('pending'):question=st.session_state.pop('pending')
    if question:
        with st.chat_message('user'):st.markdown(question)
        if not st.session_state.companies:ans='Load a company using the left sidebar first.';calls=[]
        else:
            with st.spinner('Retrieving data and applying financial tools...'):
                sources=st.session_state.reports.get(active,[]) if active else []
                passages=[]
                for report in sources:
                    passages.extend(evidence(report,question,limit=4))
                passages=sorted(passages,key=lambda x:x['relevance'],reverse=True)[:8]
                ans,calls=agent_answer(question,{k:v['frames'] for k,v in st.session_state.companies.items()},enabled=use_ai,report_evidence=passages)
        with st.chat_message('assistant'):
            st.markdown(ans)
            if calls:
                with st.expander('View agent tools used'):
                    st.json(calls)
        st.session_state.messages.extend([{'role':'user','content':question},{'role':'assistant','content':ans}])
with tab_why:
    st.markdown('#### 🔎 Why did the numbers move?')
    st.caption('Calculated changes come from Yahoo Finance. Uploaded annual-report passages can provide possible explanations, with PDF-page references; authenticity and causation still require review.')
    if active:
        inc=frames.get('Income')
        available=sorted({pd.Timestamp(c).year for c in inc.columns}) if inc is not None else []
        if len(available)>=2:
            period=st.select_slider('Choose ending year',options=available[1:],value=available[-1])
            prior=available[available.index(period)-1]
            result=investigate(active,frames,years=[prior,period])
            st.markdown(format_investigation(result))
            attached=st.session_state.reports.get(active,[])
            if attached:
                st.markdown('##### 📄 Related annual-report evidence')
                q=st.text_input('Which business reason should we investigate?',value='revenue growth operating margin employee costs demand')
                snippets=sorted((hit for rep in attached for hit in evidence(rep,q)),key=lambda x:x['relevance'],reverse=True)[:7]
                if snippets:
                    for snippet in snippets:
                        st.markdown('**'+reference_label(snippet)+'**')
                        st.write(snippet['excerpt'])
                    st.caption('These are retrieved passages, not independently established causal conclusions.')
                else:st.info('No matching extractable passages. Try another phrase or report.')
            else:st.info('Open 📄 Annual reports, find an official-company PDF and index it to investigate possible business explanations.')
            with st.expander('Show the source accounts, formulas and raw audit record'):
                st.json(result)
            st.download_button('⬇ Download investigation evidence JSON',__import__('json').dumps(result,indent=2),file_name=f'{active}_FY{prior}_FY{period}_investigation.json',mime='application/json')
        else: st.warning('At least two comparable annual Income Statements are needed.')
    else:st.info('Load a company from the sidebar first.')
with tab_reports:
    st.markdown('#### 📄 Annual Report Evidence Library')
    st.caption('Find company reports automatically, or upload a PDF as a fallback. Sources must be checked against the company and report year.')
    if active:
        st.markdown('##### ✨ Find the annual report automatically')
        guess_years=sorted({pd.Timestamp(c).year for df in frames.values() if df is not None and not df.empty for c in df.columns},reverse=True)
        report_year=st.selectbox('Report financial year',guess_years if guess_years else [2026],key='report_year_'+active)
        if st.button('🔎 Find report on company website',key='autofind_'+active):
            with st.spinner('Looking for report links on company sources...'):
                try:st.session_state['report_options_'+active]=discover(active,report_year)
                except Exception as error:st.error('Report discovery was unavailable: '+str(error))
        options=st.session_state.get('report_options_'+active,[])
        if options:
            labels=[f"{x['label']} — {x['url']}" for x in options]
            idx=st.selectbox('Found possible sources (verify company and report year)',range(len(options)),format_func=lambda i:labels[i],key='report_pick_'+active)
            item=options[idx]
            st.link_button('Open selected source for verification',item['url'])
            if item['is_pdf']:
                if st.button('⬇ Fetch PDF and index evidence',key='download_report_'+active,type='primary'):
                    with st.spinner('Downloading and extracting annual-report pages...'):
                        try:
                            raw=fetch_official_pdf(item['url'],item['host'])
                            doc_name=item['url'].split('/')[-1].split('?')[0]
                            report=extract_pdf(raw,doc_name,active)
                            report['source_url']=item['url']
                            report['source_type']='Discovered corporate-host PDF; authenticity and fiscal year unverified'
                            library=st.session_state.reports.setdefault(active,[])
                            if not any(r.get('source_url')==item['url'] for r in library):library.append(report)
                            st.success(f"Indexed {report['count']} searchable pages from {doc_name}.")
                        except Exception as error:st.error('Automatic PDF retrieval failed: '+str(error))
            else:st.info('This is a company reports page, not a direct PDF. Open it and choose a direct annual-report PDF, or use the optional upload below.')
        else:st.caption('Click Find report to search corporate sources. Automatic discovery cannot guarantee a report for every ticker.')
        st.divider()
        st.markdown('##### 📎 Optional upload if automatic discovery fails')
        uploads=st.file_uploader('Upload annual report PDFs (ideally from the official investor-relations website)',type=['pdf'],accept_multiple_files=True,key='filing_'+active)
        if uploads:
            loaded=st.session_state.reports.setdefault(active,[])
            names={rep['name'] for rep in loaded}
            for uploaded in uploads:
                if uploaded.name in names:continue
                try:
                    report=extract_pdf(uploaded.getvalue(),uploaded.name,active)
                    loaded.append(report)
                    names.add(uploaded.name)
                    st.success(f"Indexed {uploaded.name}: {report['count']} searchable pages")
                except Exception as error:st.error(f'{uploaded.name}: {error}')
        attached=st.session_state.reports.get(active,[])
        if attached:
            for rep in attached:
                st.caption(f"📘 {rep['name']} — {rep['count']} searchable pages · source not independently authenticated")
                if rep.get('source_url'):st.link_button('View source: '+rep['name'],rep['source_url'])
            query=st.text_input('Find passages about...',value='revenue growth client demand and operating margin')
            if st.button('Find evidence',type='primary'):
                found=sorted((hit for report in attached for hit in evidence(report,query)),key=lambda x:x['relevance'],reverse=True)[:8]
                if not found:st.warning('No matching passages. Try simpler keywords, or check whether the PDF is scanned.')
                for hit in found:
                    st.markdown('**'+reference_label(hit)+'**')
                    st.write(hit['excerpt'])
            if st.button('Clear all uploaded reports for this company'):
                st.session_state.reports.pop(active,None)
                st.rerun()
        else:st.info('Find and index a company annual report above, or upload the PDF if discovery fails.')
    else:st.info('Choose a company in the sidebar first.')
with tab_data:
    if active:
        st.markdown('#### Explore the actual financial statements 📚')
        st.caption('These are provider-extracted rows. A missing account stays missing; we do not substitute zero. Values are in raw reporting-currency units.')
        name=st.radio('Statement',['Income','Balance','CashFlow'],horizontal=True,format_func=lambda x:{'Income':'Income Statement','Balance':'Balance Sheet','CashFlow':'Cash Flow Statement'}[x])
        frame=frames[name]
        if frame.empty:st.warning('This statement is unavailable from the provider.')
        else:
            search=st.text_input('Filter accounts',placeholder='Try revenue, operating, cash, debt...')
            shown=frame.loc[frame.index.astype(str).str.contains(re.escape(search),case=False,regex=True)] if search else frame
            st.dataframe(shown,use_container_width=True,height=470)
            st.download_button('Download statement as CSV',shown.to_csv().encode('utf-8'),file_name=f'{active}_{name}_statement.csv',mime='text/csv')
        st.markdown('#### Financial indicators')
        if hist:
            hf=pd.DataFrame(hist).set_index('year')
            if 'revenue_raw' in hf:st.line_chart(hf[['revenue_raw']])
            st.dataframe(hf,use_container_width=True)
    else:st.info('Load a company to explore its statements.')
with tab_compare:
    if len(st.session_state.companies)<2:
        st.info('Load another ticker from the sidebar to compare companies. You can research each company even when forecasting is unsupported.')
    else:
        chosen=st.multiselect('Select companies to compare',list(st.session_state.companies),default=list(st.session_state.companies)[:2])
        if len(chosen)>1:
            tables=[]
            for t in chosen:
                for row in math_results(t,st.session_state.companies[t]['frames'])['historical']:
                    tables.append({'ticker':t,**row})
            comp=pd.DataFrame(tables)
            st.dataframe(comp,use_container_width=True)
            st.caption('Compare overlapping years and compatible reporting currencies; currency conversion is not automatic.')
with tab_model:
    if active:
        st.markdown('#### Your what-if modeling studio ✨')
        st.caption('Research is available for all companies with statements. This simplified model needs additional accounts; banks and insurers require specialized models.')
        c1,c2=st.columns(2)
        growth=c1.slider('Assumed annual revenue growth (%)',-20.,30.,5.8,.1)/100
        years=c2.slider('Forecast years',2,5,3)
        wacc=c1.slider('WACC (%)',2.,30.,11.,.1)/100
        terminal=c2.slider('Terminal growth (%)',-2.,8.,4.,.1)/100
        min_cash=st.number_input('Minimum cash, in model currency crore-equivalent',min_value=0.,value=0.,step=100.)
        st.markdown('##### 📍 Stock Valuation Lab')
        shares_input=st.number_input('Verified diluted shares outstanding (actual shares; 0 if unknown)',min_value=0.,value=0.,step=1000000.,format='%.0f')
        price_input=st.number_input('Verified market price per share (INR; 0 if unknown)',min_value=0.,value=0.,step=1.)
        st.caption('Confirm reporting currency, share count, share class, and quote date. If missing, workbook leaves per-share result blank.')
        if st.button('✨ Create my Excel model',type='primary'):
            if active.upper().startswith(('HDFCBANK','ICICIBANK','SBIN','AXISBANK')):st.warning('Banks require a bank-specific valuation model. Research and chat remain available.')
            elif not active.endswith('.NS'):st.warning('Current model assumes INR crore; international tickers are supported for research, not the current modeling currency convention.')
            elif st.session_state.companies[active]['demo'] is False and active !=ticker: st.info('Generating using the active company, not necessarily the ticker currently entered.')
            try:
                if not active.endswith('.NS'):raise ValueError('Forecast model is INR-specific; other tickers are research-only until currency handling is extended.')
                with st.spinner('Building and validating model...'):
                    binary,h,forecast,val,checks=build(active,st.session_state.companies[active]['demo'],growth,wacc,terminal,years,min_cash,shares_input or None,price_input or None)
                st.session_state.report={'ticker':active,'file':binary,'forecast':forecast,'value':val,'checks':checks}
            except Exception as exc:st.warning(f'Model unavailable for {active}: {exc}. Financial research and agent chat still work.')
        report=st.session_state.get('report')
        if report and report['ticker']==active:
            st.metric('Illustrative enterprise value (₹ crore)',f"{report['value']['enterprise_value']:,.0f}")
            if shares_input>0:
                per_share=report['value']['equity_value']*10000000/shares_input
                st.metric('Illustrative intrinsic value / share (₹)',f'{per_share:,.2f}')
                if price_input>0:st.metric('Model difference vs user-entered price',f'{100*(per_share/price_input-1):+.1f}%')
            else:st.info('Enter verified diluted shares above to calculate value per share. Otherwise use the workbook for an illustrative company-level valuation.')
            st.dataframe(pd.DataFrame(report['forecast']),use_container_width=True)
            st.dataframe(pd.DataFrame(report['checks']),use_container_width=True)
            st.download_button('⬇ Download my Excel model',report['file'],file_name=f'FinSight_{active.replace(".","_")}_Model.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',type='primary')
            st.caption('Forecasts are scenarios, not audited valuation or investment recommendations.')
    else:st.info('Load a company first.')
