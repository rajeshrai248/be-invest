"""Email report sender for be-invest broker fee comparisons.

Sends bi-weekly HTML email reports containing cost comparison tables and
investor persona TCO rankings. Uses Gmail SMTP via stdlib smtplib only.
"""

import logging
import os
import smtplib
import ssl
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

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
    body { font-family: Arial, sans-serif; color: #333; margin: 0; padding: 0; background: #f5f5f5; }
    .wrapper { max-width: 800px; margin: 0 auto; background: #fff; }
    .header { background: #1a3a5c; color: #fff; padding: 24px 32px; }
    .header h1 { margin: 0; font-size: 22px; }
    .header p { margin: 6px 0 0; font-size: 13px; opacity: 0.8; }
    .content { padding: 24px 32px; }
    h2 { color: #1a3a5c; font-size: 17px; border-bottom: 2px solid #e0e0e0; padding-bottom: 6px; margin-top: 28px; }
    h3 { color: #2c5f8a; font-size: 14px; margin: 18px 0 8px; }
    table { border-collapse: collapse; width: 100%; margin-bottom: 16px; font-size: 13px; }
    th { background: #1a3a5c; color: #fff; padding: 7px 10px; text-align: right; }
    th:first-child { text-align: left; }
    td { padding: 6px 10px; border-bottom: 1px solid #eee; text-align: right; }
    td:first-child { text-align: left; font-weight: bold; }
    tr:hover td { background: #f0f7ff; }
    .rank-1 td:first-child { color: #27ae60; }
    .rank-2 td:first-child { color: #2980b9; }
    .footer { background: #f5f5f5; border-top: 1px solid #ddd; padding: 14px 32px; font-size: 11px; color: #888; }
    .tag { display: inline-block; background: #e8f4fd; color: #1a3a5c; border-radius: 3px;
           padding: 2px 7px; font-size: 11px; margin: 2px; }
"""


def _render_fee_table(asset_label: str, fee_data: dict) -> str:
    """Render one <table> for a single asset type (stocks/ETFs/bonds).

    Args:
        asset_label: Display label e.g. "Stocks"
        fee_data: {"Broker Name": {"250": 2.5, "500": 3.0, ...}, ...}
    """
    if not fee_data:
        return f"<h3>{asset_label}</h3><p><em>No data available.</em></p>"

    # Collect all amount columns (sorted numerically)
    amount_cols: list[str] = sorted(
        {amt for broker_fees in fee_data.values() for amt in broker_fees},
        key=lambda x: int(x),
    )

    header_cells = "".join(f"<th>€{amt}</th>" for amt in amount_cols)
    header = f"<tr><th>Broker</th>{header_cells}</tr>"

    rows = []
    for broker, fees in sorted(fee_data.items()):
        cells = []
        for amt in amount_cols:
            val = fees.get(amt)
            cells.append(f"<td>€{val:.2f}</td>" if val is not None else "<td>—</td>")
        rows.append(f"<tr><td>{broker}</td>{''.join(cells)}</tr>")

    return (
        f"<h3>{asset_label}</h3>"
        f"<table><thead>{header}</thead><tbody>{''.join(rows)}</tbody></table>"
    )


def _render_persona_section(investor_personas: dict, persona_definitions: dict) -> str:
    """Render ranked TCO tables per investor persona."""
    if not investor_personas:
        return ""

    sections = ["<h2>Investor Persona TCO Rankings</h2>"]
    sections.append(
        "<p>Annual total cost of ownership (TCO) per investor profile, "
        "including trading costs, custody, connectivity, and other fees.</p>"
    )

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
                f"<td>#{rank}</td><td>{broker}</td>"
                f"<td>€{trading:.2f}</td><td>€{custody:.2f}</td>"
                f"<td>€{other:.2f}</td><td><strong>€{tco:.2f}</strong></td>"
                "</tr>"
            )

        sections.append(
            f"<table><thead>{header}</thead><tbody>{''.join(rows)}</tbody></table>"
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

    # Extract fee tables (merge across markets if multiple)
    all_stocks: dict = {}
    all_etfs: dict = {}
    all_bonds: dict = {}
    for _market, market_data in tables_data.items():
        if not isinstance(market_data, dict):
            continue
        all_stocks.update(market_data.get("stocks", {}))
        all_etfs.update(market_data.get("etfs", {}))
        all_bonds.update(market_data.get("bonds", {}))

    investor_personas = tables_data.get("investor_personas", {})
    persona_definitions = tables_data.get("persona_definitions", {})

    fee_section = (
        "<h2>Transaction Fee Comparison (Euronext Brussels)</h2>"
        "<p>Fees shown per trade for common investment amounts. "
        "All amounts in EUR. Calculations are deterministic and rule-based.</p>"
        + _render_fee_table("Stocks", all_stocks)
        + _render_fee_table("ETFs", all_etfs)
        + _render_fee_table("Bonds", all_bonds)
    )

    persona_section = _render_persona_section(investor_personas, persona_definitions)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>BE-Invest Broker Fee Report</title>
  <style>{_STYLES}</style>
</head>
<body>
<div class="wrapper">
  <div class="header">
    <h1>BE-Invest Broker Fee Report</h1>
    <p>Bi-weekly comparison of Belgian broker fees — generated {now_str}</p>
  </div>
  <div class="content">
    <p>
      This automated report compares transaction fees and annual costs across
      Belgian retail brokers for Euronext Brussels instruments.
      Data is computed deterministically from verified fee rules.
    </p>
    {fee_section}
    {persona_section}
  </div>
  <div class="footer">
    Generated automatically by BE-Invest on {now_str}.<br>
    Fees are based on published tariff schedules and may change; always verify with your broker.
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
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    # Use certifi CA bundle if available (fixes SSL cert issues on Windows/macOS);
    # fall back to system default context otherwise.
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
    from .validation.fee_calculator import build_comparison_tables, _ensure_rules_loaded, FEE_RULES
    from .validation.persona_calculator import build_persona_comparison

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

    # Add persona data (non-fatal if it fails)
    try:
        persona_data = build_persona_comparison(broker_keys)
        tables["investor_personas"] = persona_data.get("investor_personas", {})
        tables["persona_definitions"] = persona_data.get("persona_definitions", {})
    except Exception:
        logger.warning("Persona comparison failed — email will omit TCO section", exc_info=True)

    html_body = build_email_html(tables)

    now = datetime.now(timezone.utc)
    subject = f"BE-Invest Broker Fee Report — {now.strftime('%d %b %Y')}"

    send_email(subject, html_body, recipients)

    return {
        "status": "sent",
        "recipients": recipients,
        "sent_at": now.isoformat(timespec="seconds"),
        "subject": subject,
    }
