import streamlit as st
import asyncio
import threading
import pandas as pd
from scrapers.zonaprop import scrape_zonaprop
from scrapers.argenprop import scrape_argenprop
from analyzer import analyze_acm


def run_async(coro):
    """Corre una coroutine async desde Streamlit en Windows."""
    result = []
    error = []

    def target():
        # Windows requiere ProactorEventLoop para subprocesos (Playwright)
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

    st.markdown("#### 🌐 Fuentes de búsqueda")
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        usar_zonaprop = st.checkbox("Zonaprop", value=True)
    with col_f2:
        usar_argenprop = st.checkbox("ArgenProp", value=True)

    max_resultados = st.slider("Máximo de resultados por fuente", 5, 30, 15)

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

            if usar_zonaprop:
                st.write(f"📡 Buscando en Zonaprop — {barrio_actual}...")
                try:
                    zp_results = run_async(scrape_zonaprop(prop_barrio, resultados_por_barrio))
                    resultados.extend(zp_results)
                    st.write(f"✅ Zonaprop ({barrio_actual}): {len(zp_results)} resultados")
                except Exception as e:
                    st.write(f"⚠️ Zonaprop ({barrio_actual}): error — {e}")

            if usar_argenprop:
                st.write(f"📡 Buscando en ArgenProp — {barrio_actual}...")
                try:
                    ap_results = run_async(scrape_argenprop(prop_barrio, resultados_por_barrio))
                    resultados.extend(ap_results)
                    st.write(f"✅ ArgenProp ({barrio_actual}): {len(ap_results)} resultados")
                except Exception as e:
                    st.write(f"⚠️ ArgenProp ({barrio_actual}): error — {e}")

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
    columnas_mostrar = [c for c in ["fuente","titulo","barrio","tipo","ambientes","metros_cubiertos",
                                    "precio_usd","precio_m2","antiguedad","amenities","url"]
                        if c in df.columns or (c == "precio_m2" and "precio_m2" in df_valid.columns)]
    df_display = df_valid[columnas_mostrar] if not df_valid.empty else df
    st.dataframe(df_display, use_container_width=True, hide_index=True,
                 column_config={
                     "url": st.column_config.LinkColumn("🔗 Ver publicación"),
                     "precio_usd": st.column_config.NumberColumn("Precio USD", format="$%d"),
                     "precio_m2":  st.column_config.NumberColumn("USD/m²", format="$%d"),
                     "metros_cubiertos": st.column_config.NumberColumn("m² cub."),
                 })

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
