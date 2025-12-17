# Data Sources

> Comprehensive documentation of broker data sources, extraction methods, and data quality considerations.

## Overview

BE-Invest aggregates broker fee data from multiple sources using various extraction methods. This document details the data sources, extraction strategies, and quality assurance measures for each supported broker.

## Data Source Types

### PDF Documents
Most brokers publish comprehensive fee schedules as PDF documents.

**Advantages:**
- Complete fee information
- Official and authoritative  
- Structured format
- Legally binding information

**Challenges:**
- Text extraction complexity
- Format variations
- Multi-language content
- Large file sizes

### Web Pages
Some brokers maintain fee information on dedicated web pages.

**Advantages:**
- Real-time updates
- Mobile-friendly
- Interactive calculators
- Easy access

**Challenges:**
- Dynamic content
- Anti-scraping measures
- Frequent layout changes
- Incomplete information

### API Access
Limited brokers provide direct API access to fee data.

**Advantages:**
- Structured data
- Real-time updates
- High reliability
- Easy integration

**Challenges:**
- Rare availability
- Authentication requirements
- Rate limiting
- API changes

## Broker-Specific Data Sources

### Bolero

**Primary Source**: PDF Fee Schedule
- **URL**: `https://www.bolero.be/uploads/media/667ecf0aabd9a/101-tarieven-nl.pdf`
- **Language**: Dutch
- **Update Frequency**: Quarterly
- **Format**: Structured PDF with tables
- **Scraping Allowed**: No (manual download required)

**Fee Structure**:
- Flat fee model: €15 per transaction
- Applies to all instruments (stocks, ETFs, bonds)
- No minimum or maximum thresholds
- Annual custody fee: 0.15%

**Extraction Notes**:
- Clear tabular format
- Consistent terminology
- Multiple instrument types covered
- Includes custody fee information

**Data Quality Issues**:
- None currently identified
- High extraction confidence

### Keytrade Bank

**Primary Source**: PDF Tariff Overview
- **URL**: `https://assets.ctfassets.net/pniyec9izm4q/5VbvGvZ0r8C2Pk8wKneOak/ba9cdc0b8f5427a728eb68ee617dc520/Tarifs_en2025.pdf`
- **Language**: French/English
- **Update Frequency**: Annually
- **Format**: Detailed PDF with multiple sections
- **Scraping Allowed**: No

**Fee Structure**:
- Percentage-based fees
- ETFs: 0.19% (minimum €2.50)
- Stocks: 0.35% (minimum €7.50)
- No custody fees

**Extraction Notes**:
- Multi-language document
- Percentage rates clearly stated
- Minimum fee thresholds specified
- Options trading covered

**Data Quality Issues**:
- None currently identified
- Clear fee structure presentation

### Degiro Belgium

**Primary Source**: Dutch Fee Overview PDF
- **URL**: `https://www.degiro.nl/data/pdf/Tarievenoverzicht.pdf`
- **Language**: Dutch
- **Update Frequency**: As needed
- **Format**: Comprehensive PDF
- **Scraping Allowed**: No

**Fee Structure**:
- Composite fee model
- Stocks: €2 + 0.026% + €1 handling fee
- ETFs: €1 handling fee only (for core selection)
- No custody fees for stocks/ETFs

**Extraction Notes**:
- Complex fee structure with multiple components
- Handling fees often overlooked
- Different rates for different markets
- Core ETF selection with free trading

**Data Quality Issues**:
- **Critical**: Missing €1 handling fee in extraction
- Composite fees require careful parsing
- Market-specific variations

**LLM Extraction Improvements**:
```
CRITICAL: Degiro has a €1 handling fee that is often missed.
Look for 'handling fee', 'verwerkingskosten', or similar terms.
Total cost = commission + €1 handling fee.
```

### ING Self Invest

**Primary Source**: English Fee Schedule PDF
- **URL**: `https://assets.ing.com/m/2dbfdfb6dd2baf82/original/TariefRoerendeWaardeNewEN.pdf`
- **Language**: English
- **Update Frequency**: Annually
- **Format**: Clean PDF format
- **Scraping Allowed**: No

**Fee Structure**:
- Flat fee model: €7.50 per transaction
- Applies to stocks and ETFs
- Annual custody fee: 0.24%
- Minimum/maximum custody fees apply

**Extraction Notes**:
- English language simplifies extraction
- Clear flat fee structure
- Custody fee calculations detailed
- Bond trading separate pricing

**Data Quality Issues**:
- None currently identified
- Extraction reliable

### Rebel (formerly Belfius)

**Primary Source**: MIFID Tariff Schedule PDF
- **URL**: `https://www.belfius.be/imagingservlet/GetDocument?id=TARIFBELPART_NL&src=mifid`
- **Language**: Dutch/French
- **Update Frequency**: Annually
- **Format**: Regulatory document (MIFID)
- **Scraping Allowed**: No

**Fee Structure**:
- Tiered pricing based on trade size
- Brussels stocks: €3 (up to €2,500), then percentage
- Paris/Amsterdam: Different rates
- ETFs: 0.25% of trade value

**Extraction Notes**:
- Multiple market pricing
- Tiered structure complexity
- MIFID regulatory format
- Multiple language sections

**Data Quality Issues**:
- **Critical**: Confusion between Brussels vs Paris/Amsterdam pricing
- Wrong market data being extracted
- Tiered structure complexity

**LLM Extraction Improvements**:
```
CRITICAL: Use Euronext Brussels pricing, NOT Paris/Amsterdam.
Look for 'Brussels', 'Bruxelles', 'XBRU' market codes.
For stocks up to €2.5k: €3. Verify market-specific pricing.
```

### Revolut

**Primary Source**: Help Documentation Web Page
- **URL**: `https://help.revolut.com/help/wealth/stocks/trading-stocks/trading-fees/what-fees-will-i-be-charged-for-my-trading/`
- **Language**: English
- **Update Frequency**: Real-time
- **Format**: HTML help page
- **Scraping Allowed**: Yes (with Playwright)

**Fee Structure**:
- Subscription-based model
- Different rates for different plans
- Zero commission with limitations
- Currency conversion fees

**Extraction Notes**:
- Web-based content
- Dynamic loading (requires Playwright)
- Plan-specific variations
- Frequent updates

**Data Quality Issues**:
- Incomplete coverage (plan variations)
- Dynamic content challenges
- Currency conversion complexity

## Extraction Methods

### LLM-Powered Extraction

**Primary Method**: OpenAI GPT-4o / Anthropic Claude 3
- Intelligent text processing
- Context-aware extraction
- Handles complex formatting
- Multi-language support

**Process Flow**:
1. **Document Retrieval**: Download or scrape source documents
2. **Text Extraction**: Convert PDF/HTML to plain text
3. **Text Preprocessing**: Clean and focus on fee-related content
4. **LLM Processing**: Use enhanced prompts for extraction
5. **Data Validation**: Validate against expected patterns
6. **Post-processing**: Clean and normalize extracted data

**Enhanced Prompts**:
```python
# Broker-specific instructions
broker_instructions = {
    "Degiro Belgium": """
    CRITICAL: Degiro has a €1 handling fee that is often missed.
    Look for 'handling fee', 'verwerkingskosten', or similar terms.
    Total cost = commission + €1 handling fee.
    """,
    
    "Rebel": """
    CRITICAL: Use Euronext Brussels pricing, NOT Paris/Amsterdam.
    Look for 'Brussels', 'Bruxelles', 'XBRU' market codes.
    For stocks up to €2.5k: €3.
    """
}
```

### Manual Data Entry (Fallback)

**When Used**:
- LLM extraction fails
- Complex document formats
- Verification and validation
- Initial data seeding

**Process**:
1. Manual document review
2. CSV data entry with validation
3. Quality assurance checks
4. Integration with main dataset

### Hybrid Approach

**Combination Strategy**:
- LLM extraction for initial processing
- Manual validation for quality assurance
- Automated testing against expected values
- Regular re-extraction to detect changes

## Data Quality Assurance

### Validation Framework

**Automated Tests**:
```python
# Expected fee validation
def test_bolero_etf_fees():
    """Test Bolero ETF fees match expected values."""
    records = extract_fees("Bolero")
    etf_record = find_etf_record(records)
    assert etf_record.base_fee == 15.0  # €15 flat fee
    assert calculate_cost(etf_record, 5000) == 15.0
```

**Quality Metrics**:
- Extraction success rate
- Validation error count
- Data completeness percentage
- Update detection accuracy

### Known Issues and Solutions

#### Issue 1: Missing Handling Fees (Degiro)
**Problem**: LLM often misses the €1 handling fee
**Solution**: Enhanced prompts with specific keyword detection
**Status**: Improved but requires ongoing monitoring

#### Issue 2: Market Confusion (Rebel)
**Problem**: Extracting Paris/Amsterdam rates instead of Brussels
**Solution**: Market-specific keyword detection in prompts
**Status**: Partially resolved, validation tests in place

#### Issue 3: Complex Fee Structures
**Problem**: Composite fees (€X + Y%) not properly parsed
**Solution**: Post-processing to handle composite fee formats
**Status**: Resolved with regex-based parsing

### Update Detection

**Change Monitoring**:
- Document hash comparison
- Content-based change detection
- Scheduled re-extraction
- Alert system for significant changes

**Update Workflow**:
1. Daily hash check for document changes
2. Weekly full re-extraction
3. Validation against previous results
4. Alert on significant deviations
5. Manual review of changes

## Data Freshness

### Update Schedules

| Broker | Source Type | Update Frequency | Last Updated | Next Check |
|--------|-------------|------------------|--------------|------------|
| Bolero | PDF | Quarterly | 2025-12-01 | 2026-03-01 |
| Keytrade Bank | PDF | Annually | 2025-01-01 | 2026-01-01 |
| Degiro Belgium | PDF | As needed | 2025-11-15 | 2026-01-15 |
| ING Self Invest | PDF | Annually | 2025-01-01 | 2026-01-01 |
| Rebel | PDF | Annually | 2025-01-01 | 2026-01-01 |
| Revolut | Web | Real-time | 2025-12-09 | Daily |

### Cache Strategy

**Caching Levels**:
1. **Document Cache**: Raw PDF/HTML content (24 hours)
2. **Extraction Cache**: LLM results (1 week)  
3. **Analysis Cache**: Computed analyses (1 hour)
4. **API Cache**: Response data (30 minutes)

**Cache Invalidation**:
- Time-based expiration
- Content hash changes
- Manual invalidation
- Error-based invalidation

## Data Privacy and Compliance

### Legal Considerations

**Public Information**:
- All data sources are publicly available
- No personal information collected
- Fee schedules are public documents
- No login credentials required

**Web Scraping Compliance**:
- Respect robots.txt files
- Reasonable request rates
- No circumvention of access controls
- Focus on publicly available information

### Data Usage Rights

**Fair Use**:
- Informational and comparison purposes
- No commercial redistribution of raw data
- Attribution to original sources
- Educational and research applications

## Technical Implementation

### PDF Text Extraction

```python
def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text from PDF using pdfminer."""
    from pdfminer.high_level import extract_text
    
    text = extract_text(pdf_path)
    # Clean and preprocess text
    return clean_extracted_text(text)
```

### Web Scraping (Revolut)

```python
def scrape_revolut_fees() -> str:
    """Scrape Revolut fees using Playwright."""
    from playwright.sync_api import sync_playwright
    
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(revolut_url)
        content = page.content()
        browser.close()
        
    return extract_fee_content(content)
```

### LLM Integration

```python
def extract_via_llm(
    text: str,
    broker: str,
    model: str = "gpt-4o"
) -> List[FeeRecord]:
    """Extract fees using LLM."""
    prompt = create_enhanced_prompt(broker, text)
    
    response = openai.ChatCompletion.create(
        model=model,
        messages=prompt,
        temperature=0.0
    )
    
    return parse_llm_response(response.choices[0].message.content)
```

## Future Improvements

### Planned Enhancements

1. **Real-time Monitoring**
   - Webhook notifications for document changes
   - Automated re-extraction on updates
   - Dashboard for data freshness status

2. **Advanced LLM Features**
   - Multi-modal processing (images in PDFs)
   - Table structure recognition
   - Confidence scoring for extractions

3. **Data Quality**
   - ML-based anomaly detection
   - Automated test case generation
   - Historical trend analysis

4. **Coverage Expansion**
   - Additional Belgian brokers
   - European broker expansion
   - Alternative data sources (APIs)

### Research Areas

- **Document Understanding**: Improved PDF layout analysis
- **Multilingual Processing**: Better French/Dutch support  
- **Structured Extraction**: Direct table extraction from PDFs
- **Change Detection**: Semantic change detection vs textual

This data sources documentation provides the foundation for understanding how BE-Invest collects and processes broker fee information. Regular updates ensure accuracy and completeness of the fee comparison data.
