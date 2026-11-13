#!/usr/bin/env python3
"""
Switch2 Price Watch - scraper.py

Varre as páginas de busca/categoria de jogos de Nintendo Switch 2 em
algumas lojas brasileiras, extrai título, preço atual, preço original
(quando a loja mostra um preço "de tabela" riscado) e calcula o
desconto. Salva/atualiza um histórico em data/prices.json.

IMPORTANTE:
- Isso é scraping de HTML público, não uso de API oficial. Lojas podem
  mudar o layout da página a qualquer momento, o que quebra o parser
  daquela loja específica até alguém ajustar os seletores abaixo.
- Cada loja tem sua própria função `scrape_<loja>()`. Se uma quebrar,
  as outras continuam funcionando normalmente (erros são isolados).
- Ajuste os seletores (CSS/regex) conforme o HTML real mudar.
"""

import json
import re
import sys
import time
import traceback
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

DATA_FILE = Path(__file__).parent / "data" / "prices.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}

# A API pública do Mercado Livre bloqueia alguns ranges de IP de datacenter
# (incluindo os dos runners do GitHub Actions) com 403 genérico, independente
# de User-Agent. Usamos um header de Accept específico de API como última
# tentativa; se continuar bloqueando, é bloqueio por IP mesmo, não por header.
ML_API_HEADERS = {**HEADERS, "Accept": "application/json"}

REQUEST_TIMEOUT = 20
MAX_PAGES_PER_STORE = 3  # limita o número de páginas de busca por loja


@dataclass
class Listing:
    store: str
    title: str
    url: str
    price: float
    original_price: Optional[float]
    discount_pct: Optional[float]
    currency: str = "BRL"


def _to_float_brl(raw: str) -> Optional[float]:
    """Converte string de preço no formato brasileiro (R$ 1.234,56) para float."""
    if not raw:
        return None
    cleaned = re.sub(r"[^\d,\.]", "", raw)
    if not cleaned:
        return None
    # formato BR: ponto = milhar, vírgula = decimal
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _discount(price: float, original: Optional[float]) -> Optional[float]:
    if not original or original <= price:
        return None
    return round((1 - price / original) * 100, 1)


DEBUG_HTML_DIR = Path(__file__).parent / "debug_html"
DEBUG_MODE = __import__("os").environ.get("SCRAPER_DEBUG") == "1"


def _save_debug(name: str, text: str) -> None:
    if not DEBUG_MODE:
        return
    DEBUG_HTML_DIR.mkdir(parents=True, exist_ok=True)
    (DEBUG_HTML_DIR / f"{name}.html").write_text(text, encoding="utf-8")


def _get_raw(
    url: str, debug_name: Optional[str] = None, headers: Optional[dict] = None
) -> Optional[requests.Response]:
    """GET que sempre salva o corpo em modo debug, mesmo em erro HTTP
    (útil pra inspecionar páginas de bloqueio/challenge das lojas)."""
    try:
        resp = requests.get(url, headers=headers or HEADERS, timeout=REQUEST_TIMEOUT)
        if debug_name:
            _save_debug(debug_name, resp.text)
        resp.raise_for_status()
        return resp
    except requests.RequestException as e:
        print(f"[WARN] Falha ao buscar {url}: {e}", file=sys.stderr)
        return None


def _get(url: str, debug_name: Optional[str] = None) -> Optional[BeautifulSoup]:
    resp = _get_raw(url, debug_name=debug_name)
    if resp is None:
        return None
    return BeautifulSoup(resp.text, "html.parser")


def _get_json(
    url: str, debug_name: Optional[str] = None, headers: Optional[dict] = None
) -> Optional[dict]:
    resp = _get_raw(url, debug_name=debug_name, headers=headers)
    if resp is None:
        return None
    try:
        return resp.json()
    except ValueError as e:
        print(f"[WARN] Resposta não é JSON válido em {url}: {e}", file=sys.stderr)
        return None


def _get_rendered(
    url: str, debug_name: Optional[str] = None, wait_ms: int = 4000
) -> Optional[BeautifulSoup]:
    """Abre a URL num navegador real (Chromium headless via Playwright) e
    devolve o HTML já renderizado. Usado pras lojas cujo bloqueio parece
    ser por fingerprint de bot (não por IP), onde um navegador de verdade
    tem chance de passar onde um requests.get() simples não passa."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[WARN] Playwright não instalado - pulando fetch via navegador", file=sys.stderr)
        return None

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = browser.new_context(
                user_agent=HEADERS["User-Agent"],
                viewport={"width": 1366, "height": 768},
                locale="pt-BR",
                timezone_id="America/Sao_Paulo",
            )
            context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            )
            page = context.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(wait_ms)
                html = page.content()
            finally:
                browser.close()
            if debug_name:
                _save_debug(debug_name, html)
            return BeautifulSoup(html, "html.parser")
    except Exception as e:
        print(f"[WARN] Playwright falhou em {url}: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Mercado Livre
# ---------------------------------------------------------------------------
# Tentativa 1 (API pública) e a página HTML simples via requests.get() foram
# bloqueadas (403 / página de "tráfego suspeito"), aparentemente por IP do
# datacenter do runner, não só por fingerprint. Como último recurso, abrimos
# a página de busca normal num navegador real headless (Playwright). Se isso
# também for bloqueado, é sinal de que o bloqueio é por IP mesmo, e não há
# muito o que fazer sem mudar de rede (proxy residencial etc.), o que está
# fora do escopo deste projeto.
def scrape_mercadolivre() -> list[Listing]:
    store = "Mercado Livre"
    listings: list[Listing] = []
    url = "https://lista.mercadolivre.com.br/jogo-nintendo-switch-2"

    soup = _get_rendered(url, debug_name="mercadolivre_browser")
    if not soup:
        return listings

    # Mercado Livre usa variações de classe entre o layout "clássico" e o
    # novo "poly-card"; tentamos os dois.
    items = soup.select("li.ui-search-layout__item") or soup.select("div.poly-card")
    if not items:
        title_tag = soup.find("title")
        print(
            f"[WARN] Mercado Livre: 0 cards encontrados no HTML renderizado "
            f"(título da página: {title_tag.get_text(strip=True) if title_tag else '??'}). "
            f"Rode com SCRAPER_DEBUG=1 e confira debug_html/mercadolivre_browser.html",
            file=sys.stderr,
        )
    for item in items:
        title_el = (
            item.select_one("h2.ui-search-item__title")
            or item.select_one("h3.poly-component__title")
            or item.select_one("a.poly-component__title")
        )
        link_el = item.select_one("a.ui-search-link") or item.select_one("a.poly-component__title")
        price_el = item.select_one("span.andes-money-amount__fraction")
        original_el = item.select_one(
            "s.andes-money-amount--previous span.andes-money-amount__fraction"
        )

        if not title_el or not price_el:
            continue

        title = title_el.get_text(strip=True)
        if "switch" not in title.lower():
            continue

        href = link_el.get("href", "") if link_el else ""
        price = _to_float_brl(price_el.get_text(strip=True))
        original = _to_float_brl(original_el.get_text(strip=True)) if original_el else None

        if price is None:
            continue

        listings.append(
            Listing(
                store=store,
                title=title,
                url=href,
                price=price,
                original_price=original,
                discount_pct=_discount(price, original),
            )
        )

    return listings


# ---------------------------------------------------------------------------
# Kabum
# ---------------------------------------------------------------------------
# A página de busca da Kabum é renderizada via Next.js e os cards de produto
# só existem depois da hidratação em JS - não aparecem nas classes CSS do
# HTML estático. Porém a página embute os dados completos (inclusive preço
# com e sem desconto) num <script id="__NEXT_DATA__"> com JSON, que é o que
# o React usa pra hidratar. Lemos esse JSON direto, é bem mais estável do
# que depender de nomes de classe.
def scrape_kabum() -> list[Listing]:
    store = "Kabum"
    listings: list[Listing] = []
    url = "https://www.kabum.com.br/busca/nintendo-switch-2-jogo"

    resp = _get_raw(url, debug_name="kabum")
    if not resp:
        return listings

    match = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', resp.text, re.DOTALL
    )
    if not match:
        print("[WARN] Kabum: __NEXT_DATA__ não encontrado na página", file=sys.stderr)
        return listings

    try:
        next_data = json.loads(match.group(1))
        items = next_data["props"]["pageProps"]["data"]["catalogServer"]["data"]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"[WARN] Kabum: estrutura do __NEXT_DATA__ mudou ({e})", file=sys.stderr)
        return listings

    for item in items:
        title = item.get("name", "")
        if "switch" not in title.lower():
            continue

        code = item.get("code")
        friendly_name = item.get("friendlyName", "")
        href = f"https://www.kabum.com.br/produto/{code}/{friendly_name}" if code else ""

        price_table = item.get("price") or 0  # preço "de tabela"
        price_final = item.get("priceWithDiscount") or price_table  # preço com desconto aplicado

        if not price_final:
            continue

        original = price_table if price_table and price_table > price_final else None

        listings.append(
            Listing(
                store=store,
                title=title,
                url=href,
                price=float(price_final),
                original_price=float(original) if original else None,
                discount_pct=_discount(float(price_final), float(original) if original else None),
            )
        )

    return listings


# ---------------------------------------------------------------------------
# Magazine Luiza
# ---------------------------------------------------------------------------
# A Magalu bloqueia requests simples com um desafio Akamai Bot Manager
# (página "Não é possível acessar a página", erro 403). Tentamos via
# navegador real headless antes de desistir.
def scrape_magalu() -> list[Listing]:
    store = "Magalu"
    listings: list[Listing] = []
    url = "https://www.magazineluiza.com.br/busca/nintendo+switch+2+jogo/"

    soup = _get_rendered(url, debug_name="magalu_browser")
    if not soup:
        return listings

    cards = soup.select("[data-testid='product-card']")
    if not cards:
        title_tag = soup.find("title")
        print(
            f"[WARN] Magalu: 0 cards encontrados no HTML renderizado "
            f"(título da página: {title_tag.get_text(strip=True) if title_tag else '??'}). "
            f"Rode com SCRAPER_DEBUG=1 e confira debug_html/magalu_browser.html",
            file=sys.stderr,
        )
    for card in cards:
        title_el = card.select_one("[data-testid='product-title']")
        link_el = card.select_one("a")
        price_el = card.select_one("[data-testid='price-value']")
        original_el = card.select_one("[data-testid='price-original']")

        if not title_el or not price_el:
            continue

        title = title_el.get_text(strip=True)
        if "switch" not in title.lower():
            continue

        href = link_el.get("href", "") if link_el else ""
        if href and href.startswith("/"):
            href = "https://www.magazineluiza.com.br" + href

        price = _to_float_brl(price_el.get_text(strip=True))
        original = _to_float_brl(original_el.get_text(strip=True)) if original_el else None

        if price is None:
            continue

        listings.append(
            Listing(
                store=store,
                title=title,
                url=href,
                price=price,
                original_price=original,
                discount_pct=_discount(price, original),
            )
        )

    return listings


# ---------------------------------------------------------------------------
# Amazon BR
# ---------------------------------------------------------------------------
def scrape_amazon() -> list[Listing]:
    """
    Aviso: a Amazon bloqueia scraping agressivamente (anti-bot, CAPTCHA) e
    seus Termos de Uso proíbem explicitamente coleta automatizada de dados
    das páginas. Essa função tenta uma requisição simples; se a Amazon
    retornar bloqueio/CAPTCHA, ela falha silenciosamente (lista vazia) em
    vez de insistir. Para uma integração robusta e dentro das regras,
    o caminho recomendado é o Amazon PA-API via Programa de Afiliados.
    """
    store = "Amazon BR"
    listings: list[Listing] = []
    url = "https://www.amazon.com.br/s?k=nintendo+switch+2+jogo"

    soup = _get(url, debug_name="amazon")
    if not soup:
        return listings

    if soup.select_one("form[action*='validateCaptcha']"):
        print("[INFO] Amazon retornou CAPTCHA - pulando esta loja nesta execução.", file=sys.stderr)
        return listings

    cards = soup.select("div[data-component-type='s-search-result']")
    for card in cards:
        title_el = card.select_one("h2 span")
        link_el = card.select_one("h2 a")
        price_el = card.select_one("span.a-price > span.a-offscreen")
        original_el = card.select_one("span.a-price.a-text-price > span.a-offscreen")

        if not title_el or not price_el:
            continue

        title = title_el.get_text(strip=True)
        if "switch" not in title.lower():
            continue

        href = link_el.get("href", "") if link_el else ""
        if href and href.startswith("/"):
            href = "https://www.amazon.com.br" + href

        price = _to_float_brl(price_el.get_text(strip=True))
        original = _to_float_brl(original_el.get_text(strip=True)) if original_el else None

        if price is None:
            continue

        listings.append(
            Listing(
                store=store,
                title=title,
                url=href,
                price=price,
                original_price=original,
                discount_pct=_discount(price, original),
            )
        )

    return listings



# ---------------------------------------------------------------------------
# Promobit (agregador de ofertas)
# ---------------------------------------------------------------------------
# O Promobit não é uma loja - é um site que agrega ofertas de várias lojas,
# postadas pela própria comunidade. A página da categoria "Nintendo Switch"
# embute um bloco <script id="jsonld-category-offers"> com JSON-LD
# (schema.org/ItemList de Offer) já com preço, preço "de tabela" e a loja
# vendedora - não precisa de navegador, uma requisição simples já basta e
# (até onde testamos) não é bloqueada por IP de datacenter. A lista vem
# fixa em ~10 itens por página (não achamos paginação funcional via HTML
# puro), então é uma fonte complementar, não uma varredura completa.
def scrape_promobit() -> list[Listing]:
    store = "Promobit"
    listings: list[Listing] = []
    url = "https://www.promobit.com.br/promocoes/nintendo-switch/s/"

    resp = _get_raw(url, debug_name="promobit")
    if not resp:
        return listings

    match = re.search(
        r'<script id="jsonld-category-offers"[^>]*>(.*?)</script>', resp.text, re.DOTALL
    )
    if not match:
        print("[WARN] Promobit: bloco jsonld-category-offers não encontrado na página", file=sys.stderr)
        return listings

    try:
        data = json.loads(match.group(1))
        items = data["itemListElement"]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"[WARN] Promobit: estrutura do JSON-LD mudou ({e})", file=sys.stderr)
        return listings

    for list_item in items:
        product = list_item.get("item", {})
        title = product.get("name", "")
        title_lower = title.lower()
        if "switch 2" not in title_lower:
            continue
        # Foco em jogos, não no console/bundle em si, e ignora ofertas de
        # "cupom" cujo "preço" listado é simbólico (ex: R$0,01) e não reflete
        # o preço real de compra.
        if "console" in title_lower or "bundle" in title_lower:
            continue

        offers = product.get("offers") or []
        if not offers:
            continue
        offer = offers[0]

        price = offer.get("price")
        high = offer.get("highPrice")
        try:
            price = float(price)
        except (TypeError, ValueError):
            continue
        if price < 5:
            # Preço simbólico de "ative o cupom pra ver o valor real" - não
            # é um preço de compra de verdade.
            continue
        try:
            original = float(high) if high else None
        except (TypeError, ValueError):
            original = None
        if original is not None and original <= price:
            original = None

        seller = (offer.get("seller") or {}).get("name", "")
        href = offer.get("url", "")

        listings.append(
            Listing(
                store=f"Promobit ({seller})" if seller else store,
                title=title,
                url=href,
                price=price,
                original_price=original,
                discount_pct=_discount(price, original),
            )
        )

    return listings


SCRAPERS = {
    "Mercado Livre": scrape_mercadolivre,
    "Kabum": scrape_kabum,
    "Magalu": scrape_magalu,
    "Amazon BR": scrape_amazon,
    "Promobit": scrape_promobit,
}


def load_history() -> dict:
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"games": {}, "last_updated": None}


def save_history(history: dict) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_key(title: str, store: str) -> str:
    """Chave estável por anúncio (loja + título normalizado)."""
    norm = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return f"{store}::{norm}"


def main() -> None:
    history = load_history()
    now_iso = datetime.now(timezone.utc).isoformat()

    all_listings: list[Listing] = []
    for store, fn in SCRAPERS.items():
        print(f"[INFO] Coletando {store}...")
        try:
            results = fn()
            print(f"[INFO] {store}: {len(results)} jogos encontrados")
            all_listings.extend(results)
        except Exception:
            print(f"[ERROR] Falha na loja {store}:", file=sys.stderr)
            traceback.print_exc()
        time.sleep(2)

    for listing in all_listings:
        key = normalize_key(listing.title, listing.store)
        entry = history["games"].setdefault(
            key,
            {
                "title": listing.title,
                "store": listing.store,
                "url": listing.url,
                "currency": listing.currency,
                "history": [],
                "lowest_price_ever": None,
            },
        )
        entry["title"] = listing.title
        entry["url"] = listing.url
        entry["history"].append(
            {
                "date": now_iso,
                "price": listing.price,
                "original_price": listing.original_price,
                "discount_pct": listing.discount_pct,
            }
        )
        # mantém só os últimos 180 registros por jogo pra não crescer sem limite
        entry["history"] = entry["history"][-180:]

        lowest = entry.get("lowest_price_ever")
        if lowest is None or listing.price < lowest:
            entry["lowest_price_ever"] = listing.price

    history["last_updated"] = now_iso
    save_history(history)
    print(f"[INFO] Histórico salvo em {DATA_FILE} ({len(history['games'])} jogos no total)")


if __name__ == "__main__":
    main()
