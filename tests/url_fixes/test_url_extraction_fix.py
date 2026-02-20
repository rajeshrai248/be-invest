#!/usr/bin/env python
"""
Test the URL extraction fix for Degiro blog URLs.
"""

import sys
from urllib.parse import urljoin

# Setup path
sys.path.append('src')

def test_url_extraction():
    """Test the fixed URL extraction logic."""

    print("🧪 Testing URL extraction fix...")

    # Import the updated function
    from be_invest.sources.news_scrape import NewsScraper

    scraper = NewsScraper()
    base_url = "https://www.degiro.nl/blog/"

    # Test cases that might cause duplication
    test_cases = [
        ("blog/top-sp500-etfs", "https://www.degiro.nl/blog/top-sp500-etfs"),  # Should remove duplicate 'blog'
        ("/blog/top-sp500-etfs", "https://www.degiro.nl/blog/top-sp500-etfs"),  # Root-relative
        ("https://www.degiro.nl/blog/article", "https://www.degiro.nl/blog/article"),  # Absolute
        ("other-article", "https://www.degiro.nl/blog/other-article"),  # Regular relative
    ]

    # Mock article object for testing
    class MockArticle:
        def __init__(self, href):
            self.href = href
            self.name = 'a'

        def get(self, attr):
            if attr == 'href':
                return self.href
            return None

        def select_one(self, selector):
            return None

    print(f"Base URL: {base_url}")
    print("\\nTest cases:")

    all_passed = True
    for i, (input_href, expected) in enumerate(test_cases, 1):
        article = MockArticle(input_href)
        result = scraper._extract_url(article, base_url)

        passed = result == expected
        status = "✅ PASS" if passed else "❌ FAIL"

        print(f"  {i}. Input: '{input_href}'")
        print(f"     Expected: {expected}")
        print(f"     Got:      {result}")
        print(f"     Status:   {status}")

        if not passed:
            all_passed = False
        print()

    if all_passed:
        print("🎉 All URL extraction tests passed!")
    else:
        print("❌ Some tests failed - URL extraction needs more work")

    return all_passed

if __name__ == "__main__":
    try:
        test_url_extraction()
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
