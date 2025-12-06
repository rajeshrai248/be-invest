from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional, Dict, Any
from pathlib import Path
from io import BytesIO
from datetime import datetime
import logging
import json
import hashlib
import re
import os

from ..config_loader import load_brokers_from_yaml
from ..models import Broker
from ..sources.scrape import scrape_fee_records, _fetch_url
from ..sources.llm_extract import extract_fee_records_via_llm

app = FastAPI(title="be-invest PDF Text API", version="0.1.0")
logger = logging.getLogger(__name__)

# Add CORS middleware to support OPTIONS requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods including OPTIONS
    allow_headers=["*"],  # Allow all headers
)

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

                # Clean up any markdown formatting Claude might add
                if response_format == "json" and response_text.strip().startswith("```"):
                    # Remove markdown code blocks
                    lines = response_text.strip().split("\n")
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].startswith("```"):
                        lines = lines[:-1]
                    response_text = "\n".join(lines).strip()

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

@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}

@app.get("/cost-analysis", response_class=JSONResponse)
def get_cost_analysis() -> Dict[str, Any]:
    """Get the comprehensive cost and charges analysis for all brokers."""
    return _get_cost_analysis_data()

@app.get("/cost-comparison-tables", response_class=JSONResponse)
def get_cost_comparison_tables(
    model: str = Query("gpt-4o", description="LLM to use: gpt-4o (default), claude-sonnet-4-20250514, gpt-4-turbo")
) -> Dict[str, Any]:
    """
    Generates three cost comparison tables for ETFs, Stocks, and Bonds
    based on the existing broker_cost_analyses.json data.

    Supports both OpenAI (gpt-*) and Anthropic (claude-*) models.

    Role: You are a Financial Data Analyst specializing in the Belgian investment market.

    Task: Conduct a pricing analysis of Belgian brokerage platforms and output the data
    into three distinct matrix tables.
    """
    cost_data = _get_cost_analysis_data()
    
    # Extract broker names
    broker_names = [name for name in cost_data.keys() if "error" not in cost_data.get(name, {})]

    if not broker_names:
        raise HTTPException(
            status_code=404,
            detail="No valid broker data found. Run generate_exhaustive_summary.py first."
        )

    # Prepare detailed instructions for the LLM
    prompt = f"""You are a Financial Data Analyst specializing in the Belgian investment market.

TASK: Conduct a precise pricing analysis of Belgian brokerage platforms and output the data into three distinct matrix tables.

BROKERS TO ANALYZE: {', '.join(broker_names)}

TRANSACTION SIZES (in EUR): 250, 500, 1000, 1500, 2000, 2500, 5000, 10000, 50000

BROKER DATA:
{json.dumps(cost_data, indent=2)}

CRITICAL INSTRUCTIONS:

1. **Parse Tiered Fee Structures Correctly**:
   
   Example from Keytrade Bank stocks (brussels_amsterdam_paris):
   ```
   "0_to_€_250": "€ 2.45"
   "€_250.01_to_€_2,500": "€ 5.95"
   "€_2,500.01_to_€_10,000": "€ 14.95"
   "each_additional_€_10,000": "+ € 7.50"
   ```
   
   Calculations:
   - €250: €2.45 (tier 1)
   - €500: €5.95 (tier 2)
   - €1000: €5.95 (tier 2)
   - €1500: €5.95 (tier 2)
   - €2000: €5.95 (tier 2)
   - €2500: €5.95 (tier 2, upper bound)
   - €5000: €14.95 (tier 3)
   - €10000: €14.95 (tier 3, upper bound)
   - €50000: €14.95 + ((50000-10000)/10000)*7.50 = 14.95 + 30.00 = 44.95

2. **Parse Percentage + Minimum Fee Structures**:
   
   Example from ING Self Invest stocks (via web/app on Euronext Brussels/Amsterdam/Paris):
   ```
   "via_web_and_app": "0.35%"
   "min_via_web_and_app": "€1"
   ```
   
   Calculations:
   - €250: max(250 * 0.0035, 1) = max(0.875, 1) = €1.00
   - €500: max(500 * 0.0035, 1) = max(1.75, 1) = €1.75
   - €1000: max(1000 * 0.0035, 1) = max(3.50, 1) = €3.50
   - €1500: max(1500 * 0.0035, 1) = €5.25
   - €2000: max(2000 * 0.0035, 1) = €7.00
   - €2500: max(2500 * 0.0035, 1) = €8.75
   - €5000: max(5000 * 0.0035, 1) = €17.50
   - €10000: max(10000 * 0.0035, 1) = €35.00
   - €50000: max(50000 * 0.0035, 1) = €175.00

3. **Product-Specific Fee Selection**:
   - **Stocks**: Look for "stock_markets_online", "shares", "equities", "aandelen" keys
   - **ETFs**: Look for "ETF", "trackers", "etfs" keys. Use standard fees, not free selections
   - **Bonds**: Look for "bonds", "obligaties", "bond_markets" keys
   
   For ING Self Invest:
   - Stocks/ETFs: Use "shares_stock_exchange_traded_funds_trackers" → "euronext_brussels_amsterdam_paris" → "via_web_and_app"
   - Bonds: Use "bonds" section with 0.50% fee and €50 minimum

4. **Handle Different Data Formats**:
   - Comma decimals: "€ 2,5" → 2.50
   - Ranges with slashes: "€ 15/€ 10.000 (max. € 50)" → means €15 per €10,000, capped at €50
   - Percentages: "0.35%" → 0.0035 multiplier
   - Multiple tiers: Apply the correct tier based on transaction amount

5. **Currency Conversion**:
   - 1 USD = 0.92 EUR
   - 1 GBP = 1.17 EUR
   - Convert all results to EUR

6. **Avoid Common Mistakes**:
   - ❌ DO NOT use the minimum fee for all transaction sizes
   - ❌ DO NOT create duplicate broker rows
   - ❌ DO NOT ignore percentage calculations
   - ❌ DO NOT use tier 1 fees for all amounts
   - ✅ DO calculate each transaction size individually
   - ✅ DO apply the correct tier for each amount
   - ✅ DO use max(percentage_fee, minimum_fee) when both exist

7. **Output Format**: Return ONLY a valid JSON object with this EXACT structure:
{{
  "etfs": [
    {{"broker": "ING Self Invest", "250": 1.0, "500": 1.75, "1000": 3.5, "1500": 5.25, "2000": 7.0, "2500": 8.75, "5000": 17.5, "10000": 35.0, "50000": 175.0}},
    {{"broker": "Bolero", "250": 2.5, "500": 5.0, "1000": 5.0, "1500": 7.5, "2000": 7.5, "2500": 7.5, "5000": 10.0, "10000": 15.0, "50000": 50.0}},
    {{"broker": "Keytrade Bank", "250": 2.45, "500": 5.95, "1000": 5.95, "1500": 5.95, "2000": 5.95, "2500": 5.95, "5000": 14.95, "10000": 14.95, "50000": 44.95}}
  ],
  "stocks": [
    {{"broker": "ING Self Invest", "250": 1.0, "500": 1.75, ...}},
    {{"broker": "Bolero", "250": 2.5, "500": 5.0, ...}},
    {{"broker": "Keytrade Bank", "250": 2.45, "500": 5.95, ...}}
  ],
  "bonds": [
    {{"broker": "ING Self Invest", "250": 50.0, "500": 50.0, ...}},
    {{"broker": "Bolero", "250": null, ...}},
    {{"broker": "Keytrade Bank", "250": 29.95, ...}}
  ],
  "notes": {{
    "ING Self Invest": {{"stocks": "0.35% with €1 minimum via web/app", "etfs": "Same as stocks", "bonds": "0.50% with €50 minimum"}},
    "Keytrade Bank": {{"stocks": "Tiered pricing: €2.45 up to €250, €5.95 up to €2,500, €14.95 up to €10,000, then +€7.50 per €10,000"}},
    "Bolero": {{"stocks": "Tiered pricing with max €50", "bonds": "Primary market only: €25 per €10,000"}}
  }}
}}

8. **Broker Order**: List each broker EXACTLY ONCE. Sort alphabetically with ING Self Invest first.

Return ONLY the JSON object. No explanations, no apologies, no markdown formatting."""

    system_prompt = "You are a precise financial data analyst. You calculate exact transaction costs and return only valid JSON with numeric values."

    try:
        logger.info(f"📊 Analyzing {len(broker_names)} brokers: {', '.join(broker_names)}")

        # Call the unified LLM helper
        response_text = _call_llm(model, system_prompt, prompt, response_format="json")

        if not response_text:
            raise HTTPException(status_code=500, detail="LLM returned an empty response.")

        # Parse and validate response
        result = json.loads(response_text)

        # Validation
        required_keys = ["etfs", "stocks", "bonds"]
        for key in required_keys:
            if key not in result:
                raise ValueError(f"Missing required key: {key}")
            if not isinstance(result[key], list):
                raise ValueError(f"Key '{key}' must be a list")

        # Validate structure of each table
        transaction_sizes = ["250", "500", "1000", "1500", "2000", "2500", "5000", "10000", "50000"]
        for table_name in required_keys:
            for row in result[table_name]:
                if "broker" not in row:
                    raise ValueError(f"Row in '{table_name}' missing 'broker' field")
                for size in transaction_sizes:
                    if size not in row:
                        logger.warning(f"Row for {row['broker']} in '{table_name}' missing size '{size}'")

        logger.info(f"✅ Successfully generated comparison tables for {len(result.get('etfs', []))} brokers")

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
    model: str = Query("gpt-4o", description="LLM to use: gpt-4o (default), claude-sonnet-4-20250514")
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
    cost_data = _get_cost_analysis_data()

    # Extract broker names
    broker_names = [name for name in cost_data.keys() if "error" not in cost_data.get(name, {})]

    if not broker_names:
        raise HTTPException(
            status_code=404,
            detail="No valid broker data found. Run generate_exhaustive_summary.py first."
        )

    # Prepare comprehensive prompt for financial analysis
    system_prompt = """You are a senior financial analyst and investment journalist specializing in Belgian financial markets. 
You create structured, data-driven content for modern financial applications."""

    # Create explicit list of all brokers
    broker_list = ", ".join(broker_names)

    user_prompt = f"""Generate a comprehensive financial analysis comparing ALL Belgian investment brokers.

CRITICAL: You MUST include ALL {len(broker_names)} brokers in your analysis:
{broker_list}

BROKER DATA:
{json.dumps(cost_data, indent=2)}

Return a SIMPLE JSON object with this structure (KEEP ALL STRINGS SHORT - MAX 150 CHARS):

{{
  "metadata": {{
    "title": "Short catchy title (max 80 chars)",
    "subtitle": "Key insight (max 100 chars)",
    "publishDate": "{datetime.now().strftime('%B %d, %Y')}",
    "readingTimeMinutes": 12
  }},
  "executiveSummary": [
    "Finding 1 (max 150 chars)",
    "Finding 2 (max 150 chars)",
    "Finding 3 (max 150 chars)",
    "Finding 4 (max 150 chars)"
  ],
  "brokerComparisons": [
    {{
      "broker": "DEGIRO Belgium",
      "overallRating": 5,
      "etfRating": 5,
      "stockRating": 5,
      "bondRating": 4,
      "pros": ["Pro 1", "Pro 2", "Pro 3"],
      "cons": ["Con 1", "Con 2"],
      "bestFor": ["Use case 1", "Use case 2"]
    }},
    ...repeat for ALL {len(broker_names)} brokers
  ],
  "categoryWinners": {{
    "etfs": {{"winner": "Broker name", "reason": "Short reason"}},
    "stocks": {{"winner": "Broker name", "reason": "Short reason"}},
    "bonds": {{"winner": "Broker name", "reason": "Short reason"}},
    "overall": {{"winner": "Broker name", "reason": "Short reason"}}
  }},
  "costComparison": {{
    "monthly500ETF": [
      {{"broker": "DEGIRO Belgium", "annualCost": 0}},
      ...all {len(broker_names)} brokers
    ],
    "activeTrader": [
      {{"broker": "DEGIRO Belgium", "annualCost": 100}},
      ...all {len(broker_names)} brokers
    ]
  }}
}}

CRITICAL RULES:
1. Keep EVERY string under 150 characters
2. Use simple arrays, not nested objects
3. Include ALL {len(broker_names)} brokers in brokerComparisons
4. Include ALL {len(broker_names)} brokers in costComparison arrays
5. Return ONLY valid JSON - no markdown, no code blocks
6. Ensure all brackets close properly"""

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

        # Validate required keys for simplified structure
        required_keys = ["metadata", "executiveSummary", "brokerComparisons", "categoryWinners", "costComparison"]
        for key in required_keys:
            if key not in result:
                logger.warning(f"⚠️ Missing key in response: {key}")

        # Validate that all brokers are included
        if "brokerComparisons" in result:
            included_brokers = [b.get("broker", "") for b in result["brokerComparisons"]]
            missing_brokers = [b for b in broker_names if b not in included_brokers]
            if missing_brokers:
                logger.warning(f"⚠️ Missing brokers in response: {', '.join(missing_brokers)}")
                logger.warning(f"   Expected {len(broker_names)} brokers, got {len(included_brokers)}")

        logger.info(f"✅ Financial analysis generated successfully")
        logger.info(f"   Brokers included: {len(result.get('brokerComparisons', []))}/{len(broker_names)}")

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to generate financial analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate financial analysis: {e}")

# The rest of the server file remains the same...
@app.get("/brokers")
def list_brokers() -> List[Dict[str, Any]]:
    path = _default_brokers_yaml()
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Brokers file not found: {path}")
    brokers: List[Broker] = load_brokers_from_yaml(path)
    return [b.dict() for b in brokers]

@app.post("/refresh-pdfs")
def refresh_pdfs(
    brokers_to_refresh: Optional[List[str]] = Query(None, description="Specific brokers to refresh (if None, refreshes all)"),
    force: bool = Query(False, description="Ignore allowed_to_scrape flag if true"),
    save_dir: Optional[str] = Query(None, description="Directory to save extracted text (default: data/output/pdf_text)"),
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
    brokers_to_process: Optional[List[str]] = Query(None, description="Specific brokers to analyze (if None, analyzes all)"),
    force: bool = Query(False, description="Ignore allowed_to_scrape flag if true"),
    model: str = Query("gpt-4o", description="LLM model: gpt-4o (default), claude-sonnet-4-20250514, etc."),
) -> Dict[str, Any]:
    """
    Refresh PDFs, extract text, and generate comprehensive cost analysis.
    This endpoint combines /refresh-pdfs with LLM-based analysis generation.

    Supports both OpenAI (gpt-*) and Anthropic (claude-*) models.
    """
    import time
    from pathlib import Path

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

    # Step 2: Refresh PDFs and extract text
    output_dir = _default_pdf_text_dir()
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"📥 Downloading PDFs and extracting text to: {output_dir}")

    refresh_start = time.time()
    try:
        scraped_records = scrape_fee_records(
            brokers=brokers_list,
            force=force,
            pdf_text_dump_dir=output_dir,
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

