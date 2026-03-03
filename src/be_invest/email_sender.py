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
    .wrapper { max-width: 700px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 16px rgba(0,0,0,0.06); }
    .header { background: #FF6200; color: #fff; padding: 24px 40px; }
    .header-eyebrow { font-size: 11px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; opacity: 0.85; margin: 0 0 6px; }
    .header p { margin: 0; font-size: 13px; opacity: 0.85; }
    .content { padding: 36px 40px; }
    p { word-wrap: break-word; overflow-wrap: break-word; max-width: 100%; margin: 0 0 16px; }
    em { word-wrap: break-word; overflow-wrap: break-word; }
    .intro { font-size: 14px; color: #374151; line-height: 1.75; margin-bottom: 32px; padding-bottom: 28px; border-bottom: 1px solid #e5e7eb; }
    .section-eyebrow { font-size: 11px; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase; color: #FF6200; margin: 36px 0 4px; }
    h2 { font-size: 20px; font-weight: 700; color: #111827; margin: 0 0 16px; }
    h3 { color: #111827; font-size: 14px; font-weight: 700; margin: 0 0 12px; }
    .table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; margin-bottom: 6px; }
    table { border-collapse: collapse; width: 100%; min-width: 420px; font-size: 13px; }
    th { background: #FF6200; color: #fff; padding: 11px 14px; text-align: right; font-weight: 600; font-size: 12px; }
    th:first-child { text-align: left; }
    td { padding: 10px 14px; border-bottom: 1px solid #f0f2f5; text-align: right; color: #374151; }
    td:first-child { text-align: left; font-weight: 600; color: #111827; }
    tbody tr:nth-child(even) td { background: #f9fafb; }
    tbody tr:hover td { background: #fff7ed !important; }
    .cheapest { background: #dcfce7 !important; color: #166534; font-weight: 700; }
    .rank-1 td { background: #fff7ed !important; }
    .rank-2 td { background: #f9fafb; }
    .table-note { font-size: 12px; color: #6b7280; margin: 0 0 24px; line-height: 1.6; }
    .footnotes { font-size: 11px; color: #6b7280; margin: 10px 0 28px; padding: 14px 16px; background: #f9fafb; border-left: 3px solid #FF6200; line-height: 1.9; border-radius: 0 4px 4px 0; }
    .footnotes strong { color: #374151; }
    .divider { border: none; border-top: 1px solid #e5e7eb; margin: 36px 0; }
    .footer { background: #f9fafb; border-top: 1px solid #e5e7eb; padding: 24px 40px; font-size: 11px; color: #9ca3af; text-align: center; line-height: 1.9; }
    .footer a { color: #FF6200; text-decoration: none; font-weight: 600; }
    @media only screen and (max-width: 620px) {
        .wrapper { border-radius: 0 !important; }
        .header { padding: 16px !important; }
        .content { padding: 20px 16px !important; }
        .footer { padding: 16px !important; }
        table { min-width: 0 !important; }
        th { padding: 9px 8px !important; }
        td { padding: 8px 8px !important; }
        h2 { font-size: 16px !important; }
        h3 { font-size: 13px !important; }
        .section-eyebrow { margin-top: 24px !important; }
        .hide-mob { display: none !important; }
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
    for broker, fees in sorted(fee_data.items()):
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
                cells.append(f'<td class="{cls}"{t}>€{val:.2f}</td>')
            else:
                cells.append(f'<td class="hide-mob"{t}>€{val:.2f}</td>' if mob else f"<td{t}>€{val:.2f}</td>")
        logo = _broker_logo_img(broker)
        rows.append(f"<tr><td>{logo}{broker}</td>{''.join(cells)}</tr>")

    return (
        f"<h3>{asset_label}</h3>"
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


def _render_broker_notes(hidden_costs: dict) -> str:
    """Render a broker notes section with investment-related notes as bullet lists.

    Args:
        hidden_costs: {broker_name: HiddenCosts dataclass or dict}
    """
    if not hidden_costs:
        return ""

    blocks = []
    for broker, c in sorted(hidden_costs.items()):
        g = c if isinstance(c, dict) else c.__dict__
        raw_notes = g.get('notes', '')
        items = _split_notes(raw_notes)
        if not items:
            continue
        logo = _broker_logo_img(broker)
        bullets = "".join(
            f'<li style="margin-bottom:4px;">{_highlight_note(html.escape(item))}</li>'
            for item in items
        )
        blocks.append(
            f'<div style="margin-bottom:20px;padding:16px 20px;background:#f9fafb;'
            f'border-radius:8px;border-left:3px solid #FF6200;">'
            f'<div style="font-weight:700;font-size:14px;color:#111827;margin-bottom:8px;">'
            f'{logo}{html.escape(broker)}</div>'
            f'<ul style="margin:0;padding-left:18px;font-size:12px;color:#374151;line-height:1.8;">'
            f'{bullets}</ul>'
            f'</div>'
        )

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
            row_class = f' class="rank-{rank}"' if rank in (1, 2) else ""
            rows.append(
                f"<tr{row_class}>"
                f"<td>#{rank}</td><td>{_broker_logo_img(broker)}{broker}</td>"
                f"<td>€{trading:.2f}</td><td>€{custody:.2f}</td>"
                f"<td>€{other:.2f}</td><td><strong>€{tco:.2f}</strong></td>"
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
    now_str = datetime.now(timezone.utc).strftime("%d %B %Y at %H:%M UTC")

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

    cheapest_badge = (
        "<span style='background:#dcfce7;color:#166534;font-weight:700;"
        "padding:2px 8px;border-radius:10px;font-size:11px;'>Green</span>"
    )
    fee_section = (
        '<h2>Transaction Fees by Investment Amount</h2>'
        f'<p class="table-note">All amounts in EUR. Fees are deterministic and rule-based. '
        f"{cheapest_badge} = cheapest broker for that amount. "
        f'See <a href="#broker-notes" style="color:#FF6200;font-weight:600;">'
        f'Broker Notes</a> below for additional fees, conditions, and promotions.</p>'
        + _render_fee_table(
            "Stocks \u2014 Euronext Brussels, Amsterdam & Paris",
            all_stocks,
            stocks_logic,
        )
        + _render_methodology_block(all_methodology, "stocks")
        + _render_fee_table(
            "ETFs \u2014 Euronext Brussels, Amsterdam & Paris",
            all_etfs,
            etfs_logic,
        )
        + _render_methodology_block(all_methodology, "etfs")
        + _render_broker_notes(hidden_costs)
    )

    html = f"""<!DOCTYPE html>
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
    <p class="header-eyebrow">Broker Pricing Monitor · Belgium</p>
    <p>{now_str}</p>
  </div>
  <div class="content">
    <p class="intro">
      This weekly digest provides a structured, data-driven comparison of transaction fees
      and total cost of ownership (TCO) across Belgian retail brokers. All figures are
      computed deterministically from published tariff schedules, ensuring full
      reproducibility and auditability for research purposes.<br><br>
      Use this report to benchmark competitive fee positioning, detect pricing shifts
      between brokers, and support your analysis of retail investment cost structures
      in the Belgian brokerage market.
    </p>
    {fee_section}
  </div>
  <div class="footer">
    Generated on {now_str}.<br>
    Fees sourced from published tariff schedules as of the report date.<br><br>
    Full comparisons, live data, and personalised cost analysis at
    <a href="https://rajeshrai248.uk">rajeshrai248.uk</a><br>
    <span style="font-size:10px;color:#c0c4cc;">
      For informational purposes only. Not financial advice.<br>
      Fee data is extracted and compiled by AI agents and may contain errors — always verify against official broker tariff schedules.
    </span>
  </div>
</div>
</body>
</html>"""

    return html


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

    # Collect broker names from loaded rules
    broker_keys = list({rule.broker for rule in FEE_RULES.values()})
    if not broker_keys:
        raise ValueError("No fee rules loaded — cannot build comparison tables.")

    logger.info(f"Building comparison tables for {len(broker_keys)} brokers")
    tables = build_comparison_tables(broker_keys)

    # Add hidden costs
    tables["hidden_costs"] = dict(HIDDEN_COSTS)

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
