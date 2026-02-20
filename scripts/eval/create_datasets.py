"""Create Langfuse datasets with ground-truth fee data for /chat evaluation.

Datasets:
  - chat-fee-accuracy:       single-broker fee questions (~120 items)
  - chat-broker-comparison:  multi-broker comparison questions (12 items)

Safe to re-run — uses idempotent item IDs.

Usage:
    python scripts/eval/create_datasets.py
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path so we can import be_invest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from langfuse import Langfuse

from be_invest.validation.fee_calculator import calculate_fee, generate_explanation
from scripts.eval.config import (
    BROKERS, INSTRUMENTS, AMOUNTS,
    DATASET_FEE_ACCURACY, DATASET_BROKER_COMPARISON,
)


def create_fee_accuracy_dataset(langfuse: Langfuse) -> int:
    """Create single-broker fee-accuracy dataset items.

    Returns number of items created.
    """
    dataset = langfuse.create_dataset(
        name=DATASET_FEE_ACCURACY,
        description="Single-broker fee questions with deterministic ground truth",
    )

    count = 0
    for broker in BROKERS:
        for instrument in INSTRUMENTS:
            for amount in AMOUNTS:
                fee = calculate_fee(broker, instrument, amount)
                if fee is None:
                    continue

                explanation = generate_explanation(broker, instrument, amount)
                item_id = f"{broker}-{instrument}-{amount}".lower().replace(" ", "-")
                question = f"How much does {broker} charge for a EUR{amount} {instrument.rstrip('s')} trade?"

                langfuse.create_dataset_item(
                    dataset_name=DATASET_FEE_ACCURACY,
                    id=item_id,
                    input={"question": question},
                    expected_output={
                        "broker": broker,
                        "instrument": instrument,
                        "amount": amount,
                        "fee": fee,
                        "explanation": explanation,
                    },
                )
                count += 1

    print(f"  {DATASET_FEE_ACCURACY}: {count} items")
    return count


def create_comparison_dataset(langfuse: Langfuse) -> int:
    """Create multi-broker comparison dataset items.

    Returns number of items created.
    """
    dataset = langfuse.create_dataset(
        name=DATASET_BROKER_COMPARISON,
        description="Multi-broker comparison questions with deterministic ground truth",
    )

    count = 0
    for instrument in INSTRUMENTS:
        for amount in AMOUNTS:
            fees = {}
            for broker in BROKERS:
                fee = calculate_fee(broker, instrument, amount)
                if fee is not None:
                    fees[broker] = fee

            if not fees:
                continue

            cheapest = min(fees, key=fees.get)
            item_id = f"compare-{instrument}-{amount}"
            question = f"Compare all brokers for a EUR{amount} {instrument.rstrip('s')} purchase. Which is cheapest?"

            langfuse.create_dataset_item(
                dataset_name=DATASET_BROKER_COMPARISON,
                id=item_id,
                input={"question": question},
                expected_output={
                    "instrument": instrument,
                    "amount": amount,
                    "fees": fees,
                    "cheapest": cheapest,
                },
            )
            count += 1

    print(f"  {DATASET_BROKER_COMPARISON}: {count} items")
    return count


def main():
    print("Creating Langfuse evaluation datasets...")
    langfuse = Langfuse()

    total = 0
    total += create_fee_accuracy_dataset(langfuse)
    total += create_comparison_dataset(langfuse)

    langfuse.flush()
    print(f"Done. {total} total items created/updated.")


if __name__ == "__main__":
    main()
