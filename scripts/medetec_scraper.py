"""
REDISUS - Medetec Image Database Scraper
==========================================

Script para coleta automatizada de imagens médicas do Medetec Database
para treinamento de redes neurais de classificação de feridas.

Estrutura de saída compatível com:
- torchvision.datasets.ImageFolder
- tf.keras.utils.image_dataset_from_directory

Estrutura gerada:
    dataset/
    ├── leg_ulcers/
    │   ├── img_001.jpg
    │   ├── img_002.jpg
    │   └── ...
    ├── pressure_ulcers/
    │   ├── img_001.jpg
    │   └── ...
    ├── burn_wounds/
    │   └── ...
    └── ...

AVISO LEGAL:
    Este script é destinado APENAS para fins de pesquisa acadêmica.
    As imagens são propriedade do Medetec e não devem ser redistribuídas.
    Respeite os termos de uso do site.

Autor: REDISUS Team
Data: 2026
"""

import os
import re
import sys
import time
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup

# ============================================================================
# CONFIGURAÇÕES
# ============================================================================

# URL base do Medetec
BASE_URL = "https://www.medetec.co.uk/files/medetec-image-databases.html"
MEDETEC_ROOT = "https://www.medetec.co.uk/"

# Categorias conhecidas do Medetec (descobertas via análise da página)
KNOWN_CATEGORIES = {
    "abdominal_wounds": "https://www.medetec.co.uk/slide%20scans/abdominal-wounds/index.html",
    "burns": "https://www.medetec.co.uk/slide%20scans/burns/index.html",
    "epidermolysis_bullosa": "https://www.medetec.co.uk/slide%20scans/epidermolysis-bullosa/index.html",
    "extravasation_injuries": "https://www.medetec.co.uk/slide%20scans/extravasation-wound-images/index.html",
    "diabetic_foot_ulcers": "https://www.medetec.co.uk/slide%20scans/foot-ulcers/index.html",
    "haemangiomas": "https://www.medetec.co.uk/slide%20scans/haemangioma/index.html",
    "venous_arterial_ulcers_1": "https://www.medetec.co.uk/slide%20scans/leg-ulcer-images/index.html",
    "venous_arterial_ulcers_2": "https://www.medetec.co.uk/slide%20scans/leg-ulcer-images-2/index.html",
    "malignant_wounds": "https://www.medetec.co.uk/slide%20scans/malignant-wound-images/index.html",
    "meningitis_wounds": "https://www.medetec.co.uk/slide%20scans/meningitis/index.html",
    "orthopaedic_wounds": "https://www.medetec.co.uk/slide%20scans/orthopaedic%20wounds/index.html",
    "miscellaneous_wounds": "https://www.medetec.co.uk/slide%20scans/miscellaneous/index.html",
    "pressure_ulcers_1": "https://www.medetec.co.uk/slide%20scans/pressure-ulcer-images-a/index.html",
    "pressure_ulcers_2": "https://www.medetec.co.uk/slide%20scans/pressure-ulcer-images-b/index.html",
    "pilonidal_sinus": "https://www.medetec.co.uk/slide%20scans/pilonidal-sinus/index.html",
    "necrotic_toes": "https://www.medetec.co.uk/slide%20scans/toes/index.html",
}

# Diretório de saída para o dataset
OUTPUT_DIR = Path(__file__).parent.parent / "dataset" / "medetec"

# Configurações de requisição
REQUEST_TIMEOUT = 30  # segundos
DELAY_BETWEEN_REQUESTS = 1.5  # segundos (seja educado com o servidor)
MAX_RETRIES = 3

# User-Agent para simular navegador real (Chrome)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

# Headers simples - evita bloqueio por headers suspeitos
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.medetec.co.uk/",
}

# Extensões de imagem válidas
VALID_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"}

# Cria diretório de saída antes de configurar logging
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(OUTPUT_DIR / "scraper.log", mode="w", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class ImageInfo:
    """Informações sobre uma imagem a ser baixada"""
    url: str
    category: str
    filename: str
    thumbnail_url: Optional[str] = None
    downloaded: bool = False
    error: Optional[str] = None


@dataclass
class CategoryInfo:
    """Informações sobre uma categoria de feridas"""
    name: str
    url: str
    folder_name: str
    images: List[ImageInfo] = field(default_factory=list)
    total_images: int = 0
    downloaded_images: int = 0


@dataclass
class ScrapingStats:
    """Estatísticas do processo de scraping"""
    start_time: datetime = field(default_factory=datetime.now)
    categories_found: int = 0
    total_images: int = 0
    downloaded_images: int = 0
    failed_downloads: int = 0
    skipped_existing: int = 0
    
    def get_summary(self) -> str:
        elapsed = datetime.now() - self.start_time
        return f"""
{'='*60}
RESUMO DO SCRAPING - MEDETEC DATABASE
{'='*60}
Tempo total: {elapsed}
Categorias encontradas: {self.categories_found}
Total de imagens encontradas: {self.total_images}
Imagens baixadas com sucesso: {self.downloaded_images}
Downloads com falha: {self.failed_downloads}
Imagens já existentes (puladas): {self.skipped_existing}
Taxa de sucesso: {(self.downloaded_images / max(1, self.total_images)) * 100:.1f}%
{'='*60}
"""


# ============================================================================
# CLASSE PRINCIPAL DO SCRAPER
# ============================================================================

class MedetecScraper:
    """
    Scraper para o banco de imagens Medetec.
    
    Coleta imagens de feridas organizadas por categoria para
    treinamento de modelos de machine learning.
    """
    
    def __init__(
        self,
        output_dir: Path = OUTPUT_DIR,
        delay: float = DELAY_BETWEEN_REQUESTS
    ):
        self.output_dir = Path(output_dir)
        self.delay = delay
        self.session = self._create_session()
        self.stats = ScrapingStats()
        self.categories: List[CategoryInfo] = []
        
        # Cria diretório de saída
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Scraper inicializado. Output: {self.output_dir}")
    
    def _create_session(self) -> requests.Session:
        """Cria sessão HTTP com configurações otimizadas"""
        session = requests.Session()
        session.headers.update(HEADERS)
        
        # Configuração de retry
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        retry_strategy = Retry(
            total=MAX_RETRIES,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def _initialize_session(self) -> bool:
        """
        Inicializa sessão acessando página principal para obter cookies.
        
        O Medetec usa proteção que requer cookie de sessão válido.
        """
        logger.info("Inicializando sessão com Medetec...")
        
        try:
            # Acessa página principal para obter cookies
            response = self.session.get(
                "https://www.medetec.co.uk/",
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            
            cookies = self.session.cookies.get_dict()
            logger.info(f"  Sessão iniciada. Cookies: {list(cookies.keys())}")
            
            # Pequeno delay antes de continuar
            time.sleep(2)
            return True
            
        except Exception as e:
            logger.error(f"Falha ao inicializar sessão: {e}")
            return False
    
    def _polite_request(
        self,
        url: str,
        stream: bool = False
    ) -> Optional[requests.Response]:
        """
        Faz requisição HTTP com delay e tratamento de erros.
        
        Implementa "politeness" para não sobrecarregar o servidor.
        """
        time.sleep(self.delay)
        
        try:
            response = self.session.get(
                url,
                timeout=REQUEST_TIMEOUT,
                stream=stream,
                allow_redirects=True
            )
            response.raise_for_status()
            return response
            
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout ao acessar: {url}")
        except requests.exceptions.HTTPError as e:
            logger.warning(f"Erro HTTP {e.response.status_code}: {url}")
        except requests.exceptions.ConnectionError:
            logger.warning(f"Erro de conexão: {url}")
        except requests.exceptions.RequestException as e:
            logger.warning(f"Erro na requisição: {url} - {e}")
        
        return None
    
    def _normalize_folder_name(self, name: str) -> str:
        """Normaliza nome de categoria para nome de pasta válido"""
        # Remove caracteres especiais e normaliza
        normalized = re.sub(r'[^\w\s-]', '', name.lower())
        normalized = re.sub(r'[\s-]+', '_', normalized)
        normalized = normalized.strip('_')
        return normalized
    
    def _get_image_extension(self, url: str, content_type: str = "") -> str:
        """Determina extensão do arquivo de imagem"""
        # Tenta extrair da URL
        parsed = urlparse(url)
        path = parsed.path.lower()
        
        for ext in VALID_IMAGE_EXTENSIONS:
            if path.endswith(ext):
                return ext
        
        # Tenta do content-type
        if "jpeg" in content_type or "jpg" in content_type:
            return ".jpg"
        elif "png" in content_type:
            return ".png"
        elif "gif" in content_type:
            return ".gif"
        
        # Default
        return ".jpg"
    
    def _generate_filename(
        self,
        url: str,
        category: str,
        index: int,
        content_type: str = ""
    ) -> str:
        """Gera nome único para arquivo de imagem"""
        ext = self._get_image_extension(url, content_type)
        
        # Usa hash parcial da URL para garantir unicidade
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        
        return f"{category}_{index:04d}_{url_hash}{ext}"
    
    def discover_categories(self) -> List[CategoryInfo]:
        """
        Descobre categorias de feridas na página principal.
        
        Usa lista de categorias conhecidas do Medetec.
        """
        logger.info(f"Carregando categorias conhecidas do Medetec...")
        
        categories = []
        
        # Usa categorias pré-mapeadas (estrutura conhecida do site)
        for folder_name, url in KNOWN_CATEGORIES.items():
            # Cria nome legível
            name = folder_name.replace("_", " ").title()
            
            category = CategoryInfo(
                name=name,
                url=url,
                folder_name=folder_name
            )
            categories.append(category)
            logger.info(f"  Categoria: {name}")
        
        # Também tenta descobrir dinamicamente da página
        try:
            response = self._polite_request(BASE_URL)
            if response:
                soup = BeautifulSoup(response.content, "html.parser")
                dynamic_categories = self._discover_from_page(soup)
                
                # Adiciona categorias novas não conhecidas
                for cat in dynamic_categories:
                    if not any(c.url == cat.url for c in categories):
                        categories.append(cat)
                        logger.info(f"  Nova categoria encontrada: {cat.name}")
        except Exception as e:
            logger.warning(f"Erro ao descobrir categorias dinamicamente: {e}")
        
        self.categories = categories
        self.stats.categories_found = len(categories)
        
        logger.info(f"Total de categorias: {len(categories)}")
        
        return categories
    
    def _discover_from_page(self, soup: BeautifulSoup) -> List[CategoryInfo]:
        """Descobre categorias dinamicamente da página HTML"""
        categories = []
        
        # Procura links que apontam para /slide%20scans/
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            text = link.get_text(strip=True)
            
            if "slide%20scans" in href or "slide scans" in href:
                full_url = urljoin(BASE_URL, href)
                folder_name = self._normalize_folder_name(text)
                
                if folder_name and len(folder_name) > 2:
                    categories.append(CategoryInfo(
                        name=text,
                        url=full_url,
                        folder_name=folder_name
                    ))
        
        return categories
    
    def discover_images_in_category(self, category: CategoryInfo) -> List[ImageInfo]:
        """
        Descobre todas as imagens em uma categoria.
        
        Estrutura do Medetec:
        - index.html contém thumbnails em thumbnails/
        - Thumbnails linkam para targetN.html
        - targetN.html contém imagem full em images/
        
        Para otimizar, baixamos thumbnails diretamente se não quisermos
        fazer muitas requisições. Para imagens full, acesse cada target.
        """
        logger.info(f"Explorando categoria: {category.name}")
        
        response = self._polite_request(category.url)
        if not response:
            logger.warning(f"Falha ao acessar categoria: {category.name}")
            return []
        
        # Verifica se foi bloqueado
        if "Access Denied" in response.text:
            logger.warning(f"Acesso bloqueado para: {category.name}")
            return []
        
        soup = BeautifulSoup(response.text, "html.parser")
        images = []
        
        # Coleta thumbnails dos links target (mais rápido)
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if "target" in href.lower() and href.endswith(".html"):
                target_url = urljoin(category.url, href)
                
                # Encontra thumbnail dentro do link
                thumb = link.find("img")
                if thumb and thumb.get("src"):
                    thumb_src = thumb.get("src", "")
                    thumb_url = urljoin(category.url, thumb_src)
                    
                    # Converte thumbnail URL para imagem full
                    # thumbnails/image.jpg -> images/image.jpg
                    full_url = thumb_url.replace("/thumbnails/", "/images/")
                    
                    if not any(i.url == full_url for i in images):
                        images.append(ImageInfo(
                            url=full_url,
                            category=category.folder_name,
                            filename="",
                            thumbnail_url=thumb_url
                        ))
        
        # Estratégia 2: Imagens diretas sem link target
        for img in soup.find_all("img", src=True):
            src = img.get("src", "")
            
            # Pula thumbnails (já processadas), ícones e navegação
            if "thumbnail" in src.lower():
                continue
            if any(x in src.lower() for x in ["icon", "logo", "button", "nav", "banner"]):
                continue
            
            # Verifica se é uma imagem válida
            if any(src.lower().endswith(ext) for ext in VALID_IMAGE_EXTENSIONS):
                img_url = urljoin(category.url, src)
                
                if not any(i.url == img_url for i in images):
                    images.append(ImageInfo(
                        url=img_url,
                        category=category.folder_name,
                        filename="",
                        thumbnail_url=None
                    ))
        
        # Gera nomes de arquivo
        for i, img in enumerate(images):
            img.filename = self._generate_filename(
                img.url, 
                category.folder_name, 
                i + 1
            )
        
        category.images = images
        category.total_images = len(images)
        
        logger.info(f"  Imagens encontradas: {len(images)}")
        
        return images
    
    def _get_full_image_from_target(self, target_url: str) -> Optional[str]:
        """
        Busca URL da imagem em tamanho completo na página target.
        
        As páginas targetN.html contém a imagem full em images/
        """
        response = self._polite_request(target_url)
        if not response:
            return None
        
        # Verifica se foi bloqueado
        if "Access Denied" in response.text:
            logger.debug(f"Acesso bloqueado para target: {target_url}")
            return None
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Procura imagem na pasta images/
        for img in soup.find_all("img", src=True):
            src = img.get("src", "")
            
            # Imagens full estão na pasta images/
            if "images/" in src:
                if any(src.lower().endswith(ext) for ext in VALID_IMAGE_EXTENSIONS):
                    return urljoin(target_url, src)
        
        return None
    
    def download_image(self, image: ImageInfo, output_folder: Path) -> bool:
        """
        Baixa uma imagem individual.
        
        Tenta baixar a versão em alta resolução primeiro,
        fallback para thumbnail se necessário.
        """
        output_path = output_folder / image.filename
        
        # Verifica se já existe
        if output_path.exists():
            logger.debug(f"  Já existe: {image.filename}")
            self.stats.skipped_existing += 1
            image.downloaded = True
            return True
        
        # Tenta baixar imagem principal
        response = self._polite_request(image.url, stream=True)
        
        # Fallback para thumbnail
        if not response and image.thumbnail_url:
            logger.debug(f"  Tentando thumbnail: {image.filename}")
            response = self._polite_request(image.thumbnail_url, stream=True)
        
        if not response:
            logger.warning(f"  Falha ao baixar: {image.filename}")
            image.error = "Download failed"
            self.stats.failed_downloads += 1
            return False
        
        # Verifica se é realmente uma imagem
        content_type = response.headers.get("content-type", "")
        if "image" not in content_type and "octet-stream" not in content_type:
            logger.warning(f"  Não é imagem: {image.filename} ({content_type})")
            image.error = f"Invalid content type: {content_type}"
            self.stats.failed_downloads += 1
            return False
        
        # Salva arquivo
        try:
            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            # Verifica tamanho mínimo (evita arquivos corrompidos)
            if output_path.stat().st_size < 1000:  # < 1KB
                output_path.unlink()
                logger.warning(f"  Arquivo muito pequeno: {image.filename}")
                image.error = "File too small"
                self.stats.failed_downloads += 1
                return False
            
            logger.info(f"  ✓ Baixado: {image.filename}")
            image.downloaded = True
            self.stats.downloaded_images += 1
            return True
            
        except IOError as e:
            logger.error(f"  Erro ao salvar: {image.filename} - {e}")
            image.error = str(e)
            self.stats.failed_downloads += 1
            return False
    
    def download_category(self, category: CategoryInfo) -> int:
        """
        Baixa todas as imagens de uma categoria.
        
        Cria pasta da categoria e baixa imagens sequencialmente.
        """
        logger.info(f"\nBaixando categoria: {category.name}")
        logger.info(f"Total de imagens: {category.total_images}")
        
        # Cria pasta da categoria
        category_folder = self.output_dir / category.folder_name
        category_folder.mkdir(parents=True, exist_ok=True)
        
        downloaded = 0
        
        for i, image in enumerate(category.images, 1):
            logger.info(f"  [{i}/{category.total_images}] {image.filename}")
            
            if self.download_image(image, category_folder):
                downloaded += 1
        
        category.downloaded_images = downloaded
        
        logger.info(f"Categoria {category.name}: {downloaded}/{category.total_images} imagens")
        
        return downloaded
    
    def run(self) -> ScrapingStats:
        """
        Executa o pipeline completo de scraping.
        
        1. Inicializa sessão (obtém cookies)
        2. Descobre categorias
        3. Para cada categoria, descobre imagens
        4. Baixa todas as imagens
        5. Retorna estatísticas
        """
        logger.info("=" * 60)
        logger.info("MEDETEC IMAGE SCRAPER - INICIANDO")
        logger.info("=" * 60)
        logger.info(f"Diretório de saída: {self.output_dir}")
        logger.info(f"Delay entre requisições: {self.delay}s")
        logger.info("")
        
        # Fase 0: Inicializar sessão (obter cookies de autenticação)
        if not self._initialize_session():
            logger.error("Falha ao inicializar sessão. Abortando.")
            return self.stats
        
        # Fase 1: Descobrir categorias
        logger.info("\nFASE 1: Descobrindo categorias...")
        categories = self.discover_categories()
        
        if not categories:
            logger.error("Nenhuma categoria encontrada. Abortando.")
            return self.stats
        
        # Fase 2: Descobrir imagens em cada categoria
        logger.info("\nFASE 2: Descobrindo imagens...")
        for category in categories:
            self.discover_images_in_category(category)
            self.stats.total_images += category.total_images
        
        logger.info(f"\nTotal de imagens encontradas: {self.stats.total_images}")
        
        # Fase 3: Download das imagens
        logger.info("\nFASE 3: Baixando imagens...")
        for category in categories:
            if category.total_images > 0:
                self.download_category(category)
        
        # Resumo final
        logger.info(self.stats.get_summary())
        
        # Salva metadados
        self._save_metadata()
        
        return self.stats
    
    def _save_metadata(self):
        """Salva metadados do dataset em arquivo JSON"""
        import json
        
        metadata = {
            "source": "Medetec Image Databases",
            "url": BASE_URL,
            "scraped_at": datetime.now().isoformat(),
            "categories": [
                {
                    "name": c.name,
                    "folder": c.folder_name,
                    "total_images": c.total_images,
                    "downloaded": c.downloaded_images,
                    "images": [
                        {
                            "filename": img.filename,
                            "url": img.url,
                            "downloaded": img.downloaded,
                            "error": img.error
                        }
                        for img in c.images
                    ]
                }
                for c in self.categories
            ],
            "stats": {
                "categories": self.stats.categories_found,
                "total_images": self.stats.total_images,
                "downloaded": self.stats.downloaded_images,
                "failed": self.stats.failed_downloads,
                "skipped": self.stats.skipped_existing
            },
            "license_notice": (
                "Images are property of Medetec. "
                "For research and educational purposes only. "
                "Do not redistribute."
            )
        }
        
        metadata_path = self.output_dir / "metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Metadados salvos em: {metadata_path}")


# ============================================================================
# FUNÇÃO PRINCIPAL
# ============================================================================

def main():
    """Função principal do scraper"""
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║   REDISUS - MEDETEC IMAGE DATABASE SCRAPER                   ║
    ║                                                              ║
    ║   Coleta automatizada de imagens médicas para treinamento    ║
    ║   de modelos de classificação de feridas.                    ║
    ║                                                              ║
    ║   AVISO: Apenas para fins de pesquisa acadêmica.             ║
    ║   Não redistribua as imagens coletadas.                      ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    # Verifica dependências
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError as e:
        print(f"[ERRO] Dependência não encontrada: {e}")
        print("Execute: pip install requests beautifulsoup4")
        sys.exit(1)
    
    # Cria e executa scraper
    scraper = MedetecScraper(
        output_dir=OUTPUT_DIR,
        delay=DELAY_BETWEEN_REQUESTS
    )
    
    try:
        stats = scraper.run()
        
        if stats.downloaded_images > 0:
            print(f"\n✓ Dataset salvo em: {OUTPUT_DIR}")
            print(f"✓ Total de imagens: {stats.downloaded_images}")
            print("\nEstrutura compatível com ImageFolder/image_dataset_from_directory")
        else:
            print("\n⚠ Nenhuma imagem foi baixada.")
            print("Verifique a conexão e tente novamente.")
        
    except KeyboardInterrupt:
        print("\n\n[INFO] Interrompido pelo usuário")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Erro fatal: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
