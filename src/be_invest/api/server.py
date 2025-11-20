from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional, Dict, Any
from pathlib import Path
from io import BytesIO
from datetime import datetime
import logging
import json
import hashlib

from ..config_loader import load_brokers_from_yaml
from ..models import Broker
from ..sources.scrape import _fetch_url  # reuse existing fetch logic
from ..sources.llm_extract import extract_fee_records_via_openai

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

HAS_MULTIPART = False  # Deprecated: we now accept raw body for uploads


def pdf_bytes_to_text(data: bytes, *, method: str = "auto") -> str:
    """Extract text from PDF bytes.

    Strategies:
    1. PyMuPDF (fitz) if available and method in {auto, fitz}
    2. pdfminer.six as fallback
    Returns concatenated page texts; does not truncate.
    """
    if not data or not isinstance(data, (bytes, bytearray)):
        raise ValueError("No PDF data provided")
    if not data.startswith(b"%PDF"):
        raise ValueError("Content is not a PDF (missing %PDF header)")

    text = ""
    errors: List[str] = []

    if method in {"auto", "fitz"}:
        try:  # PyMuPDF path
            import fitz  # type: ignore
            with fitz.open(stream=data, filetype="pdf") as doc:
                page_texts = []
                for page in doc:
                    try:
                        page_texts.append(page.get_text("text"))
                    except Exception as p_exc:
                        errors.append(f"page_error:{p_exc}")
                text = "\n".join(page_texts)
        except Exception as exc:
            if method == "fitz":
                raise RuntimeError(f"PyMuPDF extraction failed: {exc}") from exc
            errors.append(f"fitz_failed:{exc}")

    if not text:  # fallback to pdfminer
        try:
            from pdfminer.high_level import extract_text  # type: ignore
            text = extract_text(BytesIO(data)) or ""
        except Exception as exc:
            raise RuntimeError("Both PyMuPDF and pdfminer.six failed to extract text: " + str(exc)) from exc

    # Normalize excessive whitespace (optional light cleanup)
    lines = [ln.rstrip() for ln in text.splitlines()]
    cleaned = "\n".join(lines)
    if not cleaned.strip():
        logger.warning("PDF extraction produced empty text. Errors: %s", ";".join(errors))
    return cleaned


def _default_brokers_yaml() -> Path:
    """Resolve the brokers.yaml path.

    Tries CWD "data/brokers.yaml" first. If missing, tries repository root
    relative to this file (../../.. / data / brokers.yaml).
    """
    cwd_path = Path("data") / "brokers.yaml"
    if cwd_path.exists():
        return cwd_path
    # server.py is at src/be_invest/api/server.py -> repo root is parents[3]
    repo_root = Path(__file__).resolve().parents[3]
    fallback = repo_root / "data" / "brokers.yaml"
    return fallback


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/brokers")
def list_brokers() -> List[Dict[str, Any]]:
    path = _default_brokers_yaml()
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Brokers file not found: {path}")
    brokers: List[Broker] = load_brokers_from_yaml(path)
    result: List[Dict[str, Any]] = []
    for b in brokers:
        result.append(
            {
                "name": b.name,
                "website": b.website,
                "country": b.country,
                "instruments": b.instruments,
                "data_sources": [
                    {
                        "type": ds.type,
                        "url": ds.url,
                        "allowed_to_scrape": ds.allowed_to_scrape,
                        "description": ds.description,
                    }
                    for ds in getattr(b, "data_sources", []) or []
                ],
            }
        )
    return result


@app.get("/pdf-text", response_class=PlainTextResponse)
def pdf_text_from_url(url: str, method: str = Query("auto", pattern="^(auto|fitz|pdfminer)$")) -> str:
    data = _fetch_url(url)
    if not data:
        raise HTTPException(status_code=502, detail="Failed to fetch URL or empty response")
    try:
        text = pdf_bytes_to_text(data, method=method)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return text


@app.post("/pdf-to-text", response_class=PlainTextResponse)
async def pdf_text_from_body(request: Request, method: str = Query("auto", pattern="^(auto|fitz|pdfminer)$")) -> str:
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="Empty request body")
    try:
        text = pdf_bytes_to_text(body, method=method)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return text


@app.get("/brokers/{broker_name}/pdf-text")
def broker_pdf_text(
    broker_name: str,
    force: bool = Query(False, description="Ignore allowed_to_scrape flag if true"),
    dump_dir: Optional[str] = Query(None, description="Optional folder to write extracted .txt files"),
) -> Dict[str, Any]:
    path = _default_brokers_yaml()
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Brokers file not found: {path}")
    brokers: List[Broker] = load_brokers_from_yaml(path)
    target = next((b for b in brokers if b.name.lower() == broker_name.lower()), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"Broker not found: {broker_name}")

    outputs: List[Dict[str, Any]] = []
    for ds in getattr(target, "data_sources", []) or []:
        url = ds.url or ""
        if not url:
            continue
        if (ds.allowed_to_scrape is False) and not force:
            outputs.append({"url": url, "skipped": True, "reason": "allowed_to_scrape=false"})
            continue
        data = _fetch_url(url)
        if not data:
            outputs.append({"url": url, "error": "fetch_failed"})
            continue
        try:
            text = pdf_bytes_to_text(data, method="auto")
        except Exception as exc:
            outputs.append({"url": url, "error": str(exc)})
            continue
        if dump_dir:
            try:
                out_dir = Path(dump_dir)
                out_dir.mkdir(parents=True, exist_ok=True)
                safe_name = "".join(ch if ch.isalnum() else "_" for ch in Path(url).name)
                out_path = out_dir / f"{safe_name}.txt"
                out_path.write_text(text, encoding="utf-8")
            except Exception:
                pass
        outputs.append({"url": url, "chars": len(text), "text": text})

    return {"broker": target.name, "results": outputs}


@app.post("/brokers/analyze-fees")
def analyze_all_broker_fees(
    model: str = Query("gpt-5", description="LLM model: gpt-5 (latest), gpt-4o, gpt-4-turbo"),
    force: bool = Query(False, description="Ignore allowed_to_scrape if true"),
    api_key_env: str = Query("OPENAI_API_KEY", description="Environment variable for API key"),
    temperature: float = Query(1, description="LLM temperature (GPT-5 only supports 1)"),
    max_tokens: int = Query(2000, description="Max output tokens per chunk"),
) -> Dict[str, Any]:
    """Extract detailed cost and charges from all brokers using latest LLM models.

    Returns structured fee records for each broker's PDF sources.
    """
    path = _default_brokers_yaml()
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Brokers file not found: {path}")
    brokers: List[Broker] = load_brokers_from_yaml(path)

    results: Dict[str, Any] = {"model": model, "brokers": []}

    for broker in brokers:
        broker_result: Dict[str, Any] = {
            "name": broker.name,
            "sources": [],
            "fee_records": [],
        }

        for ds in getattr(broker, "data_sources", []) or []:
            url = ds.url or ""
            if not url:
                continue
            if (ds.allowed_to_scrape is False) and not force:
                broker_result["sources"].append(
                    {"url": url, "skipped": True, "reason": "allowed_to_scrape=false"}
                )
                continue

            # Fetch and extract PDF text
            data = _fetch_url(url)
            if not data:
                broker_result["sources"].append({"url": url, "error": "fetch_failed"})
                continue

            try:
                text = pdf_bytes_to_text(data, method="auto")
            except Exception as exc:
                broker_result["sources"].append({"url": url, "error": str(exc)})
                continue

            if not text.strip():
                broker_result["sources"].append(
                    {"url": url, "error": "empty_text_after_extraction"}
                )
                continue

            broker_result["sources"].append(
                {"url": url, "chars": len(text), "status": "extracted"}
            )

            # Run LLM extraction
            try:
                fee_records = extract_fee_records_via_openai(
                    text,
                    broker=broker.name,
                    source_url=url,
                    model=model,
                    api_key_env=api_key_env,
                    llm_cache_dir=None,  # disable cache for API calls
                    max_output_tokens=max_tokens,
                    temperature=temperature,
                    strict_mode=False,
                    focus_fee_lines=True,
                )
                for record in fee_records:
                    broker_result["fee_records"].append(
                        {
                            "broker": record.broker,
                            "instrument_type": record.instrument_type,
                            "order_channel": record.order_channel,
                            "base_fee": record.base_fee,
                            "variable_fee": record.variable_fee,
                            "currency": record.currency,
                            "source": record.source,
                            "notes": record.notes,
                        }
                    )
            except Exception as exc:
                broker_result["sources"].append(
                    {"url": url, "llm_error": str(exc)}
                )

        results["brokers"].append(broker_result)

    return results


# ============================================================================
# Cost & Charges Analysis Endpoints
# ============================================================================

def _default_output_dir() -> Path:
    """Resolve the output directory path."""
    cwd_path = Path("data") / "output"
    if cwd_path.exists():
        return cwd_path
    repo_root = Path(__file__).resolve().parents[3]
    fallback = repo_root / "data" / "output"
    return fallback


def _default_pdf_text_dir() -> Path:
    """Resolve the PDF text directory path."""
    cwd_path = Path("data") / "output" / "pdf_text"
    if cwd_path.exists():
        return cwd_path
    repo_root = Path(__file__).resolve().parents[3]
    fallback = repo_root / "data" / "output" / "pdf_text"
    return fallback


@app.get("/cost-analysis")
def get_cost_analysis() -> Dict[str, Any]:
    """Get the comprehensive cost and charges analysis for all brokers.

    Returns the latest broker_cost_analyses.json data.
    """
    output_dir = _default_output_dir()
    analysis_file = output_dir / "broker_cost_analyses.json"

    if not analysis_file.exists():
        raise HTTPException(
            status_code=404,
            detail="Cost analysis not found. Run generate_exhaustive_summary.py first."
        )

    try:
        import json
        with open(analysis_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load analysis: {str(exc)}")


@app.get("/cost-analysis/{broker_name}")
def get_broker_cost_analysis(broker_name: str) -> Dict[str, Any]:
    """Get cost and charges analysis for a specific broker.

    Args:
        broker_name: Name of the broker (e.g., Bolero, Keytrade Bank, ING Self Invest)

    Returns:
        Detailed cost structure for the broker
    """
    output_dir = _default_output_dir()
    analysis_file = output_dir / "broker_cost_analyses.json"

    if not analysis_file.exists():
        raise HTTPException(
            status_code=404,
            detail="Cost analysis not found. Run generate_exhaustive_summary.py first."
        )

    try:
        import json
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
    """Get the comprehensive markdown summary of broker costs and charges.

    Returns the latest exhaustive_cost_charges_summary.md as plain text.
    """
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


@app.post("/refresh-pdfs")
def refresh_pdfs(
    brokers_to_refresh: Optional[List[str]] = Query(None, description="Specific brokers to refresh (if None, refreshes all)"),
    force: bool = Query(False, description="Ignore allowed_to_scrape flag if true"),
    save_dir: Optional[str] = Query(None, description="Directory to save extracted text (default: data/output/pdf_text)"),
) -> Dict[str, Any]:
    """Refresh PDF downloads and text extraction for all or specific brokers.

    This endpoint:
    1. Downloads PDFs from broker data sources
    2. Extracts text from PDFs
    3. Saves extracted text files
    4. Returns statistics on what was processed

    Args:
        brokers_to_refresh: List of broker names to refresh (None = all)
        force: Override allowed_to_scrape restrictions
        save_dir: Directory to save PDF text files

    Returns:
        Dictionary with refresh statistics and results
    """
    brokers_yaml = _default_brokers_yaml()
    if not brokers_yaml.exists():
        raise HTTPException(status_code=404, detail=f"Brokers file not found: {brokers_yaml}")

    brokers: List[Broker] = load_brokers_from_yaml(brokers_yaml)

    if brokers_to_refresh:
        # Filter to requested brokers
        brokers = [
            b for b in brokers
            if b.name.lower() in [br.lower() for br in brokers_to_refresh]
        ]

        if not brokers:
            raise HTTPException(
                status_code=404,
                detail=f"No matching brokers found. Requested: {brokers_to_refresh}"
            )

    # Determine output directory
    if save_dir:
        output_dir = Path(save_dir)
    else:
        output_dir = _default_pdf_text_dir()

    output_dir.mkdir(parents=True, exist_ok=True)

    results: Dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "brokers_refreshed": [],
        "total_pdfs_processed": 0,
        "total_errors": 0,
        "total_chars_extracted": 0,
    }

    for broker in brokers:
        broker_result: Dict[str, Any] = {
            "name": broker.name,
            "sources": [],
            "pdfs_processed": 0,
            "chars_extracted": 0,
        }

        for ds in getattr(broker, "data_sources", []) or []:
            url = ds.url or ""
            if not url:
                continue

            # Check scraping permission
            if (ds.allowed_to_scrape is False) and not force:
                broker_result["sources"].append({
                    "url": url,
                    "status": "skipped",
                    "reason": "allowed_to_scrape=false"
                })
                continue

            # Download PDF
            try:
                data = _fetch_url(url)
                if not data:
                    broker_result["sources"].append({
                        "url": url,
                        "status": "error",
                        "error": "fetch_failed"
                    })
                    results["total_errors"] += 1
                    continue
            except Exception as exc:
                broker_result["sources"].append({
                    "url": url,
                    "status": "error",
                    "error": f"fetch_error: {str(exc)}"
                })
                results["total_errors"] += 1
                continue

            # Extract text
            try:
                text = pdf_bytes_to_text(data, method="auto")
                if not text.strip():
                    broker_result["sources"].append({
                        "url": url,
                        "status": "error",
                        "error": "empty_text_after_extraction"
                    })
                    results["total_errors"] += 1
                    continue
            except Exception as exc:
                broker_result["sources"].append({
                    "url": url,
                    "status": "error",
                    "error": f"extraction_error: {str(exc)}"
                })
                results["total_errors"] += 1
                continue

            # Save extracted text
            try:
                # Create a safe filename
                pdf_filename = Path(url).name or "document.pdf"
                safe_name = "".join(ch if ch.isalnum() or ch in ".-_" else "_" for ch in pdf_filename)

                # Generate unique filename with hash
                import hashlib
                url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
                text_filename = f"{safe_name}_{url_hash}.txt"

                text_path = output_dir / text_filename
                text_path.write_text(text, encoding="utf-8")

                broker_result["sources"].append({
                    "url": url,
                    "status": "extracted",
                    "filename": text_filename,
                    "chars": len(text)
                })

                broker_result["pdfs_processed"] += 1
                broker_result["chars_extracted"] += len(text)
                results["total_pdfs_processed"] += 1
                results["total_chars_extracted"] += len(text)

            except Exception as exc:
                broker_result["sources"].append({
                    "url": url,
                    "status": "error",
                    "error": f"save_error: {str(exc)}"
                })
                results["total_errors"] += 1

        results["brokers_refreshed"].append(broker_result)

    return results


@app.post("/refresh-and-analyze")
def refresh_and_analyze(
    brokers_to_process: Optional[List[str]] = Query(None, description="Specific brokers to process"),
    force: bool = Query(False, description="Ignore allowed_to_scrape flag"),
    model: str = Query("gpt-5", description="LLM model: gpt-5 (latest available)"),
    temperature: float = Query(1, description="LLM temperature (GPT-5 only supports 1)"),
    max_tokens: int = Query(4000, description="Max tokens per response"),
) -> Dict[str, Any]:
    """Refresh PDFs, extract text, analyze with LLM, and regenerate summary.

    This is a comprehensive endpoint that:
    1. Downloads and extracts PDFs
    2. Runs LLM analysis on extracted text
    3. Saves updated cost analyses
    4. Returns the complete analysis result

    Args:
        brokers_to_process: Specific brokers to process (None = all)
        force: Override scraping restrictions
        model: LLM model (gpt-4o, gpt-4o-mini, etc.)
        temperature: LLM temperature
        max_tokens: Max output tokens

    Returns:
        Combined refresh and analysis results
    """
    import json
    from datetime import datetime

    brokers_yaml = _default_brokers_yaml()
    if not brokers_yaml.exists():
        raise HTTPException(status_code=404, detail=f"Brokers file not found")

    output_dir = _default_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Refresh PDFs
    pdf_refresh = refresh_pdfs(brokers_to_process, force)

    # Step 2: Analyze fees
    brokers: List[Broker] = load_brokers_from_yaml(brokers_yaml)

    if brokers_to_process:
        brokers = [
            b for b in brokers
            if b.name.lower() in [br.lower() for br in brokers_to_process]
        ]
    analyses: Dict[str, Any] = {}
    analysis_errors: List[str] = []

    for broker in brokers:
        broker_analyses = {"name": broker.name, "sources": []}

        for ds in getattr(broker, "data_sources", []) or []:
            url = ds.url or ""
            if not url or ((ds.allowed_to_scrape is False) and not force):
                continue

            try:
                # Fetch and extract
                data = _fetch_url(url)
                if not data:
                    continue

                text = pdf_bytes_to_text(data, method="auto")
                if not text.strip():
                    continue

                # Run LLM analysis
                fee_records = extract_fee_records_via_openai(
                    text,
                    broker=broker.name,
                    source_url=url,
                    model=model,
                    api_key_env="OPENAI_API_KEY",
                    llm_cache_dir=None,
                    max_output_tokens=max_tokens,
                    temperature=temperature,
                    strict_mode=False,
                    focus_fee_lines=True,
                )

                if fee_records:
                    broker_analyses["sources"].append({
                        "url": url,
                        "records": len(fee_records)
                    })

            except Exception as exc:
                analysis_errors.append(f"{broker.name}: {str(exc)}")

        analyses[broker.name] = broker_analyses

    # Step 3: Save updated analyses
    try:
        analyses_file = output_dir / "broker_cost_analyses.json"
        with open(analyses_file, "w", encoding="utf-8") as f:
            json.dump(analyses, f, indent=2, ensure_ascii=False)
    except Exception as exc:
        analysis_errors.append(f"Failed to save analyses: {str(exc)}")

    return {
        "timestamp": datetime.now().isoformat(),
        "refresh_results": pdf_refresh,
        "analysis_results": analyses,
        "errors": analysis_errors,
        "message": "Refresh and analysis complete. Run /generate-summary to create markdown report."
    }
