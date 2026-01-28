"""Script temporário para debugar o método discover_images_in_category"""
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Referer': 'https://www.medetec.co.uk/',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
}

# Usar session para manter cookies
session = requests.Session()
session.headers.update(headers)

# Primeiro, acessar página principal para obter cookies
print("Acessando página principal primeiro...")
home = session.get('https://www.medetec.co.uk/')
print(f"Home status: {home.status_code}")
time.sleep(2)

# Testar a lógica do discover_images_in_category
print("\nTestando lógica de descoberta de imagens...")
category_url = 'https://www.medetec.co.uk/slide%20scans/burns/index.html'

r = session.get(category_url)
print(f"Category page status: {r.status_code}")
print(f"Content-Length: {len(r.text)}")

soup = BeautifulSoup(r.text, 'html.parser')

# Debug: mostrar todos os links
all_links = soup.find_all('a', href=True)
print(f"\nTotal de links na página: {len(all_links)}")

# Procurar links para target
print("\nProcurando links para páginas target...")
for link in all_links:
    href = link.get('href', '')
    
    # Verificar se é target (a condição do scraper)
    if 'target' in href.lower() and href.endswith('.html'):
        print(f"  Encontrado target: {href}")
        
        thumb = link.find('img')
        if thumb and thumb.get('src'):
            thumb_src = thumb.get('src', '')
            target_url = urljoin(category_url, href)
            print(f"    Thumb: {thumb_src}")
            print(f"    Target URL: {target_url}")
            
            # Buscar imagem full
            print(f"    Buscando imagem full...")
            time.sleep(1)
            target_r = session.get(target_url)
            if target_r.status_code == 200:
                target_soup = BeautifulSoup(target_r.text, 'html.parser')
                for img in target_soup.find_all('img', src=True):
                    src = img.get('src', '')
                    if 'images/' in src.lower() or 'thumbnail' not in src.lower():
                        full_url = urljoin(target_url, src)
                        print(f"    -> FULL IMAGE: {full_url}")
                        break
            else:
                print(f"    Erro ao acessar target: {target_r.status_code}")
            break
