"""Inspect HTML structure of broker news pages."""
import requests
from bs4 import BeautifulSoup

url = 'https://www.bolero.be/nl/analyse-en-inzicht/blog'
print(f"Fetching {url}...")
r = requests.get(url)
soup = BeautifulSoup(r.content, 'lxml')

print(f"\n=== HTML Structure Analysis ===")
print(f"Article tags: {len(soup.find_all('article'))}")
print(f"Divs with 'blog' in class: {len(soup.find_all('div', class_=lambda x: x and 'blog' in str(x).lower()))}")
print(f"Divs with 'card' in class: {len(soup.find_all('div', class_=lambda x: x and 'card' in str(x).lower()))}")
print(f"Divs with 'item' in class: {len(soup.find_all('div', class_=lambda x: x and 'item' in str(x).lower()))}")
print(f"Divs with 'post' in class: {len(soup.find_all('div', class_=lambda x: x and 'post' in str(x).lower()))}")
print(f"Links (a tags): {len(soup.find_all('a'))}")

print(f"\n=== Common patterns ===")
# Look for repeating patterns that might be blog posts
all_divs = soup.find_all('div', class_=True)
class_counts = {}
for div in all_divs:
    classes = ' '.join(div.get('class', []))
    if classes:
        class_counts[classes] = class_counts.get(classes, 0) + 1

print("Most common div classes (top 10):")
for cls, count in sorted(class_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
    if count > 2:  # Only show repeated elements
        print(f"  {count}x: {cls}")

print("\n=== Sample h2/h3 titles ===")
for tag in ['h1', 'h2', 'h3']:
    headers = soup.find_all(tag)
    if headers:
        print(f"{tag}: {len(headers)} found")
        for h in headers[:3]:
            print(f"  - {h.get_text().strip()[:80]}")

