"""
Comprehensive validation script for Euronext Brussels broker fees.
Verifies each tier calculation against stated methodology.
"""

import json
import math
from typing import Dict, List, Tuple


class FeeValidator:
    def __init__(self, data: dict):
        self.data = data
        self.errors = []
        self.warnings = []
        
    def validate_all(self):
        """Validate all broker fees across all instruments and tiers."""
        print("=" * 80)
        print("EURONEXT BRUSSELS FEE VALIDATION REPORT")
        print("=" * 80)
        print()
        
        brokers = ["Bolero", "Keytrade Bank", "Degiro Belgium", "ING Self Invest", 
                   "Rebel", "Revolut", "Trade Republic"]
        instruments = ["stocks", "etfs", "bonds"]
        tiers = [50, 100, 250, 500, 1000, 1500, 2000, 2500, 5000, 10000, 50000]
        
        for broker in brokers:
            print(f"\n{'='*80}")
            print(f"BROKER: {broker}")
            print(f"{'='*80}")
            
            for instrument in instruments:
                # Check if broker has this instrument
                if instrument not in self.data["euronext_brussels"]:
                    continue
                if broker not in self.data["euronext_brussels"][instrument]:
                    continue
                    
                print(f"\n{instrument.upper()}:")
                print("-" * 80)
                
                for tier in tiers:
                    tier_key = str(tier)
                    if tier_key in self.data["euronext_brussels"][instrument][broker]:
                        self.validate_fee(broker, instrument, tier)
        
        # Print summary
        print("\n" + "="*80)
        print("VALIDATION SUMMARY")
        print("="*80)
        print(f"Total Errors Found: {len(self.errors)}")
        print(f"Total Warnings: {len(self.warnings)}")
        
        if self.errors:
            print("\nERRORS:")
            for error in self.errors:
                print(f"  [X] {error}")
        
        if self.warnings:
            print("\nWARNINGS:")
            for warning in self.warnings:
                print(f"  [!] {warning}")
        
        if not self.errors and not self.warnings:
            print("\n[SUCCESS] All fees validated successfully!")
        
        return len(self.errors) == 0
    
    def validate_fee(self, broker: str, instrument: str, amount: int):
        """Validate a single fee calculation."""
        tier_key = str(amount)
        
        # Get stated fee
        stated_fee = self.data["euronext_brussels"][instrument][broker].get(tier_key)
        if stated_fee is None:
            return
        
        # Calculate expected fee
        expected_fee = self.calculate_fee(broker, instrument, amount)
        
        # Compare
        if expected_fee is None:
            self.warnings.append(f"{broker} - {instrument} - EUR{amount}: Cannot calculate (methodology unclear)")
            print(f"  EUR{amount:>6}: Stated={stated_fee:>8.2f} | Expected=UNKNOWN | [WARNING] CANNOT VERIFY")
            return
        
        tolerance = 0.01  # 1 cent tolerance for rounding
        if abs(stated_fee - expected_fee) > tolerance:
            error_msg = f"{broker} - {instrument} - EUR{amount}: Stated={stated_fee:.2f}, Expected={expected_fee:.2f}, Diff={stated_fee-expected_fee:.2f}"
            self.errors.append(error_msg)
            print(f"  EUR{amount:>6}: Stated={stated_fee:>8.2f} | Expected={expected_fee:>8.2f} | [ERROR] MISMATCH (diff: {stated_fee-expected_fee:+.2f})")
        else:
            print(f"  EUR{amount:>6}: Stated={stated_fee:>8.2f} | Expected={expected_fee:>8.2f} | [OK]")
    
    def calculate_fee(self, broker: str, instrument: str, amount: int) -> float:
        """Calculate expected fee based on broker methodology."""
        
        if broker == "Bolero":
            return self._calc_bolero(instrument, amount)
        elif broker == "Keytrade Bank":
            return self._calc_keytrade(instrument, amount)
        elif broker == "Degiro Belgium":
            return self._calc_degiro(instrument, amount)
        elif broker == "ING Self Invest":
            return self._calc_ing(instrument, amount)
        elif broker == "Rebel":
            return self._calc_rebel(instrument, amount)
        elif broker == "Revolut":
            return self._calc_revolut(instrument, amount)
        elif broker == "Trade Republic":
            return self._calc_trade_republic(instrument, amount)
        
        return None
    
    def _calc_bolero(self, instrument: str, amount: int) -> float:
        """
        Bolero fee structure:
        Stocks/ETFs: €2.50 (≤€250), €5.00 (≤€1,000), €7.50 (≤€2,500), 
                     then €15.00 per started €10,000 slice (max €50.00)
        Bonds: €25.00 per started €10,000 slice
        """
        if instrument in ["stocks", "etfs"]:
            if amount <= 250:
                return 2.50
            elif amount <= 1000:
                return 5.00
            elif amount <= 2500:
                return 7.50
            else:
                # Calculate slices for amount > 2500
                remaining = amount - 2500
                slices = math.ceil(remaining / 10000)
                fee = slices * 15.00
                return min(fee, 50.00)  # Cap at €50
        
        elif instrument == "bonds":
            slices = math.ceil(amount / 10000)
            return slices * 25.00
        
        return None
    
    def _calc_keytrade(self, instrument: str, amount: int) -> float:
        """
        Keytrade Bank fee structure:
        Stocks: €17.45 (≤€250), €20.95 (≤€2,500), €29.95 (≤€10,000), 
                then 0.09% × order amount for amounts above €10,000
        ETFs: €2.45 (≤€250), €5.95 (≤€2,500), €14.95 (≤€10,000), 
              then €7.50 per started €10,000 slice
        Bonds: 0.20% × order amount (min €29.95)
        """
        if instrument == "stocks":
            if amount <= 250:
                return 17.45
            elif amount <= 2500:
                return 20.95
            elif amount <= 10000:
                return 29.95
            else:
                # Percentage pricing for high amounts
                return round(amount * 0.0009, 2)
        
        elif instrument == "etfs":
            if amount <= 250:
                return 2.45
            elif amount <= 2500:
                return 5.95
            elif amount <= 10000:
                return 14.95
            else:
                # Calculate slices for amount > 10000
                remaining = amount - 10000
                slices = math.ceil(remaining / 10000)
                return slices * 7.50
        
        elif instrument == "bonds":
            fee = amount * 0.002  # 0.20%
            return max(fee, 29.95)
        
        return None
    
    def _calc_degiro(self, instrument: str, amount: int) -> float:
        """
        Degiro Belgium fee structure:
        All instruments: Flat fee €2.00 + €1.00 handling = €3.00
        """
        return 3.00
    
    def _calc_ing(self, instrument: str, amount: int) -> float:
        """
        ING Self Invest fee structure:
        Stocks/ETFs: 1.00% × order amount (min €40.00)
        Bonds: 0.50% × order amount (min €50.00)
        """
        if instrument in ["stocks", "etfs"]:
            fee = amount * 0.01  # 1.00%
            return max(fee, 40.00)
        
        elif instrument == "bonds":
            fee = amount * 0.005  # 0.50%
            return max(fee, 50.00)
        
        return None
    
    def _calc_rebel(self, instrument: str, amount: int) -> float:
        """
        Rebel fee structure:
        Stocks: €3.00 (≤€2,500), then €10.00 per started €10,000 slice
        ETFs: €1.00 (≤€250), €2.00 (≤€1,000), €3.00 (≤€2,500), 
              then €10.00 per started €10,000 slice
        """
        if instrument == "stocks":
            if amount <= 2500:
                return 3.00
            else:
                remaining = amount - 2500
                slices = math.ceil(remaining / 10000)
                return slices * 10.00
        
        elif instrument == "etfs":
            if amount <= 250:
                return 1.00
            elif amount <= 1000:
                return 2.00
            elif amount <= 2500:
                return 3.00
            else:
                remaining = amount - 2500
                slices = math.ceil(remaining / 10000)
                return slices * 10.00
        
        return None
    
    def _calc_revolut(self, instrument: str, amount: int) -> float:
        """
        Revolut fee structure:
        Stocks/ETFs: 0.12% × order amount (min €1.00)
        """
        if instrument in ["stocks", "etfs"]:
            fee = amount * 0.0012  # 0.12%
            return max(fee, 1.00)
        
        return None
    
    def _calc_trade_republic(self, instrument: str, amount: int) -> float:
        """
        Trade Republic fee structure:
        All instruments: Flat fee €1.00
        """
        return 1.00


def main():
    # Load the data from the actual JSON file
    import os
    json_file_path = os.path.join(os.path.dirname(__file__), "data", "output", "cost_comparison_tables.json")
    
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find file: {json_file_path}")
        return 1
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in file: {e}")
        return 1
    
    # Create validator and run
    validator = FeeValidator(json_data)
    success = validator.validate_all()
    
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
