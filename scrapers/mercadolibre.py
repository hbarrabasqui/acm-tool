"""
Scraper para MercadoLibre Inmuebles (Argentina) — usa la API oficial de ML.
No requiere scraping, obtiene datos estructurados directamente.
"""

import os
import re
import time
import urllib.request
import urllib.parse
import json
from typing import Optional

# Cache del token para no pedir uno nuevo en cada búsqueda
_token_cache = {"access_token": None, "expires_at": 0}


def _get_app_token() -> str:
    """Obtiene un App Token usando Client Credentials flow. Cachea el token."""
    now = time.time()
    if _token_cache["access_token"] and now < _token_cache["expires_at"] - 60:
        return _token_cache["access_token"]

    client_id = os.getenv("ML_CLIENT_ID")
    client_secret = os.getenv("ML_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise ValueError("Faltan ML_CLIENT_ID o ML_CLIENT_SECRET en el .env")

    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode()

    req = urllib.request.Request(
        "https://api.mercadolibre.com/oauth/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        resp = json.loads(r.read())

    _token_cache["access_token"] = resp["access_token"]
    _token_cache["expires_at"] = now + resp.get("expires_in", 21600)
    return _token_cache["access_token"]


def _api_get(url: str, token: str) -> dict:
    """Hace un GET a la API de ML con el token."""
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def _build_search_url(prop: dict, offset: int = 0, limit: int = 20) -> str:
    """Construye la URL de búsqueda en la API de ML."""
    # Categoría MLA1459 = Inmuebles Argentina
    # Subcategorías: MLA1472 Departamentos, MLA1473 Casas, etc.
    tipo_cat = {
        "Departamento": "MLA1472",
        "Casa": "MLA1473",
        "PH": "MLA1476",
        "Local": "MLA1477",
        "Oficina": "MLA1478",
    }
    categoria = tipo_cat.get(prop.get("tipo", "Departamento"), "MLA1472")

    barrio = prop.get("barrio", "").strip()
    ambientes = prop.get("ambientes", "")

    query_parts = [barrio]
    if ambientes and str(ambientes).isdigit():
        query_parts.append(f"{ambientes} ambientes")
    query = " ".join(query_parts)

    params = urllib.parse.urlencode({
        "category": categoria,
        "q": query,
        "currency_id": "USD",
        "offset": offset,
        "limit": limit,
    })
    return f"https://api.mercadolibre.com/sites/MLA/search?{params}"


def _parse_item(item: dict) -> Optional[dict]:
    """Convierte un item de la API de ML al formato normalizado."""
    try:
        precio_usd = 0
        if item.get("currency_id") == "USD":
            precio_usd = int(item.get("price", 0) or 0)
        if precio_usd == 0:
            return None

        # Atributos
        attrs = {a["id"]: a.get("value_name", "") for a in item.get("attributes", [])}

        metros = 0
        metros_str = attrs.get("COVERED_AREA") or attrs.get("TOTAL_AREA") or ""
        if metros_str:
            m = re.search(r"(\d+[\.,]?\d*)", str(metros_str))
            if m:
                metros = float(m.group(1).replace(",", "."))

        rooms = attrs.get("ROOMS", "") or attrs.get("BEDROOMS", "")
        ambientes = f"{rooms} amb." if rooms else ""

        location = item.get("location", {})
        barrio_parts = [
            location.get("neighborhood", {}).get("name", ""),
            location.get("city", {}).get("name", ""),
        ]
        barrio_encontrado = ", ".join(p for p in barrio_parts if p)

        return {
            "fuente": "MercadoLibre",
            "titulo": item.get("title", "Sin título")[:120],
            "barrio": barrio_encontrado,
            "tipo": "",
            "ambientes": ambientes,
            "metros_cubiertos": metros,
            "precio_usd": precio_usd,
            "antiguedad": attrs.get("PROPERTY_AGE", ""),
            "amenities": "",
            "url": item.get("permalink", "").split("?")[0],
        }
    except Exception:
        return None


async def scrape_mercadolibre(prop: dict, max_results: int = 15) -> list[dict]:
    """
    Busca propiedades en MercadoLibre via API oficial y devuelve comparables.

    Args:
        prop: Diccionario con los datos de la propiedad buscada.
        max_results: Máximo de resultados a retornar.

    Returns:
        Lista de dicts con propiedades normalizadas.
    """
    from dotenv import load_dotenv
    load_dotenv()

    token = _get_app_token()
    url = _build_search_url(prop, limit=min(max_results * 2, 48))
    data = _api_get(url, token)

    resultados = []
    for item in data.get("results", []):
        parsed = _parse_item(item)
        if parsed:
            resultados.append(parsed)
        if len(resultados) >= max_results:
            break

    return resultados


# ── Test rápido ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import asyncio
    from dotenv import load_dotenv
    load_dotenv()

    prop_test = {
        "barrio": "Palermo",
        "tipo": "Departamento",
        "ambientes": 2,
        "metros_cubiertos": 55,
    }
    results = asyncio.run(scrape_mercadolibre(prop_test, max_results=10))
    print(f"Resultados: {len(results)}")
    for r in results:
        print(r)
