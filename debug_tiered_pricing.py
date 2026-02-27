"""Debug script to compare two interpretations of tiered_flat_then_slice pattern."""

import math

# Bolero ETF/Stock pricing tiers
BOLEROtiers = [
    {"up_to": 250, "fee": 2.5},
    {"up_to": 1000, "fee": 5.0},
    {"up_to": 2500, "fee": 7.5},
    {"per_slice": 10000, "fee": 15.0, "max_fee": 50.0}
]

# Rebel stock pricing tiers
REBELtiers = [
    {"up_to": 2500, "fee": 3.0},
    {"per_slice": 10000, "fee": 10.0}
]

def calculate_current_implementation(tiers, amount):
    """Current implementation: highest flat tier fee as base + slices."""
    flat_tiers = [t for t in tiers if "up_to" in t]
    slice_tiers = [t for t in tiers if "per_slice" in t and "up_to" not in t]
    
    # Find the applicable flat tier
    for tier in flat_tiers:
        if amount <= tier["up_to"]:
            return tier["fee"]
    
    # Amount exceeds all flat tiers -> use highest flat tier as base
    if slice_tiers:
        slice_tier = slice_tiers[0]
        highest_flat_threshold = max(t["up_to"] for t in flat_tiers) if flat_tiers else 0
        highest_flat_fee = max((t for t in flat_tiers), key=lambda t: t["up_to"])["fee"] if flat_tiers else 0.0
        
        remainder = amount - highest_flat_threshold
        slices = math.ceil(remainder / slice_tier["per_slice"])
        fee = highest_flat_fee + (slices * slice_tier["fee"])
        
        # Apply max_fee cap
        tier_max = slice_tier.get("max_fee")
        if tier_max is not None:
            fee = min(fee, tier_max)
        
        return fee
    
    return 0.0


def calculate_alternative_interpretation(tiers, amount):
    """Alternative: when in slice tier, ONLY use slice calculation (no base)."""
    flat_tiers = [t for t in tiers if "up_to" in t]
    slice_tiers = [t for t in tiers if "per_slice" in t and "up_to" not in t]
    
    # Find the applicable flat tier
    for tier in flat_tiers:
        if amount <= tier["up_to"]:
            return tier["fee"]
    
    # Amount exceeds all flat tiers -> use ONLY slice calculation
    if slice_tiers:
        slice_tier = slice_tiers[0]
        highest_flat_threshold = max(t["up_to"] for t in flat_tiers) if flat_tiers else 0
        
        # Calculate slices for the remainder (OR from 0 if no flat tiers)
        remainder = amount - highest_flat_threshold
        slices = math.ceil(remainder / slice_tier["per_slice"])
        fee = slices * slice_tier["fee"]  # NO BASE FEE
        
        # Apply max_fee cap
        tier_max = slice_tier.get("max_fee")
        if tier_max is not None:
            fee = min(fee, tier_max)
        
        return fee
    
    return 0.0


print("=" * 80)
print("BOLERO ETFs/Stocks Comparison")
print("=" * 80)
print(f"{'Amount':<10} {'Current':<12} {'Alternative':<12} {'Difference':<12}")
print("-" * 80)

amounts = [250, 500, 1000, 1500, 2000, 2500, 5000, 10000, 50000]

for amount in amounts:
    current = calculate_current_implementation(BOLEROtiers, amount)
    alternative = calculate_alternative_interpretation(BOLEROtiers, amount)
    diff = current - alternative
    print(f"EUR {amount:<7} EUR {current:<9.2f} EUR {alternative:<9.2f} EUR {diff:<9.2f}")

print("\n" + "=" * 80)
print("REBEL Stocks Comparison")
print("=" * 80)
print(f"{'Amount':<10} {'Current':<12} {'Alternative':<12} {'Difference':<12}")
print("-" * 80)

for amount in amounts:
    current = calculate_current_implementation(REBELtiers, amount)
    alternative = calculate_alternative_interpretation(REBELtiers, amount)
    diff = current - alternative
    print(f"EUR {amount:<7} EUR {current:<9.2f} EUR {alternative:<9.2f} EUR {diff:<9.2f}")

print("\n" + "=" * 80)
print("Analysis:")
print("=" * 80)
print("Current implementation adds the highest flat tier fee as a 'base' when amounts")
print("exceed all flat tiers. The alternative interpretation treats the slice tier as")
print("a completely separate pricing category with NO carry-forward from flat tiers.")
print("\nTo determine which is correct, we need to check Bolero's actual pricing docs.")
