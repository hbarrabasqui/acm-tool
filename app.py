import streamlit as st
import asyncio
import threading
import re
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from scrapers.zonaprop import scrape_zonaprop
from scrapers.argenprop import scrape_argenprop
from analyzer import analyze_acm

# Geocodificador compartido
_geolocator = Nominatim(user_agent="acm-tool")

# Mapeo jurisdicción → query Nominatim precisa
JURISDICCION_GEOCODING = {
    "CABA":                        "Ciudad Autónoma de Buenos Aires, Argentina",
    "GBA - Almirante Brown":       "Almirante Brown, Buenos Aires, Argentina",
    "GBA - Avellaneda":            "Avellaneda, Buenos Aires, Argentina",
    "GBA - Berazategui":           "Berazategui, Buenos Aires, Argentina",
    "GBA - Esteban Echeverría":    "Esteban Echeverría, Buenos Aires, Argentina",
    "GBA - Ezeiza":                "Ezeiza, Buenos Aires, Argentina",
    "GBA - Florencio Varela":      "Florencio Varela, Buenos Aires, Argentina",
    "GBA - General San Martín":    "General San Martín, Buenos Aires, Argentina",
    "GBA - Hurlingham":            "Hurlingham, Buenos Aires, Argentina",
    "GBA - Ituzaingó":             "Ituzaingó, Buenos Aires, Argentina",
    "GBA - José C. Paz":           "José C. Paz, Buenos Aires, Argentina",
    "GBA - La Matanza":            "La Matanza, Buenos Aires, Argentina",
    "GBA - La Plata":              "La Plata, Buenos Aires, Argentina",
    "GBA - Lanús":                 "Lanús, Buenos Aires, Argentina",
    "GBA - Lomas de Zamora":       "Lomas de Zamora, Buenos Aires, Argentina",
    "GBA - Malvinas Argentinas":   "Malvinas Argentinas, Buenos Aires, Argentina",
    "GBA - Merlo":                 "Merlo, Buenos Aires, Argentina",
    "GBA - Moreno":                "Moreno, Buenos Aires, Argentina",
    "GBA - Morón":                 "Morón, Buenos Aires, Argentina",
    "GBA - Quilmes":               "Quilmes, Buenos Aires, Argentina",
    "GBA - San Fernando":          "San Fernando, Buenos Aires, Argentina",
    "GBA - San Isidro":            "San Isidro, Buenos Aires, Argentina",
    "GBA - San Miguel":            "San Miguel, Buenos Aires, Argentina",
    "GBA - Tigre":                 "Tigre, Buenos Aires, Argentina",
    "GBA - Tres de Febrero":       "Tres de Febrero, Buenos Aires, Argentina",
    "GBA - Vicente López":         "Vicente López, Buenos Aires, Argentina",
}

@st.cache_data(show_spinner=False)
def geocodificar(direccion: str, ciudad: str = "Ciudad Autónoma de Buenos Aires, Argentina"):
    """Convierte una dirección a coordenadas (lat, lon). Retorna None si falla.
    Resultado cacheado — Nominatim solo se consulta una vez por dirección."""
    import time, re
    try:
        # Limpiar "al NNNN" -> "NNNN" para que Nominatim lo interprete como numeración
        direccion_limpia = re.sub(r'\bal\b\s*(\d)', r'\1', direccion, flags=re.IGNORECASE).strip()
        # Si solo tiene nombre de barrio (sin número), agregar ciudad directamente
        query = f"{direccion_limpia}, {ciudad}"
        time.sleep(1.1)  # Nominatim exige máximo 1 request/segundo
        loc = _geolocator.geocode(query, timeout=10)
        if loc:
            # Verificar que el resultado esté dentro del GBA/CABA (bbox razonable)
            # CABA: lat -34.70 a -34.52, lon -58.53 a -58.33
            # Ampliamos un poco para cubrir GBA cercano
            if -34.85 < loc.latitude < -34.40 and -58.70 < loc.longitude < -58.20:
                return (loc.latitude, loc.longitude)
    except Exception:
        pass
    return None


def run_async(coro):
    """Corre una coroutine async desde Streamlit en Windows."""
    result = []
    error = []

    def target():
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
        try:
            result.append(loop.run_until_complete(coro))
        except Exception as e:
            error.append(e)
        finally:
            loop.close()

    t = threading.Thread(target=target)
    t.start()
    t.join()
    if error:
        raise error[0]
    return result[0] if result else []


def run_async_parallel(*coros):
    """Corre múltiples coroutines en paralelo y devuelve lista de resultados."""
    async def _gather():
        return await asyncio.gather(*coros, return_exceptions=True)

    result = []
    error = []

    def target():
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
        try:
            result.append(loop.run_until_complete(_gather()))
        except Exception as e:
            error.append(e)
        finally:
            loop.close()

    t = threading.Thread(target=target)
    t.start()
    t.join()
    if error:
        raise error[0]
    return result[0] if result else []

st.set_page_config(
    page_title="ACM Tool",
    page_icon="🏠",
    layout="wide",
)

# ── Estilos ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Lato:wght@300;400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Lato', sans-serif; }
    .block-container { padding-top: 2rem; }
    .stButton > button {
        background: #E2231A; color: white; border: none;
        font-weight: 700; padding: 0.6rem 2rem; border-radius: 6px;
        font-size: 1rem; width: 100%;
    }
    .stButton > button:hover { background: #b71c1c; }
    h1 { color: #1a1a2e; }
    .result-card {
        background: #f8f9fa; border-left: 4px solid #E2231A;
        padding: 1rem 1.5rem; border-radius: 4px; margin-bottom: 1rem;
    }
    .metric-box {
        background: white; border: 1px solid #e0e0e0; border-radius: 8px;
        padding: 1.2rem; text-align: center;
    }
    .metric-box h2 { color: #E2231A; margin: 0; }
    .metric-box p  { color: #555; margin: 0; font-size: 0.85rem; }
</style>
""", unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────────────────────────────────
col_logo, col_title = st.columns([1, 6])
with col_logo:
    st.markdown("## 🏠")
with col_title:
    st.markdown("# ACM Tool — Análisis Comparativo de Mercado")
    st.caption("Análisis Comparativo de Mercado — búsqueda automática en Zonaprop y ArgenProp")

st.divider()

# ── Formulario ─────────────────────────────────────────────────────────────────
with st.form("acm_form"):
    st.subheader("📋 Datos de la propiedad a valuar")

    col1, col2, col3 = st.columns(3)

    with col1:
        barrio = st.text_input("Barrio / Zona *", placeholder="ej: Palermo, Belgrano")
        ciudad = st.selectbox(
            "Jurisdicción *",
            list(JURISDICCION_GEOCODING.keys()),
            help="CABA o partido del GBA. Se usa para precisar la búsqueda y la geocodificación en el mapa."
        )
        tipo = st.selectbox("Tipo de propiedad *", ["Departamento", "Casa", "PH", "Local", "Oficina"])
        ambientes = st.selectbox("Ambientes *", [1, 2, 3, 4, 5, "6+"])

    with col2:
        metros_cubiertos = st.number_input("m² cubiertos *", min_value=10, max_value=2000, value=60)
        metros_totales = st.number_input("m² totales (incl. descubiertos)", min_value=0, max_value=5000, value=0,
                                         help="Dejar en 0 si no aplica")
        antiguedad = st.selectbox("Antigüedad", ["A estrenar", "0-5 años", "6-15 años", "16-30 años", "Más de 30 años"])

    with col3:
        precio_estimado = st.number_input("Precio estimado (USD)", min_value=0, value=0,
                                           help="Opcional — ayuda a calibrar el análisis")
        dormitorios = st.selectbox("Dormitorios", [0, 1, 2, 3, 4, "5+"])
        banos = st.selectbox("Baños", [1, 2, 3, 4, "5+"])

    st.markdown("#### ✨ Amenities y características adicionales")
    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a:
        terraza      = st.checkbox("Terraza / Balcón")
        piscina      = st.checkbox("Piscina")
        jardin       = st.checkbox("Jardín")
    with col_b:
        cochera      = st.checkbox("Cochera")
        baulera      = st.checkbox("Baulera")
        laundry      = st.checkbox("Laundry")
    with col_c:
        gym          = st.checkbox("Gimnasio")
        seguridad24  = st.checkbox("Seguridad 24h")
        sum_amenity  = st.checkbox("SUM")
    with col_d:
        vista_al_mar = st.checkbox("Vista al río/mar")
        luminoso     = st.checkbox("Muy luminoso")
        apto_prof    = st.checkbox("Apto profesional")

    amenities_extras = st.text_input("Otros amenities / notas libres", placeholder="ej: piso alto, frente, remodelado")

    st.markdown("#### 💬 Contexto adicional para el análisis")
    contexto_libre = st.text_area(
        "Instrucciones o contexto libre para Claude",
        placeholder="ej: El dueño necesita vender rápido. La propiedad tiene vista al río y es de categoría premium. Buscar precio competitivo considerando la demanda de alquiler temporario en la zona.",
        height=100,
        help="Este texto va directo al análisis de IA. Usalo para agregar cualquier contexto que no esté en los campos anteriores."
    )

    st.markdown("#### 🗺️ Mapa de ubicación (opcional)")
    st.caption("Si ingresás una dirección de referencia se mostrará el mapa. El radio se puede ajustar después sin repetir la búsqueda.")
    direccion_referencia = st.text_input(
        "Dirección de referencia",
        placeholder="ej: Gorriti 4500, Palermo, Buenos Aires",
        help="La propiedad que querés valuar. Se marcará con un pin especial en el mapa."
    )
    usar_mapa = bool(direccion_referencia)

    st.markdown("#### 🌐 Fuentes de búsqueda")
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        usar_zonaprop = st.checkbox("Zonaprop", value=True)
    with col_f2:
        usar_argenprop = st.checkbox("ArgenProp", value=True)

    max_resultados = st.slider("Máximo de resultados por fuente", 5, 100, 50)

    submitted = st.form_submit_button("🔍 Buscar comparables y generar ACM")

# ── Ejecución ──────────────────────────────────────────────────────────────────
if submitted:
    if not barrio:
        st.error("⚠️ El campo Barrio / Zona es obligatorio.")
        st.stop()

    amenities_list = []
    if terraza:      amenities_list.append("terraza/balcón")
    if piscina:      amenities_list.append("piscina")
    if jardin:       amenities_list.append("jardín")
    if cochera:      amenities_list.append("cochera")
    if baulera:      amenities_list.append("baulera")
    if laundry:      amenities_list.append("laundry")
    if gym:          amenities_list.append("gimnasio")
    if seguridad24:  amenities_list.append("seguridad 24h")
    if sum_amenity:  amenities_list.append("SUM")
    if vista_al_mar: amenities_list.append("vista al río/mar")
    if luminoso:     amenities_list.append("muy luminoso")
    if apto_prof:    amenities_list.append("apto profesional")
    if amenities_extras:
        amenities_list.append(amenities_extras)

    prop = {
        "barrio": barrio,
        "ciudad": ciudad,
        "tipo": tipo,
        "ambientes": ambientes,
        "metros_cubiertos": metros_cubiertos,
        "metros_totales": metros_totales if metros_totales > 0 else metros_cubiertos,
        "antiguedad": antiguedad,
        "dormitorios": dormitorios,
        "banos": banos,
        "precio_estimado": precio_estimado,
        "amenities": amenities_list,
        "contexto_libre": contexto_libre,
    }

    resultados = []
    barrios = [b.strip() for b in barrio.split(",") if b.strip()]
    resultados_por_barrio = max_resultados // len(barrios) if len(barrios) > 1 else max_resultados

    with st.status("🔍 Buscando propiedades comparables...", expanded=True) as status:
        for barrio_actual in barrios:
            prop_barrio = {**prop, "barrio": barrio_actual}

            # Construir coroutines a ejecutar en paralelo
            coros = []
            fuentes = []
            if usar_zonaprop:
                coros.append(scrape_zonaprop(prop_barrio, resultados_por_barrio))
                fuentes.append(("Zonaprop", barrio_actual))
            if usar_argenprop:
                coros.append(scrape_argenprop(prop_barrio, resultados_por_barrio))
                fuentes.append(("ArgenProp", barrio_actual))

            if not coros:
                continue

            st.write(f"📡 Buscando en {' y '.join(f[0] for f in fuentes)} — {barrio_actual} (en paralelo)...")
            resultados_paralelos = run_async_parallel(*coros)

            for (fuente, barrio_f), res in zip(fuentes, resultados_paralelos):
                if isinstance(res, Exception):
                    st.write(f"⚠️ {fuente} ({barrio_f}): error — {res}")
                else:
                    resultados.extend(res)
                    st.write(f"✅ {fuente} ({barrio_f}): {len(res)} resultados")

        if not resultados:
            status.update(label="⚠️ Sin resultados", state="error")
            st.error("No se encontraron propiedades comparables. Probá ampliar la búsqueda.")
            st.stop()

        st.write("🤖 Analizando con IA...")
        try:
            analisis = analyze_acm(prop, resultados)
            status.update(label="✅ Análisis completado", state="complete")
        except Exception as e:
            status.update(label="⚠️ Error en análisis IA", state="error")
            st.warning(f"No se pudo analizar con IA: {e}. Mostrando resultados crudos.")
            analisis = None

    # Guardar en session_state para persistir después de descargar
    st.session_state["resultados"] = resultados
    st.session_state["analisis"] = analisis
    st.session_state["prop"] = prop
    st.session_state["barrio"] = barrio
    st.session_state["tipo"] = tipo
    st.session_state["usar_mapa"] = usar_mapa
    st.session_state["direccion_referencia"] = direccion_referencia

# ── Resultados (se muestran desde session_state) ───────────────────────────────
if "resultados" in st.session_state and st.session_state["resultados"]:
    resultados = st.session_state["resultados"]
    analisis   = st.session_state["analisis"]
    prop       = st.session_state["prop"]
    barrio     = st.session_state["barrio"]
    tipo       = st.session_state["tipo"]

    st.divider()
    col_titulo, col_limpiar = st.columns([6, 1])
    with col_titulo:
        st.subheader("📊 Resultados del ACM")
    with col_limpiar:
        if st.button("🗑️ Limpiar búsqueda"):
            for k in ["resultados", "analisis", "prop", "barrio", "tipo"]:
                st.session_state.pop(k, None)
            st.rerun()

    df = pd.DataFrame(resultados)

    if "precio_usd" in df.columns and "metros_cubiertos" in df.columns:
        df_valid = df[df["precio_usd"] > 0].copy()
        if not df_valid.empty:
            df_valid["precio_m2"] = df_valid["precio_usd"] / df_valid["metros_cubiertos"].replace(0, pd.NA)
            df_valid = df_valid.dropna(subset=["precio_m2"])

            avg_precio = df_valid["precio_usd"].mean()
            avg_m2     = df_valid["precio_m2"].mean()
            min_precio = df_valid["precio_usd"].min()
            max_precio = df_valid["precio_usd"].max()

            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.markdown(f"""<div class="metric-box"><p>Precio promedio</p><h2>USD {avg_precio:,.0f}</h2></div>""", unsafe_allow_html=True)
            with m2:
                st.markdown(f"""<div class="metric-box"><p>Precio promedio / m²</p><h2>USD {avg_m2:,.0f}</h2></div>""", unsafe_allow_html=True)
            with m3:
                st.markdown(f"""<div class="metric-box"><p>Mínimo encontrado</p><h2>USD {min_precio:,.0f}</h2></div>""", unsafe_allow_html=True)
            with m4:
                st.markdown(f"""<div class="metric-box"><p>Máximo encontrado</p><h2>USD {max_precio:,.0f}</h2></div>""", unsafe_allow_html=True)
            st.markdown("")

    st.markdown("#### 📋 Propiedades comparables encontradas")
    # La tabla muestra TODAS las propiedades (incluso las sin precio/m²)
    df_tabla = df.copy()
    if "precio_usd" in df_tabla.columns and "metros_cubiertos" in df_tabla.columns:
        df_tabla["precio_m2"] = df_tabla.apply(
            lambda r: r["precio_usd"] / r["metros_cubiertos"]
            if r.get("metros_cubiertos", 0) > 0 and r.get("precio_usd", 0) > 0 else None,
            axis=1
        )

    # Agregar columna mapa si se usó geolocalización
    urls_en_mapa = st.session_state.get("urls_en_mapa")
    if urls_en_mapa is not None:
        df_tabla["en_mapa"] = df_tabla["url"].apply(lambda u: "📍" if u in urls_en_mapa else "")

    columnas_mostrar = [c for c in ["en_mapa","fuente","titulo","barrio","tipo","ambientes",
                                    "metros_cubiertos","precio_usd","precio_m2","antiguedad","amenities","url"]
                        if c in df_tabla.columns]
    st.dataframe(df_tabla[columnas_mostrar], use_container_width=True, hide_index=True,
                 column_config={
                     "en_mapa": st.column_config.TextColumn("📍"),
                     "url": st.column_config.LinkColumn("🔗 Ver publicación"),
                     "precio_usd": st.column_config.NumberColumn("Precio USD", format="$%d"),
                     "precio_m2":  st.column_config.NumberColumn("USD/m²", format="$%d"),
                     "metros_cubiertos": st.column_config.NumberColumn("m² cub."),
                 })

    # ── Mapa ──────────────────────────────────────────────────────────────────
    if st.session_state.get("usar_mapa") and st.session_state.get("direccion_referencia"):
        st.divider()
        st.subheader("🗺️ Mapa de comparables")

        dir_ref = st.session_state["direccion_referencia"]
        radio_km = st.select_slider(
            "Radio de referencia en el mapa",
            options=[0.5, 1.0, 1.5, 2.0, 3.0, 5.0],
            value=2.0,
            format_func=lambda x: f"{int(x*1000)}m" if x < 1 else f"{x:.1f}km",
            help="Cambiá el radio sin repetir la búsqueda — solo redibuja el mapa."
        )

        ciudad_ctx = JURISDICCION_GEOCODING.get(prop.get("ciudad", "CABA"), "Ciudad Autónoma de Buenos Aires, Argentina")
        with st.spinner("Geolocalizando propiedades..."):
            coords_ref = geocodificar(dir_ref, ciudad_ctx)

        if not coords_ref:
            st.warning(f"No se pudo geolocalizar la dirección de referencia: '{dir_ref}'. Verificá que esté bien escrita.")
        else:
            # Geocodificar cada comparable
            geolocalizados = []
            no_en_mapa = 0
            urls_en_mapa = set()

            for item in resultados:
                # Usar campo "direccion" si existe, sino "barrio"
                direccion = item.get("direccion", "") or item.get("barrio", "")
                # Solo geocodificar si tiene número de calle (dirección real, no solo barrio)
                if not direccion or not re.search(r'\d{3,}', direccion):
                    no_en_mapa += 1
                    continue
                # Usar la ciudad ingresada por el usuario como contexto de geocodificación
                ciudad_ctx = JURISDICCION_GEOCODING.get(prop.get("ciudad", "CABA"), "Ciudad Autónoma de Buenos Aires, Argentina")
                coords = geocodificar(direccion, ciudad_ctx)
                if coords:
                    dist = geodesic(coords_ref, coords).km
                    geolocalizados.append({**item, "_coords": coords, "_dist_km": round(dist, 2)})
                    urls_en_mapa.add(item.get("url", ""))
                else:
                    no_en_mapa += 1

            # Construir mapa
            from folium.plugins import MarkerCluster
            mapa = folium.Map(location=coords_ref, zoom_start=15)

            # Círculo de radio
            folium.Circle(
                location=coords_ref,
                radius=radio_km * 1000,
                color="#E2231A",
                fill=True,
                fill_opacity=0.05,
            ).add_to(mapa)

            # Pin de referencia (propiedad a valuar) — fuera del cluster
            folium.Marker(
                location=coords_ref,
                tooltip="📍 Propiedad a valuar",
                popup=folium.Popup(f"<b>Propiedad a valuar</b><br>{dir_ref}", max_width=250),
                icon=folium.Icon(color="red", icon="home", prefix="fa"),
            ).add_to(mapa)

            # Cluster para los comparables
            cluster = MarkerCluster().add_to(mapa)
            colores = {"Zonaprop": "blue", "ArgenProp": "green"}
            for item in geolocalizados:
                color = colores.get(item.get("fuente", ""), "gray")
                precio = f"USD {item['precio_usd']:,}" if item.get("precio_usd") else "N/D"
                metros = f"{item['metros_cubiertos']} m²" if item.get("metros_cubiertos") else "N/D"
                ambientes = item.get("ambientes", "")
                url = item.get("url", "")
                link_html = f'<br><a href="{url}" target="_blank">🔗 Ver publicación</a>' if url else ""
                popup_html = f"""
                    <b>{item.get('fuente','')}</b><br>
                    {item.get('barrio','')}<br>
                    {precio} · {metros} · {ambientes}
                    {link_html}
                """
                folium.Marker(
                    location=item["_coords"],
                    tooltip=f"{precio} · {metros}",
                    popup=folium.Popup(popup_html, max_width=280),
                    icon=folium.Icon(color=color, icon="building", prefix="fa"),
                ).add_to(cluster)

            st_folium(mapa, use_container_width=True, height=500)

            col_geo1, col_geo2 = st.columns(2)
            with col_geo1:
                st.success(f"✅ {len(geolocalizados)} propiedades mostradas en el mapa")
            with col_geo2:
                if no_en_mapa > 0:
                    st.info(f"ℹ️ {no_en_mapa} propiedades sin ubicación en el radio — aparecen solo en la tabla")

            # Guardar urls_en_mapa para marcarlas en la tabla
            st.session_state["urls_en_mapa"] = urls_en_mapa

    if analisis:
        st.divider()
        st.subheader("🤖 Análisis de IA — Informe ACM")
        if "precio_sugerido" in analisis:
            st.markdown(f"""<div class="result-card">
                <strong>💡 Precio de lista sugerido:</strong> {analisis['precio_sugerido']}
            </div>""", unsafe_allow_html=True)
        if "resumen" in analisis:
            st.markdown("**Resumen ejecutivo:**")
            st.markdown(analisis["resumen"])
        if "outliers" in analisis and analisis["outliers"]:
            with st.expander("⚠️ Outliers detectados"):
                st.markdown(analisis["outliers"])
        if "recomendaciones" in analisis:
            with st.expander("📌 Recomendaciones adicionales"):
                st.markdown(analisis["recomendaciones"])

    # ── Exportar con hipervínculos ─────────────────────────────────────────────
    import io
    from openpyxl import load_workbook
    from openpyxl.styles import Font

    excel_buffer = io.BytesIO()
    df.to_excel(excel_buffer, index=False, engine="openpyxl")
    excel_buffer.seek(0)

    wb = load_workbook(excel_buffer)
    ws = wb.active

    # Encontrar columna URL y convertir a hipervínculos
    url_col = None
    for col_idx, cell in enumerate(ws[1], 1):
        if cell.value == "url":
            url_col = col_idx
            break

    if url_col:
        for row in ws.iter_rows(min_row=2, min_col=url_col, max_col=url_col):
            for cell in row:
                if cell.value and str(cell.value).startswith("http"):
                    url_val = cell.value
                    cell.hyperlink = url_val
                    cell.value = url_val
                    cell.font = Font(color="0563C1", underline="single")

    final_buffer = io.BytesIO()
    wb.save(final_buffer)
    final_buffer.seek(0)

    st.divider()
    st.markdown("#### 💾 Exportar resultados")
    st.download_button(
        "⬇️ Descargar Excel",
        data=final_buffer,
        file_name=f"ACM_{barrio.replace(' ','_')}_{tipo}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
