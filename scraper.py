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


def _get(url: str) -> Optional[BeautifulSoup]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except requests.RequestException as e:
        print(f"[WARN] Falha ao buscar {url}: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Mercado Livre
# ---------------------------------------------------------------------------
def scrape_mercadolivre() -> list[Listing]:
    store = "Mercado Livre"
    listings: list[Listing] = []
    base = "https://lista.mercadolivre.com.br/jogo-nintendo-switch-2"

    for page in range(MAX_PAGES_PER_STORE):
        offset = page * 50 + 1
        url = base if page == 0 else f"{base}_Desde_{offset}"
        soup = _get(url)
        if not soup:
            break

        items = soup.select("li.ui-search-layout__item")
        if not items:
            break

        for item in items:
            title_el = item.select_one("h2.ui-search-item__title, h3.poly-component__title")
            link_el = item.select_one("a.ui-search-link, a.poly-component__title")
            price_el = item.select_one("span.andes-money-amount__fraction")
            original_el = item.select_one(
                "s.andes-money-amount--previous span.andes-money-amount__fraction"
            )

            if not title_el or not link_el or not price_el:
                continue

            title = title_el.get_text(strip=True)
            if "switch" not in title.lower():
                continue

            url_item = link_el.get("href", "")
            price = _to_float_brl(price_el.get_text(strip=True))
            original = (
                _to_float_brl(original_el.get_text(strip=True)) if original_el else None
            )

            if price is None:
                continue

            listings.append(
                Listing(
                    store=store,
                    title=title,
                    url=url_item,
                    price=price,
                    original_price=original,
                    discount_pct=_discount(price, original),
                )
            )
        time.sleep(1)

    return listings


# ---------------------------------------------------------------------------
# Kabum
# ---------------------------------------------------------------------------
def scrape_kabum() -> list[Listing]:
    store = "Kabum"
    listings: list[Listing] = []
    url = "https://www.kabum.com.br/busca/nintendo-switch-2-jogo"

    soup = _get(url)
    if not soup:
        return listings

    cards = soup.select("[data-testid='product-card']")
    for card in cards:
        title_el = card.select_one("[data-testid='product-card::name'], .nameCard")
        link_el = card if card.name == "a" else card.find_parent("a")
        price_el = card.select_one("[data-testid='price-value']")
        original_el = card.select_one("[data-testid='old-price-value'], .oldPriceCard")

        if not title_el or not price_el:
            continue

        title = title_el.get_text(strip=True)
        if "switch" not in title.lower():
            continue

        href = link_el.get("href", "") if link_el else ""
        if href and href.startswith("/"):
            href = "https://www.kabum.com.br" + href

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
# Magazine Luiza
# ---------------------------------------------------------------------------
def scrape_magalu() -> list[Listing]:
    store = "Magalu"
    listings: list[Listing] = []
    url = "https://www.magazineluiza.com.br/busca/nintendo+switch+2+jogo/"

    soup = _get(url)
    if not soup:
        return listings

    cards = soup.select("[data-testid='product-card']")
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

    soup = _get(url)
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


SCRAPERS = {
    "Mercado Livre": scrape_mercadolivre,
    "Kabum": scrape_kabum,
    "Magalu": scrape_magalu,
    "Amazon BR": scrape_amazon,
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
