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
    .header { background: #e87722; color: #fff; padding: 24px 32px; }
    .header h1 { margin: 0; font-size: 22px; }
    .header p { margin: 6px 0 0; font-size: 13px; opacity: 0.85; }
    .content { padding: 24px 32px; }
    h3 { color: #e87722; font-size: 15px; border-bottom: 2px solid #ffe0c2; padding-bottom: 6px; margin: 28px 0 10px; }
    table { border-collapse: collapse; width: 100%; margin-bottom: 16px; font-size: 13px; }
    th { background: #e87722; color: #fff; padding: 7px 10px; text-align: right; cursor: help; }
    th:first-child { text-align: left; }
    td { padding: 6px 10px; border-bottom: 1px solid #eee; text-align: right; }
    td:first-child { text-align: left; font-weight: bold; }
    tr:hover td { background: #fff5ee; }
    .cheapest { background: #eafaf1; color: #1a7a3c; font-weight: bold; }
    .footer { background: #f5f5f5; border-top: 1px solid #ddd; padding: 14px 32px; font-size: 11px; color: #888; }
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

    header_cells = "".join(f"<th>€{amt}</th>" for amt in amount_cols)
    header = f"<tr><th>Broker</th>{header_cells}</tr>"

    rows = []
    for broker, fees in sorted(fee_data.items()):
        broker_logic = (calc_logic or {}).get(broker, {})
        cells = []
        for amt in amount_cols:
            val = fees.get(amt)
            tooltip = broker_logic.get(amt, "")
            title_attr = f' title="{tooltip}"' if tooltip else ""
            if val is None:
                cells.append("<td>—</td>")
            elif val == min_per_col[amt]:
                cells.append(f'<td class="cheapest"{title_attr}>€{val:.2f}</td>')
            else:
                cells.append(f"<td{title_attr}>€{val:.2f}</td>")
        rows.append(f"<tr><td>{broker}</td>{''.join(cells)}</tr>")

    return (
        f"<h3>{asset_label}</h3>"
        f"<table><thead>{header}</thead><tbody>{''.join(rows)}</tbody></table>"
    )


def _fmt_pct(val: float, suffix: str = "") -> str:
    """Format a percentage value, returning '—' if zero."""
    return f"{val * 100:.2f}%{suffix}" if val else "—"


def _fmt_eur(val: float, suffix: str = "") -> str:
    """Format a EUR value, returning '—' if zero."""
    return f"€{val:.2f}{suffix}" if val else "—"


def _render_hidden_costs_table(hidden_costs: dict) -> str:
    """Render a table of hidden / ongoing broker costs.

    Args:
        hidden_costs: {broker_name: HiddenCosts dataclass or dict}
    """
    if not hidden_costs:
        return ""

    columns = [
        ("Custody", "custody",
         "Ongoing fee charged by the broker to hold your securities. "
         "Usually a monthly percentage of your portfolio value, often with a minimum charge."),
        ("Connectivity", "connectivity",
         "Annual fee to access a specific stock exchange (e.g. Euronext Brussels, NYSE). "
         "Some brokers waive this if you trade a minimum number of times."),
        ("Subscription", "subscription",
         "Fixed monthly platform or account fee, charged regardless of trading activity. "
         "Common with brokers that offer premium tools or research."),
        ("FX Fee", "fx",
         "Currency conversion charge applied when you buy or sell instruments priced "
         "in a foreign currency (e.g. USD stocks). Shown as a percentage of the converted amount."),
        ("Handling/trade", "handling",
         "A small fixed fee added on top of the transaction fee per trade. "
         "Covers administrative processing costs."),
        ("Dividend Fee", "dividend",
         "Fee charged when a dividend is paid into your account. "
         "Usually a percentage of the dividend amount, often with a minimum and maximum cap."),
    ]

    header_cells = "".join(f'<th title="{tip}">{label} &#9432;</th>' for label, _, tip in columns)
    header = f"<tr><th>Broker</th>{header_cells}</tr>"

    rows = []
    for broker, c in sorted(hidden_costs.items()):
        # Accept both dataclass and plain dict
        g = c if isinstance(c, dict) else c.__dict__

        custody = (
            f"{g.get('custody_fee_monthly_pct', 0) * 100:.3f}%/mo"
            + (f" (min {_fmt_eur(g.get('custody_fee_monthly_min', 0))})" if g.get('custody_fee_monthly_min') else "")
            if g.get('custody_fee_monthly_pct') else "—"
        )
        connectivity = (
            _fmt_eur(g.get('connectivity_fee_per_exchange_year', 0), "/exchange/yr")
            if g.get('connectivity_fee_per_exchange_year') else "—"
        )
        sub_fee = g.get('subscription_fee_monthly', 0)
        sub_plan = g.get('subscription_plan_name', '')
        if sub_fee:
            sub_label = f"{sub_plan}: " if sub_plan else ""
            subscription = f"{sub_label}{_fmt_eur(sub_fee)}/mo"
        else:
            subscription = "—"
        fx = _fmt_pct(g.get('fx_fee_pct', 0))
        handling = (
            _fmt_eur(g.get('handling_fee_per_trade', 0), "/trade")
            if g.get('handling_fee_per_trade') else "—"
        )
        div_pct = g.get('dividend_fee_pct', 0)
        div_min = g.get('dividend_fee_min', 0)
        div_max = g.get('dividend_fee_max', 0)
        if div_pct:
            div_parts = [f"{div_pct * 100:.2f}%"]
            if div_min:
                div_parts.append(f"min {_fmt_eur(div_min)}")
            if div_max:
                div_parts.append(f"max {_fmt_eur(div_max)}")
            dividend = " / ".join(div_parts)
        else:
            dividend = "—"

        notes = g.get('notes', '')
        row_title = f' title="{notes}"' if notes else ""
        cells = "".join(
            f"<td>{v}</td>" for v in [custody, connectivity, subscription, fx, handling, dividend]
        )
        rows.append(f"<tr{row_title}><td>{broker}</td>{cells}</tr>")

    return (
        "<h3>Additional Ongoing Costs</h3>"
        "<p style='font-size:12px;color:#666;margin:0 0 8px;'>"
        "Costs beyond per-trade fees — custody, connectivity, subscriptions, and FX charges. "
        "Hover over a column header &#9432; for an explanation of each cost type. "
        "Hover over a broker row for broker-specific notes.</p>"
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

    # Extract fee tables and calculation logic (merge across markets if multiple)
    all_stocks: dict = {}
    all_etfs: dict = {}
    stocks_logic: dict = {}
    etfs_logic: dict = {}
    for _market, market_data in tables_data.items():
        if not isinstance(market_data, dict):
            continue
        all_stocks.update(market_data.get("stocks", {}))
        all_etfs.update(market_data.get("etfs", {}))
        for broker, asset_logic in market_data.get("calculation_logic", {}).items():
            stocks_logic.setdefault(broker, {}).update(asset_logic.get("stocks", {}))
            etfs_logic.setdefault(broker, {}).update(asset_logic.get("etfs", {}))

    hidden_costs = tables_data.get("hidden_costs", {})

    fee_section = (
        "<p>Fees shown per trade for common investment amounts. "
        "All amounts in EUR. Calculations are deterministic and rule-based. "
        "<span style='background:#eafaf1;color:#1a7a3c;font-weight:bold;padding:1px 5px;border-radius:3px;font-size:12px;'>Green</span>"
        " = cheapest broker for that amount. Hover over any value to see how it is calculated.</p>"
        + _render_fee_table(
            "Stocks transaction fees by investment amount (Euronext Brussels)",
            all_stocks,
            stocks_logic,
        )
        + _render_fee_table(
            "ETFs transaction fees by investment amount (Euronext Brussels)",
            all_etfs,
            etfs_logic,
        )
        + _render_hidden_costs_table(hidden_costs)
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Your Belgian Investment Cost Digest</title>
  <style>{_STYLES}</style>
</head>
<body>
<div class="wrapper">
  <div class="header">
    <h1>Your Belgian Investment Cost Digest</h1>
    <p>Fee comparison for Belgian retail investors — {now_str}</p>
  </div>
  <div class="content">
    <p>
      Knowing what you pay in broker fees can make a significant difference to your
      long-term investment returns. This digest compares transaction costs across
      Belgian retail brokers so you can make informed, cost-efficient decisions.
    </p>
    {fee_section}
  </div>
  <div class="footer">
    Your Belgian Investment Cost Digest — generated on {now_str}.<br>
    Fees are based on published tariff schedules and may change; always verify with your broker.<br><br>
    For full broker comparisons, live data, and personalised cost analysis, visit
    <a href="https://rajeshrai248.uk" style="color: #e87722; text-decoration: none; font-weight: bold;">rajeshrai248.uk</a>.<br>
    <span style="font-size: 10px; color: #aaa;">
      This report is for informational purposes only and does not constitute financial advice.
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
    msg["To"] = ", ".join(recipients)
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
    subject = f"Your Belgian Investment Cost Digest — {now.strftime('%d %b %Y')}"

    send_email(subject, html_body, recipients)

    return {
        "status": "sent",
        "recipients": recipients,
        "sent_at": now.isoformat(timespec="seconds"),
        "subject": subject,
    }
