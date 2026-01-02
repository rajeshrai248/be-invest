# LLM Integration

> Comprehensive guide to Large Language Model integration for intelligent broker fee extraction.

## Overview

BE-Invest leverages advanced Large Language Models (LLMs) to automatically extract broker fee information from complex documents like PDFs and web pages. This eliminates the need for manual data entry while maintaining high accuracy through sophisticated validation and quality assurance.

## Supported LLM Providers

### OpenAI

**Recommended Models**:
- **GPT-4o**: Best overall performance, handles complex documents
- **GPT-4 Turbo**: Good balance of cost and performance
- **GPT-3.5 Turbo**: Cost-effective for simple extractions

**Configuration**:
```python
# Environment variable
export OPENAI_API_KEY="your-openai-api-key"

# Usage in code
from openai import OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

response = client.chat.completions.create(
    model="gpt-4o",
    messages=prompt_messages,
    temperature=0.0,  # Deterministic output
    max_tokens=2000
)
```

### Anthropic

**Recommended Models**:
- **Claude 3 Opus**: Highest accuracy for complex financial documents
- **Claude 3 Haiku**: Fast and cost-effective for simple extractions

**Configuration**:
```python
# Environment variable
export ANTHROPIC_API_KEY="your-anthropic-api-key"

# Usage in code
from anthropic import Anthropic
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

response = client.messages.create(
    model="claude-3-opus-20240229",
    system=system_prompt,
    messages=[{"role": "user", "content": user_prompt}],
    temperature=0.0,
    max_tokens=2000
)
```

## Prompt Engineering

### System Prompt Design

The system prompt establishes the LLM's role and behavior:

```python
ENHANCED_SYSTEM_PROMPT = """
You are a precision financial data extraction specialist. Your task is to extract 
ALL fee components with absolute accuracy. Pay special attention to:

1. HANDLING FEES - Often overlooked but critical (e.g., €1 handling fee)
2. MARKET-SPECIFIC PRICING - Different fees for different exchanges
3. COMPOSITE FEES - Combinations of flat + percentage fees  
4. CUSTODY FEES - Annual portfolio management fees
5. FEE TIERS - Different fees based on trade size

Return ONLY valid JSON array. Never invent data. If unclear, use null.
"""
```

### Broker-Specific Instructions

Each broker requires specialized extraction logic:

```python
BROKER_SPECIFIC_INSTRUCTIONS = {
    "Bolero": """
    CRITICAL: Bolero charges €15 for trades, not €10.
    Look for the correct tier structure and verify the 5k trade cost is €15.
    """,
    
    "Degiro Belgium": """
    CRITICAL: Degiro has a €1 handling fee that is often missed.
    Look for 'handling fee', 'verwerkingskosten', or similar terms.
    Total cost = commission + €1 handling fee.
    """,
    
    "Rebel": """
    CRITICAL: Use Euronext Brussels pricing, NOT Paris/Amsterdam.
    Look for 'Brussels', 'Bruxelles', 'XBRU' market codes.
    For stocks up to €2.5k: €3. Verify market-specific pricing.
    """
}
```

### Output Schema Definition

Structured JSON schema ensures consistent extraction:

```python
JSON_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["broker", "instrument_type", "base_fee", "variable_fee"],
        "properties": {
            "broker": {"type": "string"},
            "instrument_type": {
                "type": "string",
                "enum": ["Equities", "ETFs", "Options", "Bonds", "Funds"]
            },
            "order_channel": {
                "type": "string", 
                "enum": ["Online Platform", "Phone", "Branch", "Other"],
                "default": "Online Platform"
            },
            "base_fee": {
                "type": ["number", "null"],
                "description": "Fixed fee component in EUR"
            },
            "variable_fee": {
                "type": ["string", "null"],
                "description": "Percentage or tiered fee description"
            },
            "handling_fee": {
                "type": ["number", "null"],
                "description": "Separate handling/processing fee"
            },
            "market": {
                "type": ["string", "null"],
                "description": "Specific exchange (e.g., Euronext Brussels)"
            },
            "fee_structure_type": {
                "type": ["string", "null"],
                "enum": ["flat", "percentage", "tiered", "composite"]
            }
        }
    }
}
```

## Text Preprocessing

### Document Chunking

Large documents are split into manageable chunks:

```python
def split_semantic_chunks(
    text: str, 
    max_len: int = 18000,
    max_chunks: int = 8
) -> List[str]:
    """Split text into semantic chunks based on fee-related headers."""
    
    # Find fee-related section headers
    header_keywords = [
        "tarif", "fee", "commission", "kosten", "charges", "pricing"
    ]
    
    lines = text.split('\n')
    header_indices = []
    
    for i, line in enumerate(lines):
        if any(keyword in line.lower() for keyword in header_keywords):
            header_indices.append(i)
    
    # Create chunks based on headers
    chunks = []
    for idx, start in enumerate(header_indices):
        end = header_indices[idx + 1] if idx + 1 < len(header_indices) else len(lines)
        segment = '\n'.join(lines[start:end])
        
        if len(segment) > max_len:
            # Further split large segments
            for i in range(0, len(segment), max_len):
                chunks.append(segment[i:i + max_len])
        else:
            chunks.append(segment)
    
    return chunks[:max_chunks]
```

### Content Focusing

Extract only fee-related content to improve accuracy:

```python
def create_focused_text(text: str, max_lines: int = 500) -> str:
    """Focus on fee-related content using keyword scoring."""
    
    lines = text.split('\n')
    scored_lines = []
    
    for i, line in enumerate(lines):
        score = 0
        line_lower = line.lower()
        
        # Primary fee indicators (high score)
        primary_keywords = ["tarif", "fee", "commission", "kosten", "charges"]
        for keyword in primary_keywords:
            if keyword in line_lower:
                score += 10
        
        # Currency and percentage indicators
        if any(symbol in line_lower for symbol in ["€", "%", "eur"]):
            score += 5
            
        # Market indicators
        if any(market in line_lower for market in ["brussels", "euronext"]):
            score += 3
            
        scored_lines.append((score, i, line))
    
    # Sort by score and take top lines
    scored_lines.sort(key=lambda x: x[0], reverse=True)
    top_lines = [line for _, _, line in scored_lines[:max_lines]]
    
    return '\n'.join(top_lines)
```

## Extraction Pipeline

### Main Extraction Function

```python
def extract_fee_records_via_llm(
    text: str,
    broker: str,
    source_url: str,
    *,
    model: str = "claude-sonnet-4-20250514",
    llm_cache_dir: Optional[Path] = None,
    max_output_tokens: int = 2000,
    temperature: float = 0.0,
    chunk_chars: int = 18000,
    max_chunks: int = 8,
    strict_mode: bool = False,
    focus_fee_lines: bool = True,
    max_focus_lines: int = 450
) -> List[FeeRecord]:
    """Extract fee records using LLM with enhanced prompts."""
    
    if not text.strip():
        return []
    
    # Determine provider and check API key
    provider = "anthropic" if model.startswith("claude") else "openai"
    api_key_env = "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY"
    api_key = os.getenv(api_key_env)
    
    if not api_key:
        logger.warning(f"{provider.title()} API key not found")
        return []
    
    # Setup caching
    cache = SimpleCache(llm_cache_dir, ttl_seconds=0) if llm_cache_dir else None
    cache_key = f"llm:{model}:{broker}:{hash_key(text, model, broker)}"
    
    # Check cache first
    if cache and cache.get(cache_key):
        try:
            cached_data = json.loads(cache.get(cache_key).decode("utf-8"))
            return [r for r in (coerce_record(o) for o in cached_data) if r]
        except Exception:
            pass  # Cache miss
    
    # Initialize LLM client
    client = get_llm_client(provider, api_key)
    
    # Process text in chunks
    raw_text = text.strip()
    chunks = split_semantic_chunks(raw_text, chunk_chars, max_chunks)
    
    all_records = []
    
    for chunk in chunks:
        # Focus on fee-related content
        if focus_fee_lines:
            focused_text = create_focused_text(chunk, max_focus_lines)
        else:
            focused_text = chunk
        
        # Create enhanced prompt
        messages = create_enhanced_prompt(broker, source_url, focused_text)
        
        # Call LLM
        try:
            content = call_llm(client, provider, model, messages, temperature, max_output_tokens)
            
            # Parse and validate response
            parsed_records = parse_llm_response(content)
            validated_records = validate_extraction_result(parsed_records, broker)
            
            all_records.extend(validated_records)
            
        except Exception as exc:
            logger.warning(f"LLM extraction failed for {broker}: {exc}")
            continue
    
    # Deduplicate results
    deduplicated = deduplicate_records(all_records)
    
    # Cache successful results
    if cache and deduplicated:
        try:
            cache_data = json.dumps([asdict(record) for record in deduplicated])
            cache.put(cache_key, cache_data.encode("utf-8"))
        except Exception:
            pass
    
    return deduplicated
```

### Response Parsing and Validation

```python
def parse_llm_response(content: str) -> List[Dict[str, Any]]:
    """Parse LLM response and extract JSON array."""
    
    try:
        # Try direct JSON parsing
        parsed = json.loads(content)
    except json.JSONDecodeError:
        # Extract JSON array from response
        start, end = content.find("["), content.rfind("]")
        if start != -1 and end != -1:
            try:
                parsed = json.loads(content[start:end + 1])
            except json.JSONDecodeError:
                logger.error(f"Failed to parse LLM response: {content[:200]}...")
                return []
        else:
            logger.error(f"No JSON array found in response: {content[:200]}...")
            return []
    
    # Handle wrapped responses
    if isinstance(parsed, dict) and "results" in parsed:
        parsed = parsed.get("results", [])
    
    if not isinstance(parsed, list):
        logger.error(f"Expected list, got {type(parsed)}")
        return []
    
    return parsed

def validate_extraction_result(
    records: List[Dict[str, Any]], 
    broker: str
) -> List[FeeRecord]:
    """Validate and clean extraction results."""
    
    validated = []
    
    for record in records:
        if not isinstance(record, dict):
            continue
        
        # Required field validation
        required_fields = ["broker", "instrument_type", "base_fee", "variable_fee"]
        if not all(field in record for field in required_fields):
            continue
        
        # Clean and normalize data
        cleaned = clean_record(record, broker)
        
        # Convert to FeeRecord
        try:
            fee_record = FeeRecord(**cleaned)
            validated.append(fee_record)
        except Exception as e:
            logger.warning(f"Failed to create FeeRecord: {e}")
            continue
    
    return validated
```

## Error Handling and Recovery

### Common LLM Errors

```python
class LLMExtractionError(Exception):
    """Base exception for LLM extraction errors."""
    pass

class APIKeyError(LLMExtractionError):
    """API key not configured or invalid."""
    pass

class ModelNotAvailableError(LLMExtractionError):
    """Requested model not available."""
    pass

class ExtractionTimeoutError(LLMExtractionError):
    """LLM request timed out."""
    pass

def handle_llm_errors(func):
    """Decorator to handle common LLM errors."""
    
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except openai.AuthenticationError:
            raise APIKeyError("Invalid OpenAI API key")
        except openai.RateLimitError:
            logger.warning("Rate limit hit, waiting...")
            time.sleep(60)  # Wait 1 minute
            return func(*args, **kwargs)  # Retry
        except openai.ServiceUnavailableError:
            logger.error("OpenAI service unavailable")
            raise LLMExtractionError("LLM service temporarily unavailable")
        except Exception as e:
            logger.error(f"Unexpected LLM error: {e}")
            raise LLMExtractionError(f"Extraction failed: {e}")
    
    return wrapper
```

### Fallback Strategies

```python
def extract_with_fallback(
    text: str,
    broker: str,
    source_url: str
) -> List[FeeRecord]:
    """Extract with fallback to different models/providers."""
    
    # Try primary model first
    try:
        return extract_fee_records_via_llm(
            text, broker, source_url, model="claude-sonnet-4-20250514"
        )
    except APIKeyError:
        logger.info("OpenAI not available, trying Anthropic...")
        
    # Fallback to Anthropic
    try:
        return extract_fee_records_via_llm(
            text, broker, source_url, model="claude-3-haiku-20240307"
        )
    except APIKeyError:
        logger.warning("No LLM providers available")
        
    # Final fallback to manual extraction prompt
    logger.info("Falling back to manual extraction")
    return []
```

## Performance Optimization

### Caching Strategy

```python
class LLMCache:
    """Intelligent caching for LLM results."""
    
    def __init__(self, cache_dir: Path, ttl_hours: int = 24):
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_hours * 3600
        
    def get_cache_key(self, text: str, model: str, broker: str) -> str:
        """Generate cache key from content hash."""
        content = f"{model}\n{broker}\n{text}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    def is_cached(self, cache_key: str) -> bool:
        """Check if result is cached and not expired."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        if not cache_file.exists():
            return False
            
        # Check expiration
        mtime = cache_file.stat().st_mtime
        age = time.time() - mtime
        
        return age < self.ttl_seconds
    
    def get(self, cache_key: str) -> Optional[List[FeeRecord]]:
        """Retrieve cached result."""
        if not self.is_cached(cache_key):
            return None
            
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
            return [FeeRecord(**record) for record in data]
        except Exception as e:
            logger.warning(f"Cache read error: {e}")
            return None
    
    def put(self, cache_key: str, records: List[FeeRecord]):
        """Cache extraction result."""
        self.cache_dir.mkdir(exist_ok=True)
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        try:
            data = [asdict(record) for record in records]
            with open(cache_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Cache write error: {e}")
```

### Batch Processing

```python
async def extract_multiple_brokers(
    broker_documents: Dict[str, str],
    model: str = "claude-sonnet-4-20250514",
    max_concurrent: int = 3
) -> Dict[str, List[FeeRecord]]:
    """Extract fees for multiple brokers concurrently."""
    
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def extract_single(broker: str, text: str):
        async with semaphore:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                extract_fee_records_via_llm,
                text, broker, f"batch_{broker}", model
            )
    
    tasks = [
        extract_single(broker, text) 
        for broker, text in broker_documents.items()
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    return {
        broker: result if not isinstance(result, Exception) else []
        for broker, result in zip(broker_documents.keys(), results)
    }
```

## Quality Assurance

### Validation Tests

```python
def validate_extraction_quality(
    records: List[FeeRecord], 
    broker: str
) -> List[str]:
    """Validate extraction quality against known patterns."""
    
    issues = []
    
    # Check for minimum expected records
    if len(records) == 0:
        issues.append(f"No records extracted for {broker}")
        return issues
    
    # Broker-specific validations
    if broker == "Bolero":
        etf_records = [r for r in records if r.instrument_type == "ETFs"]
        if etf_records and etf_records[0].base_fee != 15.0:
            issues.append(f"Bolero ETF fee should be €15, got €{etf_records[0].base_fee}")
    
    elif broker == "Degiro Belgium":
        for record in records:
            if record.base_fee is not None and record.base_fee < 1.0:
                issues.append(f"Degiro missing €1 handling fee for {record.instrument_type}")
    
    elif broker == "Rebel":
        stock_records = [r for r in records if r.instrument_type == "Equities"]
        for record in stock_records:
            if record.notes and ("Paris" in record.notes or "Amsterdam" in record.notes):
                if "Brussels" not in record.notes:
                    issues.append("Rebel using Paris/Amsterdam data instead of Brussels")
    
    # General validations
    for record in records:
        if record.base_fee is None and record.variable_fee is None:
            issues.append(f"Record missing both base and variable fees: {record.instrument_type}")
        
        if record.currency not in ["EUR", "USD"]:
            issues.append(f"Unexpected currency: {record.currency}")
    
    return issues
```

### Monitoring and Alerting

```python
class ExtractionMonitor:
    """Monitor LLM extraction quality and performance."""
    
    def __init__(self):
        self.metrics = defaultdict(list)
    
    def record_extraction(
        self, 
        broker: str, 
        success: bool, 
        record_count: int,
        validation_issues: List[str],
        duration: float
    ):
        """Record extraction metrics."""
        self.metrics[broker].append({
            'timestamp': time.time(),
            'success': success,
            'record_count': record_count,
            'issue_count': len(validation_issues),
            'duration': duration
        })
    
    def get_quality_report(self, broker: str) -> Dict[str, Any]:
        """Generate quality report for broker."""
        if broker not in self.metrics:
            return {'error': 'No data available'}
        
        data = self.metrics[broker]
        recent_data = [d for d in data if time.time() - d['timestamp'] < 86400]  # Last 24h
        
        return {
            'success_rate': sum(d['success'] for d in recent_data) / len(recent_data),
            'avg_records': sum(d['record_count'] for d in recent_data) / len(recent_data),
            'avg_issues': sum(d['issue_count'] for d in recent_data) / len(recent_data),
            'avg_duration': sum(d['duration'] for d in recent_data) / len(recent_data),
            'total_extractions': len(recent_data)
        }
```

## Cost Management

### API Cost Tracking

```python
class CostTracker:
    """Track LLM API usage and costs."""
    
    def __init__(self):
        self.usage_log = []
    
    def log_usage(
        self, 
        model: str, 
        input_tokens: int, 
        output_tokens: int,
        cost: float
    ):
        """Log API usage."""
        self.usage_log.append({
            'timestamp': time.time(),
            'model': model,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'cost': cost
        })
    
    def get_daily_cost(self, date: str = None) -> float:
        """Get total cost for specific date."""
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        day_start = datetime.strptime(date, '%Y-%m-%d').timestamp()
        day_end = day_start + 86400
        
        day_usage = [
            u for u in self.usage_log 
            if day_start <= u['timestamp'] < day_end
        ]
        
        return sum(u['cost'] for u in day_usage)
    
    def get_cost_by_broker(self) -> Dict[str, float]:
        """Get cost breakdown by broker."""
        # Implementation depends on how broker info is stored
        pass
```

### Cost Optimization

```python
def optimize_extraction_cost(
    text: str,
    broker: str,
    budget_limit: float = 0.10  # $0.10 per extraction
) -> List[FeeRecord]:
    """Extract with cost optimization."""
    
    # Try cheaper model first
    try:
        records = extract_fee_records_via_llm(
            text, broker, "", model="gpt-3.5-turbo"
        )
        
        # Validate quality
        issues = validate_extraction_quality(records, broker)
        
        if len(issues) == 0:
            return records  # Success with cheap model
        
    except Exception as e:
        logger.info(f"Cheap model failed: {e}")
    
    # Fall back to expensive model if needed
    logger.info("Using expensive model for better quality")
    return extract_fee_records_via_llm(
        text, broker, "", model="claude-sonnet-4-20250514"
    )
```

This comprehensive LLM integration guide provides the foundation for implementing and maintaining intelligent broker fee extraction. The system balances accuracy, performance, and cost while providing robust error handling and quality assurance.
