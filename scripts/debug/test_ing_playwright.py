"""Test ING newsroom with Playwright."""
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

url = "https://newsroom.ing.be/en?category=9986"
print(f"Testing {url} with Playwright...")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    try:
        response = page.goto(url, wait_until="networkidle", timeout=30000)
        print(f"Status: {response.status}")

        html = page.content()
        print(f"HTML size: {len(html)} bytes\n")

        soup = BeautifulSoup(html, 'lxml')

        print("=== Structure Analysis ===")
        print(f"Article tags: {len(soup.find_all('article'))}")
        print(f"Divs with 'news' in class: {len(soup.select('div[class*=\"news\"]'))}")
        print(f"Divs with 'card' in class: {len(soup.select('div[class*=\"card\"]'))}")
        print(f"Links (a tags): {len(soup.find_all('a'))}")

        print("\n=== Headers ===")
        h2s = soup.find_all('h2')
        print(f"H2 tags: {len(h2s)} found")
        for h in h2s[:5]:
            text = h.get_text().strip()
            if text and len(text) > 10:
                print(f"  - {text[:80]}")

        # Look for article containers
        articles = soup.find_all('article')
        if articles:
            print(f"\n=== First Article ===")
            art = articles[0]
            print(f"Classes: {art.get('class', [])}")
            title = art.find(['h1', 'h2', 'h3'])
            if title:
                print(f"Title: {title.get_text().strip()[:80]}")

    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        browser.close()

