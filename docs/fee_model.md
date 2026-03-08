# Enriched Fee Data Model

## Overview

The fee model defines how broker trading fees are structured, stored, and computed.
Each `FeeRule` represents a single fee schedule for a `(broker, instrument, exchange)` combination.

## FeeRule Schema

| Field | Type | Default | Description |
|---|---|---|---|
| `broker` | `str` | *required* | Canonical broker name (e.g., "Bolero") |
| `instrument` | `str` | *required* | Asset type: `"stocks"`, `"etfs"`, `"bonds"` |
| `pattern` | `str` | `"unknown"` | Fee pattern type (see below) |
| `tiers` | `List[dict]` | `[]` | Tier definitions (see below) |
| `handling_fee` | `float` | `0.0` | Per-trade handling fee in EUR |
| `min_fee` | `float \| None` | `None` | Rule-level minimum fee |
| `max_fee` | `float \| None` | `None` | Rule-level maximum fee cap |
| `exchange` | `str` | `"all"` | Exchange scope (see Exchange Naming) |
| `conditions` | `List[dict]` | `[]` | Applicability conditions (see Conditions) |
| `notes` | `str` | `""` | Free-text edge cases or caveats |
| `source` | `dict` | `{}` | Provenance metadata (see Source) |

## Pattern Types

| Pattern | Description | Example |
|---|---|---|
| `flat` | Simple flat fee for all amounts | Degiro EUR2 + EUR1 handling |
| `tiered_flat` | Flat fees by tier (`up_to` thresholds only) | — |
| `tiered_flat_then_slice` | Flat tiers for low amounts, per-slice above | Bolero, Keytrade, Rebel |
| `percentage_with_min` | Percentage rate with minimum fee | ING, Revolut |
| `base_plus_slice` | Base fee up to threshold + per-slice remainder | — |

## Tier Types

```json
{"flat": 2.00}                                          // simple flat fee
{"up_to": 2500, "fee": 7.50}                            // flat fee for amounts ≤ threshold
{"per_slice": 10000, "fee": 15.00}                       // per-started-slice (after all flat tiers)
{"per_slice": 10000, "fee": 15.00, "max_fee": 50.00}    // per-slice with fee cap
{"base_up_to": 10000, "base_fee": 14.95, "per_slice": 10000, "slice_fee": 7.50}  // base + slice
{"rate": 0.0035, "min_fee": 1.00}                        // percentage rate with minimum
```

## Exchange Naming Conventions

| Value | Meaning |
|---|---|
| `"all"` | Applies to all exchanges (default / catch-all) |
| `"euronext_brussels"` | Euronext Brussels |
| `"euronext_amsterdam"` | Euronext Amsterdam |
| `"euronext_paris"` | Euronext Paris |
| `"nyse"` | New York Stock Exchange |
| `"nasdaq"` | NASDAQ |
| `"xetra"` | Deutsche Börse Xetra |
| `"lse"` | London Stock Exchange |

Convention: lowercase, underscores, no spaces.

## Registry Key

The global `FEE_RULES` registry is keyed by a 3-tuple:

```python
(broker.lower(), instrument.lower(), exchange.lower())
```

### Lookup Precedence

`calculate_fee(broker, instrument, amount, exchange="all")`:

1. **Exact match**: `(broker, instrument, exchange)`
2. **Fallback**: `(broker, instrument, "all")`

This ensures backward compatibility — existing rules with `exchange="all"` are always found.

## Conditions

The `conditions` field is a list of typed condition objects. Each condition
narrows when a rule applies. An empty list means the rule is the default/standard rate.

### Condition Type Catalog

| `type` | Fields | Example |
|---|---|---|
| `age` | `min_age`, `max_age` | `{"type": "age", "min_age": 18, "max_age": 24}` — Rebel youth rate |
| `plan` | `plan_name`, `plan_tier` | `{"type": "plan", "plan_name": "Plus", "plan_tier": "paid"}` — Revolut plan |
| `order_type` | `order_type` | `{"type": "order_type", "order_type": "phone"}` — phone order surcharge |
| `promotion` | `promo_name`, `valid_until` | `{"type": "promotion", "promo_name": "Welcome bonus", "valid_until": "2026-06-30"}` |
| `private_member` | `membership` | `{"type": "private_member", "membership": "keytradeplus"}` |

### Important

- Rules **without** conditions represent the **standard/default** fee.
- Rules **with** conditions represent exceptions or special pricing.
- The calculator currently uses the standard rule (no conditions).
  Condition-aware lookup is a future extension.

## Source (Provenance)

```json
{
  "pdf": "bolero_fee_schedule_2026.pdf",
  "page": 3,
  "extracted_at": "2026-03-01T10:30:00",
  "model": "claude-sonnet-4-20250514"
}
```

Only written when non-empty. Optional for manually defined rules.

## Numeric Convention Reminder

**Two different conventions in the same JSON file:**

1. `rate` in tier objects → **decimal fraction**: `0.0035` = 0.35%
   - Calculator: `fee = amount * rate`
2. `_pct` in hidden_costs → **percentage notation**: `0.25` = 0.25%, `1.0` = 1%

## Backward Compatibility

- `calculate_fee(broker, instrument, amount)` works unchanged (`exchange` defaults to `"all"`)
- Existing `fee_rules.json` without new fields loads cleanly (all defaults are safe)
- All existing API endpoints have no signature changes
- `_compute_from_tiers()` and `HiddenCosts` are not modified

## Examples

### Rebel Youth Discount

```json
{
  "broker": "Rebel",
  "instrument": "stocks",
  "exchange": "euronext_brussels",
  "conditions": [{"type": "age", "min_age": 18, "max_age": 24}],
  "notes": "Reduced rate for young investors (18-24)",
  "pattern": "flat",
  "tiers": [{"flat": 1.00}]
}
```

### Revolut Plan Tier

```json
{
  "broker": "Revolut",
  "instrument": "stocks",
  "exchange": "all",
  "conditions": [{"type": "plan", "plan_name": "Plus", "plan_tier": "paid"}],
  "notes": "Plus plan: 3 free trades/month, then 0.25% (min EUR1)",
  "pattern": "percentage_with_min",
  "tiers": [{"rate": 0.0025, "min_fee": 1.00}]
}
```

### Exchange-Specific Rule

```json
{
  "broker": "Bolero",
  "instrument": "stocks",
  "exchange": "nyse",
  "pattern": "tiered_flat_then_slice",
  "tiers": [
    {"up_to": 2500, "fee": 15.00},
    {"per_slice": 10000, "fee": 20.00, "max_fee": 75.00}
  ],
  "source": {"pdf": "bolero_tariffs_2026.pdf", "page": 5}
}
```
