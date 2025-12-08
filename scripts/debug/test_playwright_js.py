"""Test Playwright rendering for JS-heavy pages."""
import sys
from pathlib import Path
import logging

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

logging.basicConfig(level=logging.INFO)

from playwright.sync_api import sync_playwright

urls_to_test = [
    ("Keytrade", "https://www.keytradebank.be/en/our-blog/investing/"),
    ("Degiro", "https://www.degiro.nl/blog/"),
    ("ING", "https://www.ing.be/en/individuals/news/economy-and-financial-markets"),
]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    for name, url in urls_to_test:
        print(f"\n{'='*60}")
        print(f"{name}: {url}")
        try:
            page = browser.new_page()
            response = page.goto(url, wait_until="networkidle", timeout=30000)
            print(f"  Status: {response.status}")

            html = page.content()
            print(f"  HTML size: {len(html)} bytes")

            # Check for common news article patterns
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'lxml')

            print(f"  Articles: {len(soup.find_all('article'))}")
            print(f"  H2 tags: {len(soup.find_all('h2'))}")
            print(f"  Links: {len(soup.find_all('a'))}")

            # Sample h2
            h2s = soup.find_all('h2')
            if h2s:
                print(f"  Sample h2: '{h2s[0].get_text().strip()[:60]}'")

            page.close()
        except Exception as e:
            print(f"  Error: {str(e)[:100]}")

    browser.close()

