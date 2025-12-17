# Test Directory Organization

This directory contains all test files and debugging scripts for the be-invest project, organized into logical subdirectories.

## Directory Structure

### 📁 `/tests` (Root)
Core functionality tests that should run in CI/CD:
- `test_cache.py` - Caching system tests
- `test_data_quality_validation.py` - Data validation tests  
- `test_import_fix.py` - Module import tests
- `test_llm_extraction_validation.py` - LLM extraction tests
- `enhanced_llm_prompts.py` - Enhanced prompting logic
- `quick_test.py` - Quick sanity checks

### 📁 `/debug`
Debugging scripts for troubleshooting specific issues:
- `debug_broker_loading.py` - Debug broker configuration loading
- `debug_degiro_scraping.py` - Debug Degiro scraping issues
- `debug_ing_decoding.py` - Debug ING content decoding problems
- `debug_ing_scraping.py` - Debug ING scraping restrictions

### 📁 `/scraping`
News scraping related tests and validations:
- `test_degiro_fixed.py` - Test fixed Degiro scraping configuration
- `test_endpoint_caching.py` - Test API endpoint caching
- `test_improved_scraping.py` - Test scraping improvements
- `test_ing_revolut_fix.py` - Test ING/Revolut scraping fixes
- `test_news_scraping.py` - General news scraping tests
- `test_revolut_*.py` - Various Revolut scraping tests
- `test_rss_first_strategy.py` - RSS-first scraping strategy tests

### 📁 `/url_fixes`
URL handling and extraction fixes:
- `test_url_extraction_fix.py` - Test URL extraction improvements
- `test_url_fix_simple.py` - Simple URL fixing logic tests

### 📁 `/analysis`
Analysis and diagnostic scripts:
- `test_ing_analysis.py` - Comprehensive ING scraping analysis
- `test_scraping_disabled_analysis.py` - Analysis of disabled scraping sources

## Running Tests

### Core Tests (CI/CD)
```bash
# Run core functionality tests
python -m pytest tests/test_*.py -v

# Run specific test
python -m pytest tests/test_cache.py -v
```

### Debug Scripts
```bash
# Run debugging scripts manually
python tests/debug/debug_degiro_scraping.py
python tests/debug/debug_ing_scraping.py
```

### Scraping Tests
```bash
# Test specific broker scraping
python tests/scraping/test_degiro_fixed.py
python tests/scraping/test_revolut_news.py
```

### Analysis Scripts
```bash
# Run analysis for troubleshooting
python tests/analysis/test_ing_analysis.py
```

## Notes

- Debug scripts are meant for manual execution during development
- Scraping tests may require network access and can be flaky
- Core tests should be stable and suitable for automated testing
- Analysis scripts provide detailed reports on scraping issues

## Recent Cleanup (December 17, 2025)

All test files were moved from the project root to this organized structure to maintain a clean project root directory while preserving all debugging and testing capabilities.
