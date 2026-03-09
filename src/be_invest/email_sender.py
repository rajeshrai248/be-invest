"""Email report sender for be-invest broker fee comparisons.

Sends bi-weekly HTML email reports containing cost comparison tables and
investor persona TCO rankings. Uses Gmail SMTP via stdlib smtplib only.
"""

import html
import logging
import os
import re
import smtplib
import ssl
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

# ========================================================================================
# BROKER LOGO URLS (Google Favicon API — reliable, consistent sizing)
# ========================================================================================

_BROKER_LOGO_DOMAINS: dict[str, str] = {
    "bolero": "bolero.be",
    "degiro": "degiro.nl",
    "degiro belgium": "degiro.nl",
    "ing": "ing.be",
    "ing self invest": "ing.be",
    "keytrade": "keytradebank.be",
    "keytrade bank": "keytradebank.be",
    "rebel": "belfius.be",
    "re=bel": "belfius.be",
    "revolut": "revolut.com",
    "trade republic": "traderepublic.com",
}

_LOGO_SIZE = 20  # px


def _broker_logo_img(broker_name: str) -> str:
    """Return an <img> tag for the broker's favicon, or empty string if unknown."""
    domain = _BROKER_LOGO_DOMAINS.get(broker_name.lower())
    if not domain:
        return ""
    url = f"https://www.google.com/s2/favicons?domain={domain}&sz={_LOGO_SIZE * 2}"
    return (
        f'<img src="{url}" alt="" width="{_LOGO_SIZE}" height="{_LOGO_SIZE}" '
        f'style="vertical-align:middle;margin-right:6px;border-radius:3px;" />'
    )


# ========================================================================================
# MODULE-LEVEL CONFIG (read from env at import time)
# ========================================================================================

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.environ.get("SMTP_FROM_EMAIL", SMTP_USER)


def _get_recipients() -> list[str]:
    """Read EMAIL_RECIPIENTS at call time so env changes are picked up."""
    raw = os.environ.get("EMAIL_RECIPIENTS", "")
    return [r.strip() for r in raw.split(",") if r.strip()]


# ========================================================================================
# HTML RENDERING HELPERS
# ========================================================================================

_STYLES = """
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; color: #111827; margin: 0; padding: 24px 0; background: #f3f4f6; }
    /* No box-shadow or border-radius — both silently fail in Outlook */
    .wrapper { max-width: 700px; margin: 0 auto; background: #ffffff; border: 1px solid #e5e7eb; }
    .header { background: #FF6200; color: #fff; padding: 28px 40px 24px; }
    .header-eyebrow { font-size: 11px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; opacity: 0.85; margin: 0 0 6px; }
    .header-title { font-size: 22px; font-weight: 700; margin: 0 0 6px; line-height: 1.3; }
    .header-date { margin: 0; font-size: 12px; opacity: 0.75; }
    .content { padding: 36px 40px; }
    p { word-wrap: break-word; overflow-wrap: break-word; max-width: 100%; margin: 0 0 16px; }
    em { word-wrap: break-word; overflow-wrap: break-word; }
    .greeting { font-size: 16px; font-weight: 600; color: #111827; margin: 0 0 12px; }
    .intro { font-size: 14px; color: #374151; line-height: 1.7; margin-bottom: 24px; padding-bottom: 24px; border-bottom: 1px solid #e5e7eb; }
.section-eyebrow { font-size: 11px; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase; color: #FF6200; margin: 36px 0 4px; }
    h2 { font-size: 18px; font-weight: 700; color: #111827; margin: 0 0 16px; }
    h3 { color: #111827; font-size: 14px; font-weight: 700; margin: 20px 0 10px; }
    .table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; margin-bottom: 4px; }
    .scroll-hint { font-size: 11px; color: #9ca3af; text-align: right; margin: 0 0 4px; display: none; }
    table { border-collapse: collapse; width: 100%; min-width: 420px; font-size: 13px; }
    th { background: #FF6200; color: #fff; padding: 11px 14px; text-align: right; font-weight: 600; font-size: 12px; }
    th:first-child { text-align: left; }
    td { padding: 10px 14px; border-bottom: 1px solid #f0f2f5; text-align: right; color: #374151; }
    td:first-child { text-align: left; font-weight: 600; color: #111827; }
    /* No :hover — ignored by all email clients; no nth-child striping — broken in Outlook */
    /* bgcolor attributes on <tr> tags handle Outlook striping (see HTML) */
    .cheapest { background: #dcfce7 !important; color: #166534; font-weight: 700; }
    /* rank-1: amber tint; rank-2: blue tint — clearly distinct from each other and plain rows */
    .rank-1 td { background: #fef3c7 !important; }
    .rank-2 td { background: #eff6ff !important; }
    .table-note { font-size: 12px; color: #6b7280; margin: 0 0 16px; line-height: 1.6; }
    .footnotes { font-size: 11px; color: #6b7280; margin: 10px 0 28px; padding: 14px 16px; background: #f9fafb; border-left: 3px solid #FF6200; line-height: 1.9; }
    .footnotes strong { color: #374151; }
    .divider { border: none; border-top: 1px solid #e5e7eb; margin: 36px 0; }
    /* CTA button */
    .cta-wrap { text-align: center; padding: 32px 40px 8px; }
    .cta-btn { display: inline-block; background: #FF6200; color: #ffffff !important; font-weight: 700; font-size: 14px; padding: 14px 36px; text-decoration: none; letter-spacing: 0.3px; }
    .coverage-note { font-size: 13px; color: #6b7280; background: #f9fafb; border-left: 3px solid #d1d5db; padding: 10px 14px; margin: 0 0 24px; border-radius: 0 4px 4px 0; line-height: 1.6; }
    .footer { background: #f9fafb; border-top: 1px solid #e5e7eb; padding: 24px 40px; font-size: 12px; color: #9ca3af; text-align: center; line-height: 1.9; }
    .footer a { color: #FF6200; text-decoration: none; font-weight: 600; }
    .footer-legal { font-size: 11px; color: #c0c4cc; margin-top: 8px; line-height: 1.7; }
    @media only screen and (max-width: 620px) {
        .wrapper { border: none !important; }
        .header { padding: 16px !important; }
        .header-title { font-size: 18px !important; }
        .content { padding: 20px 16px !important; }
        .cta-wrap { padding: 24px 16px 8px !important; }
        .footer { padding: 16px !important; }
        table { min-width: 0 !important; }
        th { padding: 9px 8px !important; font-size: 11px !important; }
        td { padding: 8px 8px !important; }
        h2 { font-size: 16px !important; }
        h3 { font-size: 13px !important; }
        .section-eyebrow { margin-top: 24px !important; }
        .hide-mob { display: none !important; }
        .scroll-hint { display: block !important; }
        .summary-item { display: block !important; margin-bottom: 10px !important; }
    }
"""



def _render_fee_table(asset_label: str, fee_data: dict, calc_logic: dict | None = None) -> str:
    """Render one <table> for a single asset type (stocks/ETFs/bonds).

    Args:
        asset_label: Display label e.g. "Stocks"
        fee_data: {"Broker Name": {"250": 2.5, "500": 3.0, ...}, ...}
        calc_logic: {"Broker Name": {"250": "explanation...", ...}, ...}
                    Used as title= tooltip on each cell.
    """
    if not fee_data:
        return f"<h3>{asset_label}</h3><p><em>No data available.</em></p>"

    # Collect all amount columns (sorted numerically)
    amount_cols: list[str] = sorted(
        {amt for broker_fees in fee_data.values() for amt in broker_fees},
        key=lambda x: int(x),
    )

    # Find the cheapest broker per amount column
    min_per_col = {
        amt: min(
            (fees[amt] for fees in fee_data.values() if amt in fees),
            default=None,
        )
        for amt in amount_cols
    }

    # On mobile keep 4 evenly-spaced columns; hide the rest with .hide-mob
    n = len(amount_cols)
    if n <= 4:
        mobile_hidden: set[str] = set()
    else:
        keep = {0, round((n - 1) / 3), round(2 * (n - 1) / 3), n - 1}
        mobile_hidden = {amt for i, amt in enumerate(amount_cols) if i not in keep}

    def _th(amt: str) -> str:
        cls = ' class="hide-mob"' if amt in mobile_hidden else ""
        return f"<th{cls}>€{amt}</th>"

    header_cells = "".join(_th(amt) for amt in amount_cols)
    header = f"<tr><th>Broker</th>{header_cells}</tr>"

    rows = []
    for row_idx, (broker, fees) in enumerate(sorted(fee_data.items())):
        broker_logic = (calc_logic or {}).get(broker, {})
        cells = []
        for amt in amount_cols:
            mob = amt in mobile_hidden
            val = fees.get(amt)
            tooltip = broker_logic.get(amt, "")
            # title on <td> works in Gmail/web browsers; Outlook ignores it
            # (methodology section below provides the same info for all clients)
            t = f' title="{html.escape(tooltip)}"' if tooltip else ""
            if val is None:
                cells.append('<td class="hide-mob">—</td>' if mob else "<td>—</td>")
            elif val == min_per_col[amt]:
                cls = "cheapest hide-mob" if mob else "cheapest"
                # ★ label makes "cheapest" legible without relying on color alone
                cells.append(f'<td class="{cls}"{t}>\u20ac{val:.2f} \u2605</td>')
            else:
                cells.append(f'<td class="hide-mob"{t}>\u20ac{val:.2f}</td>' if mob else f"<td{t}>\u20ac{val:.2f}</td>")
        logo = _broker_logo_img(broker)
        # bgcolor on <tr> is the Outlook-safe fallback for alternating row shading
        row_bg = ' bgcolor="#f9fafb"' if row_idx % 2 == 1 else ""
        rows.append(f"<tr{row_bg}><td>{logo}{broker}</td>{''.join(cells)}</tr>")

    return (
        f"<h3>{asset_label}</h3>"
        f'<p class="scroll-hint">&#8592; scroll for more columns &#8594;</p>'
        f'<div class="table-wrap">'
        f"<table><thead>{header}</thead><tbody>{''.join(rows)}</tbody></table>"
        f"</div>"
    )



def _render_methodology_block(methodology: dict, asset_type: str) -> str:
    """Render fee calculation formulas as a footnote block.

    Args:
        methodology: {broker_name: {asset_type: "formula description", ...}, ...}
        asset_type: "stocks" or "etfs"
    """
    entries = {
        broker: meth[asset_type]
        for broker, meth in sorted(methodology.items())
        if asset_type in meth
    }
    if not entries:
        return ""

    lines = "".join(
        f"<strong>{html.escape(broker)}:</strong> {html.escape(formula)}<br>"
        for broker, formula in entries.items()
    )
    return (
        '<div style="font-size:11px;color:#6b7280;margin:6px 0 20px;'
        "padding:12px 16px;background:#f9fafb;border-left:3px solid #FF6200;"
        'line-height:1.9;">'
        '<strong style="color:#374151;">How fees are calculated</strong><br>'
        f"{lines}"
        "</div>"
    )


_SKIP_NOTE = re.compile(
    r'\b(card\b|ATM|cash balance|saveback|cash interest'
    r'|debit interest|dormant account|post correspondence'
    r'|administrative quer|general meeting certificate'
    r'|bearer conversion|best effort order'
    r'|nominee to bearer)',
    re.IGNORECASE,
)

# Notes that state zero fees / no fees — not useful to show
_ZERO_NOTE = re.compile(
    r'^no\s+(custody|entry|exit|dossier|dividend|connectivity|subscription|management)'
    r'|^no\s+\w+\s+(fee|cost|charge)s?\b'
    r'|\bEUR\s*0[\s.,]|\b€\s*0[\s.,]|\bEUR\s*0$|\b€\s*0$'
    r'|\bEUR\s+0\.00\b|\b€\s*0\.00\b'
    r'|\bnot\s+retain\b|\bnot\s+disclosed\b'
    r'|processing:\s*EUR\s*0',
    re.IGNORECASE,
)


_HIGHLIGHT = re.compile(
    r'('
    # EUR/USD amounts: €1.00, EUR 2.50, $100, USD 50, or "1 EUR", "2.50 EUR"
    r'(?:€|EUR\s?|USD\s?|\$)\d[\d,.]*(?:\s*%)?'
    r'|\d[\d,.]*\s*(?:€|EUR|USD)\b'
    # Percentages: 0.25%, 1.40%
    r'|\d[\d,.]*\s*%'
    # "free" / "no charge" / "waived" as standalone keywords
    r'|\bfree\b|\bno charge\b|\bwaived\b'
    # min/max clauses: "min EUR 1.00", "max 0.25%", "maximum €50"
    r'|\b(?:min(?:imum)?|max(?:imum)?)\s+(?:€|EUR\s?|USD\s?|\$)?\d[\d,.]*(?:\s*%)?'
    r')',
    re.IGNORECASE,
)


def _highlight_note(text: str) -> str:
    """Bold important financial figures in a note string.

    Applies <strong> to EUR/USD amounts, percentages, free/waived keywords,
    and min/max caps. Input must already be HTML-escaped.
    """
    return _HIGHLIGHT.sub(r'<strong>\1</strong>', text)


def _split_notes(notes: str) -> list[str]:
    """Split a notes string into individual bullet items.

    Handles both numbered items ("1) ...", "2) ...") and plain sentences.
    Filters out non-investment content.
    """
    if not notes:
        return []
    # Protect common abbreviations from sentence splitting
    _ABBREVS = {'incl.': 'incl\x00', 'excl.': 'excl\x00',
                'e.g.': 'e\x00g\x00', 'i.e.': 'i\x00e\x00',
                'min.': 'min\x00', 'max.': 'max\x00'}
    protected = notes
    for abbr, placeholder in _ABBREVS.items():
        protected = protected.replace(abbr, placeholder)

    # Try splitting on numbered patterns like "1) " at boundaries
    numbered = re.split(r'\s*\d+\)\s+', protected.strip())
    if len(numbered) > 2:
        items = [s.strip().rstrip('.') for s in numbered if s.strip()]
    else:
        # Fall back to sentence splitting
        items = [s.strip().rstrip('.') for s in re.split(r'(?<=\.)\s+', protected.strip()) if s.strip()]

    # Restore abbreviations
    restored = []
    for item in items:
        for abbr, placeholder in _ABBREVS.items():
            item = item.replace(placeholder, abbr)
        restored.append(item)
    return [
        item for item in restored
        if item and not _SKIP_NOTE.search(item) and not _ZERO_NOTE.search(item)
    ]


def _render_broker_notes(hidden_costs: dict, structured_notes: dict | None = None) -> str:
    """Render a broker notes section with investment-related notes as bullet lists.

    Args:
        hidden_costs: {broker_name: HiddenCosts dataclass or dict}
        structured_notes: {broker_name: [{"category": ..., "label": ..., "description": ..., "highlight": ...}]}
                          If provided, promotion items are rendered with bold red styling.
    """
    if not hidden_costs:
        return ""

    promo_blocks = []
    regular_blocks = []
    for broker, c in sorted(hidden_costs.items()):
        g = c if isinstance(c, dict) else c.__dict__
        raw_notes = g.get('notes', '')
        items = _split_notes(raw_notes)

        # Collect promotion items from structured notes (e.g. youth discounts)
        promotion_bullets = ""
        if structured_notes:
            broker_structured = structured_notes.get(broker, [])
            for note_item in broker_structured:
                if note_item.get("category") == "promotion":
                    desc = html.escape(note_item.get("description", ""))
                    label = html.escape(note_item.get("label", ""))
                    promotion_bullets += (
                        f'<li style="margin-bottom:4px;">'
                        f'<strong style="color:#dc2626;">{label}:</strong> '
                        f'<strong style="color:#dc2626;">{desc}</strong>'
                        f'</li>'
                    )

        if not items and not promotion_bullets:
            continue
        logo = _broker_logo_img(broker)
        bullets = "".join(
            f'<li style="margin-bottom:4px;">{_highlight_note(html.escape(item))}</li>'
            for item in items
        )
        block = (
            f'<div style="margin-bottom:20px;padding:16px 20px;background:#f9fafb;'
            f'border-radius:8px;border-left:3px solid #FF6200;">'
            f'<div style="font-weight:700;font-size:14px;color:#111827;margin-bottom:8px;">'
            f'{logo}{html.escape(broker)}</div>'
            f'<ul style="margin:0;padding-left:18px;font-size:12px;color:#374151;line-height:1.8;">'
            f'{promotion_bullets}{bullets}</ul>'
            f'</div>'
        )
        if promotion_bullets:
            promo_blocks.append(block)
        else:
            regular_blocks.append(block)
    blocks = promo_blocks + regular_blocks

    if not blocks:
        return ""

    return (
        '<a id="broker-notes"></a>'
        '<p class="section-eyebrow">Broker Notes</p>'
        "<h2>Key Investment-Related Notes</h2>"
        '<p class="table-note">'
        "Important details about fees, promotions, and conditions "
        "that may affect your investment costs.</p>"
        + "".join(blocks)
    )


def _render_persona_section(investor_personas: dict, persona_definitions: dict) -> str:
    """Render ranked TCO tables per investor persona."""
    if not investor_personas:
        return ""

    sections = [
        '<hr class="divider">'
        '<p class="section-eyebrow">Investor Profiles</p>'
        "<h2>Total Cost of Ownership Rankings</h2>"
        '<p class="table-note">Annual cost per investor profile including trading fees, '
        "custody, connectivity, and all other charges.</p>"
    ]

    for persona_key, results in investor_personas.items():
        persona_def = persona_definitions.get(persona_key, {})
        persona_name = persona_def.get("name", persona_key.replace("_", " ").title())
        persona_desc = persona_def.get("description", "")

        sections.append(f"<h3>{persona_name}</h3>")
        if persona_desc:
            sections.append(f"<p><em>{persona_desc}</em></p>")

        if not results:
            sections.append("<p><em>No data available.</em></p>")
            continue

        header = (
            "<tr>"
            "<th>Rank</th><th>Broker</th>"
            "<th>Trading</th><th>Custody</th>"
            "<th>Other</th><th>Total TCO/yr</th>"
            "</tr>"
        )
        rows = []
        for r in results:
            rank = r.get("rank", "—")
            broker = r.get("broker", "")
            trading = r.get("trading_costs", 0.0)
            custody = r.get("custody_cost_annual", 0.0)
            other = (
                r.get("connectivity_cost_annual", 0.0)
                + r.get("subscription_cost_annual", 0.0)
                + r.get("fx_cost_annual", 0.0)
                + r.get("dividend_cost_annual", 0.0)
            )
            tco = r.get("total_annual_tco", 0.0)
            # bgcolor on <tr> is the Outlook-safe fallback; CSS class handles modern clients
            if rank == 1:
                row_attrs = ' class="rank-1" bgcolor="#fef3c7"'
            elif rank == 2:
                row_attrs = ' class="rank-2" bgcolor="#eff6ff"'
            else:
                row_attrs = ""
            rows.append(
                f"<tr{row_attrs}>"
                f"<td>#{rank}</td><td>{_broker_logo_img(broker)}{broker}</td>"
                f"<td>\u20ac{trading:.2f}</td><td>\u20ac{custody:.2f}</td>"
                f"<td>\u20ac{other:.2f}</td><td><strong>\u20ac{tco:.2f}</strong></td>"
                "</tr>"
            )

        sections.append(
            f'<div class="table-wrap">'
            f"<table><thead>{header}</thead><tbody>{''.join(rows)}</tbody></table>"
            f"</div>"
        )

    return "\n".join(sections)


# ========================================================================================
# PUBLIC API
# ========================================================================================


def build_email_html(tables_data: dict) -> str:
    """Render a self-contained HTML email from cost comparison data.

    Args:
        tables_data: Output of build_comparison_tables() — keyed by market
                     (e.g. "euronext_brussels") with stocks/etfs/bonds sub-dicts.
                     May also contain "investor_personas" and "persona_definitions".
    """
    now = datetime.now(timezone.utc)
    now_str = now.strftime("%d %B %Y at %H:%M UTC")
    year = now.year

    # Extract fee tables, calculation logic, and methodology (merge across markets)
    all_stocks: dict = {}
    all_etfs: dict = {}
    stocks_logic: dict = {}
    etfs_logic: dict = {}
    all_methodology: dict = {}
    for _market, market_data in tables_data.items():
        if not isinstance(market_data, dict):
            continue
        all_stocks.update(market_data.get("stocks", {}))
        all_etfs.update(market_data.get("etfs", {}))
        for broker, asset_logic in market_data.get("calculation_logic", {}).items():
            stocks_logic.setdefault(broker, {}).update(asset_logic.get("stocks", {}))
            etfs_logic.setdefault(broker, {}).update(asset_logic.get("etfs", {}))
        for broker, meth in market_data.get("methodology", {}).items():
            all_methodology.setdefault(broker, {}).update(meth)

    hidden_costs = tables_data.get("hidden_costs", {})
    structured_notes = tables_data.get("structured_notes", None)

    fee_section = (
        '<p class="section-eyebrow">Fee Comparison</p>'
        '<h2>Transaction Fees by Investment Amount</h2>'
        '<p class="table-note">All amounts in EUR. Computed from official tariff schedules. '
        '\u2605 = cheapest broker for that column. '
        'See <a href="#broker-notes" style="color:#FF6200;font-weight:600;">'
        'Broker Notes</a> below for promotions and conditions.</p>'
        + _render_fee_table(
            "Stocks \u2014 Euronext Brussels, Amsterdam & Paris",
            all_stocks,
            stocks_logic,
        )
        + _render_fee_table(
            "ETFs \u2014 Euronext Brussels, Amsterdam & Paris",
            all_etfs,
            etfs_logic,
        )
        + _render_broker_notes(hidden_costs, structured_notes)
    )

    # Consolidated methodology appendix (moved out of per-table inline blocks)
    methodology_appendix = ""
    stocks_meth = _render_methodology_block(all_methodology, "stocks")
    etfs_meth = _render_methodology_block(all_methodology, "etfs")
    if stocks_meth or etfs_meth:
        methodology_appendix = (
            '<hr class="divider">'
            '<p class="section-eyebrow">Appendix</p>'
            '<h2>Fee Calculation Methodology</h2>'
            '<p class="table-note">How each broker\'s fees are computed for the amounts shown above.</p>'
            + (f'<h3>Stocks</h3>{stocks_meth}' if stocks_meth else "")
            + (f'<h3>ETFs</h3>{etfs_meth}' if etfs_meth else "")
        )

    html_out = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Weekly Brokerage Price Comparison</title>
  <style>{_STYLES}</style>
</head>
<body>
<div class="wrapper">
  <div class="header">
    <p class="header-eyebrow">Broker Pricing Monitor &middot; Belgium</p>
    <p class="header-title">Weekly Brokerage Fee Comparison</p>
    <p class="header-date">{now_str}</p>
  </div>
  <div class="content">
    {fee_section}
    {methodology_appendix}
  </div>
  <div class="cta-wrap">
    <a href="https://rajeshrai248.uk" class="cta-btn">View Live Dashboard &rarr;</a>
  </div>
  <div class="footer">
    Generated on {now_str}.<br>
    Fees sourced from published tariff schedules as of the report date.<br>
    Full comparisons and personalised cost analysis at
    <a href="https://rajeshrai248.uk">rajeshrai248.uk</a>
    <div class="footer-legal">
      All figures computed from published tariff schedules &mdash; no estimates, no guesswork.<br>
      For informational purposes only. Not financial advice.<br>
      Fee data is extracted and compiled by AI agents and may contain errors &mdash;
      always verify against official broker tariff schedules.<br>
      &copy; {year} Rajesh Rai. All rights reserved.
    </div>
  </div>
</div>
</body>
</html>"""

    return html_out


def send_email(subject: str, html_body: str, recipients: list[str]) -> None:
    """Send an HTML email via Gmail SMTP (TLS on port 587).

    Args:
        subject: Email subject line.
        html_body: HTML content of the email body.
        recipients: List of recipient email addresses.

    Raises:
        ValueError: If SMTP_USER or SMTP_PASSWORD are not configured.
        smtplib.SMTPException: On SMTP delivery failure.
    """
    if not SMTP_USER or not SMTP_PASSWORD:
        raise ValueError(
            "SMTP_USER and SMTP_PASSWORD must be configured to send emails. "
            "Set them as environment variables."
        )
    if not recipients:
        raise ValueError("No recipients specified.")

    from_addr = SMTP_FROM_EMAIL or SMTP_USER

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = from_addr  # BCC behaviour: recipients are passed to sendmail() only, never exposed in headers
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    # Read at call time so .env changes take effect without module reimport
    skip_verify = os.environ.get("SMTP_SKIP_VERIFY", "false").lower() == "true"
    if skip_verify:
        logger.warning("⚠️  SMTP_SKIP_VERIFY=true — SSL certificate verification is disabled")
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
    else:
        # Use certifi CA bundle if available (fixes cert chain issues on Windows/macOS)
        try:
            import certifi
            ssl_context = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            ssl_context = ssl.create_default_context()

    logger.info(f"📧 Sending email to {recipients} via {SMTP_HOST}:{SMTP_PORT}")
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.ehlo()
        server.starttls(context=ssl_context)
        server.ehlo()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(from_addr, recipients, msg.as_string())
    logger.info(f"✅ Email sent successfully to {len(recipients)} recipient(s)")


def build_and_send_report(recipients_override: list[str] | None = None) -> dict:
    """Orchestrate fee data collection, HTML rendering, and email delivery.

    Args:
        recipients_override: If provided, use these instead of EMAIL_RECIPIENTS env var.

    Returns:
        dict with keys: status, recipients, sent_at, subject

    Raises:
        ValueError: If no recipients configured and none overridden.
        smtplib.SMTPException: On delivery failure.
    """
    from .validation.fee_calculator import build_comparison_tables, _ensure_rules_loaded, FEE_RULES, HIDDEN_COSTS

    _ensure_rules_loaded()

    recipients = recipients_override if recipients_override else _get_recipients()
    if not recipients:
        raise ValueError(
            "No email recipients configured. "
            "Set EMAIL_RECIPIENTS env var or pass recipients_override."
        )

    # Always compute from FEE_RULES (loaded from fee_rules.json) — the same source
    # of truth the /cost-comparison-tables endpoint uses. Reading from a cached JSON
    # file risks serving stale values when fee rules change between file writes.
    broker_keys = list({rule.broker for rule in FEE_RULES.values()})
    if not broker_keys:
        raise ValueError("No fee rules loaded — cannot build comparison tables.")
    logger.info(f"Building comparison tables for {len(broker_keys)} brokers")
    tables = build_comparison_tables(broker_keys)
    tables["hidden_costs"] = dict(HIDDEN_COSTS)

    # Include structured notes (with promotions from FEE_RULES conditions)
    from .api.server import _build_structured_broker_notes
    tables["structured_notes"] = _build_structured_broker_notes()

    html_body = build_email_html(tables)

    now = datetime.now(timezone.utc)
    subject = f"Weekly Brokerage Price Comparison — {now.strftime('%d %b %Y')}"

    send_email(subject, html_body, recipients)

    return {
        "status": "sent",
        "recipients": recipients,
        "sent_at": now.isoformat(timespec="seconds"),
        "subject": subject,
    }
