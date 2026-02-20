"""Run /chat evaluation against a Langfuse dataset and attach scores.

Calls the /chat API for each dataset item, then scores the response against
the deterministic ground truth stored in the dataset.

Scoring functions:
  Single-broker (chat-fee-accuracy):
    - fee_mentioned:   answer text contains the exact fee string
    - fee_accurate:    pre_computed fee within +/-EUR0.01 of expected
    - pre_computed_used: pre_computed dict was present in response

  Comparison (chat-broker-comparison):
    - cheapest_correct: answer identifies the cheapest broker
    - all_fees_accurate: fraction of correctly pre-computed fees

Usage:
    python scripts/eval/run_chat_eval.py
    python scripts/eval/run_chat_eval.py --dataset chat-fee-accuracy --limit 5
    python scripts/eval/run_chat_eval.py --model groq/llama-3.3-70b-versatile --run-name groq-llama
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

import requests
from langfuse import Langfuse
from langfuse.decorators import observe, langfuse_context

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from scripts.eval.config import (
    DATASET_FEE_ACCURACY, DATASET_BROKER_COMPARISON,
    API_BASE_URL, TOLERANCE,
)


@observe(name="chat-eval-call")
def call_chat_api(question: str, model: str | None = None) -> dict:
    """Call the /chat endpoint and return the JSON response."""
    payload = {"question": question}
    if model:
        payload["model"] = model

    resp = requests.post(f"{API_BASE_URL}/chat", json=payload, timeout=120)
    resp.raise_for_status()
    result = resp.json()

    langfuse_context.update_current_observation(
        input=payload,
        output=result,
    )
    return result


def score_fee_accuracy(response: dict, expected: dict, langfuse: Langfuse, trace_id: str) -> dict:
    """Score a single-broker fee response. Returns dict of score names -> values."""
    scores = {}
    answer = response.get("answer", "")
    pre_computed = response.get("pre_computed")
    expected_fee = expected["fee"]
    broker = expected["broker"]
    instrument = expected["instrument"]

    # fee_mentioned: does the answer contain the fee amount?
    fee_str = f"{expected_fee:.2f}"
    scores["fee_mentioned"] = 1.0 if fee_str in answer else 0.0

    # pre_computed_used: was pre_computed data present?
    scores["pre_computed_used"] = 1.0 if pre_computed else 0.0

    # fee_accurate: is the pre_computed fee within tolerance?
    if pre_computed:
        # pre_computed can be a dict with broker keys or a flat dict
        actual_fee = _extract_fee_from_precomputed(pre_computed, broker, instrument)
        if actual_fee is not None:
            scores["fee_accurate"] = 1.0 if abs(actual_fee - expected_fee) <= TOLERANCE else 0.0
        else:
            scores["fee_accurate"] = 0.0
    else:
        scores["fee_accurate"] = 0.0

    # Submit scores to Langfuse
    for name, value in scores.items():
        langfuse.score(trace_id=trace_id, name=name, value=value)

    return scores


def score_comparison(response: dict, expected: dict, langfuse: Langfuse, trace_id: str) -> dict:
    """Score a multi-broker comparison response. Returns dict of score names -> values."""
    scores = {}
    answer = response.get("answer", "")
    pre_computed = response.get("pre_computed")
    expected_cheapest = expected["cheapest"]
    expected_fees = expected["fees"]

    # cheapest_correct: does the answer mention the cheapest broker?
    scores["cheapest_correct"] = 1.0 if expected_cheapest.lower() in answer.lower() else 0.0

    # all_fees_accurate: fraction of broker fees that match
    if pre_computed:
        correct = 0
        total = len(expected_fees)
        for broker, expected_fee in expected_fees.items():
            actual_fee = _extract_fee_from_precomputed(pre_computed, broker, expected["instrument"])
            if actual_fee is not None and abs(actual_fee - expected_fee) <= TOLERANCE:
                correct += 1
        scores["all_fees_accurate"] = correct / total if total > 0 else 0.0
    else:
        scores["all_fees_accurate"] = 0.0

    for name, value in scores.items():
        langfuse.score(trace_id=trace_id, name=name, value=value)

    return scores


def _extract_fee_from_precomputed(pre_computed: dict, broker: str, instrument: str) -> float | None:
    """Extract a fee value from the pre_computed response dict.

    Handles both formats:
      - {broker: {instrument: {"fee": X, ...}}}
      - {broker: {"fee": X, ...}}
    """
    if not pre_computed:
        return None

    # Try exact broker match first, then case-insensitive
    for key in pre_computed:
        if key.lower() == broker.lower():
            entry = pre_computed[key]
            if isinstance(entry, dict):
                # Nested by instrument
                if instrument in entry and isinstance(entry[instrument], dict):
                    return entry[instrument].get("fee")
                # Flat structure
                if "fee" in entry:
                    return entry["fee"]
            if isinstance(entry, (int, float)):
                return float(entry)
    return None


def run_eval(dataset_name: str, model: str | None, run_name: str, limit: int | None):
    """Run evaluation for a dataset."""
    langfuse = Langfuse()
    dataset = langfuse.get_dataset(dataset_name)
    items = dataset.items

    if limit:
        items = items[:limit]

    is_comparison = dataset_name == DATASET_BROKER_COMPARISON
    all_scores: list[dict] = []

    print(f"\nRunning eval: {dataset_name} ({len(items)} items)")
    print(f"  model: {model or 'default'}")
    print(f"  run:   {run_name}")
    print("-" * 60)

    for i, item in enumerate(items):
        question = item.input["question"]
        expected = item.expected_output

        print(f"  [{i+1}/{len(items)}] {question[:70]}...", end=" ", flush=True)

        try:
            response = call_chat_api(question, model=model)
            trace_id = langfuse_context.get_current_trace_id()

            if is_comparison:
                scores = score_comparison(response, expected, langfuse, trace_id)
            else:
                scores = score_fee_accuracy(response, expected, langfuse, trace_id)

            # Link trace to dataset item + run
            item.link(
                trace_or_observation=langfuse_context.get_current_trace_id(),
                run_name=run_name,
            )

            all_scores.append(scores)
            status = "OK" if all(v >= 0.5 for v in scores.values()) else "WARN"
            print(status)

        except Exception as e:
            print(f"ERROR: {e}")
            all_scores.append({})

    langfuse.flush()
    _print_summary(all_scores, is_comparison)


def _print_summary(all_scores: list[dict], is_comparison: bool):
    """Print a summary table of scores."""
    if not all_scores:
        print("\nNo results.")
        return

    # Collect all score names
    score_names = set()
    for s in all_scores:
        score_names.update(s.keys())
    score_names = sorted(score_names)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    for name in score_names:
        values = [s[name] for s in all_scores if name in s]
        if not values:
            continue
        avg = sum(values) / len(values)
        perfect = sum(1 for v in values if v >= 1.0)
        print(f"  {name:25s}  avg={avg:.2%}  perfect={perfect}/{len(values)}")

    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Run /chat evaluation against Langfuse datasets")
    parser.add_argument(
        "--dataset",
        choices=[DATASET_FEE_ACCURACY, DATASET_BROKER_COMPARISON, "all"],
        default="all",
        help="Which dataset to evaluate (default: all)",
    )
    parser.add_argument("--model", default=None, help="Model to pass to /chat (default: server default)")
    parser.add_argument("--run-name", default=None, help="Langfuse run name (default: auto-generated)")
    parser.add_argument("--limit", type=int, default=None, help="Max items to evaluate per dataset")

    args = parser.parse_args()

    run_name = args.run_name or f"eval-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    datasets = []
    if args.dataset in ("all", DATASET_FEE_ACCURACY):
        datasets.append(DATASET_FEE_ACCURACY)
    if args.dataset in ("all", DATASET_BROKER_COMPARISON):
        datasets.append(DATASET_BROKER_COMPARISON)

    for ds in datasets:
        run_eval(ds, model=args.model, run_name=run_name, limit=args.limit)


if __name__ == "__main__":
    main()
