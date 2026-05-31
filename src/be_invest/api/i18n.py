"""Language and structured-note helpers used by API and email rendering."""
from __future__ import annotations

import copy
import re
from typing import Dict, List

from ..validation.fee_calculator import FEE_RULES, HIDDEN_COSTS, _get_display_name


LANGUAGE_MAP = {
    "en": "English",
    "fr-be": "French (Belgian)",
    "nl-be": "Dutch (Belgian)",
}


def get_language_name(lang: str) -> str:
    """Map a language code to a full language name for LLM prompts."""

    return LANGUAGE_MAP.get(lang, "English")


# Static translations for persona definitions.
PERSONA_TRANSLATIONS: Dict[str, Dict[str, Dict[str, str]]] = {
    "fr-be": {
        "passive_investor": {
            "name": "Investisseur Passif",
            "description": "Achats mensuels d'ETF de 500 EUR. Stratégie d'achat et de conservation à long terme.",
        },
        "moderate_investor": {
            "name": "Investisseur Modéré",
            "description": "Combinaison d'achats d'ETF et d'actions. Gestion de portefeuille semi-active.",
        },
        "active_trader": {
            "name": "Trader Actif",
            "description": "Transactions fréquentes d'actions, y compris de grandes positions. Gestion active du portefeuille.",
        },
    },
    "nl-be": {
        "passive_investor": {
            "name": "Passieve Belegger",
            "description": "Maandelijkse ETF-aankopen van 500 EUR. Langetermijn buy-and-hold strategie.",
        },
        "moderate_investor": {
            "name": "Gematigde Belegger",
            "description": "Mix van ETF- en aandelenaankopen. Semi-actief portefeuillebeheer.",
        },
        "active_trader": {
            "name": "Actieve Handelaar",
            "description": "Frequente aandelentransacties inclusief grote posities. Actief portefeuillebeheer.",
        },
    },
}


NOTE_LABELS: Dict[str, Dict[str, str]] = {
    "en": {
        "custody": "Custody fee",
        "connectivity": "Connectivity fee",
        "fx": "FX fee",
        "subscription": "Subscription",
        "handling": "Handling fee",
        "dividend": "Dividend fee",
        "transfer": "Transfer out",
        "surcharge": "Surcharges",
        "market_data": "Market data",
        "promotion": "Promotions",
        "other": "Other costs",
    },
    "fr-be": {
        "custody": "Frais de garde",
        "connectivity": "Frais de connectivité",
        "fx": "Frais de change",
        "subscription": "Abonnement",
        "handling": "Frais de traitement",
        "dividend": "Frais de dividende",
        "transfer": "Transfert sortant",
        "surcharge": "Surcharges",
        "market_data": "Données de marché",
        "promotion": "Promotions",
        "other": "Autres frais",
    },
    "nl-be": {
        "custody": "Bewaarloon",
        "connectivity": "Connectiviteitskosten",
        "fx": "Wisselkoerskosten",
        "subscription": "Abonnement",
        "handling": "Verwerkingskosten",
        "dividend": "Dividendkosten",
        "transfer": "Uitgaande transfer",
        "surcharge": "Toeslagen",
        "market_data": "Marktgegevens",
        "promotion": "Promoties",
        "other": "Overige kosten",
    },
}

NOTE_CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "custody": ["custody", "bewaarloon", "garde", "dormant"],
    "connectivity": ["connectivity", "connectiviteit"],
    "fx": ["fx", "currency", "exchange cost", "wissel", "conversion"],
    "subscription": ["subscription", "plan", "abonnement"],
    "handling": ["handling", "afwikkeling", "settlement"],
    "dividend": ["dividend", "coupon"],
    "transfer": ["transfer", "outgoing", "sortant"],
    "surcharge": ["surcharge", "phone", "offline", "orderdesk"],
    "market_data": ["real-time", "quotes", "market fee"],
    "promotion": ["promotion", "youth", "discount", "saveback", "interest on cash", "free trade"],
}

ADVANTAGE_PATTERNS = ["free", "no custody", "no fee", "no connectivity", "no dividend", "eur 0", "kosteloos", "€0", "geen"]
WARNING_PATTERNS = ["not disclosed", "surcharge", "max ", "min eur", "dormant", "debit interest", "late submission"]


def classify_note_category(sentence: str) -> str:
    """Classify a sentence into a note category using keyword matching."""

    lower = sentence.lower()
    for category, keywords in NOTE_CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                return category
    return "other"


def classify_highlight(sentence: str) -> str:
    """Classify a sentence's highlight: advantage, warning, or info."""

    lower = sentence.lower()
    for pattern in WARNING_PATTERNS:
        if pattern in lower:
            return "warning"
    for pattern in ADVANTAGE_PATTERNS:
        if pattern in lower:
            return "advantage"
    return "info"


def parse_notes_text(raw_notes: str) -> List[Dict[str, str]]:
    """Parse raw note text into structured note items."""

    parts = re.split(r"\d+\)\s+", raw_notes)
    if len(parts) <= 1:
        parts = [s.strip() for s in raw_notes.split(". ") if s.strip()]
    else:
        parts = [s.strip().rstrip(".") for s in parts if s.strip()]

    items: List[Dict[str, str]] = []
    for part in parts:
        if not part or len(part) < 5:
            continue
        category = classify_note_category(part)
        items.append(
            {
                "category": category,
                "label": NOTE_LABELS["en"][category],
                "description": part.rstrip("."),
                "highlight": classify_highlight(part),
            }
        )
    return items


def build_structured_broker_notes() -> Dict[str, List[Dict[str, str]]]:
    """Build structured broker notes from hidden-cost and conditional fee-rule data."""

    notes: Dict[str, List[Dict[str, str]]] = {}

    for broker_name, costs in HIDDEN_COSTS.items():
        items: List[Dict[str, str]] = []

        if costs.custody_fee_monthly_pct == 0 and costs.custody_fee_monthly_min == 0:
            items.append({"category": "custody", "label": "Custody fee", "description": "Free", "highlight": "advantage"})
        elif costs.custody_fee_monthly_pct > 0:
            desc = f"{costs.custody_fee_monthly_pct}%/month"
            if costs.custody_fee_monthly_min > 0:
                desc += f" (min EUR{costs.custody_fee_monthly_min:.2f}/month)"
            items.append({"category": "custody", "label": "Custody fee", "description": desc, "highlight": "info"})

        if costs.connectivity_fee_per_exchange_year == 0:
            items.append({"category": "connectivity", "label": "Connectivity fee", "description": "Free", "highlight": "advantage"})
        else:
            desc = f"EUR{costs.connectivity_fee_per_exchange_year:.2f}/exchange/year"
            if costs.connectivity_fee_max_pct_account > 0:
                desc += f" (max {costs.connectivity_fee_max_pct_account}% of account)"
            items.append({"category": "connectivity", "label": "Connectivity fee", "description": desc, "highlight": "info"})

        if costs.subscription_fee_monthly > 0:
            desc = f"EUR{costs.subscription_fee_monthly:.2f}/month"
            if costs.subscription_plan_name:
                desc = f"{costs.subscription_plan_name}: {desc}"
            items.append({"category": "subscription", "label": "Subscription", "description": desc, "highlight": "info"})

        if costs.fx_fee_pct == 0:
            notes_lower = costs.notes.lower() if costs.notes else ""
            if "not disclosed" in notes_lower and ("fx" in notes_lower or "conversion" in notes_lower or "exchange" in notes_lower):
                items.append({"category": "fx", "label": "FX fee", "description": "Not disclosed", "highlight": "warning"})
            else:
                items.append({"category": "fx", "label": "FX fee", "description": "Free", "highlight": "advantage"})
        elif costs.fx_fee_pct > 0:
            items.append({"category": "fx", "label": "FX fee", "description": f"{costs.fx_fee_pct}%", "highlight": "info"})

        if costs.handling_fee_per_trade > 0:
            items.append({"category": "handling", "label": "Handling fee", "description": f"EUR{costs.handling_fee_per_trade:.2f}/trade", "highlight": "info"})

        if costs.dividend_fee_pct == 0:
            items.append({"category": "dividend", "label": "Dividend fee", "description": "Free", "highlight": "advantage"})
        elif costs.dividend_fee_pct > 0:
            desc = f"{costs.dividend_fee_pct}%"
            if costs.dividend_fee_min > 0 or costs.dividend_fee_max > 0:
                min_part = f"min EUR{costs.dividend_fee_min:.2f}" if costs.dividend_fee_min > 0 else ""
                max_part = f"max EUR{costs.dividend_fee_max:.2f}" if costs.dividend_fee_max > 0 else ""
                desc += f" ({', '.join(filter(None, [min_part, max_part]))})"
            items.append({"category": "dividend", "label": "Dividend fee", "description": desc, "highlight": "info"})

        if costs.notes:
            numeric_categories = {item["category"] for item in items}
            for parsed_item in parse_notes_text(costs.notes):
                if parsed_item["category"] not in numeric_categories:
                    items.append(parsed_item)

        notes[broker_name] = items

    for broker_key, instr_key, _exch_key in FEE_RULES:
        rule = FEE_RULES[(broker_key, instr_key, _exch_key)]
        if not rule.conditions:
            continue
        display = _get_display_name(broker_key)
        notes.setdefault(display, [])
        for cond in rule.conditions:
            if cond.get("type") != "age":
                continue
            desc = f"Reduced {instr_key} fees for ages {cond.get('min_age', '')}-{cond.get('max_age', '')} (Youth discount)"
            if not any(item.get("description") == desc for item in notes[display]):
                notes[display].append(
                    {
                        "category": "promotion",
                        "label": "Youth discount",
                        "description": desc,
                        "highlight": "advantage",
                    }
                )

    return notes


DESCRIPTION_TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "fr-be": {
        "Free": "Gratuit",
        "Not disclosed": "Non divulgué",
        "/month": "/mois",
        "/year": "/an",
        "/exchange/year": "/bourse/an",
        "/trade": "/transaction",
        "Youth discount": "Réduction jeunes",
        "Reduced": "Réduit",
        "fees for ages": "frais pour les âges",
        "Flat fee": "Frais fixe",
        "handling": "traitement",
        "minimum": "minimum",
        "Base fee": "Frais de base",
        "amount": "montant",
        "remainder": "reste",
        "slices": "tranches",
        "slice": "tranche",
        "capped at": "plafonné à",
        "No fee rule for": "Aucune règle de frais pour",
        "Fee:": "Frais :",
        "base": "base",
        "per": "par",
    },
    "nl-be": {
        "Free": "Gratis",
        "Not disclosed": "Niet bekendgemaakt",
        "/month": "/maand",
        "/year": "/jaar",
        "/exchange/year": "/beurs/jaar",
        "/trade": "/transactie",
        "Youth discount": "Jongerenkorting",
        "Reduced": "Verlaagd",
        "fees for ages": "kosten voor leeftijden",
        "Flat fee": "Vast tarief",
        "handling": "afwikkeling",
        "minimum": "minimum",
        "Base fee": "Basiskosten",
        "amount": "bedrag",
        "remainder": "restbedrag",
        "slices": "schijven",
        "slice": "schijf",
        "capped at": "geplafonneerd op",
        "No fee rule for": "Geen tariefregel voor",
        "Fee:": "Kosten:",
        "base": "basis",
        "per": "per",
    },
}


def translate_description(description: str, lang: str) -> str:
    """Translate a note description string using static substitutions."""

    translations = DESCRIPTION_TRANSLATIONS.get(lang, {})
    result = description
    for en_text, translated in sorted(translations.items(), key=lambda x: len(x[0]), reverse=True):
        result = result.replace(en_text, translated)
    return result


def localize_structured_notes(
    notes: Dict[str, List[Dict[str, str]]], lang: str
) -> Dict[str, List[Dict[str, str]]]:
    """Translate labels and descriptions in structured notes to the target language."""

    if lang == "en":
        return notes
    labels = NOTE_LABELS.get(lang, NOTE_LABELS["en"])
    localized = copy.deepcopy(notes)
    for broker_items in localized.values():
        for item in broker_items:
            cat = item.get("category", "other")
            if cat in labels:
                item["label"] = labels[cat]
            if "description" in item:
                item["description"] = translate_description(item["description"], lang)
    return localized
