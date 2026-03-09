"""
Provision all Langfuse score configs and the human-review annotation queue.

Safe to run multiple times — existing configs and queues are reused, nothing is
duplicated or overwritten.

Usage:
    python scripts/eval/setup_score_configs.py
    python scripts/eval/setup_score_configs.py --dry-run
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langfuse import Langfuse

# Load .env from project root
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# ── Score config definitions ────────────────────────────────────────────────

# fmt: off
ALL_SCORE_CONFIGS: list[dict[str, Any]] = [

    # ── Automated: LLM-as-Judge ──────────────────────────────────────────────
    {
        "name": "groundedness",
        "data_type": "NUMERIC",
        "min_value": 0.0,
        "max_value": 1.0,
        "description": (
            "Gemini judge: are all facts in the AI response grounded in the retrieved "
            "broker-fee context? 0 = hallucination detected, 1 = fully grounded."
        ),
    },

    # ── Automated: API-level signals ─────────────────────────────────────────
    {
        "name": "required_fallback",
        "data_type": "NUMERIC",
        "min_value": 0.0,
        "max_value": 1.0,
        "description": (
            "Automated: did the request fall back to a secondary LLM model? "
            "0 = primary model used, 1 = fallback was required."
        ),
    },

    # ── Eval dataset: single-broker fee accuracy (chat-fee-accuracy) ─────────
    {
        "name": "fee_mentioned",
        "data_type": "NUMERIC",
        "min_value": 0.0,
        "max_value": 1.0,
        "description": (
            "Eval (chat-fee-accuracy): does the answer text contain the exact expected "
            "fee string? 0 = fee not mentioned, 1 = fee explicitly stated."
        ),
    },
    {
        "name": "pre_computed_used",
        "data_type": "NUMERIC",
        "min_value": 0.0,
        "max_value": 1.0,
        "description": (
            "Eval (chat-fee-accuracy): was deterministic pre-computed fee data present "
            "in the response payload? 0 = missing, 1 = present."
        ),
    },
    {
        "name": "fee_accurate",
        "data_type": "NUMERIC",
        "min_value": 0.0,
        "max_value": 1.0,
        "description": (
            "Eval (chat-fee-accuracy): is the pre-computed fee within ±€0.01 of the "
            "ground-truth expected fee? 0 = outside tolerance, 1 = within tolerance."
        ),
    },

    # ── Eval dataset: broker comparison (chat-broker-comparison) ────────────
    {
        "name": "cheapest_correct",
        "data_type": "NUMERIC",
        "min_value": 0.0,
        "max_value": 1.0,
        "description": (
            "Eval (chat-broker-comparison): did the response correctly identify the "
            "cheapest broker? 0 = wrong broker named, 1 = correct."
        ),
    },
    {
        "name": "all_fees_accurate",
        "data_type": "NUMERIC",
        "min_value": 0.0,
        "max_value": 1.0,
        "description": (
            "Eval (chat-broker-comparison): fraction of broker fees in the comparison "
            "that are within ±€0.01 of ground truth. 0 = all wrong, 1 = all correct."
        ),
    },

    # ── Human review ─────────────────────────────────────────────────────────
    {
        "name": "human_accuracy",
        "data_type": "NUMERIC",
        "min_value": 0.0,
        "max_value": 1.0,
        "description": (
            "Human review: are the fee figures factually correct? "
            "0 = incorrect, 1 = fully correct."
        ),
    },
    {
        "name": "human_clarity",
        "data_type": "NUMERIC",
        "min_value": 1.0,
        "max_value": 5.0,
        "description": (
            "Human review: is the response clear and understandable to a non-technical "
            "user? 1 = very unclear, 5 = very clear."
        ),
    },
    {
        "name": "human_completeness",
        "data_type": "NUMERIC",
        "min_value": 1.0,
        "max_value": 5.0,
        "description": (
            "Human review: does the response cover all relevant brokers and instruments? "
            "1 = very incomplete, 5 = very complete."
        ),
    },
    {
        "name": "human_approval",
        "data_type": "CATEGORICAL",
        "categories": [
            {"label": "Approved", "value": 1},
            {"label": "Rejected", "value": 0},
        ],
        "description": (
            "Human review: overall approval decision. "
            "Approved = response is suitable to show to end users."
        ),
    },
]
# fmt: on

# ── Annotation queue ─────────────────────────────────────────────────────────

ANNOTATION_QUEUE_NAME = "business-analyst-review"
ANNOTATION_QUEUE_DESCRIPTION = (
    "Business analyst review queue. "
    "Score each trace on accuracy, clarity, completeness, and approval."
)
# Only human-review configs are attached to the annotation queue
QUEUE_SCORE_CONFIG_NAMES = {
    "human_accuracy",
    "human_clarity",
    "human_completeness",
    "human_approval",
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _build_langfuse_client() -> Langfuse:
    pub = os.getenv("LANGFUSE_PUBLIC_KEY")
    sec = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    if not pub or not sec:
        print("ERROR: LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY must be set.")
        sys.exit(1)

    return Langfuse(public_key=pub, secret_key=sec, host=host)


def _create_score_config(api: Any, cfg: dict[str, Any]) -> str:
    from langfuse.api.resources.score_configs.types.create_score_config_request import (
        CreateScoreConfigRequest,
    )
    from langfuse.api.resources.commons.types.score_config_data_type import ScoreConfigDataType

    kwargs: dict[str, Any] = {
        "name": cfg["name"],
        "data_type": ScoreConfigDataType(cfg["data_type"]),
        "description": cfg.get("description"),
    }
    if "min_value" in cfg:
        kwargs["min_value"] = cfg["min_value"]
    if "max_value" in cfg:
        kwargs["max_value"] = cfg["max_value"]
    if "categories" in cfg:
        from langfuse.api.resources.commons.types.config_category import ConfigCategory
        kwargs["categories"] = [
            ConfigCategory(label=c["label"], value=c["value"]) for c in cfg["categories"]
        ]

    created = api.score_configs.create(request=CreateScoreConfigRequest(**kwargs))
    return created.id


def _ensure_annotation_queue(
    api: Any, queue_score_config_ids: list[str], dry_run: bool
) -> None:
    existing_resp = api.annotation_queues.list_queues(limit=100)
    existing = next(
        (q for q in (existing_resp.data or []) if q.name == ANNOTATION_QUEUE_NAME),
        None,
    )

    if existing:
        print(f"  ↩  queue '{ANNOTATION_QUEUE_NAME}' already exists (id={existing.id}) — skipped")
        return

    if dry_run:
        print(f"  [dry-run] would create annotation queue '{ANNOTATION_QUEUE_NAME}'")
        return

    from langfuse.api.resources.annotation_queues.types.create_annotation_queue_request import (
        CreateAnnotationQueueRequest,
    )
    created = api.annotation_queues.create_queue(
        request=CreateAnnotationQueueRequest(
            name=ANNOTATION_QUEUE_NAME,
            description=ANNOTATION_QUEUE_DESCRIPTION,
            score_config_ids=queue_score_config_ids,
        )
    )
    print(f"  ✅ created annotation queue '{ANNOTATION_QUEUE_NAME}' (id={created.id})")


# ── Main ─────────────────────────────────────────────────────────────────────

def main(dry_run: bool = False) -> None:
    print("Connecting to Langfuse …")
    lf = _build_langfuse_client()
    api = lf.api

    # Fetch existing score configs once
    existing_resp = api.score_configs.get(limit=100)
    existing: dict[str, str] = {cfg.name: cfg.id for cfg in (existing_resp.data or [])}
    print(f"Found {len(existing)} existing score config(s) on server.\n")

    created_count = 0
    skipped_count = 0
    queue_config_ids: list[str] = []

    print("── Score configs ───────────────────────────────────────────────────")
    for cfg in ALL_SCORE_CONFIGS:
        name = cfg["name"]
        if name in existing:
            cfg_id = existing[name]
            print(f"  ↩  '{name}' already exists (id={cfg_id}) — skipped")
            skipped_count += 1
        else:
            if dry_run:
                print(f"  [dry-run] would create '{name}' ({cfg['data_type']})")
                cfg_id = f"<dry-run-{name}>"
            else:
                cfg_id = _create_score_config(api, cfg)
                print(f"  ✅ created '{name}' (id={cfg_id})")
            created_count += 1

        if name in QUEUE_SCORE_CONFIG_NAMES:
            queue_config_ids.append(cfg_id)

    print()
    print("── Annotation queue ────────────────────────────────────────────────")
    _ensure_annotation_queue(api, queue_config_ids, dry_run)

    print()
    print("── Summary ─────────────────────────────────────────────────────────")
    action = "would create" if dry_run else "created"
    print(f"  Score configs {action}: {created_count}")
    print(f"  Score configs skipped (already existed): {skipped_count}")
    print(f"  Total score configs configured: {len(ALL_SCORE_CONFIGS)}")

    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    print(f"\n  Dashboard → {host}")
    if dry_run:
        print("\n  (dry-run — no changes were made)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be created without making any changes.",
    )
    args = parser.parse_args()
    main(dry_run=args.dry_run)
