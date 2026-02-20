#!/usr/bin/env python
"""
Test URL joining logic to fix blog/blog duplication.
"""

from urllib.parse import urljoin, urlparse

def fixed_url_join(base_url: str, href: str) -> str:
    """Fixed URL joining that prevents path segment duplication."""

    # Handle absolute URLs
    if href.startswith(('http://', 'https://')):
        return href

    # Handle root-relative URLs
    if href.startswith('/'):
        parsed_base = urlparse(base_url)
        return f"{parsed_base.scheme}://{parsed_base.netloc}{href}"

    # Handle relative URLs - check for duplication
    parsed_base = urlparse(base_url)
    base_path = parsed_base.path.rstrip('/')

    # Check for path segment duplication (e.g., base ends with /blog/ and href starts with blog/)
    if base_path and href.startswith(base_path.split('/')[-1] + '/'):
        # Remove the duplicate segment
        href = href[len(base_path.split('/')[-1]) + 1:]

    return urljoin(base_url, href)

def test_url_fixes():
    """Test the URL fixing logic."""

    print("🧪 Testing URL joining fix for Degiro blog duplication...")

    base_url = "https://www.degiro.nl/blog/"

    test_cases = [
        # (input_href, expected_output, description)
        ("blog/top-sp500-etfs", "https://www.degiro.nl/blog/top-sp500-etfs", "Remove duplicate 'blog'"),
        ("/blog/article", "https://www.degiro.nl/blog/article", "Root-relative URL"),
        ("https://example.com/article", "https://example.com/article", "Absolute URL"),
        ("other-article", "https://www.degiro.nl/blog/other-article", "Normal relative URL"),
        ("blog/news/article", "https://www.degiro.nl/blog/news/article", "Remove duplicate with subpath"),
    ]

    print(f"Base URL: {base_url}\\n")

    all_passed = True
    for i, (input_href, expected, description) in enumerate(test_cases, 1):
        # Test old urljoin (problematic)
        old_result = urljoin(base_url, input_href)

        # Test new fixed logic
        new_result = fixed_url_join(base_url, input_href)

        passed = new_result == expected
        status = "✅ PASS" if passed else "❌ FAIL"

        print(f"{i}. {description}")
        print(f"   Input:    '{input_href}'")
        print(f"   Old:      {old_result}")
        print(f"   New:      {new_result}")
        print(f"   Expected: {expected}")
        print(f"   Status:   {status}")

        if old_result != new_result:
            print(f"   🔧 FIXED: Prevented duplication!")

        if not passed:
            all_passed = False
        print()

    if all_passed:
        print("🎉 All URL tests passed! Duplication issue should be fixed.")
    else:
        print("❌ Some tests failed")

    return all_passed

if __name__ == "__main__":
    test_url_fixes()
