import io,re

def extract_pdf(uploaded):
    from pypdf import PdfReader
    data=uploaded.getvalue() if hasattr(uploaded,'getvalue') else uploaded.read()
    reader=PdfReader(io.BytesIO(data)); pages=[]
    for i,p in enumerate(reader.pages,1):
        try:text=p.extract_text() or ''
        except Exception:text=''
        pages.append({'page':i,'text':text})
    return {'name':getattr(uploaded,'name','annual-report.pdf'),'pages':pages}

def evidence(report,query,limit=6):
    terms=[x for x in re.findall(r'[A-Za-z]{4,}',query.lower()) if x not in {'what','that','with','from','this','have'}]
    hits=[]
    for p in report.get('pages',[]):
        txt=p['text']; low=txt.lower(); score=sum(low.count(t) for t in terms)
        if score:
            pos=min([low.find(t) for t in terms if t in low] or [0]); start=max(0,pos-180); excerpt=' '.join(txt[start:start+700].split())
            hits.append({'report':report['name'],'page':p['page'],'excerpt':excerpt,'relevance':score})
    return sorted(hits,key=lambda x:x['relevance'],reverse=True)[:limit]

def reference_label(hit):return f"{hit['report']}, PDF p. {hit['page']}"
