"""
Módulo de análisis con Claude API.
Recibe los datos de la propiedad y los comparables, devuelve un análisis ACM completo.
"""

import os
import json
import re
import anthropic
from dotenv import load_dotenv
from typing import Optional

load_dotenv()


def _format_prop(prop: dict) -> str:
    amenities = ", ".join(prop.get("amenities", [])) or "sin amenities especificados"
    precio_est = f"USD {prop['precio_estimado']:,}" if prop.get("precio_estimado") else "no especificado"
    return f"""
- Tipo: {prop.get('tipo', 'N/A')}
- Barrio: {prop.get('barrio', 'N/A')}
- Ambientes: {prop.get('ambientes', 'N/A')}
- m² cubiertos: {prop.get('metros_cubiertos', 'N/A')}
- m² totales: {prop.get('metros_totales', 'N/A')}
- Antigüedad: {prop.get('antiguedad', 'N/A')}
- Dormitorios: {prop.get('dormitorios', 'N/A')}
- Baños: {prop.get('banos', 'N/A')}
- Amenities: {amenities}
- Precio estimado por el agente: {precio_est}
""".strip()


def _format_comparables(resultados: list[dict]) -> str:
    lines = []
    for i, r in enumerate(resultados, 1):
        precio_m2 = ""
        if r.get("precio_usd") and r.get("metros_cubiertos"):
            try:
                pm2 = r["precio_usd"] / r["metros_cubiertos"]
                precio_m2 = f" (USD {pm2:,.0f}/m²)"
            except Exception:
                pass
        lines.append(
            f"{i}. [{r.get('fuente','?')}] {r.get('titulo','')[:80]} | "
            f"Precio: USD {r.get('precio_usd',0):,}{precio_m2} | "
            f"m²: {r.get('metros_cubiertos',0)} | "
            f"Amb: {r.get('ambientes','')} | "
            f"Zona: {r.get('barrio','')}"
        )
    return "\n".join(lines)


def analyze_acm(prop: dict, resultados: list[dict]) -> dict:
    """
    Envía los datos a Claude y retorna el análisis estructurado.
    
    Returns:
        dict con claves: precio_sugerido, resumen, outliers, recomendaciones
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("Falta la variable de entorno ANTHROPIC_API_KEY")

    client = anthropic.Anthropic(api_key=api_key)

    prop_str = _format_prop(prop)
    comp_str = _format_comparables(resultados)
    n = len(resultados)

    contexto_libre = prop.get("contexto_libre", "").strip()
    contexto_str = f"\n## CONTEXTO ADICIONAL DEL AGENTE\n{contexto_libre}" if contexto_libre else ""

    prompt = f"""Sos un experto en valuación inmobiliaria en Argentina trabajando para un agente de Remax.
Tu tarea es analizar las propiedades comparables encontradas y generar un informe ACM (Análisis Comparativo de Mercado) profesional en español.

## PROPIEDAD A VALUAR
{prop_str}{contexto_str}

## COMPARABLES ENCONTRADOS ({n} propiedades)
{comp_str}

## ANÁLISIS REQUERIDO
Respondé ÚNICAMENTE con un JSON válido (sin markdown, sin texto extra) con la siguiente estructura:

{{
  "precio_sugerido": "Rango o precio recomendado en USD con justificación breve",
  "resumen": "Párrafo ejecutivo de 3-5 oraciones describiendo el mercado, la posición de la propiedad y el contexto general. Profesional, listo para presentar al cliente.",
  "outliers": "Descripción de propiedades con precios atípicos (muy altos o bajos respecto a la media) y posibles razones. Dejar vacío si no hay outliers significativos.",
  "recomendaciones": "2-3 recomendaciones estratégicas para el agente: cómo posicionar la propiedad, ajustes de precio si corresponde, observaciones sobre el mercado del barrio."
}}

Consideraciones importantes:
- Al calcular el precio sugerido, priorizá los comparables del mismo barrio que la propiedad a valuar ({prop.get('barrio', '')}).
- Si hay comparables de otras zonas, mencionalo explícitamente en el resumen y ponderalos con menor peso.
- Descartá del análisis de precio los outliers con superficies muy alejadas de {prop.get('metros_cubiertos', 0)} m² (más del doble o menos de la mitad).
Usá el contexto local argentino. Los precios son en USD. Sé preciso y práctico."""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()

    # Limpiar posibles markdown fences
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: devolver el texto completo como resumen
        return {"resumen": raw, "precio_sugerido": "", "outliers": "", "recomendaciones": ""}
