#!/usr/bin/env python
"""
Test ING with proper content decoding to handle compression.
"""

import requests
import gzip
import io
from bs4 import BeautifulSoup
from datetime import datetime

def test_ing_with_proper_decoding():
    print("🔧 Testing ING with proper content decoding...")

    ing_url = "https://newsroom.ing.be/en"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,nl;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
    }

    try:
        print(f"Fetching: {ing_url}")
        response = requests.get(ing_url, headers=headers, timeout=10)

        print(f"Status Code: {response.status_code}")
        print(f"Content-Encoding: {response.headers.get('content-encoding', 'None')}")
        print(f"Content-Type: {response.headers.get('content-type', 'None')}")
        print(f"Content-Length: {response.headers.get('content-length', 'None')}")

        # Try to get properly decoded content
        if response.headers.get('content-encoding') == 'gzip':
            print("✅ Detected gzip encoding - using response.text for auto-decoding")
            content = response.text  # requests automatically handles gzip
        else:
            print("📝 No gzip encoding detected")
            content = response.text

        print(f"Decoded content length: {len(content)} characters")

        # Save properly decoded content
        decoded_file = f"data/output/ing_decoded_response_{timestamp}.html"
        with open(decoded_file, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ Properly decoded response saved to: {decoded_file}")

        # Analyze content
        soup = BeautifulSoup(content, 'html.parser')

        # Check basic structure
        title = soup.title.get_text() if soup.title else "No title found"
        print(f"\\nPage Analysis:")
        print(f"  Title: {title}")

        # Check for JavaScript-heavy content
        scripts = soup.find_all('script')
        print(f"  Script tags: {len(scripts)}")

        # Look for content indicators
        body_text = soup.get_text()[:500].strip()
        print(f"  Body preview: {body_text[:100]}...")

        # Check if it's a SPA (Single Page Application)
        if 'react' in content.lower() or 'vue' in content.lower() or 'angular' in content.lower():
            print("  🔥 Detected SPA framework - content likely loads via JavaScript")

        # Look for news-related elements
        potential_news_selectors = [
            'article', '.news', '.press', '.announcement',
            '[class*="news"]', '[class*="press"]', '[class*="article"]',
            '.card', '.item', '.post'
        ]

        print(f"\\n🔍 Selector Analysis:")
        for selector in potential_news_selectors:
            elements = soup.select(selector)
            if elements:
                print(f"  {selector}: {len(elements)} elements")
                if elements[0].get_text(strip=True):
                    sample = elements[0].get_text(strip=True)[:60]
                    print(f"    Sample: {sample}...")

        # Check for API endpoints or data attributes
        if 'api' in content.lower() or 'data-' in content.lower():
            print(f"\\n🔌 API/Data indicators found - may need to find API endpoints")

        return content

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_alternative_ing_urls():
    """Test different ING URLs to find working news sources."""

    print(f"\\n🔍 Testing alternative ING URLs...")

    test_urls = [
        "https://newsroom.ing.be/",
        "https://newsroom.ing.be/en",
        "https://newsroom.ing.be/en?category=9986",
        "https://www.ing.com/Newsroom/All-news.htm",
        "https://www.ing.be/en/about/press",
        "https://www.ing.nl/nieuws",
    ]

    for url in test_urls:
        try:
            print(f"\\nTesting: {url}")
            response = requests.get(url, timeout=5, allow_redirects=True)
            print(f"  Status: {response.status_code}")
            print(f"  Final URL: {response.url}")

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                title = soup.title.get_text() if soup.title else "No title"
                print(f"  Title: {title[:60]}...")

                # Quick check for news content
                news_count = len(soup.select('article, .news, [class*="news"], [class*="press"]'))
                print(f"  Potential news items: {news_count}")

        except Exception as e:
            print(f"  ❌ Error: {str(e)[:50]}")

if __name__ == "__main__":
    content = test_ing_with_proper_decoding()
    test_alternative_ing_urls()

    if content:
        print(f"\\n🎉 ING content successfully decoded and analyzed!")
    else:
        print(f"\\n❌ Failed to decode ING content")
