"""Check selectors for all brokers."""
import requests
from bs4 import BeautifulSoup
import time

brokers_news = [
    ("Bolero", "https://www.bolero.be/nl/analyse-en-inzicht/blog", ".blog__entry"),
    ("Keytrade", "https://www.keytradebank.be/en/our-blog/investing/", ".keynews-grid__item"),
    ("Degiro", "https://www.degiro.nl/blog/", ".tag-list-item"),
    ("ING", "https://www.ing.be/en/individuals/news/economy-and-financial-markets", ".news-item"),
    ("Belfius", "https://www.belfius.be/retail/nl/publicaties/actualiteit/index.aspx", ".card-body"),
]

for name, url, selector in brokers_news:
    print(f"\n{'='*60}")
    print(f"{name}: {url}")
    print(f"Current selector: {selector}")
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.content, 'lxml')

        found = len(soup.select(selector))
        print(f"  ✓ Found {found} elements with '{selector}'")

        if found == 0:
            # Try to find better selectors
            print("  Trying alternatives:")
            alts = [
                ('article', soup.find_all('article')),
                ('div[class*="post"]', soup.select('div[class*="post"]')),
                ('div[class*="item"]', soup.select('div[class*="item"]')),
                ('div[class*="card"]', soup.select('div[class*="card"]')),
                ('div[class*="news"]', soup.select('div[class*="news"]')),
                ('div[class*="blog"]', soup.select('div[class*="blog"]')),
            ]
            for alt_name, alt_results in alts:
                if len(alt_results) > 2:
                    print(f"    - {alt_name}: {len(alt_results)} elements")

            # Show page structure hints
            print("  Page info:")
            h2s = soup.find_all('h2')
            if h2s:
                print(f"    h2 tags: {len(h2s)} found, e.g. '{h2s[0].get_text().strip()[:60]}'")
            divs_with_class = [d for d in soup.find_all('div', class_=True)[:20]]
            unique_classes = set()
            for d in divs_with_class:
                unique_classes.update(d.get('class', []))
            print(f"    Common classes: {', '.join(list(unique_classes)[:10])}")

    except Exception as e:
        print(f"  ✗ Error: {str(e)[:100]}")
    time.sleep(1)

