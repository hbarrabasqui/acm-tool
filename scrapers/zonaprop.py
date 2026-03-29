"""
Scraper para Zonaprop — usa Playwright para renderizar JS y BeautifulSoup para parsear.
Busca propiedades en venta en Argentina.
"""

import re
import asyncio
from typing import Optional
from playwright.async_api import async_playwright, TimeoutError as PWTimeout
from bs4 import BeautifulSoup


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse_price(text: str) -> Optional[int]:
    """Extrae precio en USD o ARS. Devuelve None si no es USD (o si no parsea)."""
    if not text:
        return None
    text = text.upper().replace("\xa0", " ").strip()
    if "USD" in text or "U$S" in text or "US$" in text or "$" in text:
        nums = re.sub(r"[^\d]", "", text)
        return int(nums) if nums else None
    return None


def _parse_metros(text: str) -> Optional[float]:
    """Extrae m² de un string tipo '65 m²'."""
    if not text:
        return None
    m = re.search(r"(\d+[\.,]?\d*)\s*m", text, re.IGNORECASE)
    if m:
        return float(m.group(1).replace(",", "."))
    return None


def _build_url(prop: dict, pagina: int = 1) -> str:
    """Construye la URL de búsqueda en Zonaprop para una página dada."""
    tipo_map = {
        "Departamento": "departamentos",
        "Casa": "casas",
        "PH": "ph",
        "Local": "locales-comerciales",
        "Oficina": "oficinas",
    }
    tipo_slug = tipo_map.get(prop.get("tipo", "Departamento"), "departamentos")
    barrio_slug = (
        prop.get("barrio", "")
        .lower()
        .strip()
        .replace(" ", "-")
        .replace("á", "a").replace("é", "e").replace("í", "i")
        .replace("ó", "o").replace("ú", "u").replace("ñ", "n")
    )

    ambientes = prop.get("ambientes", None)
    amb_param = ""
    if ambientes and str(ambientes).isdigit():
        n = int(str(ambientes))
        if 1 <= n <= 6:
            amb_param = f"-{n}-ambientes"

    pag_param = f"-{pagina}" if pagina > 1 else ""
    return f"https://www.zonaprop.com.ar/{tipo_slug}-venta-{barrio_slug}{amb_param}{pag_param}.html"


def _parse_listing(card, source_url: str) -> Optional[dict]:
    """Parsea un card HTML de Zonaprop y devuelve un dict normalizado."""
    try:
        # Título — h2 con clase postingCard-module__posting-description > a
        desc_h2 = card.find("h2", class_=re.compile(r"posting-description", re.I))
        titulo_el = desc_h2.find("a") if desc_h2 else None
        titulo = titulo_el.get_text(strip=True) if titulo_el else "Sin título"

        # URL — primero intenta data-to-posting, luego href del link del título
        layout_el = card.find("div", class_=re.compile(r"posting-card-layout", re.I))
        url = ""
        if layout_el and layout_el.get("data-to-posting"):
            path = layout_el["data-to-posting"].split("?")[0]
            url = "https://www.zonaprop.com.ar" + path
        elif titulo_el and titulo_el.get("href"):
            href = titulo_el["href"].split("?")[0]
            url = href if href.startswith("http") else "https://www.zonaprop.com.ar" + href

        # Precio — h2 con clase postingPrices-module__price
        precio_el = card.find("h2", class_=re.compile(r"postingPrices-module__price", re.I))
        precio_text = precio_el.get_text(strip=True) if precio_el else ""
        precio_usd = _parse_price(precio_text) or 0

        # m² y ambientes — buscar solo en el primer bloque de features (evita cards con múltiples listings anidados)
        features_block = card.find("div", class_=re.compile(r"posting-main-features-block", re.I))
        if features_block:
            feature_spans = features_block.find_all("span", class_=re.compile(r"posting-main-features-span", re.I))
        else:
            feature_spans = card.find_all("span", class_=re.compile(r"posting-main-features-span", re.I))[:6]
        metros = 0
        ambientes = ""
        for span in feature_spans:
            text = span.get_text(strip=True)
            if "m²" in text or "m2" in text.lower():
                metros = _parse_metros(text) or 0
            elif "amb" in text.lower():
                ambientes = text

        # Barrio — h4 con clase postingLocations-module__location-text
        loc_el = card.find("h4", class_=re.compile(r"location-text", re.I))
        barrio_encontrado = loc_el.get_text(strip=True) if loc_el else ""

        # Dirección de calle — h4 con clase postingLocations-module__location-address
        addr_el = card.find("h4", class_=re.compile(r"location-address", re.I))
        direccion_calle = addr_el.get_text(strip=True) if addr_el else ""

        # Descripción extra
        desc_el = card.find("p")
        descripcion = desc_el.get_text(strip=True)[:300] if desc_el else ""

        return {
            "fuente": "Zonaprop",
            "titulo": titulo,
            "barrio": barrio_encontrado,
            "direccion": direccion_calle,
            "tipo": "",
            "ambientes": ambientes,
            "metros_cubiertos": metros,
            "precio_usd": precio_usd,
            "antiguedad": "",
            "amenities": descripcion,
            "url": url,
        }
    except Exception:
        return None


# ── Scraper principal ──────────────────────────────────────────────────────────

async def scrape_zonaprop(prop: dict, max_results: int = 15, max_paginas: int = 10) -> list[dict]:
    """
    Scrapea Zonaprop paginando hasta obtener max_results o agotar max_paginas.
    Reutiliza el mismo browser entre páginas para reducir overhead.
    """
    resultados = []
    def _normalizar(s):
        for a, b in [("á","a"),("é","e"),("í","i"),("ó","o"),("ú","u"),("ñ","n")]:
            s = s.replace(a, b)
        return s.lower()

    barrio_keywords = [
        _normalizar(w) for w in re.split(r"[\s,]+", prop.get("barrio", "")) if len(w) > 2
    ]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        page = await context.new_page()

        for pagina in range(1, max_paginas + 1):
            url = _build_url(prop, pagina)
            try:
                await page.goto(url, timeout=30_000, wait_until="domcontentloaded")
                await page.wait_for_selector(
                    "[data-qa='posting-card'], .postingCard, article",
                    timeout=15_000
                )
            except PWTimeout:
                pass  # Intentamos parsear lo que cargó

            for _ in range(3):
                await page.mouse.wheel(0, 2000)
                await asyncio.sleep(1.0)

            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")

            cards = (
                soup.find_all("div", class_=re.compile(r"postingsList-module__card-container", re.I)) or
                soup.find_all("div", {"data-qa": re.compile(r"posting", re.I)}) or
                soup.find_all("div", class_=re.compile(r"posting-card|postingCard", re.I)) or
                soup.find_all("article")
            )

            if not cards:
                break  # No hay más páginas

            nuevos = 0
            for card in cards:
                layout_el = card.find("div", class_=re.compile(r"posting-card-layout", re.I))
                if layout_el and "veclappa" in layout_el.get("data-to-posting", ""):
                    continue
                item = _parse_listing(card, url)
                if not item or item["precio_usd"] <= 0:
                    continue
                barrio_result = _normalizar(item["barrio"])
                if barrio_keywords and not any(re.search(r'\b' + re.escape(kw) + r'\b', barrio_result) for kw in barrio_keywords):
                    continue
                # Evitar duplicados por URL
                if any(r["url"] == item["url"] for r in resultados):
                    continue
                resultados.append(item)
                nuevos += 1
                if len(resultados) >= max_results:
                    break

            if len(resultados) >= max_results or nuevos == 0:
                break

        await browser.close()

    return resultados

