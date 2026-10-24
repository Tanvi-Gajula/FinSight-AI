"""Small curated official-metric registry.

Only values copied from company investor-relations material belong here.  This is
intentionally tiny: an unsupported ticker must fall back to clearly-labelled
provider-derived metrics rather than pretending to be verified.
"""
OFFICIAL = {
    "TCS.NS": {
        "company": "Tata Consultancy Services",
        "currency": "INR",
        "scale": "crore",
        "source_name": "TCS Integrated Annual Report 2025-26",
        "source_url": "https://www.tcs.com/content/dam/tcs/investor-relations/financial-statements/2025-26/ar/annual-report-2025-2026.pdf",
        "years": {
            2025: {"revenue": 255324.0, "operating_margin": 24.3, "net_margin": 19.0},
            2026: {"revenue": 267021.0, "operating_margin": 25.0, "net_margin": 19.8},
        },
        "explanations": {
            "2025-2026": {
                "operating_margin": "TCS says margin support came from greater productivity and realisation, pyramid restructuring and favourable currency trends; these gains also funded investments in talent, learning, research, infrastructure and growth.",
                "revenue": "TCS reported 4.6% revenue growth in INR. It also reported a 7.0% positive currency impact and a 2.4% constant-currency decline, so reported growth should not be read as purely underlying business growth.",
            }
        },
    },
    "INFY.NS": {
        "company": "Infosys",
        "currency": "INR",
        "scale": "crore",
        "source_name": "Infosys FY2026 official financial snapshot / Form 20-F",
        "source_url": "https://www.infosys.com/about/last-fiscal.html",
        "years": {
            2025: {"revenue": 162990.0, "operating_margin": 21.1, "net_margin": 16.4},
            2026: {"revenue": 178650.0, "operating_margin": 20.3, "net_margin": 16.5, "adjusted_operating_margin": 21.0},
        },
        "explanations": {
            "2025-2026": {
                "operating_margin": "Infosys reports that FY2026 operating profit included a ₹1,289 crore impact from India's Labour Codes. Reported operating margin was 20.3%; excluding that effect, adjusted operating margin was 21.0% versus 21.1% in FY2025.",
                "revenue": "Infosys reported FY2026 consolidated INR revenue growth of 9.6%. Its USD revenue growth was lower because currency translation changes the reported growth rate across currencies.",
            }
        },
    },
}

def get_official(ticker):
    return OFFICIAL.get((ticker or "").upper().strip())
