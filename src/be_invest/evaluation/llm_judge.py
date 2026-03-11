"""LLM-as-Judge evaluator for Langfuse traces using Gemini."""

import json
import logging
import os
import time
from typing import Optional, Dict, Any, List

from google import genai
from google.genai import types
from langfuse import Langfuse

logger = logging.getLogger(__name__)

# Initialize Gemini client
_gemini_api_key = os.getenv("GOOGLE_API_KEY")
_gemini_client = genai.Client(api_key=_gemini_api_key) if _gemini_api_key else None

if not _gemini_api_key:
    logger.warning("GOOGLE_API_KEY not set — LLM judge will not work")

# Initialize Langfuse client for evaluation records (only if credentials are available)
_langfuse_client = None
try:
    if os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"):
        _langfuse_client = Langfuse(
            public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
            secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
            host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
        )
except Exception as e:
    logger.warning(f"Could not initialize Langfuse client for evaluations: {e}")

JUDGE_MODEL = "gemini-2.5-pro"

# Human evaluation queue — set up once and cached here
_QUEUE_NAME = "business-analyst-review"
_human_eval_queue_id: Optional[str] = None  # cached after first setup

# Score config definitions for human evaluation
_HUMAN_SCORE_CONFIGS = [
    {
        "name": "human_accuracy",
        "data_type": "NUMERIC",
        "min_value": 0.0,
        "max_value": 1.0,
        "description": "Human review: Are the fee figures factually correct? 0 = incorrect, 1 = fully correct.",
    },
    {
        "name": "human_clarity",
        "data_type": "NUMERIC",
        "min_value": 1.0,
        "max_value": 5.0,
        "description": "Human review: Is the response clear and understandable to a non-technical user? 1 = very unclear, 5 = very clear.",
    },
    {
        "name": "human_completeness",
        "data_type": "NUMERIC",
        "min_value": 1.0,
        "max_value": 5.0,
        "description": "Human review: Does the response cover all relevant brokers and instruments? 1 = very incomplete, 5 = very complete.",
    },
    {
        "name": "human_approval",
        "data_type": "CATEGORICAL",
        "categories": [
            {"label": "Approved", "value": 1},
            {"label": "Rejected", "value": 0},
        ],
        "description": "Human review: Overall approval decision. Approved = response is suitable to show to end users.",
    },
]


def _setup_human_evaluation() -> Optional[str]:
    """
    Idempotent setup of score configs and annotation queue for human evaluation.
    Creates configs and queue only if they do not already exist.
    Returns the queue ID, or None if Langfuse is unavailable.
    """
    global _human_eval_queue_id

    if _human_eval_queue_id:
        return _human_eval_queue_id

    if not _langfuse_client:
        return None

    try:
        api = _langfuse_client.api

        # ── 1. Resolve score configs (create missing ones) ─────────────────
        existing_configs_resp = api.score_configs.get(limit=100)
        existing_names: Dict[str, str] = {
            cfg.name: cfg.id for cfg in (existing_configs_resp.data or [])
        }

        config_ids: List[str] = []
        for cfg_def in _HUMAN_SCORE_CONFIGS:
            if cfg_def["name"] in existing_names:
                config_ids.append(existing_names[cfg_def["name"]])
                logger.debug(f"Score config '{cfg_def['name']}' already exists — reusing")
            else:
                from langfuse.api.resources.score_configs.types.create_score_config_request import (
                    CreateScoreConfigRequest,
                )
                from langfuse.api.resources.commons.types.score_config_data_type import (
                    ScoreConfigDataType,
                )

                kwargs: Dict[str, Any] = {
                    "name": cfg_def["name"],
                    "data_type": ScoreConfigDataType(cfg_def["data_type"]),
                    "description": cfg_def.get("description"),
                }
                if "min_value" in cfg_def:
                    kwargs["min_value"] = cfg_def["min_value"]
                if "max_value" in cfg_def:
                    kwargs["max_value"] = cfg_def["max_value"]
                if "categories" in cfg_def:
                    from langfuse.api.resources.commons.types.config_category import ConfigCategory
                    kwargs["categories"] = [
                        ConfigCategory(label=c["label"], value=c["value"])
                        for c in cfg_def["categories"]
                    ]

                created = api.score_configs.create(request=CreateScoreConfigRequest(**kwargs))
                config_ids.append(created.id)
                logger.info(f"Created score config '{cfg_def['name']}' (id={created.id})")

        # ── 2. Resolve annotation queue (create if missing) ────────────────
        existing_queues_resp = api.annotation_queues.list_queues(limit=100)
        existing_queue = next(
            (q for q in (existing_queues_resp.data or []) if q.name == _QUEUE_NAME),
            None,
        )

        if existing_queue:
            _human_eval_queue_id = existing_queue.id
            logger.info(f"Annotation queue '{_QUEUE_NAME}' already exists — reusing (id={_human_eval_queue_id})")
        else:
            from langfuse.api.resources.annotation_queues.types.create_annotation_queue_request import (
                CreateAnnotationQueueRequest,
            )
            created_queue = api.annotation_queues.create_queue(
                request=CreateAnnotationQueueRequest(
                    name=_QUEUE_NAME,
                    description=(
                        "Business analyst review queue. "
                        "Score each trace on accuracy, clarity, completeness, and approval."
                    ),
                    score_config_ids=config_ids,
                )
            )
            _human_eval_queue_id = created_queue.id
            logger.info(f"Created annotation queue '{_QUEUE_NAME}' (id={_human_eval_queue_id})")

        return _human_eval_queue_id

    except Exception as exc:
        logger.warning(f"⚠️ Could not set up human evaluation queue: {exc}")
        return None


def add_trace_to_review_queue(trace_id: str) -> None:
    """
    Add a trace to the business-analyst-review annotation queue.
    Runs the setup idempotently on first call.
    """
    if not _langfuse_client or not trace_id:
        return

    try:
        queue_id = _setup_human_evaluation()
        if not queue_id:
            return

        from langfuse.api.resources.annotation_queues.types.create_annotation_queue_item_request import (
            CreateAnnotationQueueItemRequest,
        )
        from langfuse.api.resources.annotation_queues.types.annotation_queue_object_type import (
            AnnotationQueueObjectType,
        )

        _langfuse_client.api.annotation_queues.create_queue_item(
            queue_id=queue_id,
            request=CreateAnnotationQueueItemRequest(
                object_id=trace_id,
                object_type=AnnotationQueueObjectType.TRACE,
            ),
        )
        logger.info(f"✅ Trace {trace_id} added to '{_QUEUE_NAME}' for human review")

    except Exception as exc:
        logger.warning(f"⚠️ Could not add trace {trace_id} to review queue: {exc}")


def get_judge_prompt_for_endpoint(
    endpoint: str,
    user_input: str,
    retrieved_context: str,
    generated_output: str,
) -> str:
    """Generate the judge prompt based on endpoint type."""

    base_prompt = """You are an expert financial auditor and strict quality assurance judge. Your task is to evaluate whether a generated response is completely grounded in the provided context data.

You must act with zero tolerance for hallucinations. A hallucination occurs if the generated response mentions ANY numbers, broker names, fees, or financial details that cannot be found in or correctly calculated from the provided context.

### Inputs
1. USER QUERY: The question or request that was made.
2. RETRIEVED CONTEXT: The raw data or context retrieved to answer the query.
3. GENERATED OUTPUT: The AI-generated response presented to the user.

### Evaluation Criteria (Groundedness)
Analyze the GENERATED OUTPUT against the RETRIEVED CONTEXT. Ignore whether the response is helpful or polite; focus entirely on factual accuracy based on the provided data.

Score the response on a scale of 0 to 1 based on the following strict rubric:
* Score 1 (Pass): Every factual statement, number, broker name, and fee in the GENERATED OUTPUT is explicitly supported by or correctly calculable from the RETRIEVED CONTEXT.
* Score 0.5 (Partial): The GENERATED OUTPUT contains mostly grounded information but has minor unverified details.
* Score 0 (Fail): The GENERATED OUTPUT includes at least one significant detail that cannot be found in or correctly calculated from the RETRIEVED CONTEXT.

### CRITICAL: Verify by Recalculating
Before flagging ANY number as a hallucination, you MUST recalculate it yourself from the fee rules in the context. Only flag a number if your own calculation produces a DIFFERENT result. If your calculation matches the output, it is NOT a hallucination."""

    # Endpoint-specific instructions
    endpoint_instructions = {
        "cost-comparison-tables": """

### Endpoint-Specific Instructions (Cost Comparison Tables)
The comparison tables are DETERMINISTICALLY computed from the fee rules. The default exchange is Euronext Brussels.

Fee pattern calculation rules you MUST follow when verifying:
- **flat**: fee = flat amount + handling_fee (constant regardless of transaction size)
- **tiered_flat**: find the tier where amount <= up_to, fee = that tier's fee + handling_fee
- **tiered_flat_then_slice**: find the highest flat tier where amount <= up_to. If amount exceeds all flat tiers, use ONLY per-slice calculation (NO base fee): ceiling(remainder / per_slice) * slice_fee, where remainder = amount - highest_tier_threshold. Apply max_fee cap if specified. Add handling_fee.
- **percentage_with_min**: fee = max(amount * rate, min_fee) + handling_fee
- **base_plus_slice**: fee = base_fee + (amount / per_slice * slice_fee) + handling_fee

IMPORTANT: Do NOT flag a fee as hallucinated unless you have recalculated it step-by-step and arrived at a DIFFERENT number. Show your calculation work in the reasoning.""",

        "financial-analysis": """

### Endpoint-Specific Instructions (Financial Analysis)
The financial analysis is generated by an LLM based on deterministic fee data. Verify that:
- All broker names mentioned exist in the context
- All fee amounts cited match the context data
- Rankings and comparisons are consistent with the underlying numbers
- No external market data or events are fabricated""",

        "refresh-and-analyze": """

### Endpoint-Specific Instructions (Refresh & Analyze)
This evaluates extracted fee rules from scraped PDFs. Verify that:
- Extracted fee patterns match the PDF content in the context
- Tier boundaries and amounts are correct
- No fee rules are fabricated or mixed between brokers""",

        "chat": """

### Endpoint-Specific Instructions (Chat)
The chat response may include pre-computed deterministic fees. Verify that:
- All fee amounts cited are present in or calculable from the context
- Broker names and instruments mentioned exist in the context
- No fabricated recommendations or external data are included
- If comparison tables are in the context, cited values must match exactly""",
    }

    extra = endpoint_instructions.get(endpoint, "")

    return f"""{base_prompt}{extra}

### Output Format
You must output a valid JSON object. Do not include markdown formatting or extra text outside the JSON.

Write step-by-step reasoning where you recalculate each fee claim before judging. Then provide the score.

{{
  "reasoning": "Step 1: Checking Bolero stocks at 50000. Rule: tiered_flat_then_slice. Highest flat tier is 2500 (fee 7.5). Remainder: 50000-2500=47500. Slices: ceil(47500/10000)=5. Slice fee: 5*15=75. But max_fee=50, so capped at 50. Total: 50.0. Output says 50.0. CORRECT.",
  "score": 1.0,
  "hallucinations": [],
  "grounded_facts": ["Bolero stocks 50000 = 50.0"]
}}"""


def _parse_judge_response(response_text: str, endpoint: str) -> Optional[Dict[str, Any]]:
    """Parse JSON from judge response, handling markdown wrappers and control characters."""
    if "```json" in response_text:
        json_str = response_text.split("```json")[1].split("```")[0].strip()
    elif "```" in response_text:
        json_str = response_text.split("```")[1].split("```")[0].strip()
    else:
        json_str = response_text.strip()

    # strict=False allows control characters (newlines, tabs) inside JSON strings
    result = json.loads(json_str, strict=False)
    logger.info(f"✅ Judge evaluation complete for {endpoint}: score={result.get('score', 'N/A')}")
    return result


def evaluate_groundedness_sync(
    endpoint: str,
    user_input: str,
    retrieved_context: str,
    generated_output: str,
) -> Optional[Dict[str, Any]]:
    """
    Synchronously evaluate the groundedness of a generated response using Gemini.
    Retries up to 3 times on rate limit (429) errors with exponential backoff.
    """
    if not _gemini_client:
        logger.warning("⚠️ Gemini client not initialized, skipping judge evaluation")
        return None

    judge_prompt = get_judge_prompt_for_endpoint(
        endpoint, user_input, retrieved_context, generated_output
    )

    max_retries = 3
    base_delay = 2.0

    for attempt in range(max_retries):
        try:
            response = _gemini_client.models.generate_content(
                model=JUDGE_MODEL,
                contents=judge_prompt,
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    response_mime_type="application/json",
                ),
            )

            return _parse_judge_response(response.text, endpoint)

        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ Judge returned invalid JSON for {endpoint}: {e}")
            return None
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "Resource exhausted" in error_str:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"⚠️ Gemini rate limit (attempt {attempt + 1}/{max_retries}). Retrying in {delay}s...")
                    time.sleep(delay)
                    continue
                else:
                    logger.warning(f"⚠️ Gemini rate limit exhausted after {max_retries} attempts for {endpoint}")
                    return None
            else:
                logger.warning(f"⚠️ Judge evaluation failed for {endpoint}: {e}")
                return None

    return None


def create_langfuse_evaluation(
    endpoint: str,
    evaluation_result: Dict[str, Any],
    trace_id: Optional[str] = None,
) -> Optional[str]:
    """
    Create an evaluation record in Langfuse's evaluation table.
    """
    if not _langfuse_client:
        logger.debug("Langfuse client not available, skipping evaluation record creation")
        return None

    try:
        score = evaluation_result.get("score", 0.0)
        reasoning = evaluation_result.get("reasoning", "")

        if not trace_id:
            logger.warning("⚠️ No trace_id provided — score will be created but not linked to a trace")

        _langfuse_client.create_score(
            trace_id=trace_id,
            name="groundedness",
            value=score,
            comment=f"Endpoint: {endpoint} | Judge: {JUDGE_MODEL}\n\nReasoning: {reasoning[:500]}...",
            data_type="NUMERIC",
        )

        # Flush to ensure the score is sent before the daemon thread exits
        _langfuse_client.flush()

        logger.info(f"✅ Created Langfuse evaluation record for trace {trace_id}")
        return trace_id

    except Exception as e:
        logger.warning(f"⚠️ Failed to create Langfuse evaluation record: {e}")
        return None


def submit_evaluation_to_langfuse(
    endpoint: str,
    user_input: str,
    retrieved_context: str,
    generated_output: str,
    trace_id: Optional[str] = None,
) -> None:
    """
    Evaluate groundedness and submit results to Langfuse evaluation table.
    Also adds the trace to the human review annotation queue.
    Runs asynchronously in a background thread.
    """
    try:
        import threading

        def evaluate_and_create_record():
            try:
                result = evaluate_groundedness_sync(
                    endpoint=endpoint,
                    user_input=user_input,
                    retrieved_context=retrieved_context,
                    generated_output=generated_output,
                )

                if result:
                    eval_id = create_langfuse_evaluation(
                        endpoint=endpoint,
                        evaluation_result=result,
                        trace_id=trace_id,
                    )
                    if eval_id:
                        logger.info(f"✅ Evaluation submitted to Langfuse for {endpoint}")
                else:
                    logger.warning(f"⚠️ Groundedness evaluation returned no result for {endpoint}")

                # Queue trace for human review regardless of LLM judge outcome
                if trace_id:
                    add_trace_to_review_queue(trace_id)

            except Exception as e:
                logger.warning(f"⚠️ Evaluation submission error: {e}")

        thread = threading.Thread(target=evaluate_and_create_record, daemon=True)
        thread.start()

    except Exception as e:
        logger.warning(f"⚠️ Failed to submit evaluation to Langfuse: {e}")
