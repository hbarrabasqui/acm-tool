"""
Scraper para ArgenProp — usa Playwright para renderizar JS y BeautifulSoup para parsear.
Busca propiedades en venta en Argentina.
"""

import re
import asyncio
from typing import Optional
from playwright.async_api import async_playwright, TimeoutError as PWTimeout
from playwright_stealth import Stealth
from bs4 import BeautifulSoup


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse_price(card) -> int:
    """Extrae precio USD. Usa data-precio si existe, sino parsea el texto."""
    # Opción 1: data-precio en botón de contacto (más limpio)
    el = card.find(attrs={"data-precio": True})
    if el:
        try:
            return int(el["data-precio"])
        except (ValueError, TypeError):
            pass

    # Opción 2: p.card__price — moneda + número
    price_el = card.find("p", class_="card__price")
    if price_el:
        currency_el = price_el.find("span", class_="card__currency")
        currency = currency_el.get_text(strip=True) if currency_el else ""
        if "USD" in currency.upper() or "U$S" in currency.upper() or "US$" in currency.upper():
            # Remover el span de moneda y el de expensas para quedarnos con el número
            price_text = price_el.get_text(separator=" ", strip=True)
            nums = re.sub(r"[^\d]", "", price_text.split("+")[0])
            if nums:
                return int(nums)
    return 0


def _parse_metros(features_ul) -> float:
    """Extrae m² cubiertos de la lista de features."""
    if not features_ul:
        return 0
    for li in features_ul.find_all("li"):
        icon = li.find("i")
        if icon and "superficie" in (icon.get("class", [""])[0] if icon.get("class") else "").lower():
            span = li.find("span")
            if span:
                m = re.search(r"(\d+[\.,]?\d*)", span.get_text())
                if m:
                    return float(m.group(1).replace(",", "."))
        # Fallback: si el span contiene "m²"
        span = li.find("span")
        if span and "m²" in span.get_text():
            m = re.search(r"(\d+[\.,]?\d*)", span.get_text())
            if m:
                return float(m.group(1).replace(",", "."))
    return 0


def _parse_ambientes(features_ul) -> str:
    """Extrae dormitorios/ambientes de la lista de features."""
    if not features_ul:
        return ""
    for li in features_ul.find_all("li"):
        icon = li.find("i")
        icon_class = (icon.get("class", [""])[0] if icon and icon.get("class") else "").lower()
        if "dormitorio" in icon_class or "ambiente" in icon_class or "cuarto" in icon_class:
            span = li.find("span")
            return span.get_text(strip=True) if span else ""
    # Fallback: buscar en atributo del card
    return ""


def _build_url(prop: dict) -> str:
    """Construye la URL de búsqueda en ArgenProp."""
    tipo_map = {
        "Departamento": "departamento",
        "Casa": "casa",
        "PH": "ph",
        "Local": "local-comercial",
        "Oficina": "oficina",
    }
    tipo_slug = tipo_map.get(prop.get("tipo", "Departamento"), "departamento")

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
            amb_param = f"--{n}-ambientes"

    return f"https://www.argenprop.com/{tipo_slug}-en-venta-en-{barrio_slug}{amb_param}"


def _parse_listing(card) -> Optional[dict]:
    """Parsea un card de ArgenProp y devuelve dict normalizado."""
    try:
        # URL y link principal
        link_el = card.find("a", class_="card")
        if not link_el:
            link_el = card.find("a", href=True)
        href = link_el["href"] if link_el and link_el.get("href") else ""
        url = ("https://www.argenprop.com" + href) if href.startswith("/") else href

        # Título
        titulo_el = card.find("h2", class_="card__title")
        titulo = titulo_el.get_text(strip=True) if titulo_el else "Sin título"

        # Precio
        precio_usd = _parse_price(card)

        # Features (m², ambientes)
        features_ul = card.find("ul", class_="card__main-features")
        metros = _parse_metros(features_ul)
        ambientes = _parse_ambientes(features_ul)

        # Fallback ambientes desde atributo del link
        if not ambientes and link_el:
            dorms = link_el.get("dormitorios", "")
            if dorms:
                ambientes = f"{dorms} dorm."

        # Barrio/dirección
        addr_el = card.find("p", class_="card__address")
        barrio_encontrado = addr_el.get_text(strip=True) if addr_el else ""

        # Descripción
        desc_el = card.find("p", class_=re.compile(r"description|detail", re.I))
        descripcion = desc_el.get_text(strip=True)[:300] if desc_el else ""

        return {
            "fuente": "ArgenProp",
            "titulo": titulo,
            "barrio": barrio_encontrado,
            "direccion": barrio_encontrado,  # En ArgenProp el barrio ya es la dirección de calle
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

async def scrape_argenprop(prop: dict, max_results: int = 15) -> list[dict]:
    """
    Scrapea ArgenProp y devuelve lista de propiedades comparables.

    Args:
        prop: Diccionario con los datos de la propiedad buscada.
        max_results: Máximo de resultados a retornar.

    Returns:
        Lista de dicts con propiedades normalizadas.
    """
    url = _build_url(prop)
    resultados = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
            locale="es-AR",
            timezone_id="America/Argentina/Buenos_Aires",
        )
        page = await context.new_page()
        await Stealth().apply_stealth_async(page)

        try:
            await page.goto(url, timeout=30_000, wait_until="domcontentloaded")
            await page.wait_for_selector(".listing__item, .card", timeout=15_000)
        except PWTimeout:
            pass

        for _ in range(3):
            await page.mouse.wheel(0, 2000)
            await asyncio.sleep(1.5)

        html = await page.content()
        await browser.close()

    soup = BeautifulSoup(html, "html.parser")

    cards = (
        soup.find_all("div", class_="listing__item") or
        soup.find_all("div", class_=re.compile(r"listing__item|card-container", re.I)) or
        soup.find_all("article")
    )

    barrio_keywords = [
        w.lower() for w in re.split(r"[\s,]+", prop.get("barrio", "")) if len(w) > 2
    ]

    for card in cards[:max_results * 3]:
        item = _parse_listing(card)
        if not item or item["precio_usd"] <= 0:
            continue
        barrio_result = item["barrio"].lower()
        if barrio_keywords and not any(kw in barrio_result for kw in barrio_keywords):
            continue
        resultados.append(item)
        if len(resultados) >= max_results:
            break

    return resultados


# ── Test rápido ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    prop_test = {
        "barrio": "Palermo",
        "tipo": "Departamento",
        "ambientes": 2,
        "metros_cubiertos": 55,
    }
    results = asyncio.run(scrape_argenprop(prop_test, max_results=10))
    print(f"Resultados: {len(results)}")
    for r in results:
        print(r)
