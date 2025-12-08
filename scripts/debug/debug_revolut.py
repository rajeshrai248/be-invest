"""Debug Revolut structure."""
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://www.revolut.com/en-BE/news/", wait_until="networkidle")
    html = page.content()
    browser.close()

soup = BeautifulSoup(html, 'lxml')

print(f"Title: {soup.title.string if soup.title else 'N/A'}\n")

# Try different selectors
selectors = [
    ("article", soup.find_all('article')),
    ("div[class*='post']", soup.select("div[class*='post']")),
    ("div[class*='Post']", soup.select("div[class*='Post']")),
    ("div[class*='card']", soup.select("div[class*='card']")),
    ("div[class*='Card']", soup.select("div[class*='Card']")),
    ("a[class*='card']", soup.select("a[class*='card']")),
]

for name, results in selectors:
    if results:
        print(f"{name}: {len(results)} found")

# Check h2/h3
h2s = soup.find_all('h2')
h3s = soup.find_all('h3')
print(f"\nh2 tags: {len(h2s)}")
print(f"h3 tags: {len(h3s)}")

if h2s:
    print("\nSample h2s:")
    for h in h2s[:3]:
        text = h.get_text().strip()
        if len(text) > 10:
            print(f"  - {text[:80]}")

