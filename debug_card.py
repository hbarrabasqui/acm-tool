"""Inspeccionar un card específico de Zonaprop."""
import asyncio, re
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

URL = "https://www.zonaprop.com.ar/departamentos-venta-villa-soldati-1-ambientes.html"

async def dump():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
        )
        page = await context.new_page()
        await page.goto(URL, timeout=30_000, wait_until="domcontentloaded")
        await asyncio.sleep(3)
        html = await page.content()
        await browser.close()

    soup = BeautifulSoup(html, "html.parser")
    cards = soup.find_all("div", class_=re.compile(r"postingsList-module__card-container", re.I))
    print(f"Cards encontrados: {len(cards)}")

    for i, card in enumerate(cards[:6]):
        print(f"\n--- Card {i+1} ---")
        # Precio
        precio_el = card.find("h2", class_=re.compile(r"postingPrices-module__price", re.I))
        print(f"Precio raw: {precio_el.get_text(strip=True) if precio_el else 'N/A'}")

        # Features
        feature_spans = card.find_all("span", class_=re.compile(r"posting-main-features-span", re.I))
        print(f"Features spans ({len(feature_spans)}):")
        for s in feature_spans:
            print(f"  '{s.get_text(strip=True)}'")

        # URL
        layout_el = card.find("div", class_=re.compile(r"posting-card-layout", re.I))
        url = layout_el.get("data-to-posting", "") if layout_el else ""
        print(f"URL: {url[:80]}")

asyncio.run(dump())
