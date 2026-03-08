# Euronext Brussels Fee Validation Report

## Executive Summary

Validated **209 fee calculations** across 7 brokers, 3 instrument types, and 11 transaction tiers.

**Result:** Found **1 calculation error**

---

## Error Details

### ❌ Keytrade Bank - Stocks - EUR 50,000 Tier

**Issue:** Incorrect fee calculation

| Aspect | Value |
|--------|-------|
| **Stated Fee** | €45.00 |
| **Expected Fee** | €30.00 |
| **Difference** | +€15.00 (50% overcharge) |
| **Error Type** | Arithmetic/Logic Error |

#### Root Cause Analysis

According to the stated methodology for Keytrade Bank stocks:
> "€17.45 (≤€250), €20.95 (≤€2,500), €29.95 (≤€10,000), then €7.50 per started €10,000 slice"

**Correct Calculation for EUR 50,000:**
1. Amount is > €10,000, so flat tiers don't apply
2. Calculate excess over €10,000: €50,000 - €10,000 = €40,000
3. Number of €10,000 slices: 40,000 ÷ 10,000 = 4 slices
4. Fee per slice: €7.50
5. **Total fee: 4 × €7.50 = €30.00**

**Current Incorrect Value:** €45.00

#### Additional Evidence - calculation_logic Inconsistency

The `calculation_logic` field in your JSON also contains an internal arithmetic error:

```json
"stocks": {
  "50000": "4 x EUR7.50 (EUR40000 / EUR10,000 slices) = EUR45.00"
}
```

**This is mathematically incorrect:** 4 × €7.50 = €30.00, not €45.00

#### Comparison with ETFs

For the same EUR 50,000 tier, **Keytrade Bank ETFs are correctly calculated**:

```json
"etfs": {
  "50000": "4 x EUR7.50 (EUR40000 / EUR10,000 slices) = EUR30.00"
}
```

This confirms the stocks calculation is an isolated error.

---

## All Validated Items Summary

### ✅ Correct Calculations: 208/209 (99.5%)

**Brokers with 100% accuracy:**
- ✅ Bolero: 33/33 correct (stocks, ETFs, bonds)
- ✅ Degiro Belgium: 33/33 correct (stocks, ETFs, bonds)
- ✅ ING Self Invest: 33/33 correct (stocks, ETFs, bonds)
- ✅ Rebel: 22/22 correct (stocks, ETFs)
- ✅ Revolut: 22/22 correct (stocks, ETFs)
- ✅ Trade Republic: 33/33 correct (stocks, ETFs, bonds)
- ⚠️  Keytrade Bank: 32/33 correct (1 error in stocks)

---

## Detailed Validation by Broker

### Bolero ✅
All 33 tiers validated successfully across:
- **Stocks:** Tiered pricing (€2.50 → €50.00 cap) - 11/11 ✅
- **ETFs:** Tiered pricing (€2.50 → €50.00 cap) - 11/11 ✅
- **Bonds:** Per-slice pricing (€25.00/slice) - 11/11 ✅

**Methodology verified:** 
- €2.50 (≤€250), €5.00 (≤€1,000), €7.50 (≤€2,500), then €15.00 per started €10,000 slice (max €50.00)

---

### Keytrade Bank ⚠️
32/33 tiers validated successfully:
- **Stocks:** 10/11 ✅, **1 error at EUR 50,000** ❌
- **ETFs:** 11/11 ✅
- **Bonds:** 11/11 ✅

**Stocks Methodology (stated):**
- €17.45 (≤€250), €20.95 (≤€2,500), €29.95 (≤€10,000), then €7.50 per started €10,000 slice

**Stocks Tiers (validated):**
| Amount | Stated | Expected | Status |
|--------|--------|----------|--------|
| €50 | €17.45 | €17.45 | ✅ |
| €100 | €17.45 | €17.45 | ✅ |
| €250 | €17.45 | €17.45 | ✅ |
| €500 | €20.95 | €20.95 | ✅ |
| €1,000 | €20.95 | €20.95 | ✅ |
| €1,500 | €20.95 | €20.95 | ✅ |
| €2,000 | €20.95 | €20.95 | ✅ |
| €2,500 | €20.95 | €20.95 | ✅ |
| €5,000 | €29.95 | €29.95 | ✅ |
| €10,000 | €29.95 | €29.95 | ✅ |
| **€50,000** | **€45.00** | **€30.00** | **❌ -€15.00** |

---

### Degiro Belgium ✅
All 33 tiers validated successfully:
- **Stocks:** Flat €3.00 - 11/11 ✅
- **ETFs:** Flat €3.00 - 11/11 ✅
- **Bonds:** Flat €3.00 - 11/11 ✅

**Methodology verified:** Flat fee €2.00 + €1.00 handling = €3.00

---

### ING Self Invest ✅
All 33 tiers validated successfully:
- **Stocks:** 1.00% (min €40) - 11/11 ✅
- **ETFs:** 1.00% (min €40) - 11/11 ✅
- **Bonds:** 0.50% (min €50) - 11/11 ✅

**Methodology verified:** 
- Stocks/ETFs: 1.00% × order amount (min €40.00)
- Bonds: 0.50% × order amount (min €50.00)

---

### Rebel ✅
All 22 tiers validated successfully:
- **Stocks:** Tiered (€3.00 → €10.00/slice) - 11/11 ✅
- **ETFs:** Tiered (€1.00 → €10.00/slice) - 11/11 ✅

**Methodology verified:**
- Stocks: €3.00 (≤€2,500), then €10.00 per started €10,000 slice
- ETFs: €1.00 (≤€250), €2.00 (≤€1,000), €3.00 (≤€2,500), then €10.00 per started €10,000 slice

---

### Revolut ✅
All 22 tiers validated successfully:
- **Stocks:** 0.12% (min €1.00) - 11/11 ✅
- **ETFs:** 0.12% (min €1.00) - 11/11 ✅

**Methodology verified:** 0.12% × order amount (min €1.00)

---

### Trade Republic ✅
All 33 tiers validated successfully:
- **Stocks:** Flat €1.00 - 11/11 ✅
- **ETFs:** Flat €1.00 - 11/11 ✅
- **Bonds:** Flat €1.00 - 11/11 ✅

**Methodology verified:** Flat fee €1.00 for all instruments

---

## Recommendations

### Immediate Action Required

1. **Fix Keytrade Bank stocks EUR 50,000 tier:** Change from €45.00 to €30.00

2. **Update calculation_logic:** Correct the arithmetic in the explanation:
   ```
   Current: "4 x EUR7.50 (EUR40000 / EUR10,000 slices) = EUR45.00"
   Corrected: "4 x EUR7.50 (EUR40000 / EUR10,000 slices) = EUR30.00"
   ```

3. **Review data source:** Verify if this error came from:
   - Manual calculation mistake
   - LLM extraction error
   - Typo in source document
   - Incorrect interpretation of broker's pricing

### Impact Assessment

**Who is affected:**
- Active traders using Keytrade Bank for large stock transactions (>€10,000)
- Specifically impacts the EUR 50,000 tier in broker comparisons

**Financial impact:**
- €15.00 overcharge per transaction at the €50,000 level
- This makes Keytrade Bank appear 50% more expensive than it actually is
- Affects broker ranking in "active_trader" persona calculations

**Data quality:**
- Overall data quality is excellent (99.5% accuracy)
- Isolated error that doesn't affect methodology understanding

---

## Validation Methodology

The validation script:
1. Parsed all 209 fee calculations
2. Implemented fee calculation logic for each broker based on stated methodology
3. Compared calculated fees with stated fees (tolerance: €0.01)
4. Identified discrepancies

**Testing coverage:**
- 7 brokers
- 3 instrument types (stocks, ETFs, bonds)
- 11 transaction tiers (€50 to €50,000)
- 100% of available data points validated

---

## Conclusion

The fee data is highly accurate with only **1 error out of 209 calculations (99.5% accuracy)**. The error in Keytrade Bank's stocks pricing at the EUR 50,000 tier should be corrected from €45.00 to €30.00 to match the stated methodology and align with the correctly calculated ETF pricing.

All other brokers and tiers have been validated and are mathematically correct according to their stated methodologies.

---

*Report generated: 2026-03-06*  
*Validation script: validate_euronext_fees.py*
