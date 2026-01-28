"""Debug: comparar headers simples vs headers completos"""
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time

# Headers simples (que funcionavam antes)
SIMPLE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Referer': 'https://www.medetec.co.uk/',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

session = requests.Session()
session.headers.update(SIMPLE_HEADERS)

print("1. Inicializando sessão com headers simples...")
r = session.get('https://www.medetec.co.uk/', timeout=30)
print(f"   Status: {r.status_code}")
time.sleep(2)

print("\n2. Acessando categoria...")
cat_url = 'https://www.medetec.co.uk/slide%20scans/burns/index.html'
r = session.get(cat_url, timeout=30)
print(f"   Status: {r.status_code}")
print(f"   Content length: {len(r.text)}")

# Verificar se tem HTML válido
if '<html' in r.text.lower():
    print("   HTML válido encontrado")
else:
    print("   HTML NÃO encontrado!")
    print(f"   Primeiros 500 chars: {r.text[:500]}")

soup = BeautifulSoup(r.text, "html.parser")

# Encontrar links target
target_links = []
for link in soup.find_all("a", href=True):
    href = link.get("href", "")
    if "target" in href.lower() and href.endswith(".html"):
        target_links.append(href)

print(f"   Links target: {len(target_links)}")

if not target_links:
    print("\n   DEBUG: Todos os links encontrados:")
    all_links = soup.find_all("a", href=True)
    print(f"   Total links: {len(all_links)}")
    for link in all_links[:10]:
        print(f"     - {link.get('href', '')}")
