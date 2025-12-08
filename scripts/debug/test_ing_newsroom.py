"""Test ING newsroom page structure."""
import requests
from bs4 import BeautifulSoup

url = "https://newsroom.ing.be/en?category=9986"
print(f"Fetching {url}...")
r = requests.get(url, timeout=10)
print(f"Status: {r.status_code}")
print(f"Content length: {len(r.content)} bytes\n")

soup = BeautifulSoup(r.content, 'lxml')

print("=== Structure Analysis ===")
print(f"Article tags: {len(soup.find_all('article'))}")
print(f"Divs with 'news' in class: {len(soup.select('div[class*=\"news\"]'))}")
print(f"Divs with 'post' in class: {len(soup.select('div[class*=\"post\"]'))}")
print(f"Divs with 'item' in class: {len(soup.select('div[class*=\"item\"]'))}")
print(f"Links (a tags): {len(soup.find_all('a'))}")

print("\n=== Headers ===")
for tag in ['h1', 'h2', 'h3']:
    headers = soup.find_all(tag)
    if headers:
        print(f"{tag}: {len(headers)} found")
        for h in headers[:3]:
            text = h.get_text().strip()
            if text and len(text) > 10:
                print(f"  - {text[:80]}")

# Check for article containers
articles = soup.find_all('article')
if articles:
    print(f"\n=== Sample Article Structure ===")
    art = articles[0]
    print(f"Article classes: {art.get('class', [])}")
    h2 = art.find('h2')
    if h2:
        print(f"H2: {h2.get_text().strip()[:80]}")
    links = art.find_all('a')
    if links:
        print(f"Links in article: {len(links)}")
        print(f"  First link: {links[0].get('href', 'N/A')}")

