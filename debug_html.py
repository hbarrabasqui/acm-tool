"""Script para dumpear el HTML real de Zonaprop y MercadoLibre."""
import asyncio
from playwright.async_api import async_playwright

async def dump(url, filename):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
        )
        page = await context.new_page()
        await page.goto(url, timeout=30_000, wait_until="domcontentloaded")
        await asyncio.sleep(3)
        for _ in range(3):
            await page.mouse.wheel(0, 2000)
            await asyncio.sleep(1.5)
        html = await page.content()
        await browser.close()
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Guardado: {filename} ({len(html)//1024} KB)")

asyncio.run(dump(
    "https://www.zonaprop.com.ar/departamentos-venta-palermo-2-ambientes.html",
    "debug_zonaprop.html"
))
asyncio.run(dump(
    "https://inmuebles.mercadolibre.com.ar/departamentos/venta/departamento-en-palermo/_PriceRange_USD",
    "debug_mercadolibre.html"
))
