# 🏠 ACM Automático · Remax

Herramienta para automatizar la búsqueda de propiedades comparables en el **Análisis Comparativo de Mercado (ACM)**.

Busca automáticamente en **Zonaprop** y **MercadoLibre Inmuebles**, y usa **Claude AI** para generar un informe profesional con precio sugerido.

---

## ⚡ Instalación rápida

### 1. Requisitos previos
- Python 3.10 o superior → https://python.org
- pip (viene con Python)

### 2. Clonar / descomprimir el proyecto
```bash
cd acm-remax
```

### 3. Crear entorno virtual (recomendado)
```bash
python -m venv venv

# En Windows:
venv\Scripts\activate

# En Mac/Linux:
source venv/bin/activate
```

### 4. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 5. Instalar el navegador de Playwright
```bash
playwright install chromium
```

### 6. Configurar la API Key de Claude
```bash
# Copiar el archivo de ejemplo
cp .env.example .env

# Editar .env con tu editor favorito y pegar tu API Key
# Obtenela gratis en: https://console.anthropic.com/
```

El archivo `.env` debe quedar así:
```
ANTHROPIC_API_KEY=sk-ant-tu-clave-aqui
```

### 7. Correr la aplicación
```bash
streamlit run app.py
```

Se abre automáticamente en `http://localhost:8501` 🎉

---

## 🗂️ Estructura del proyecto

```
acm-remax/
├── app.py                  ← Interfaz Streamlit (formulario + resultados)
├── analyzer.py             ← Análisis con Claude API
├── scrapers/
│   ├── __init__.py
│   ├── zonaprop.py         ← Scraper Zonaprop (Playwright + BS4)
│   └── mercadolibre.py     ← Scraper MercadoLibre (Playwright + BS4)
├── requirements.txt
├── .env.example            ← Template de configuración
├── .gitignore
└── README.md
```

---

## 🔧 Uso

1. Completar el formulario con los datos de la propiedad a valuar:
   - Barrio, tipo, ambientes, m², antigüedad
   - Amenities (terraza, cochera, piscina, etc.)
   - Precio estimado (opcional)

2. Elegir las fuentes (Zonaprop, MercadoLibre)

3. Hacer click en **"Buscar comparables y generar ACM"**

4. Ver:
   - Tabla de propiedades comparables con precios y m²
   - Métricas: precio promedio, USD/m², mínimo, máximo
   - Informe de IA: precio sugerido, resumen ejecutivo, outliers, recomendaciones
   - Exportar resultados a CSV

---

## ⚠️ Notas importantes

### Sobre el scraping
- Zonaprop y MercadoLibre son sitios públicos; el scraping es para uso personal del agente.
- Los sitios pueden cambiar su HTML en cualquier momento → si los resultados fallan, revisar los selectores CSS en `scrapers/zonaprop.py` y `scrapers/mercadolibre.py`.
- Playwright ejecuta un navegador real (Chromium headless), por eso funciona aunque el sitio use JavaScript.

### Detección de bloqueos
Si el scraper retorna 0 resultados, puede que el sitio esté bloqueando el bot. Opciones:
1. Correr con `headless=False` en el scraper para ver qué pasa en el navegador
2. Agregar delays más largos entre requests
3. Rotar User-Agents

### Integración con plataforma Remax (próximo paso)
Para automatizar el login en la plataforma interna de Remax:
- Crear `scrapers/remax_internal.py`
- Usar Playwright para navegar a la URL interna, hacer `page.fill("#usuario", usuario)` y `page.fill("#password", password)`
- Revisar los Términos de Uso de Remax antes de activarlo

---

## 🛠️ Troubleshooting

**Error: `playwright install` no funciona**
```bash
python -m playwright install chromium
```

**Error: `ANTHROPIC_API_KEY not found`**
- Verificar que el archivo `.env` existe y tiene la clave correcta
- Asegurarse de estar corriendo desde la carpeta del proyecto

**El scraper devuelve 0 resultados**
- Verificar que hay conexión a internet
- Probar con un barrio más conocido (ej: Palermo, Belgrano)
- Correr el scraper directamente para debug:
  ```bash
  python -m scrapers.zonaprop
  ```

---

## 📦 Dependencias principales

| Paquete | Uso |
|---------|-----|
| `streamlit` | Interfaz web del agente |
| `playwright` | Automatización del navegador |
| `beautifulsoup4` | Parsing de HTML |
| `anthropic` | Claude API para análisis ACM |
| `pandas` | Manejo de datos tabulares |
| `python-dotenv` | Variables de entorno |
