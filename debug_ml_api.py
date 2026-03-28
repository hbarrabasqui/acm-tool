"""Test MercadoLibre API pública para búsqueda de inmuebles."""
import urllib.request
import json

# MLA = Argentina. Categoría MLA1459 = Inmuebles en venta
# https://api.mercadolibre.com/sites/MLA/categories → para explorar categorías

url = (
    "https://api.mercadolibre.com/sites/MLA/search"
    "?category=MLA1459"
    "&q=departamento+palermo"
    "&price_min=50000"
    "&price_max=500000"
    "&currency_id=USD"
    "&limit=5"
)

req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req) as r:
    data = json.loads(r.read())

print(f"Total resultados: {data.get('paging', {}).get('total', 0)}")
print()
for item in data.get("results", [])[:3]:
    print(f"Título: {item.get('title')}")
    print(f"Precio: {item.get('price')} {item.get('currency_id')}")
    print(f"URL: {item.get('permalink')}")
    attrs = {a['id']: a.get('value_name') for a in item.get('attributes', [])}
    print(f"Superficie: {attrs.get('TOTAL_AREA', attrs.get('COVERED_AREA', 'N/A'))}")
    print(f"Ambientes: {attrs.get('ROOMS', 'N/A')}")
    print(f"Barrio: {item.get('location', {}).get('neighborhood', {}).get('name', 'N/A')}")
    print()
