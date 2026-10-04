# FinSight AI

### An Explainable Financial Research and Investigation Assistant

FinSight AI is a Python-based financial research application that combines structured company financial data, conversational AI, financial analysis, annual-report evidence, and scenario-based valuation in an interactive Streamlit interface.

The project explores how AI agents can support financial research while keeping calculations, assumptions, and data limitations transparent.

## Features

- **Company Research:** Retrieve available historical financial data using Yahoo Finance.
- **Conversational Financial Analysis:** Ask questions about company performance using a Groq-powered agent.
- **Investigate WHY:** Examine changes in revenue, profit margins, and financial performance using numerical analysis.
- **Annual Report Research:** Discover available corporate report PDFs or upload reports to retrieve relevant passages with page references.
- **Financial Validation:** Check accounting relationships and identify missing or inconsistent financial information.
- **What-If Modeling Studio:** Explore how different forecasting assumptions affect estimated financial outcomes.
- **Excel Reports:** Export supported financial models and analysis results.

## Technology Stack

**Programming:** Python

**Financial Data:** Yahoo Finance (`yfinance`), Pandas

**AI:** LangChain, Groq

**User Interface:** Streamlit

**Document Processing:** PyMuPDF

**Financial Reports:** Excel automation

**Development Tools:** Git, GitHub

## How It Works

1. The user selects a company ticker.
2. FinSight AI retrieves available financial data.
3. Python calculates financial metrics and validation checks.
4. The AI agent uses financial tools to answer questions.
5. Annual-report passages can provide additional evidence where available.
6. Users can test forecasting assumptions and download supported Excel outputs.

## Installation

Clone the repository:

```bash
git clone https://github.com/Tanvi-Gajula/FinSight-AI.git
cd FinSight-AI
```

Create and activate a virtual environment on Windows:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Create a `.env` file and configure your Groq API key:

```dotenv
GROQ_API_KEY=your_key_here
```

Run the application:

```powershell
python -m streamlit run app.py
```

Open `http://localhost:8501` in your browser.

## Example Questions

- How has TCS's revenue changed over the past four years?
- Compare the profitability of TCS and Infosys.
- What financial components contributed to a change in operating margin?
- What relevant evidence can be found in the available annual report?
- What happens to the forecast if revenue growth slows?

## Limitations

FinSight AI is an educational financial research prototype. Financial data availability varies by company. Automatic report discovery may fail, some reports require manual upload, and report passages do not necessarily establish causation.

Forecasting and DCF outputs depend on assumptions. Historical data and report authenticity are not independently audited. The application does not provide personalized investment advice.

## Future Improvements

- More comprehensive verification against official company filings.
- Improved industry-specific modeling, including financial institutions.
- Enhanced financial investigation and evidence assessment.
- More extensive automated testing and deployment monitoring.

## Developer

**Tanvi Gajula**

GitHub: https://github.com/Tanvi-Gajula
