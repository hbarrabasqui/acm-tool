"""Prueba técnicas anti-detección para MercadoLibre."""
import asyncio
from playwright.async_api import async_playwright

URL = "https://inmuebles.mercadolibre.com.ar/departamentos/venta/"

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-web-security",
            ]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
            locale="es-AR",
            timezone_id="America/Argentina/Buenos_Aires",
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )
        page = await context.new_page()

        # Parchar webdriver property
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
        """)

        await page.goto(URL, timeout=30_000, wait_until="domcontentloaded")
        await asyncio.sleep(5)

        title = await page.title()
        html = await page.content()
        await browser.close()

    blocked = "ingresa" in html.lower() or "iniciar sesi" in html.lower()
    listings = html.lower().count("ui-search-layout__item")
    print(f"Title: {title}")
    print(f"Bloqueado: {blocked}")
    print(f"Cards (ui-search-layout__item): {listings}")

    with open("debug_ml3.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Guardado debug_ml3.html")

asyncio.run(test())
