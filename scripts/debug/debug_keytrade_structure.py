"""Debug Keytrade article structure."""
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

url = "https://www.keytradebank.be/en/our-blog/investing/"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(url, wait_until="networkidle")
    html = page.content()
    browser.close()

soup = BeautifulSoup(html, 'lxml')
cards = soup.select("a[class*='Card']")

print(f"Found {len(cards)} card links\n")

# Inspect first 2
for i, card in enumerate(cards[:2]):
    print(f"=== Card {i+1} ===")
    print(f"href: {card.get('href', 'N/A')[:80]}")

    # Check for headers
    for tag in ['h1', 'h2', 'h3', 'h4']:
        headers = card.find_all(tag)
        if headers:
            print(f"{tag}: {len(headers)} found")
            for h in headers:
                print(f"  text: {h.get_text().strip()[:80]}")

    # Direct text
    text = card.get_text(separator=' ', strip=True)
    print(f"All text: {text[:150]}")

    # Paragraphs
    paras = card.find_all('p')
    if paras:
        print(f"Paragraphs: {len(paras)}")
        for p in paras[:2]:
            print(f"  - {p.get_text().strip()[:80]}")

    print()

