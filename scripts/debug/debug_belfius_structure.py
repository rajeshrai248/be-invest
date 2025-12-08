"""Debug Belfius article structure."""
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

url = "https://www.belfius.be/retail/nl/publicaties/actualiteit/index.aspx"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(url, wait_until="networkidle")
    html = page.content()
    browser.close()

soup = BeautifulSoup(html, 'lxml')
articles = soup.find_all('article')

print(f"Found {len(articles)} articles\n")

# Inspect first 3 articles
for i, art in enumerate(articles[:3]):
    print(f"=== Article {i+1} ===")
    print(f"Classes: {art.get('class', [])}")

    # Check for headers
    for tag in ['h1', 'h2', 'h3', 'h4']:
        headers = art.find_all(tag)
        if headers:
            print(f"{tag}: {len(headers)} found")
            for h in headers:
                print(f"  - {h.get_text().strip()[:80]}")

    # Check for links
    links = art.find_all('a')
    if links:
        print(f"Links: {len(links)}")
        for link in links[:2]:
            print(f"  - href: {link.get('href', 'N/A')[:80]}")
            print(f"    text: {link.get_text().strip()[:80]}")

    # Check for paragraphs
    paras = art.find_all('p')
    if paras:
        print(f"Paragraphs: {len(paras)}")
        print(f"  First p: {paras[0].get_text().strip()[:80]}")

    print()

