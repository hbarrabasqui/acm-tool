"""Prueba distintas URLs de MercadoLibre para ver cuál no bloquea."""
import asyncio
from playwright.async_api import async_playwright

URLS = [
    "https://inmuebles.mercadolibre.com.ar/departamentos/venta/departamento-en-palermo/_PriceRange_USD",
    "https://inmuebles.mercadolibre.com.ar/departamentos/venta/_PriceRange_USD_Desde_50000_Hasta_300000/palermo",
    "https://inmuebles.mercadolibre.com.ar/departamentos/venta/",
]

async def test(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
        )
        page = await context.new_page()
        await page.goto(url, timeout=30_000, wait_until="domcontentloaded")
        await asyncio.sleep(3)
        title = await page.title()
        html = await page.content()
        await browser.close()
    # Guardar
    fname = url.replace("https://", "").replace("/", "_")[:60] + ".html"
    with open(fname, "w", encoding="utf-8") as f:
        f.write(html)
    blocked = "ingresa" in html.lower() or "iniciar sesi" in html.lower() or "login" in html.lower()
    listings = html.lower().count("ui-search-layout__item")
    print(f"URL: {url[:80]}")
    print(f"  Title: {title}")
    print(f"  Bloqueado: {blocked}")
    print(f"  Cards encontrados (ui-search-layout__item): {listings}")
    print()

for url in URLS:
    asyncio.run(test(url))
