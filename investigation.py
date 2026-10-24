import pandas as pd
from official_metrics import get_official


def _val(df, label, year):
    if df is None or df.empty or label not in df.index:
        return None

    cols = [c for c in df.columns if pd.Timestamp(c).year == year]

    if not cols:
        return None

    v = df.loc[label, cols[0]]

    if isinstance(v, pd.Series) or pd.isna(v):
        return None

    return float(v)


def investigate(ticker, frames, years=None):
    inc = frames.get("Income")

    if inc is None or inc.empty:
        return {
            "ticker": ticker,
            "error": "Income statement unavailable"
        }

    available = sorted({
        pd.Timestamp(c).year
        for c in inc.columns
    })

    if len(available) < 2:
        return {
            "ticker": ticker,
            "error": "At least two annual periods are required"
        }

    if years:
        y0, y1 = years[-2], years[-1]
    else:
        y0, y1 = available[-2], available[-1]

    r0 = _val(inc, "Total Revenue", y0)
    r1 = _val(inc, "Total Revenue", y1)

    op0 = _val(inc, "Operating Income", y0)
    op1 = _val(inc, "Operating Income", y1)

    ni0 = _val(inc, "Net Income", y0)
    ni1 = _val(inc, "Net Income", y1)

    c0 = _val(inc, "Cost Of Revenue", y0)
    c1 = _val(inc, "Cost Of Revenue", y1)

    def margin(value, revenue):
        if value is None or revenue in (None, 0):
            return None
        return 100 * value / revenue

    def delta(old, new):
        if old is None or new is None:
            return None
        return new - old

    revenue_growth = None
    if r0 not in (None, 0) and r1 is not None:
        revenue_growth = 100 * (r1 / r0 - 1)

    provider_op_margin_0 = margin(op0, r0)
    provider_op_margin_1 = margin(op1, r1)

    provider_net_margin_0 = margin(ni0, r0)
    provider_net_margin_1 = margin(ni1, r1)

    provider_cost_share_0 = margin(c0, r0)
    provider_cost_share_1 = margin(c1, r1)

    result = {
        "ticker": ticker,
        "from_year": y0,
        "to_year": y1,

        "provider_revenue_growth_pct": revenue_growth,

        "provider_operating_margin_from": provider_op_margin_0,
        "provider_operating_margin_to": provider_op_margin_1,

        "provider_operating_margin_change_pp": delta(
            provider_op_margin_0,
            provider_op_margin_1
        ),

        "provider_net_margin_change_pp": delta(
            provider_net_margin_0,
            provider_net_margin_1
        ),

        "provider_cost_of_revenue_share_change_pp": delta(
            provider_cost_share_0,
            provider_cost_share_1
        ),

        "source": (
            "Yahoo Finance / yfinance provider extraction; "
            "accounting labels may differ from company-reported KPIs"
        )
    }

    # ---------------------------------------------------------
    # OFFICIAL COMPANY METRICS
    # ---------------------------------------------------------

    official = get_official(ticker)

    if (
        official
        and y0 in official.get("years", {})
        and y1 in official.get("years", {})
    ):
        old = official["years"][y0]
        new = official["years"][y1]

        old_op = old.get("operating_margin")
        new_op = new.get("operating_margin")

        old_net = old.get("net_margin")
        new_net = new.get("net_margin")

        official_revenue_growth = None

        if old.get("revenue") not in (None, 0) and new.get("revenue") is not None:
            official_revenue_growth = (
                100
                * (
                    new["revenue"]
                    / old["revenue"]
                    - 1
                )
            )

        result["official"] = {
            "source_name": official.get(
                "source_name",
                "Official company source"
            ),

            "source_url": official.get(
                "source_url",
                ""
            ),

            "revenue_growth_pct": official_revenue_growth,

            "operating_margin_from": old_op,
            "operating_margin_to": new_op,

            "operating_margin_change_pp": delta(
                old_op,
                new_op
            ),

            "net_margin_from": old_net,
            "net_margin_to": new_net,

            "net_margin_change_pp": delta(
                old_net,
                new_net
            ),

            "adjusted_operating_margin_to": new.get(
                "adjusted_operating_margin"
            ),

            "explanation": official.get(
                "explanations",
                {}
            ).get(
                f"{y0}-{y1}",
                {}
            )
        }

    return result


def format_investigation(result):
    if result.get("error"):
        return (
            "**Investigation unavailable:** "
            + result["error"]
        )

    def fmt(value, signed=True):
        if value is None:
            return "N/A"

        if signed:
            return f"{value:+.2f}"

        return f"{value:.2f}"

    official = result.get("official")

    # =========================================================
    # VERIFIED / CURATED OFFICIAL METRICS
    # =========================================================

    if official:
        text = f"""### Verified change for {result['ticker']}

Comparing **FY{result['from_year']} → FY{result['to_year']}** using company-reported metrics.

- **Revenue growth:** {fmt(official['revenue_growth_pct'])}%
- **Operating margin:** {fmt(official['operating_margin_from'], False)}% → {fmt(official['operating_margin_to'], False)}% (**{fmt(official['operating_margin_change_pp'])} pp**)
- **Net margin:** {fmt(official['net_margin_from'], False)}% → {fmt(official['net_margin_to'], False)}% (**{fmt(official['net_margin_change_pp'])} pp**)"""

        adjusted_margin = official.get(
            "adjusted_operating_margin_to"
        )

        if adjusted_margin is not None:
            text += (
                "\n- **Adjusted operating margin "
                f"(latest):** {adjusted_margin:.2f}%"
            )

        explanation = official.get(
            "explanation",
            {}
        )

        if explanation.get("operating_margin"):
            text += (
                "\n\n### Why may the margin have changed?\n"
                + explanation["operating_margin"]
            )

        if explanation.get("revenue"):
            text += (
                "\n\n### Revenue context\n"
                + explanation["revenue"]
            )

        source_name = official.get(
            "source_name",
            "Official company source"
        )

        source_url = official.get(
            "source_url",
            ""
        )

        if source_url:
            text += (
                f"\n\n**Official source:** "
                f"[{source_name}]({source_url})"
            )
        else:
            text += (
                f"\n\n**Official source:** "
                f"{source_name}"
            )

        text += """

---

**FinSight verification note:** Provider-derived ratios can differ from company-reported KPIs because accounting classifications and KPI definitions may be different. FinSight prefers curated official company metrics when available.

**Important:** A numerical relationship does not automatically prove causation. Business explanations are shown as evidence-backed only when supported by company reporting or uploaded evidence.
"""

        return text

    # =========================================================
    # PROVIDER-ONLY FALLBACK
    # =========================================================

    return f"""### Calculated change for {result['ticker']}

Comparing **FY{result['from_year']} → FY{result['to_year']}**

- **Provider revenue growth:** {fmt(result['provider_revenue_growth_pct'])}%
- **Provider-derived operating margin movement:** {fmt(result['provider_operating_margin_change_pp'])} percentage points
- **Provider-derived net margin movement:** {fmt(result['provider_net_margin_change_pp'])} percentage points
- **Cost of revenue / sales movement:** {fmt(result['provider_cost_of_revenue_share_change_pp'])} percentage points

### What this proves

These figures show the **numerical movement** calculated from the financial accounts supplied by the data provider.

### What this does NOT prove

These calculations alone do **not establish the underlying business cause**.

For example, a lower cost-to-revenue ratio may contribute mathematically to a higher operating margin, but FinSight should not claim why the cost changed unless there is supporting evidence.

### How to verify WHY

Upload or review the company's annual report and check:

- management commentary
- operating-cost discussion
- segment performance
- employee costs
- currency impact
- pricing or realisation
- restructuring or exceptional items
- productivity commentary

**Provider source:** {result['source']}

*FinSight treats provider-derived calculations as research signals, not company-verified explanations.*
"""
