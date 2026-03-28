"""Test MercadoLibre con playwright-stealth."""
import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

URL = "https://inmuebles.mercadolibre.com.ar/departamentos/venta/"

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
            locale="es-AR",
            timezone_id="America/Argentina/Buenos_Aires",
        )
        page = await context.new_page()
        await Stealth().apply_stealth_async(page)

        await page.goto(URL, timeout=30_000, wait_until="domcontentloaded")
        await asyncio.sleep(4)

        title = await page.title()
        html = await page.content()
        await browser.close()

    blocked = "ingresa" in html.lower() or "iniciar sesi" in html.lower()
    listings = html.lower().count("ui-search-layout__item")
    print(f"Title: {title}")
    print(f"Bloqueado: {blocked}")
    print(f"Cards: {listings}")

    with open("debug_ml4.html", "w", encoding="utf-8") as f:
        f.write(html)

asyncio.run(test())
