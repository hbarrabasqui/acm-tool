"""Test ArgenProp scraping."""
import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

URL = "https://www.argenprop.com/departamento-en-venta-en-palermo--2-ambientes"

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
            locale="es-AR",
        )
        page = await context.new_page()
        await Stealth().apply_stealth_async(page)
        await page.goto(URL, timeout=30_000, wait_until="domcontentloaded")
        await asyncio.sleep(3)
        title = await page.title()
        html = await page.content()
        await browser.close()

    blocked = "captcha" in html.lower() or "robot" in html.lower() or "blocked" in html.lower()
    # Buscar clases típicas de cards
    for kw in ["listing", "card", "property", "prop-", "inmueble"]:
        count = html.lower().count(kw)
        if count > 5:
            print(f"  Keyword '{kw}': {count} veces")

    print(f"Title: {title}")
    print(f"Bloqueado: {blocked}")
    print(f"HTML size: {len(html)//1024} KB")

    with open("debug_argenprop.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Guardado debug_argenprop.html")

asyncio.run(test())
