import io,re

STOP={'what','that','with','from','this','have','were','will','your','company','annual','report'}

def extract_pdf(uploaded):
    from pypdf import PdfReader
    data=uploaded.getvalue() if hasattr(uploaded,'getvalue') else uploaded.read()
    reader=PdfReader(io.BytesIO(data));pages=[]
    for i,p in enumerate(reader.pages,1):
        try:text=p.extract_text() or ''
        except Exception:text=''
        pages.append({'page':i,'text':text})
    return {'name':getattr(uploaded,'name','annual-report.pdf'),'pages':pages,'page_count':len(pages)}

def _terms(query):
    words=[x for x in re.findall(r'[A-Za-z]{3,}',query.lower()) if x not in STOP]
    synonyms={'margin':['margin','profitability','productivity','realisation','pricing','utilization','utilisation','cost'],
              'revenue':['revenue','growth','demand','currency','client','deal'],
              'cash':['cash','liquidity','working','capital','conversion'],
              'employee':['employee','attrition','utilization','utilisation','pyramid','talent']}
    out=list(words)
    for w in words:
        for key,vals in synonyms.items():
            if key in w or w in vals:out+=vals
    return list(dict.fromkeys(out))[:20]

def evidence(report,query,limit=6):
    terms=_terms(query);hits=[]
    for p in report.get('pages',[]):
        txt=p['text'];low=txt.lower();score=sum(min(5,low.count(t)) for t in terms)
        if score:
            positions=[low.find(t) for t in terms if t in low];pos=min(positions or [0]);start=max(0,pos-220);excerpt=' '.join(txt[start:start+900].split())
            hits.append({'report':report['name'],'page':p['page'],'excerpt':excerpt,'relevance':score})
    return sorted(hits,key=lambda x:(x['relevance'],-x['page']),reverse=True)[:limit]

def reference_label(hit):return f"{hit['report']} · PDF p. {hit['page']}"
