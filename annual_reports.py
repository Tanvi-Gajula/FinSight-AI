
"""Page-cited annual-report evidence. Extracts searchable text from user-provided PDFs;
does not pretend the PDF is audited or automatically reconcile filing vs provider."""
import io, re
from collections import Counter

STOPWORDS = set("the and for from this that were with into have been will are was what why how did does company annual report their its over under year years revenue income profit margins cash position financial changes change impact effect".split())
ALIASES = {
    "profit": ["profit","margin","operating","expenses","revenue"],
    "margin": ["margin","cost","employee","utilization","expenses","profit"],
    "growth": ["growth","revenue","demand","clients","geography","currency"],
    "cash": ["cash","dividend","deposits","reconciliation","restricted","bank"],
    "revenue": ["revenue","services","growth","segments","geography","clients"],
}
MAX_PDF_BYTES=30*1024*1024
MAX_PAGES=350
MAX_SNIPPETS=6

def extract_pdf(pdf_bytes, filename, ticker):
    if len(pdf_bytes)>MAX_PDF_BYTES:
        raise ValueError("PDF exceeds 30 MB. Please upload a smaller report.")
    if not pdf_bytes.startswith(b"%PDF-"):
        raise ValueError("This is not a valid PDF file.")
    import fitz
    pages=[]
    with fitz.open(stream=pdf_bytes,filetype="pdf") as doc:
        if doc.needs_pass:raise ValueError("Password-protected PDFs are unsupported.")
        for page in list(doc)[:MAX_PAGES]:
            raw=page.get_text("text",sort=True) or ""
            clean=re.sub(r"\s+"," ",raw).strip()
            if len(clean)>70:
                pages.append({"page":page.number+1,"text":clean[:24000]})
    if not pages:
        raise ValueError("No searchable text found. Scanned PDF requires OCR.")
    return {"name":filename,"ticker":ticker,"pages":pages,
            "count":len(pages),"truncated":len(pages)>=MAX_PAGES,
            "provenance":"User-uploaded PDF; company identity, report year and authenticity not independently verified."}

def evidence(report, question, limit=MAX_SNIPPETS):
    words=[s.lower() for s in re.findall(r"[a-zA-Z]{4,}",question)
           if s.lower() not in STOPWORDS]
    for word in list(words):
        words.extend(ALIASES.get(word,[]))
    if not words: words=["revenue","management","financial","risk"]
    terms=list(dict.fromkeys(words))
    hits=[]
    for page in report.get("pages",[]):
        text=page["text"]
        # Find compact excerpts rather than hand the LLM the entire annual report.
        for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])",text):
            if not (70<=len(sentence)<=1800):continue
            low=sentence.lower()
            strength=sum(min(low.count(term),3) for term in terms)
            if strength>=2:
                hits.append({"report":report["name"],"page":page["page"],
                             "excerpt":sentence[:900],"relevance":strength})
    hits.sort(key=lambda x:x["relevance"],reverse=True)
    seen=set();selected=[]
    for hit in hits:
        if hit["page"] in seen:continue
        seen.add(hit["page"])
        selected.append(hit)
        if len(selected)>=limit:break
    return selected

def reference_label(hit):
    return f'{hit["report"]}, PDF p. {hit["page"]}'
