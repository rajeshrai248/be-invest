"""Find correct selector for Keytrade."""
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://www.keytradebank.be/en/our-blog/investing/", wait_until="networkidle")
    
    html = page.content()
    soup = BeautifulSoup(html, 'lxml')
    
    # Find all h2 tags and their parent containers
    h2s = soup.find_all('h2')[:5]
    print(f"Found {len(soup.find_all('h2'))} h2 tags\n")
    
    for h2 in h2s:
        print(f"H2: '{h2.get_text().strip()[:60]}'")
        # Walk up to find container
        parent = h2.parent
        depth = 0
        while parent and depth < 5:
            classes = parent.get('class', [])
            if classes:
                print(f"  {'  '*depth}Parent: {parent.name} class='{' '.join(classes)}'")
            parent = parent.parent
            depth += 1
        print()
    
    browser.close()

