# ACM Tool

Herramienta para automatizar la búsqueda de propiedades comparables en el **Análisis Comparativo de Mercado (ACM)**.

Busca en **Zonaprop** y **ArgenProp** paginando múltiples páginas en paralelo, y usa **Claude AI** para generar un informe con precio sugerido, resumen ejecutivo, outliers y recomendaciones. Incluye mapa interactivo con geocodificación.

---

## Instalación

### Requisitos
- Python 3.10 o superior
- API Key de Anthropic → https://console.anthropic.com/

### Pasos

```bash
# 1. Clonar el repositorio
git clone https://github.com/hbarrabasqui/acm-tool.git
cd acm-tool

# 2. Crear entorno virtual
python -m venv venv

# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Instalar Chromium (navegador headless)
playwright install chromium

# 5. Configurar API Key
# Crear archivo .env en la raíz del proyecto con:
ANTHROPIC_API_KEY=sk-ant-tu-clave-aqui

# 6. Correr la app
streamlit run app.py
```

Se abre en `http://localhost:8501`

---

## Uso

1. Completar el formulario:
   - **Barrio / Zona**: nombre del barrio (ej: Palermo, San Nicolás). Acepta múltiples separados por coma.
   - **Jurisdicción**: CABA o partido del GBA (selectbox — evita ambigüedad en geocodificación)
   - **Tipo, ambientes, m², antigüedad, amenities**
   - **Contexto libre**: instrucciones adicionales para Claude (ej: "el dueño necesita vender rápido")
   - **Dirección de referencia** (opcional): activa el mapa con pins de cada comparable

2. Ajustar fuentes y cantidad máxima de resultados por fuente (default 50, máximo 100)

3. Click en **"Buscar comparables y generar ACM"**

4. Resultados:
   - Métricas: precio promedio, USD/m², mínimo, máximo
   - Tabla completa de comparables con links a cada publicación
   - Mapa interactivo (si se ingresó dirección de referencia) — el radio se ajusta sin repetir la búsqueda
   - Informe de IA: precio sugerido, resumen, outliers, recomendaciones
   - Exportar a Excel con hipervínculos clickeables

---

## Estructura

```
acm-tool/
├── app.py              — Interfaz Streamlit (formulario + resultados + mapa)
├── analyzer.py         — Análisis con Claude API
├── scrapers/
│   ├── zonaprop.py     — Scraper Zonaprop (Playwright + BS4, paginado)
│   └── argenprop.py    — Scraper ArgenProp (Playwright + BS4 + stealth, paginado)
├── requirements.txt
└── .env                — API Key (no se sube a GitHub)
```

---

## Detalles técnicos

### Scrapers
- Usan **Playwright** (Chromium headless) para renderizar JS antes de parsear con BeautifulSoup
- **Paginan hasta 10 páginas** por fuente, reutilizando el mismo browser entre páginas
- **Corren en paralelo** (asyncio.gather): Zonaprop y ArgenProp al mismo tiempo
- ArgenProp usa **playwright-stealth** para evadir detección de bots
- Filtro de barrio con normalización de acentos y word boundary (evita falsos positivos como "san" dentro de "santos")
- En Windows Streamlit requiere `asyncio.ProactorEventLoop` en thread separado

### Mapa
- Geocodificación con **Nominatim/OpenStreetMap** (gratuito, sin API key)
- Cache con `@st.cache_data` para no repetir geocodificaciones
- Solo geocodifica propiedades con número de calle (no solo nombre de barrio)
- Bounding box de validación para descartar resultados fuera del área
- La jurisdicción seleccionada se pasa como contexto a Nominatim para evitar ambigüedad CABA vs provincia

### IA
- Modelo: `claude-sonnet-4-20250514`
- El campo "contexto libre" permite agregar instrucciones específicas sin tocar el código

---

## Troubleshooting

**El scraper devuelve 0 resultados**
- Verificar conexión a internet
- El sitio puede haber cambiado su HTML → revisar selectores en `scrapers/zonaprop.py` o `scrapers/argenprop.py`
- Probar con un barrio más conocido (Palermo, Belgrano)

**Error: ANTHROPIC_API_KEY not found**
- Verificar que existe el archivo `.env` en la raíz con la clave correcta

**Error: playwright install no funciona**
```bash
python -m playwright install chromium
```

**El mapa muestra propiedades fuera del barrio**
- Verificar que la jurisdicción seleccionada es correcta (CABA vs GBA)
- Nominatim puede fallar con calles muy cortas o poco conocidas

---

## Dependencias principales

| Paquete | Uso |
|---------|-----|
| `streamlit` | Interfaz web |
| `playwright` | Navegador headless para scraping |
| `playwright-stealth` | Evasión de detección en ArgenProp |
| `beautifulsoup4` | Parsing de HTML |
| `anthropic` | Claude API para análisis ACM |
| `pandas` | Tablas de datos |
| `folium` + `streamlit-folium` | Mapa interactivo |
| `geopy` | Geocodificación y cálculo de distancias |
| `openpyxl` | Excel con hipervínculos |
| `python-dotenv` | Variables de entorno |
