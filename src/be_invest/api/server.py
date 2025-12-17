from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

import datetime
from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl

from ..config_loader import load_brokers_from_yaml
from ..models import Broker
from ..sources.scrape import scrape_fee_records
from ..sources.news_scrape import scrape_broker_news
from ..news import NewsFlash, save_news_flash, load_news, get_news_by_broker, delete_news_flash, get_recent_news, get_news_statistics
from ..utils.cache import FileCache


# ========================================================================================
# PYDANTIC MODELS
# ========================================================================================

class NewsFlashRequest(BaseModel):
    """Request model for creating news flashes."""
    broker: str
    title: str
    summary: str
    url: Optional[HttpUrl] = None
    date: Optional[str] = None
    source: Optional[str] = None
    notes: Optional[str] = None


class NewsFlashResponse(BaseModel):
    """Response model for news flashes."""
    broker: str
    title: str
    summary: str
    url: Optional[str] = None
    date: Optional[str] = None
    source: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None


class NewsDeleteRequest(BaseModel):
    """Request model for deleting news flashes."""
    broker: str
    title: str


# ========================================================================================
# FASTAPI APPLICATION
# ========================================================================================

app = FastAPI(title="be-invest PDF Text API", version="0.1.0")
logger = logging.getLogger(__name__)

# Add CORS middleware to allow cross-origin requests from anywhere
# IMPORTANT: When using wildcard origins ["*"], credentials MUST be False
# If you need credentials, specify exact origins instead of wildcard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=False,  # MUST be False with wildcard origins
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Initialize caches
llm_cache = FileCache(Path("data/cache/llm"), default_ttl=7 * 24 * 3600)  # 7 days
news_cache = FileCache(Path("data/cache/news"), default_ttl=24 * 3600)  # 24 hours


def _default_output_dir() -> Path:
    """Resolve the output directory path."""
    cwd_path = Path("data") / "output"
    if cwd_path.exists():
        return cwd_path
    repo_root = Path(__file__).resolve().parents[3]
    fallback = repo_root / "data" / "output"
    return fallback


def _default_brokers_yaml() -> Path:
    """Resolve the brokers.yaml file path."""
    cwd_path = Path("data") / "brokers.yaml"
    if cwd_path.exists():
        return cwd_path
    repo_root = Path(__file__).resolve().parents[3]
    fallback = repo_root / "data" / "brokers.yaml"
    return fallback


def _call_llm(model: str, system_prompt: str, user_prompt: str, response_format: str = "json") -> str:
    """
    Unified LLM caller supporting both OpenAI (gpt-*) and Anthropic (claude-*) models.

    Args:
        model: Model name (e.g., "gpt-4o", "claude-sonnet-4-20250514")
        system_prompt: System message content
        user_prompt: User message content
        response_format: "json" for JSON mode, "text" for regular text

    Returns:
        String response from the LLM
    """
    if model.startswith("claude"):
        # Use Anthropic API
        try:
            import anthropic
            import time
        except ImportError:
            raise HTTPException(
                status_code=500,
                detail="Anthropic SDK not installed. Run: pip install anthropic"
            )

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not set.")

        client = anthropic.Anthropic(api_key=api_key)

        logger.info(f"🔄 Calling Anthropic model: {model}")

        # Retry logic with exponential backoff for rate limits
        max_retries = 3
        base_delay = 2.0

        for attempt in range(max_retries):
            try:
                # Claude doesn't have native JSON mode, so we add it to the prompt
                enhanced_user_prompt = user_prompt
                if response_format == "json":
                    enhanced_user_prompt += "\n\nIMPORTANT: Return ONLY valid JSON. No markdown, no explanations, no code blocks."

                response = client.messages.create(
                    model=model,
                    max_tokens=4096,
                    temperature=0.0,
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": enhanced_user_prompt}
                    ]
                )

                response_text = response.content[0].text

                # Clean up any markdown formatting and common JSON issues Claude might add
                if response_format == "json":
                    # Remove markdown code blocks
                    if response_text.strip().startswith("```"):
                        lines = response_text.strip().split("\n")
                        if lines[0].startswith("```"):
                            lines = lines[1:]
                        if lines and lines[-1].strip().startswith("```"):
                            lines = lines[:-1]
                        response_text = "\n".join(lines).strip()

                    # Clean up common Claude JSON issues
                    response_text = response_text.strip()

                    # Remove any text before the first {
                    first_brace = response_text.find('{')
                    if first_brace > 0:
                        response_text = response_text[first_brace:]

                    # Remove any text after the last }
                    last_brace = response_text.rfind('}')
                    if last_brace > 0 and last_brace < len(response_text) - 1:
                        response_text = response_text[:last_brace + 1]

                    # Try to validate JSON and fix common issues
                    try:
                        json.loads(response_text)
                    except json.JSONDecodeError as json_error:
                        logger.warning(f"⚠️ Claude returned invalid JSON, attempting to fix: {json_error}")
                        # Try to fix common issues like unescaped quotes or trailing commas
                        # This is a basic attempt - if it fails, we'll let the calling function handle it
                        pass

                return response_text

            except anthropic.RateLimitError as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"⚠️ Rate limit hit (attempt {attempt + 1}/{max_retries}). Retrying in {delay}s...")
                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"❌ Rate limit exceeded after {max_retries} attempts")
                    # Fallback to GPT-4o if rate limited
                    logger.info("🔄 Falling back to GPT-4o due to rate limits...")
                    return _call_llm("gpt-4o", system_prompt, user_prompt, response_format)

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"❌ Anthropic API call failed: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"Anthropic API call failed: {str(e)}")

    else:
        # Use OpenAI API (default for gpt-* models)
        try:
            from openai import OpenAI
        except ImportError:
            raise HTTPException(
                status_code=500,
                detail="OpenAI SDK not installed. Run: pip install openai"
            )

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="OPENAI_API_KEY not set.")

        client = OpenAI(api_key=api_key)

        logger.info(f"🔄 Calling OpenAI model: {model}")

        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            # OpenAI-specific parameters
            params = {
                "model": model,
                "messages": messages,
                "temperature": 0.0,
            }

            if response_format == "json":
                params["response_format"] = {"type": "json_object"}

            response = client.chat.completions.create(**params)
            return response.choices[0].message.content

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ OpenAI API call failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"OpenAI API call failed: {str(e)}")


def _get_cost_analysis_data() -> Dict[str, Any]:
    """Helper to load the main cost analysis JSON."""
    output_dir = _default_output_dir()
    analysis_file = output_dir / "broker_cost_analyses.json"
    if not analysis_file.exists():
        raise HTTPException(
            status_code=404,
            detail="Cost analysis file not found. Run generate_exhaustive_summary.py first."
        )
    try:
        with open(analysis_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load analysis file: {exc}")

def _get_cost_comparison_data() -> Dict[str, Any]:
    """Helper to load the cost comparison analysis JSON."""
    output_dir = _default_output_dir()
    analysis_file = output_dir / "cost_comparison_tables.json"
    if not analysis_file.exists():
        raise HTTPException(
            status_code=404,
            detail="Cost analysis file not found. Run generate_exhaustive_summary.py first."
        )
    try:
        with open(analysis_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load analysis file: {exc}")

@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.options("/health")
@app.options("/cost-analysis")
@app.options("/cost-analysis/{broker_name}")
@app.options("/cost-comparison-tables")
@app.options("/financial-analysis")
@app.options("/brokers")
@app.options("/summary")
@app.options("/refresh-pdfs")
@app.options("/refresh-and-analyze")
@app.options("/news")
@app.options("/news/broker/{broker_name}")
@app.options("/news/recent")
@app.options("/news/statistics")
@app.options("/news/scrape")
async def options_handler():
    """Handle OPTIONS (preflight) requests for CORS."""
    return JSONResponse(
        content={"message": "OK"},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Max-Age": "3600",
            # NOTE: Do NOT include Access-Control-Allow-Credentials when using wildcard origin
        }
    )


@app.get("/cost-analysis", response_class=JSONResponse)
def get_cost_analysis() -> Dict[str, Any]:
    """Get the comprehensive cost and charges analysis for all brokers."""
    return _get_cost_analysis_data()


@app.get("/cost-comparison-tables", response_class=JSONResponse)
def get_cost_comparison_tables(
        model: str = Query("gpt-4o", description="LLM to use: gpt-4o (default), claude-sonnet-4-20250514, gpt-4-turbo"),
        force: bool = Query(False, description="Force fresh generation, ignore cache")
) -> Dict[str, Any]:
    """
    Generates three cost comparison tables for ETFs, Stocks, and Bonds
    based on the existing broker_cost_analyses.json data.

    Supports both OpenAI (gpt-*) and Anthropic (claude-*) models.
    
    Set force=True to bypass cache and generate fresh data.

    Role: You are a Financial Data Analyst specializing in the Belgian investment market.

    Task: Conduct a pricing analysis of Belgian brokerage platforms and output the data
    into three distinct matrix tables.
    """
    # Check cache first (unless force=True)
    cache_key = FileCache.make_key("cost_comparison", model)
    if not force:
        cached = llm_cache.get(cache_key)
        if cached:
            logger.info(f"📦 Returning cached cost comparison tables for model: {model}")
            return cached

    # ... (existing logic continues)
    cost_data = _get_cost_analysis_data()

    # Extract broker names
    broker_names = [name for name in cost_data.keys() if "error" not in cost_data.get(name, {})]

    if not broker_names:
        raise HTTPException(
            status_code=404,
            detail="No valid broker data found. Run generate_exhaustive_summary.py first."
        )

    # Prepare detailed instructions for the LLM
    prompt = f"""You are a Lead Financial Data Analyst specializing in the Belgian investment market.

    TASK: Conduct a rigorous pricing analysis of Belgian brokerage platforms for the **Euronext Brussels** exchange.
    Output the data into a structured JSON dataset grouped strictly by **Market**, then by **Asset Class**.

    BROKERS TO ANALYZE: {', '.join(broker_names)}

    TRANSACTION SIZES (in EUR): 250, 500, 1000, 1500, 2000, 2500, 5000, 10000, 50000

    MARKETS TO ANALYZE:
    1. **Euronext Brussels** (Stocks)
    2. **Euronext Brussels** (ETFs)
    3. **Euronext Brussels** (Bonds - Secondary Market)

    BROKER DATA:
    {json.dumps(cost_data, indent=2)}

    ### CRITICAL INSTRUCTIONS

    1. **Fee Analysis**:
       - **Handling Fees**: ALWAYS ADD any "Handling" or "Service" fees to the base fee (e.g., Degiro's €1.00 handling fee).
       - **Slice Logic**:
         - **Rebel**: Above €2,500, the fee is per *started* slice.
         - **Keytrade**: Above €2,500, base fee applies up to €10k. Above €10k, add "additional slice" cost for every extra €10k started.
         - **Bolero**: Respect the "Max" caps defined in the tiers.
       - **Bond Minimums**: Pay close attention to minimum fees for bonds (e.g., ING's €50 minimum, Keytrade's €29.95 minimum).

    2. **Calculation Logic (EXHAUSTIVE & MANDATORY)**:
       - For **EVERY** Broker (Bolero, Keytrade, Degiro, ING, Rebel, Revolut):
       - For **EVERY** Asset Class (Stocks, ETFs, Bonds):
       - You MUST provide a specific text explanation for **ALL 9 TIERS**:
         `["250", "500", "1000", "1500", "2000", "2500", "5000", "10000", "50000"]`
       - **STRICT PROHIBITION**: Do not skip keys. Do not group keys (e.g., do not say "250-2500: €3"). Do not say "Same as stocks". You must write out the logic for every single line item.
       - **Format**: Show the math. E.g., "Base €14.95 + (4 x €7.50 slices) = €44.95".

    3. **Notes & Hidden Fees (VERIFIED)**:
       - **Custody Fees**: Check ING Self Invest carefully (0.0242%/month).
       - **Real-Time Quotes**: Verify cost in source (Keytrade €2.50/mo vs Bolero Free).
       - **Connectivity Fees**: Mention Degiro's €2.50/yr fee.
    
    ### PHASE 1: LOGIC EXTRACTION (CRITICAL)
    Before calculating any numbers, you must scan the data and extract the **Lowest Available Online/Web Rate** for each broker.
    **Rules for Extraction**:
    1. **Online Priority**: If multiple fees exist (e.g., "Standard" vs "Web App" or "Offline" vs "Online"), YOU MUST CHOOSE THE "ONLINE/WEB/APP" RATE. Ignore "Phone", "Desk", or "Normal" rates if a cheaper digital option exists.
       - *Example Fix*: For ING, ignore "1% (Min €40)". Pick "0.35% (Min €1)".
    2. **Rate Identification**:
       - If text says "25 per 10,000", translate to: `Amount * 0.0025`.
       - If text says "15 per 10,000 slice", translate to: `ceil(Amount/10000) * 15`.
    3. **Constraint Identification**: Note all Minimums (Floor) and Maximums (Cap).
    
    ### PHASE 2: CALCULATION
    Calculate the fee for these exact amounts: [250, 500, 1000, 1500, 2000, 2500, 5000, 10000, 50000].
    *Perform the calculation step-by-step in your reasoning to ensure accuracy.*

    ### OUTPUT FORMAT
    Return ONLY a valid JSON object.

    {{
      "euronext_brussels": {{
        "stocks": [
          {{
            "broker": "Rebel",
            "250": 3.00,
            "500": 3.00,
            "1000": 3.00,
            "1500": 3.00,
            "2000": 3.00,
            "2500": 3.00,
            "5000": 10.00,
            "10000": 10.00,
            "50000": 50.00
          }}
        ],
        "etfs": [ ... ],
        "bonds": [ ... ],
        "calculation_logic": {{
          "Rebel": {{
            "stocks": {{
              "250": "Tier 1: Flat fee of €3 (<= €2,500)",
              "500": "Tier 1: Flat fee of €3 (<= €2,500)",
              "1000": "Tier 1: Flat fee of €3 (<= €2,500)",
              "1500": "Tier 1: Flat fee of €3 (<= €2,500)",
              "2000": "Tier 1: Flat fee of €3 (<= €2,500)",
              "2500": "Tier 1: Flat fee of €3 (<= €2,500)",
              "5000": "Slice Tier (>€2,500): 1st started €10k slice = €10",
              "10000": "Slice Tier (>€2,500): 1st started €10k slice = €10",
              "50000": "Slice Tier (>€2,500): 5 x €10k slices = €50"
            }},
            "etfs": {{
              "250": "Tier 1: Flat fee of €1 (<= €250)",
              "500": "Tier 2: Flat fee of €2 (<= €1,000)",
              "1000": "Tier 3: Flat fee of €3 (<= €2,500)",
              "1500": "Tier 3: Flat fee of €3 (<= €2,500)",
              "2000": "Tier 3: Flat fee of €3 (<= €2,500)",
              "2500": "Tier 3: Flat fee of €3 (<= €2,500)",
              "5000": "Slice Tier (>€2,500): 1st started €10k slice = €10",
              "10000": "Slice Tier (>€2,500): 1st started €10k slice = €10",
              "50000": "Slice Tier (>€2,500): 5 x €10k slices = €50"
            }}
          }},
          "Keytrade Bank": {{
            "stocks": {{
              "250": "Tier 1: Flat fee of €2.45 (<= €250)",
              "500": "Tier 2: Flat fee of €5.95 (<= €2,500)",
              "1000": "Tier 2: Flat fee of €5.95 (<= €2,500)",
              "1500": "Tier 2: Flat fee of €5.95 (<= €2,500)",
              "2000": "Tier 2: Flat fee of €5.95 (<= €2,500)",
              "2500": "Tier 2: Flat fee of €5.95 (<= €2,500)",
              "5000": "Tier 3: Flat fee of €14.95 (<= €10,000)",
              "10000": "Tier 3: Flat fee of €14.95 (<= €10,000)",
              "50000": "Tier 4: €14.95 (base) + 4 additional €10k slices (€7.50 each) = €44.95"
            }},
            "etfs": {{
              "250": "Tier 1: Flat fee of €2.45 (<= €250)",
              "500": "Tier 2: Flat fee of €5.95 (<= €2,500)",
              "1000": "Tier 2: Flat fee of €5.95 (<= €2,500)",
              "1500": "Tier 2: Flat fee of €5.95 (<= €2,500)",
              "2000": "Tier 2: Flat fee of €5.95 (<= €2,500)",
              "2500": "Tier 2: Flat fee of €5.95 (<= €2,500)",
              "5000": "Tier 3: Flat fee of €14.95 (<= €10,000)",
              "10000": "Tier 3: Flat fee of €14.95 (<= €10,000)",
              "50000": "Tier 4: €14.95 (base) + 4 additional €10k slices (€7.50 each) = €44.95"
            }}
          }}
        }},
        "notes": {{
          "Rebel": "Free real-time quotes. No custody fee.",
          "Degiro Belgium": "Includes €1 handling fee. Connectivity fee (€2.50/yr) applies.",
          "Keytrade Bank": "Real-time quotes cost €2.50/month (Euronext). No custody fee.",
          "ING Self Invest": "0.0242% monthly custody fee applies to shares/ETFs (min €0.30/mo)."
        }}
      }}
    }}
    """

    system_prompt = "You are a precise financial data analyst. You calculate exact transaction costs and return only valid JSON with numeric values."

    try:
        logger.info(f"📊 Analyzing {len(broker_names)} brokers: {', '.join(broker_names)}")

        # Call the unified LLM helper
        response_text = _call_llm(model, system_prompt, prompt, response_format="json")

        if not response_text:
            raise HTTPException(status_code=500, detail="LLM returned an empty response.")

        # Parse and validate response with Claude fallback
        try:
            result = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON parsing failed for {model}: {e}")
            logger.error(f"Response preview: {response_text[:500]}")

            # If Claude failed, try with GPT-4o as fallback
            if model.startswith("claude"):
                logger.info("🔄 Retrying with GPT-4o due to JSON parsing failure...")
                try:
                    response_text = _call_llm("gpt-4o", system_prompt, prompt, response_format="json")
                    result = json.loads(response_text)
                    logger.info("✅ Successfully generated with GPT-4o fallback")
                except Exception as fallback_error:
                    logger.error(f"❌ Fallback to GPT-4o also failed: {fallback_error}")
                    raise HTTPException(status_code=500, detail=f"Failed to parse LLM response as JSON: {e}")
            else:
                raise HTTPException(status_code=500, detail=f"Failed to parse LLM response as JSON: {e}")


        # Validation - Response should be grouped by exchanges (like "euronext_brussels", "usa", etc.)
        logger.info(f"🔍 Validating response structure...")

        if not isinstance(result, dict):
            raise ValueError("Response must be a JSON object")

        # Expected exchanges - at least one should be present
        found_exchanges = []
        total_broker_entries = 0

        for exchange_key, exchange_data in result.items():
            if isinstance(exchange_data, dict):
                found_exchanges.append(exchange_key)

                # Check if this exchange has the expected structure
                if "stocks" in exchange_data or "etfs" in exchange_data:
                    logger.info(f"✅ Found valid exchange data for: {exchange_key}")

                    # Count and validate broker entries
                    for asset_type in ["stocks", "etfs"]:
                        if asset_type in exchange_data and isinstance(exchange_data[asset_type], list):
                            total_broker_entries += len(exchange_data[asset_type])

                            # Validate each row has broker field
                            for row in exchange_data[asset_type]:
                                if not isinstance(row, dict) or "broker" not in row:
                                    logger.warning(f"Invalid row structure in {exchange_key}.{asset_type}")
                                    continue

                                # Check for transaction sizes (optional validation)
                                transaction_sizes = ["250", "500", "1000", "1500", "2000", "2500", "5000", "10000", "50000"]
                                missing_sizes = [size for size in transaction_sizes if size not in row]
                                if missing_sizes:
                                    logger.warning(f"Row for {row.get('broker', 'unknown')} in '{exchange_key}.{asset_type}' missing sizes: {missing_sizes}")

        if not found_exchanges:
            raise ValueError("No valid exchange data found in response")

        logger.info(f"✅ Successfully generated comparison tables for {len(found_exchanges)} exchanges with {total_broker_entries} broker entries")

        # Save the JSON response to output directory
        output_dir = _default_output_dir()
        output_dir.mkdir(parents=True, exist_ok=True)

        # Create filename with timestamp and model name
        from datetime import datetime
        output_path = output_dir / f"cost_comparison_tables.json"

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            logger.info(f"💾 Saved cost comparison tables to: {output_path}")
        except Exception as save_error:
            logger.warning(f"⚠️  Failed to save JSON response to file: {save_error}")

        # Cache the result
        llm_cache.set(cache_key, result)
        logger.info(f"💾 Cached cost comparison tables for model: {model}")

        return result

    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON parsing failed: {e}")
        logger.error(f"Response was: {response_text[:500]}")
        raise HTTPException(status_code=500, detail=f"Failed to parse LLM response as JSON: {e}")
    except Exception as e:
        logger.error(f"❌ Failed to generate cost comparison tables: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate cost comparison tables: {e}")


@app.get("/financial-analysis")
def generate_financial_analysis(
        model: str = Query("gpt-4o", description="LLM to use: gpt-4o (default), claude-sonnet-4-20250514"),
        force: bool = Query(False, description="Force fresh generation, ignore cache")
) -> Dict[str, Any]:
    """
    Generate a comprehensive financial analysis comparing Belgian investment brokers.

    Returns structured JSON with:
    - Title and metadata
    - Executive summary
    - Detailed cost analysis by product type (ETFs, Stocks, Bonds)
    - Broker comparisons and recommendations
    - Market insights and trends
    - Investment scenarios

    Perfect for React/Vue/Angular apps to render with custom styling.
    """
    # Check cache first (unless force=True)
    cache_key = FileCache.make_key("financial_analysis", model)
    if not force:
        cached = llm_cache.get(cache_key)
        if cached:
            logger.info(f"📦 Returning cached financial analysis for model: {model}")
            return cached

    # ... (existing logic continues)
    cost_data = _get_cost_comparison_data()

    # Extract broker names
    broker_names = [name for name in cost_data.keys() if "error" not in cost_data.get(name, {})]

    if not broker_names:
        raise HTTPException(
            status_code=404,
            detail="No valid broker data found. Run generate_exhaustive_summary.py first."
        )

    # Prepare comprehensive prompt for financial analysis
    system_prompt = """
    Act as a Senior Financial Analyst and Investment Journalist specializing in the Euronext Brussels market. I need a structured, evidence-based investment memo on [INSERT TICKER/COMPANY NAME HERE] designed for a modern financial application (mobile-first, scannable).

Your analysis must include:

The 'Lede': A 2-sentence executive summary of the current investment thesis.

Quantitative Evidence: Use LaTeX for financial formulas. Focus on Free Cash Flow (FCF), EBITDA margins, Net Debt/EBITDA, and P/E ratios relative to historical averages and peers.

The Belgian Context: Analyze specific local factors (e.g., Belgian withholding tax, index weighting in the BEL20, exposure to the Belgian economy/bonds).

Bull vs. Bear: Three distinct, data-backed points for both the upside and downside.

Valuation & Verdict: A clear rating (Buy/Hold/Sell) based on a specific valuation method (DCF or Peer Multiples).

Tone: Professional, skeptical, and objective. Avoid generic fluff; prioritize hard data.
    """

    # Create explicit list of all brokers
    broker_list = ", ".join(broker_names)

    # Get current date for the analysis
    from datetime import datetime
    current_date = datetime.now().strftime('%B %d, %Y')

    user_prompt = f"""Generate a comprehensive financial analysis comparing ALL Belgian investment brokers.

    CRITICAL: You MUST include ALL {len(broker_names)} brokers in your analysis:
    {broker_list}

    BROKER DATA:
    {json.dumps(cost_data, indent=2)}

    ### CALCULATION RULES (STRICT):
    1. **Total Cost of Ownership (TCO)**: You MUST add ALL hidden fees to the transaction cost:
       - **Handling Fees**: e.g., Degiro's €1.00 per trade.
       - **Connectivity Fees**: e.g., Degiro's €2.50/year (amortize or add to annual totals).
       - **Custody Fees**: e.g., ING's % fee per month.
       - **Service Fees**: Any fixed monthly platform fees (e.g., Keytrade Pro if applicable, though usually free).
    2. **Profiles for Annual Cost**:
       - **Passive Investor (monthly500ETF)**: Buys €500 of ETFs once per month (12 trades/year). *Assumption: Core Selection if available, otherwise standard.*
       - **Active Trader**: Buys €2,500 of Stocks 10 times/month + €10,000 of Stocks 2 times/month (144 trades/year).

    ### OUTPUT STRUCTURE
    Return a SIMPLE JSON object. Keep all text strings short (max 150 chars).

    {{
      "metadata": {{
        "title": "Short catchy title (max 80 chars)",
        "subtitle": "Key insight (max 100 chars)",
        "publishDate": "{current_date}",
        "readingTimeMinutes": 12
      }},
      "executiveSummary": [
        "Finding 1 (max 150 chars)",
        "Finding 2 (max 150 chars)",
        "Finding 3 (max 150 chars)"
      ],
      "brokerComparisons": [
        {{
          "broker": "Name",
          "overallRating": 5,
          "etfRating": 5,
          "stockRating": 5,
          "pros": ["Pro 1", "Pro 2"],
          "cons": ["Con 1", "Con 2"],
          "bestFor": ["Buy & Hold", "Day Trading"]
        }}
        // ... Repeat for ALL brokers
      ],
      "cheapestPerTier": {{
        "stocks": {{
          "250": "Broker Name (€Cost)",
          "2500": "Broker Name (€Cost)",
          "10000": "Broker Name (€Cost)",
          "50000": "Broker Name (€Cost)"
        }},
        "etfs": {{
          "500": "Broker Name (€Cost)",
          "5000": "Broker Name (€Cost)"
        }}
      }},
      "costComparison": {{
        "passiveInvestor": [
          {{"broker": "Name", "annualCost": 0, "rank": 1}},
          // ... All brokers sorted by cost
        ],
        "activeTrader": [
          {{"broker": "Name", "annualCost": 100, "rank": 1}},
          // ... All brokers sorted by cost
        ]
      }},
      "costEvidence": {{
        "passiveInvestor": {{
          "Broker Name": "12 x (€0 fee + €1 handling) + €0 custody = €12/yr",
          "Another Broker": "12 x €5 fee = €60/yr"
        }},
        "activeTrader": {{
          "Broker Name": "120x(€3) + 24x(€10) + €2.50 conn = €602.50/yr"
        }}
      }}
    }}

    CRITICAL OUTPUT RULES:
    1. **Valid JSON Only**: No markdown formatting.
    2. **All Brokers**: Every list must contain exactly {len(broker_names)} entries.
    3. **Math Check**: Verify your "Active Trader" sums. (e.g. if fee is €3/trade, annual is ~€432, not €50).
    """

    try:
        logger.info(f"📊 Generating structured financial analysis using {model}...")

        # Call the unified LLM helper
        response_text = _call_llm(model, system_prompt, user_prompt, response_format="json")

        if not response_text or not response_text.strip():
            raise HTTPException(status_code=500, detail="LLM returned an empty response.")

        # Parse JSON response with retry on failure
        try:
            result = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON parsing failed: {e}")
            logger.error(f"Response preview: {response_text[:500]}")

            # If Claude failed, try with GPT-4o as fallback
            if model.startswith("claude"):
                logger.info("🔄 Retrying with GPT-4o due to JSON parsing failure...")
                try:
                    response_text = _call_llm("gpt-4o", system_prompt, user_prompt, response_format="json")
                    result = json.loads(response_text)
                    logger.info("✅ Successfully generated with GPT-4o fallback")
                except Exception as fallback_error:
                    logger.error(f"❌ Fallback to GPT-4o also failed: {fallback_error}")
                    raise HTTPException(status_code=500, detail=f"Failed to parse LLM response as JSON: {e}")
            else:
                raise HTTPException(status_code=500, detail=f"Failed to parse LLM response as JSON: {e}")

        # Validation - The response should be grouped by exchanges
        logger.info(f"🔍 Validating response structure...")

        if not isinstance(result, dict):
            raise ValueError("Response must be a JSON object")

        # Expected exchanges - at least one should be present
        found_exchanges = []
        total_broker_entries = 0

        for exchange_key, exchange_data in result.items():
            if isinstance(exchange_data, dict):
                found_exchanges.append(exchange_key)

                # Check if this exchange has the expected structure
                if "stocks" in exchange_data or "etfs" in exchange_data:
                    logger.info(f"✅ Found valid exchange data for: {exchange_key}")

                    # Count and validate broker entries
                    for asset_type in ["stocks", "etfs"]:
                        if asset_type in exchange_data and isinstance(exchange_data[asset_type], list):
                            total_broker_entries += len(exchange_data[asset_type])

                            # Validate each row has broker field
                            for row in exchange_data[asset_type]:
                                if not isinstance(row, dict) or "broker" not in row:
                                    logger.warning(f"Invalid row structure in {exchange_key}.{asset_type}")
                                    continue

                                # Check for transaction sizes (optional validation)
                                transaction_sizes = ["250", "500", "1000", "1500", "2000", "2500", "5000", "10000", "50000"]
                                missing_sizes = [size for size in transaction_sizes if size not in row]
                                if missing_sizes:
                                    logger.warning(f"Row for {row.get('broker', 'unknown')} in '{exchange_key}.{asset_type}' missing sizes: {missing_sizes}")

        if not found_exchanges:
            raise ValueError("No valid exchange data found in response")

        logger.info(f"✅ Successfully generated comparison tables for {len(found_exchanges)} exchanges with {total_broker_entries} broker entries")

        # Save the JSON response to output directory
        output_dir = _default_output_dir()
        output_dir.mkdir(parents=True, exist_ok=True)

        # Create filename with timestamp and model name
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_model_name = re.sub(r'[^\w\-.]', '_', model)
        output_filename = f"financial_analysis_{safe_model_name}_{timestamp}.json"
        output_path = output_dir / output_filename

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            logger.info(f"💾 Saved financial analysis to: {output_path}")
        except Exception as save_error:
            logger.warning(f"⚠️  Failed to save JSON response to file: {save_error}")

        # Cache the result
        llm_cache.set(cache_key, result)
        logger.info(f"💾 Cached financial analysis for model: {model}")

        return result

    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON parsing failed: {e}")
        logger.error(f"Response was: {response_text[:500]}")
        raise HTTPException(status_code=500, detail=f"Failed to parse LLM response as JSON: {e}")
    except Exception as e:
        logger.error(f"❌ Failed to generate financial analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate financial analysis: {e}")



@app.get("/brokers")
def list_brokers() -> List[Dict[str, Any]]:
    path = _default_brokers_yaml()
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Brokers file not found: {path}")
    brokers: List[Broker] = load_brokers_from_yaml(path)
    return [b.dict() for b in brokers]


@app.post("/refresh-pdfs")
def refresh_pdfs(
        brokers_to_refresh: Optional[List[str]] = Query(None,
                                                        description="Specific brokers to refresh (if None, refreshes all)"),
        force: bool = Query(False, description="Ignore allowed_to_scrape flag if true"),
        save_dir: Optional[str] = Query(None,
                                        description="Directory to save extracted text (default: data/output/pdf_text)"),
) -> Dict[str, Any]:
    brokers_yaml = _default_brokers_yaml()
    if not brokers_yaml.exists():
        raise HTTPException(status_code=404, detail=f"Brokers file not found: {brokers_yaml}")

    all_brokers: List[Broker] = load_brokers_from_yaml(brokers_yaml)
    brokers_to_process = all_brokers

    if brokers_to_refresh:
        brokers_to_process = [
            b for b in all_brokers
            if b.name.lower() in [br.lower() for br in brokers_to_refresh]
        ]
        if not brokers_to_process:
            raise HTTPException(
                status_code=404,
                detail=f"No matching brokers found. Requested: {brokers_to_refresh}"
            )

    output_dir = Path(save_dir) if save_dir else _default_pdf_text_dir()
    output_dir.mkdir(parents=True, exist_ok=True)

    cleaned_files_count = 0
    for txt_file in output_dir.glob("*.txt"):
        try:
            txt_file.unlink()
            cleaned_files_count += 1
        except OSError as e:
            logger.warning("Error deleting old text file %s: %s", txt_file, e)
    if cleaned_files_count > 0:
        logger.info("Cleaned up %d old text files from %s", cleaned_files_count, output_dir)

    try:
        scraped_records = scrape_fee_records(
            brokers=brokers_to_process,
            force=force,
            pdf_text_dump_dir=output_dir,
            use_playwright=True
        )

        broker_summary = {}
        for record in scraped_records:
            broker_summary.setdefault(record.broker, 0)
            broker_summary[record.broker] += 1

        return {
            "status": "completed",
            "message": "Scraping process finished.",
            "records_found_by_broker": broker_summary,
            "total_records_found": len(scraped_records)
        }

    except Exception as e:
        logger.error("An error occurred during the scraping process.", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An internal error occurred: {e}")


def _default_pdf_text_dir() -> Path:
    """Resolve the PDF text directory path."""
    cwd_path = Path("data") / "output" / "pdf_text"
    if cwd_path.exists():
        return cwd_path
    repo_root = Path(__file__).resolve().parents[3]
    fallback = repo_root / "data" / "output" / "pdf_text"
    return fallback


def _clear_pdf_text_dir(directory: Path, keep: Optional[List[str]] = None) -> None:
    """
    Remove all files and subdirectories in the PDF text directory.
    Optionally keep files named in `keep` (e.g. ['.gitkeep']).
    """
    if not directory.exists():
        return

    keep_set = set(keep or [])
    removed_count = 0

    try:
        for child in directory.iterdir():
            try:
                if child.name in keep_set:
                    continue

                if child.is_dir():
                    shutil.rmtree(child)
                    logger.info(f"🗑️  Removed directory: {child.name}")
                else:
                    child.unlink()
                    logger.info(f"🗑️  Removed file: {child.name}")
                removed_count += 1

            except Exception as exc:
                logger.warning(f"⚠️  Failed to remove {child}: {exc}")

        if removed_count > 0:
            logger.info(f"✅ Cleared {removed_count} old items from PDF text directory")
        else:
            logger.info("📂 PDF text directory was already empty")

    except Exception as exc:
        logger.error(f"❌ Error clearing PDF text directory: {exc}")


@app.get("/cost-analysis/{broker_name}")
def get_broker_cost_analysis(broker_name: str) -> Dict[str, Any]:
    output_dir = _default_output_dir()
    analysis_file = output_dir / "broker_cost_analyses.json"

    if not analysis_file.exists():
        raise HTTPException(
            status_code=404,
            detail="Cost analysis not found. Run generate_exhaustive_summary.py first."
        )

    try:
        with open(analysis_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        if broker_name not in data:
            raise HTTPException(
                status_code=404,
                detail=f"Broker not found: {broker_name}. Available: {', '.join(data.keys())}"
            )

        return {
            "broker": broker_name,
            "analysis": data[broker_name]
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load analysis: {str(exc)}")


@app.get("/summary")
def get_summary() -> str:
    output_dir = _default_output_dir()
    summary_file = output_dir / "exhaustive_cost_charges_summary.md"

    if not summary_file.exists():
        raise HTTPException(
            status_code=404,
            detail="Summary not found. Run generate_exhaustive_summary.py first."
        )

    try:
        with open(summary_file, "r", encoding="utf-8") as f:
            content = f.read()
        return content
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load summary: {str(exc)}")


@app.post("/refresh-and-analyze")
def refresh_and_analyze(
        brokers_to_process: Optional[List[str]] = Query(None,
                                                        description="Specific brokers to analyze (if None, analyzes all)"),
        force: bool = Query(False, description="Ignore allowed_to_scrape flag if true"),
        model: str = Query("gpt-4o", description="LLM model: gpt-4o (default), claude-sonnet-4-20250514, etc."),
) -> Dict[str, Any]:
    """
    Refresh PDFs, extract text, and generate comprehensive cost analysis.
    This endpoint combines /refresh-pdfs with LLM-based analysis generation.

    Supports both OpenAI (gpt-*) and Anthropic (claude-*) models.
    """
    import time

    logger.info("=" * 80)
    logger.info("🚀 REFRESH AND ANALYZE REQUEST")
    logger.info("=" * 80)

    # Step 1: Load brokers
    brokers_yaml = _default_brokers_yaml()
    if not brokers_yaml.exists():
        raise HTTPException(status_code=404, detail=f"Brokers file not found: {brokers_yaml}")

    all_brokers: List[Broker] = load_brokers_from_yaml(brokers_yaml)
    brokers_list = all_brokers

    if brokers_to_process:
        brokers_list = [
            b for b in all_brokers
            if b.name.lower() in [br.lower() for br in brokers_to_process]
        ]
        if not brokers_list:
            raise HTTPException(
                status_code=404,
                detail=f"No matching brokers found. Requested: {brokers_to_process}"
            )

    logger.info(f"📋 Processing {len(brokers_list)} broker(s): {', '.join(b.name for b in brokers_list)}")

    # Step 2: Clear old PDF text files and prepare output directory
    output_dir = _default_pdf_text_dir()

    logger.info("🧹 Clearing old PDF text files...")
    _clear_pdf_text_dir(output_dir, keep=[".gitkeep"])

    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"📥 Downloading PDFs and extracting text to: {output_dir}")

    refresh_start = time.time()
    try:
        scraped_records = scrape_fee_records(
            brokers=brokers_list,
            force=force,
            pdf_text_dump_dir=output_dir,
            use_llm=True,
            llm_model=model,
        )

        refresh_duration = time.time() - refresh_start

        broker_summary = {}
        for record in scraped_records:
            broker_summary.setdefault(record.broker, 0)
            broker_summary[record.broker] += 1

        refresh_results = {
            "status": "completed",
            "duration_seconds": round(refresh_duration, 2),
            "records_found_by_broker": broker_summary,
            "total_records_found": len(scraped_records)
        }

        logger.info(f"✅ PDF refresh completed in {refresh_duration:.2f}s")

    except Exception as e:
        logger.error(f"❌ PDF refresh failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"PDF refresh failed: {e}")

    # Step 3: Load extracted texts
    logger.info("📂 Loading extracted PDF texts...")

    def get_text_filename_for_broker_source(broker_name: str, ds_description: str, url: str) -> str:
        """Recreate the exact filename generated by the scraper."""
        safe_broker_name = re.sub(r'[\s/]+', '_', broker_name)
        safe_desc = re.sub(r'[\s/]+', '_', ds_description or 'document')
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        return f"{safe_broker_name}_{safe_desc}_{url_hash}.txt"

    pdf_texts = {}
    for broker in brokers_list:
        if not broker.data_sources:
            continue

        broker_texts = []
        for ds in broker.data_sources:
            if not ds.url:
                continue

            expected_filename = get_text_filename_for_broker_source(broker.name, ds.description, ds.url)
            text_file_path = output_dir / expected_filename

            if text_file_path.exists():
                try:
                    content = text_file_path.read_text(encoding="utf-8")
                    if content.strip():
                        broker_texts.append({
                            "filename": text_file_path.name,
                            "content": content,
                            "size": len(content)
                        })
                        logger.info(f"  📄 {broker.name}: {text_file_path.name} ({len(content):,} chars)")
                except Exception as e:
                    logger.error(f"  ❌ Failed to read {text_file_path.name}: {e}")

        if broker_texts:
            pdf_texts[broker.name] = broker_texts

    logger.info(f"✅ Loaded texts for {len(pdf_texts)} broker(s)")

    if not pdf_texts:
        raise HTTPException(
            status_code=500,
            detail="No PDF texts extracted. Check broker data sources and allowed_to_scrape flags."
        )

    # Step 4: Run LLM analysis
    logger.info(f"🤖 Running LLM analysis using {model}...")

    all_analyses = {}
    analysis_start = time.time()

    for broker_name, texts in pdf_texts.items():
        combined_text = "\n\n".join(t["content"] for t in texts)
        logger.info(f"  🔍 Analyzing {broker_name} ({len(combined_text):,} chars)...")

        analysis_prompt = f"""Extract ALL broker fees from the following tariffs for {broker_name}.
Return ONLY a valid JSON object with structured fee data.

{combined_text[:15000]}
"""

        system_prompt = "You are a financial analyst. Return ONLY valid JSON, no explanations."

        try:
            # Use unified LLM caller (supports both OpenAI and Claude)
            response_text = _call_llm(model, system_prompt, analysis_prompt, response_format="json")

            if not response_text or not response_text.strip().startswith('{'):
                logger.error(f"  ❌ Invalid response for {broker_name}")
                all_analyses[broker_name] = {"error": "Invalid LLM response"}
            else:
                analysis = json.loads(response_text)
                all_analyses[broker_name] = analysis
                logger.info(f"  ✅ {broker_name} analysis complete")

        except Exception as e:
            logger.error(f"  ❌ Analysis failed for {broker_name}: {e}")
            all_analyses[broker_name] = {"error": str(e)}

    analysis_duration = time.time() - analysis_start
    logger.info(f"✅ LLM analysis completed in {analysis_duration:.2f}s")

    # Step 5: Save results
    json_output_path = _default_output_dir() / "broker_cost_analyses.json"
    logger.info(f"💾 Saving analysis to: {json_output_path}")

    try:
        with open(json_output_path, "w", encoding="utf-8") as f:
            json.dump(all_analyses, f, indent=2, ensure_ascii=False)
        logger.info("✅ Analysis saved successfully")
    except Exception as e:
        logger.error(f"❌ Failed to save analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save analysis: {e}")

    # Return comprehensive results
    logger.info("=" * 80)
    logger.info("✅ REFRESH AND ANALYZE COMPLETE")
    logger.info("=" * 80)

    return {
        "status": "completed",
        "refresh_results": refresh_results,
        "analysis_results": {
            "brokers_analyzed": len(all_analyses),
            "duration_seconds": round(analysis_duration, 2),
            "model_used": model,
            "analyses": all_analyses
        },
        "output_file": str(json_output_path)
    }


# ========================================================================================
# NEWS FLASH ENDPOINTS
# ========================================================================================

@app.post("/news/scrape")
def scrape_news_endpoint(
    brokers_to_scrape: Optional[List[str]] = Query(None, description="Specific brokers to scrape (if None, scrapes all with news_sources)"),
    force: bool = Query(False, description="Force fresh scrape, ignore cache"),
) -> Dict[str, Any]:
    """
    Automatically scrape news from broker websites, RSS feeds, and APIs.

    Set force=True to bypass cache and perform fresh scrape.
    """
    import time
    start_time = time.time()

    try:
        # Check cache first (unless force=True)
        cache_key = FileCache.make_key("news_scrape", ",".join(brokers_to_scrape) if brokers_to_scrape else "all")
        if not force:
            cached = news_cache.get(cache_key)
            if cached:
                logger.info(f"📦 Returning cached news scrape results")
                cached["duration_seconds"] = round(time.time() - start_time, 2)
                cached["from_cache"] = True
                return cached

        # Load brokers configuration
        brokers_yaml = _default_brokers_yaml()
        if not brokers_yaml.exists():
            raise HTTPException(status_code=404, detail=f"Brokers file not found: {brokers_yaml}")

        all_brokers = load_brokers_from_yaml(brokers_yaml)

        # Filter brokers if specified
        if brokers_to_scrape:
            brokers_to_process = [
                b for b in all_brokers
                if b.name.lower() in [name.lower() for name in brokers_to_scrape]
            ]
            if not brokers_to_process:
                raise HTTPException(
                    status_code=404,
                    detail=f"No brokers found matching: {brokers_to_scrape}"
                )
        else:
            # Only process brokers that have news_sources configured
            brokers_to_process = [b for b in all_brokers if b.news_sources]

        if not brokers_to_process:
            response = {
                "status": "no_news_sources",
                "message": "No brokers have news_sources configured",
                "brokers_checked": len(all_brokers),
                "duration_seconds": round(time.time() - start_time, 2)
            }
            return response

        logger.info("=" * 80)
        logger.info("📰 AUTOMATED NEWS SCRAPING STARTED")
        logger.info("=" * 80)
        logger.info(f"🎯 Brokers to process: {[b.name for b in brokers_to_process]} (force={force})")

        # Perform the scraping
        scraped_news = scrape_broker_news(brokers_to_process, force=force)

        # Group results by broker for summary
        broker_summary = {}
        error_summary = {}

        for broker in brokers_to_process:
            broker_news_count = len([n for n in scraped_news if n.broker == broker.name])
            if broker_news_count > 0:
                broker_summary[broker.name] = broker_news_count

            # Check for any news sources that might have failed
            if broker.news_sources:
                sources_attempted = len([s for s in broker.news_sources if s.allowed_to_scrape or force])
                if sources_attempted > 0 and broker_news_count == 0:
                    error_summary[broker.name] = f"No news found from {sources_attempted} source(s)"

        duration = round(time.time() - start_time, 2)

        logger.info("=" * 80)
        logger.info("✅ AUTOMATED NEWS SCRAPING COMPLETED")
        logger.info("=" * 80)
        logger.info(f"📊 Total news items: {len(scraped_news)}")
        logger.info(f"⏱️ Duration: {duration}s")

        # Convert news items to response format
        news_items_response = [
            {
                "broker": news.broker,
                "title": news.title,
                "summary": news.summary[:150] + "..." if len(news.summary) > 150 else news.summary,
                "url": news.url,
                "date": news.date,
                "source": news.source
            }
            for news in scraped_news
        ]

        response = {
            "status": "success",
            "message": f"Successfully scraped {len(scraped_news)} news items from {len(broker_summary)} brokers",
            "news_by_broker": broker_summary,
            "news_items": news_items_response,  # Add actual news items with URLs
            "total_scraped": len(scraped_news),
            "brokers_with_news": len(broker_summary),
            "brokers_processed": len(brokers_to_process),
            "duration_seconds": duration,
            "from_cache": False
        }

        if error_summary:
            response["warnings"] = error_summary

        # Cache the result
        news_cache.set(cache_key, response)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ News scraping failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"News scraping failed: {str(e)}")


@app.post("/news", status_code=201)
def add_news_flash(news: NewsFlashRequest) -> Dict[str, str]:
    """
    Add a new news flash for a broker.
    """
    try:
        # Convert Pydantic model to NewsFlash dataclass
        news_flash = NewsFlash(
            broker=news.broker,
            title=news.title,
            summary=news.summary,
            url=str(news.url) if news.url else None,
            date=news.date,
            source=news.source,
            notes=news.notes
        )

        save_news_flash(news_flash)

        return {
            "status": "success",
            "message": f"News flash added for {news.broker}",
            "broker": news.broker,
            "title": news.title
        }
    except Exception as e:
        logger.error(f"❌ Failed to save news flash: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save news flash: {str(e)}")


@app.get("/news", response_model=List[NewsFlashResponse])
def get_all_news() -> List[NewsFlashResponse]:
    """
    Get all news flashes, sorted by creation date (newest first).
    """
    try:
        news_list = load_news()
        return [
            NewsFlashResponse(
                broker=news.broker,
                title=news.title,
                summary=news.summary,
                url=news.url,
                date=news.date,
                source=news.source,
                notes=news.notes,
                created_at=news.created_at
            )
            for news in news_list
        ]
    except Exception as e:
        logger.error(f"❌ Failed to load news: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load news: {str(e)}")


@app.get("/news/broker/{broker_name}", response_model=List[NewsFlashResponse])
def get_news_for_broker(broker_name: str) -> List[NewsFlashResponse]:
    """
    Get all news flashes for a specific broker.
    """
    try:
        news_list = get_news_by_broker(broker_name)
        return [
            NewsFlashResponse(
                broker=news.broker,
                title=news.title,
                summary=news.summary,
                url=news.url,
                date=news.date,
                source=news.source,
                notes=news.notes,
                created_at=news.created_at
            )
            for news in news_list
        ]
    except Exception as e:
        logger.error(f"❌ Failed to load news for {broker_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load news for broker: {str(e)}")


@app.get("/news/recent", response_model=List[NewsFlashResponse])
def get_recent_news_endpoint(limit: int = Query(10, description="Maximum number of news items to return")) -> List[NewsFlashResponse]:
    """
    Get the most recent news flashes across all brokers.
    """
    try:
        news_list = get_recent_news(limit)
        return [
            NewsFlashResponse(
                broker=news.broker,
                title=news.title,
                summary=news.summary,
                url=news.url,
                date=news.date,
                source=news.source,
                notes=news.notes,
                created_at=news.created_at
            )
            for news in news_list
        ]
    except Exception as e:
        logger.error(f"❌ Failed to load recent news: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load recent news: {str(e)}")


@app.get("/news/statistics")
def get_news_stats() -> Dict[str, Any]:
    """
    Get statistics about the news data.
    """
    try:
        return get_news_statistics()
    except Exception as e:
        logger.error(f"❌ Failed to get news statistics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get news statistics: {str(e)}")


@app.delete("/news")
def delete_news_endpoint(request: NewsDeleteRequest) -> Dict[str, str]:
    """
    Delete a specific news flash by broker and title.
    """
    try:
        deleted = delete_news_flash(request.broker, request.title)

        if deleted:
            return {
                "status": "success",
                "message": f"News flash deleted for {request.broker}: {request.title}"
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"News flash not found for {request.broker}: {request.title}"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete news flash: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete news flash: {str(e)}")
