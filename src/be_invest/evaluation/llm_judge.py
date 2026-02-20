"""LLM-as-Judge evaluator for Langfuse traces using Claude."""

import asyncio
import json
import logging
import os
from typing import Optional, Dict, Any
from anthropic import Anthropic, AsyncAnthropic
from langfuse import Langfuse
from langfuse.decorators import langfuse_context

logger = logging.getLogger(__name__)

# Initialize Anthropic clients
sync_client = Anthropic()
async_client = AsyncAnthropic()

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

JUDGE_MODEL = "claude-opus-4-6"


def get_judge_prompt_for_endpoint(
    endpoint: str,
    user_input: str,
    retrieved_context: str,
    generated_output: str,
) -> str:
    """Generate the judge prompt based on endpoint type."""

    base_prompt = """You are an expert financial auditor and strict quality assurance judge. Your task is to evaluate whether a generated portfolio insight is completely grounded in the provided portfolio data.

You must act with zero tolerance for hallucinations. A hallucination occurs if the generated response mentions ANY numbers, stock tickers, asset allocations, account balances, broker names, fees, or market events that are not explicitly present in the provided context.

### Inputs
1. USER QUERY: The question or request that was made.
2. RETRIEVED CONTEXT: The raw data or context retrieved to answer the query.
3. GENERATED OUTPUT: The AI-generated response presented to the user.

### Evaluation Criteria (Groundedness)
Analyze the GENERATED OUTPUT against the RETRIEVED CONTEXT. Ignore whether the response is helpful or polite; focus entirely on factual accuracy based on the provided data.

Score the response on a scale of 0 to 1 based on the following strict rubric:
* Score 1 (Pass): Every factual statement, number, ticker, broker name, and fee in the GENERATED OUTPUT is explicitly supported by the RETRIEVED CONTEXT. The model made reasonable, mathematically sound deductions without adding outside information.
* Score 0.5 (Partial): The GENERATED OUTPUT contains mostly grounded information but may have minor unverified details or reasonable inferences that go slightly beyond the context.
* Score 0 (Fail): The GENERATED OUTPUT includes at least one significant detail (a number, a ticker, a broker name, a fee, or an external market event) that cannot be found in or directly calculated from the RETRIEVED CONTEXT.

### Output Format
You must output a valid JSON object. Do not include markdown formatting or extra text outside the JSON.

First, write out your step-by-step reasoning. Identify every factual claim in the output and verify if it exists in the context. Finally, provide the score between 0 and 1.

{
  "reasoning": "Step 1: The output claims X. Checking context... [verification]. Step 2: The output claims Y...",
  "score": 0.8,
  "hallucinations": ["claim that is not grounded", "another unverified claim"],
  "grounded_facts": ["fact that is grounded", "another verified fact"]
}"""

    if endpoint == "cost-comparison-tables":
        prompt = f"""{base_prompt}

---

USER QUERY: {user_input}

RETRIEVED CONTEXT (Fee Rules and Broker Data):
{retrieved_context}

GENERATED OUTPUT (Comparison Tables):
{generated_output}"""

    elif endpoint == "refresh-and-analyze":
        prompt = f"""{base_prompt}

---

USER QUERY: {user_input}

RETRIEVED CONTEXT (Extracted PDF Content):
{retrieved_context}

GENERATED OUTPUT (Extracted Fee Rules and Analysis):
{generated_output}"""

    elif endpoint == "financial-analysis":
        prompt = f"""{base_prompt}

---

USER QUERY: {user_input}

RETRIEVED CONTEXT (Broker Fee Data):
{retrieved_context}

GENERATED OUTPUT (Financial Analysis):
{generated_output}"""

    elif endpoint == "chat":
        prompt = f"""{base_prompt}

---

USER QUERY: {user_input}

RETRIEVED CONTEXT (Fee Rules, Comparison Tables, Hidden Costs):
{retrieved_context}

GENERATED OUTPUT (Chat Response):
{generated_output}"""

    else:
        # Fallback for unknown endpoints
        prompt = f"""{base_prompt}

---

USER QUERY: {user_input}

RETRIEVED CONTEXT:
{retrieved_context}

GENERATED OUTPUT:
{generated_output}"""

    return prompt


async def evaluate_groundedness_async(
    endpoint: str,
    user_input: str,
    retrieved_context: str,
    generated_output: str,
) -> Optional[Dict[str, Any]]:
    """
    Asynchronously evaluate the groundedness of a generated response using Claude.

    Args:
        endpoint: The endpoint being evaluated (cost-comparison-tables, refresh-and-analyze, etc.)
        user_input: The user's query or request
        retrieved_context: The context data used to generate the output
        generated_output: The generated response to evaluate

    Returns:
        Dict with 'score' and 'reasoning', or None if evaluation fails
    """
    try:
        judge_prompt = get_judge_prompt_for_endpoint(
            endpoint, user_input, retrieved_context, generated_output
        )

        message = await async_client.messages.create(
            model=JUDGE_MODEL,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": judge_prompt,
                }
            ],
        )

        response_text = message.content[0].text

        # Parse JSON response
        # Try to extract JSON if it's wrapped in markdown code blocks
        if "```json" in response_text:
            json_str = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            json_str = response_text.split("```")[1].split("```")[0].strip()
        else:
            json_str = response_text.strip()

        result = json.loads(json_str)
        logger.info(f"✅ Judge evaluation complete for {endpoint}: score={result.get('score', 'N/A')}")
        return result

    except json.JSONDecodeError as e:
        logger.warning(f"⚠️ Judge returned invalid JSON for {endpoint}: {e}")
        logger.debug(f"Response was: {response_text[:200]}")
        return None
    except Exception as e:
        logger.warning(f"⚠️ Judge evaluation failed for {endpoint}: {e}")
        return None


def evaluate_groundedness_sync(
    endpoint: str,
    user_input: str,
    retrieved_context: str,
    generated_output: str,
) -> Optional[Dict[str, Any]]:
    """
    Synchronously evaluate the groundedness of a generated response using Claude.
    Use async version when possible for non-blocking evaluation.
    """
    try:
        judge_prompt = get_judge_prompt_for_endpoint(
            endpoint, user_input, retrieved_context, generated_output
        )

        message = sync_client.messages.create(
            model=JUDGE_MODEL,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": judge_prompt,
                }
            ],
        )

        response_text = message.content[0].text

        # Parse JSON response
        if "```json" in response_text:
            json_str = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            json_str = response_text.split("```")[1].split("```")[0].strip()
        else:
            json_str = response_text.strip()

        result = json.loads(json_str)
        logger.info(f"✅ Judge evaluation complete for {endpoint}: score={result.get('score', 'N/A')}")
        return result

    except json.JSONDecodeError as e:
        logger.warning(f"⚠️ Judge returned invalid JSON for {endpoint}: {e}")
        return None
    except Exception as e:
        logger.warning(f"⚠️ Judge evaluation failed for {endpoint}: {e}")
        return None


def submit_evaluation_async(
    endpoint: str,
    user_input: str,
    retrieved_context: str,
    generated_output: str,
) -> None:
    """
    Submit evaluation task asynchronously in a fire-and-forget manner.
    Does not block the response.
    """
    try:
        # Try to run in event loop if available
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(
                evaluate_groundedness_async(
                    endpoint, user_input, retrieved_context, generated_output
                )
            )
        except RuntimeError:
            # No event loop, run in new thread with new loop
            asyncio.run(
                evaluate_groundedness_async(
                    endpoint, user_input, retrieved_context, generated_output
                )
            )
    except Exception as e:
        logger.warning(f"⚠️ Failed to submit async evaluation: {e}")


def create_langfuse_evaluation(
    endpoint: str,
    evaluation_result: Dict[str, Any],
    trace_id: Optional[str] = None,
) -> Optional[str]:
    """
    Create an evaluation record in Langfuse's evaluation table.

    Args:
        endpoint: The endpoint being evaluated
        evaluation_result: The evaluation result from the judge (contains score, reasoning, etc.)
        trace_id: Optional trace ID to link this evaluation to a specific trace

    Returns:
        The evaluation record ID if successful, None otherwise
    """
    if not _langfuse_client:
        logger.debug("Langfuse client not available, skipping evaluation record creation")
        return None

    try:
        score = evaluation_result.get("score", 0.0)
        reasoning = evaluation_result.get("reasoning", "")
        hallucinations = evaluation_result.get("hallucinations", [])
        grounded_facts = evaluation_result.get("grounded_facts", [])

        # Create evaluation record in Langfuse
        eval_record = _langfuse_client.score(
            trace_id=trace_id,
            observation_id=None,
            name="groundedness",
            value=score,
            comment=f"Endpoint: {endpoint}\n\nReasoning: {reasoning[:500]}...",  # Truncate long reasoning
            data_type="numeric",
        )

        logger.info(f"✅ Created Langfuse evaluation record: {eval_record}")
        return str(eval_record)

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
    Runs asynchronously in a background thread.

    Args:
        endpoint: The endpoint being evaluated
        user_input: The user's query or request
        retrieved_context: The context data used to generate the output
        generated_output: The generated response to evaluate
        trace_id: Optional trace ID to link evaluation to specific trace
    """
    try:
        import threading

        def evaluate_and_create_record():
            """Inner function to run in background thread."""
            try:
                # Evaluate groundedness
                result = evaluate_groundedness_sync(
                    endpoint=endpoint,
                    user_input=user_input,
                    retrieved_context=retrieved_context,
                    generated_output=generated_output,
                )

                if result:
                    # Create Langfuse evaluation record
                    eval_id = create_langfuse_evaluation(
                        endpoint=endpoint,
                        evaluation_result=result,
                        trace_id=trace_id,
                    )
                    if eval_id:
                        logger.info(f"✅ Evaluation submitted to Langfuse for {endpoint}")
                else:
                    logger.warning(f"⚠️ Groundedness evaluation returned no result for {endpoint}")

            except Exception as e:
                logger.warning(f"⚠️ Evaluation submission error: {e}")

        # Run in background thread to not block response
        thread = threading.Thread(target=evaluate_and_create_record, daemon=True)
        thread.start()

    except Exception as e:
        logger.warning(f"⚠️ Failed to submit evaluation to Langfuse: {e}")
