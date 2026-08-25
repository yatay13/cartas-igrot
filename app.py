import json
import os
import re
import html
import zipfile
import gdown
import streamlit as st
from google import genai

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Igrot Kodesh - AI Premium",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- ESTILOS CSS PERSONALIZADOS (UI/UX PREMIUM) ---
st.markdown("""
    <style>
    .stApp {
        background-color: #0f172a;
        color: #f8fafc;
    }
    .carta-box {
        background-color: #1e293b;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
    }
    .badge {
        background-color: #3b82f6;
        color: white;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 600;
        display: inline-block;
        margin-right: 5px;
    }
    .footer {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background-color: rgba(15, 23, 42, 0.95);
        color: #94a3b8;
        text-align: center;
        padding: 10px 0px;
        font-size: 13px;
        font-weight: 600;
        letter-spacing: 0.5px;
        border-top: 1px solid #334155;
        backdrop-filter: blur(8px);
        z-index: 999;
    }
    </style>
""", unsafe_allow_html=True)

# --- SEGURIDAD: SANITIZACIÓN DE ENTRADAS ---
def sanitizar_texto(texto: str) -> str:
    if not texto:
        return ""
    clean = html.escape(texto.strip())
    clean = re.sub(r'[^\w\s\u0590-\u05FF\'"\-\.\,]', '', clean)
    return clean[:200]

# --- OBTENCIÓN SEGURA DE API KEY ---
API_KEY = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
ID_DRIVE = "1ARt_qkxwuGIKeA7LkKSITbzo4Q_w7Pzk"

@st.cache_resource
def obtener_cliente_gemini(api_key):
    if api_key:
        try:
            return genai.Client(api_key=api_key.strip())
        except Exception:
            return None
    return None

client = obtener_cliente_gemini(API_KEY)

# --- DETECCION DINÁMICA DE MODELOS DISPONIBLES ---
@st.cache_resource
def obtener_modelos_disponibles():
    if not client:
        return None, None
    try:
        modelos = [m.name for m in client.models.list() if "generateContent" in getattr(m, "supported_actions", getattr(m, "supported_generation_methods", []))]
        
        # Buscar el mejor modelo Flash disponible
        flash_model = next((m for m in modelos if "flash" in m.lower()), None)
        # Buscar el mejor modelo Pro disponible
        pro_model = next((m for m in modelos if "pro" in m.lower()), None)
        
        # Fallbacks si no detecta por palabra clave
        if not flash_model and modelos:
            flash_model = modelos[0]
        if not pro_model:
            pro_model = flash_model
            
        return pro_model, flash_model
    except Exception:
        # Respaldos directos en caso de que falle el listado
        return "models/gemini-3.6-pro", "models/gemini-3.6-flash"

MODELO_PRO, MODELO_FLASH = obtener_modelos_disponibles()

# --- CARGA DE DATOS OPTIMIZADA ---
@st.cache_data(ttl=3600, show_spinner=False)
def cargar_datos_drive(file_id):
    archivo_local = "base_datos_descargada"
    
    if not os.path.exists(archivo_local):
        url_drive = f"https://drive.google.com/uc?id={file_id}"
        try:
            with st.spinner("📦 Cargando base de datos por primera vez..."):
                gdown.download(url_drive, archivo_local, quiet=False)
        except Exception as e:
            return {}, f"Error al descargar desde Drive: {e}"

    try:
        with open(archivo_local, "r", encoding="utf-8") as f:
            return json.load(f), "Google Drive (JSON)"
    except Exception:
        pass

    try:
        with zipfile.ZipFile(archivo_local, 'r') as z:
            nombres_json = [f for f in z.namelist() if f.endswith('.json') and not f.startswith('__MACOSX')]
            if nombres_json:
                with z.open(nombres_json[0]) as f:
                    return json.load(f), "Google Drive (ZIP)"
    except Exception as e:
        return {}, f"Error al procesar el archivo: {e}"

    return {}, "Formato no compatible"

base_datos, origen_datos = cargar_datos_drive(ID_DRIVE)

# --- CABECERA VISUAL ---
col_img1, col_img2, col_img3 = st.columns([1.8, 1, 1.8])
with col_img2:
    if os.path.exists("rebe.jpg"):
        st.image("rebe.jpg", caption="Menachem Mendel Schneerson - El Rebe de Lubavitch", use_container_width=True)
    elif os.path.exists("rebe.png"):
        st.image("rebe.png", caption="Menachem Mendel Schneerson - El Rebe de Lubavitch", use_container_width=True)
    else:
        st.info("💡 Coloca 'rebe.jpg' en el directorio para mostrar la imagen oficial.")

st.markdown("<h1 style='text-align: center;'>📜 Buscador de Igrot Kodesh</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #94a3b8;'>Plataforma Inteligente de Exploración e Interpretación de Correspondencia Rabínica.</p>", unsafe_allow_html=True)
st.divider()

# --- ESTADO DE SESIÓN ---
if "query_activa" not in st.session_state:
    st.session_state["query_activa"] = ""

# --- CONTROLES Y BUSCADOR ---
col_f1, col_f2, col_f3, col_f4 = st.columns([2.5, 1.5, 1.2, 1])

tomos_disponibles = ["Todos"] + list(base_datos.keys()) if base_datos else ["Todos"]

with col_f1:
    raw_query = st.text_input(
        "Ingrese tema, concepto o ID:",
        value=st.session_state["query_activa"],
        placeholder="Ej: Educación, Salud, Bendición...",
        key="input_query"
    )
    query = sanitizar_texto(raw_query)

with col_f2:
    raw_fecha = st.text_input("Filtrar por año/fecha:", placeholder="Ej: תש''ה, 1945...", key="input_fecha")
    filtro_fecha = sanitizar_texto(raw_fecha)

with col_f3:
    tomo_seleccionado = st.selectbox("Tomo:", tomos_disponibles)

with col_f4:
    cant_cartas = st.selectbox("Mostrar:", [3, 5, 10, 20, 50], index=1)

# Opciones de IA avanzadas
col_opt1, col_opt2 = st.columns([2, 2])
with col_opt1:
    generar_traduccion = st.checkbox("Interpretación Erudita con IA (Modelo Pro)", value=True)
with col_opt2:
    idioma_destino = st.selectbox(
        "Idioma de traducción:",
        ["Español", "Hebreo Moderno", "English", "Français", "Português", "Ruso"],
        disabled=not generar_traduccion
    )

# --- BOTONES DE ACCESO RÁPIDO ---
st.write("📌 **Categorías Principales:**")
col_b1, col_b2, col_b3, col_b4, col_b5, col_b6 = st.columns(6)

if col_b1.button("🩺 Salud", use_container_width=True):
    st.session_state["query_activa"] = "Salud"
    st.rerun()
if col_b2.button("🎓 Educación", use_container_width=True):
    st.session_state["query_activa"] = "Educación"
    st.rerun()
if col_b3.button("✨ Bendición", use_container_width=True):
    st.session_state["query_activa"] = "Bendición"
    st.rerun()
if col_b4.button("💼 Trabajo", use_container_width=True):
    st.session_state["query_activa"] = "Trabajo"
    st.rerun()
if col_b5.button("💍 Matrimonio", use_container_width=True):
    st.session_state["query_activa"] = "Matrimonio"
    st.rerun()
if col_b6.button("🧹 Limpiar", use_container_width=True):
    st.session_state["query_activa"] = ""
    st.rerun()

st.markdown("---")
btn_buscar = st.button("🔍 Realizar Búsqueda Avanzada", type="primary", use_container_width=True)

# --- ENGINE DE BÚSQUEDA E IA AVANZADA ---
DICCIONARIO_RESPALDO = {
    "salud": ["רפואה", "רפואה שלימה", "בריאות", "רופא"],
    "educacion": ["חינוך", "חינוך ילדים", "תלמוד תורה"],
    "educación": ["חינוך", "חינוך ילדים", "תלמוד תורה"],
    "bendicion": ["ברכה", "ברכה והצלחה", "אגרת"],
    "bendición": ["ברכה", "ברכה והצלחה", "אגרת"],
    "trabajo": ["פרנסה", "עבודה", "מסחר"],
    "matrimonio": ["שידוך", "חתונה", "זיווג"]
}

def obtener_conceptos_hebreo(consulta):
    if not consulta:
        return []
    if client and MODELO_FLASH:
        prompt = f"""
        Como erudito en la literatura de Chabad e Igrot Kodesh, analiza este tema: '{consulta}'.
        Proporciona entre 5 y 8 términos clave exactos en HEBREO e IÍDISH asociados comunitariamente o rabínicamente a este tema.
        Responde ÚNICAMENTE las palabras en hebreo/iídish separadas por comas.
        """
        try:
            res = client.models.generate_content(model=MODELO_FLASH, contents=prompt)
            return [t.strip().lower() for t in res.text.split(',') if t.strip()]
        except Exception:
            pass

    consulta_clean = consulta.lower().strip()
    for clave, lista in DICCIONARIO_RESPALDO.items():
        if clave in consulta_clean:
            return lista
            
    return [consulta_clean]

@st.cache_data(show_spinner=False, ttl=86400)
def traducir_carta_premium(contenido, idioma, tema):
    if not client:
        return "⚠️ *Servicio de IA no disponible. Configura la clave GEMINI_API_KEY en los Secrets de Streamlit Cloud.*"
        
    prompt = f"""
    Eres un Rabino y erudito lingüista de alto nivel, experto en la correspondencia del Rebe de Lubavitch (Igrot Kodesh).
    
    TEXTO ORIGINAL EN HEBREO/IÍDISH:
    {contenido[:4000]}

    Instrucciones para la respuesta en {idioma}:
    1. Aclaración inicial obligatoria:
       "⚠️ *Nota de Traducción: Interpretación asistida por IA avanzada. Los conceptos halájicos deben ser revisados con un Rabino calificado.*"
    2. **Contexto & Esencia**: Explica brevemente de qué trata la carta y cómo conecta con el tema '{tema}'.
    3. **Traducción Contextual Fluida**: Traduce el texto al {idioma} manteniendo el tono pastoral, elevado y respetuoso original (evita traducciones literales palabra por palabra que pierdan sentido).
    4. **Glosario de Términos Rabínicos**: Explica de 2 a 4 conceptos en hebreo/iídish presentes en el texto original.
    """
    
    modelos_a_probar = [m for m in [MODELO_PRO, MODELO_FLASH, "models/gemini-3.6-flash", "models/gemini-3.6-pro"] if m]
    
    for modelo in modelos_a_probar:
        try:
            res = client.models.generate_content(model=modelo, contents=prompt)
            return res.text
        except Exception:
            continue
            
    return "⚠️ *No se pudo establecer conexión con ningún modelo activo de la API. Verifica los permisos de tu clave de API.*"

# --- EJECUCIÓN DE BÚSQUEDA Y RESULTADOS ---
consulta_efectiva = query or st.session_state["query_activa"]

if btn_buscar or consulta_efectiva or filtro_fecha or tomo_seleccionado != "Todos":
    if not base_datos:
        st.error("La base de datos de cartas no está disponible.")
    else:
        es_hebreo = bool(re.search(r'[\u0590-\u05FF]', consulta_efectiva)) if consulta_efectiva else False
        terminos = [consulta_efectiva.lower()] if es_hebreo else obtener_conceptos_hebreo(consulta_efectiva)
        
        if consulta_efectiva:
            badges_html = "".join([f"<span class='badge'>{t}</span>" for t in terminos])
            st.markdown(f"🎯 **Conceptos clave identificados:** {badges_html}", unsafe_allow_html=True)
            st.write("")

        resultados = []
        for tomo, info in base_datos.items():
            if tomo_seleccionado != "Todos" and tomo != tomo_seleccionado:
                continue
            
            for carta in info.get("cartas", []):
                texto = carta.get("contenido", "")
                texto_lower = texto.lower()
                id_carta = str(carta.get("id_carta", "")).lower()
                
                coincide_termino = any(t in texto_lower or t == id_carta for t in terminos) if terminos else True
                coincide_fecha = (filtro_fecha.lower() in texto_lower or filtro_fecha.lower() in tomo.lower()) if filtro_fecha else True
                
                if coincide_termino and coincide_fecha:
                    resultados.append({
                        "tomo": os.path.basename(tomo),
                        "id_carta": id_carta,
                        "contenido": texto
                    })
                    if len(resultados) >= cant_cartas:
                        break
            if len(resultados) >= cant_cartas:
                break

        if resultados:
            st.success(f"Se encontraron **{len(resultados)}** cartas coincidentes.")
            
            for idx, res in enumerate(resultados, 1):
                with st.expander(f"📜 Carta {idx} | ID: {res['id_carta']} | {res['tomo']}", expanded=True):
                    if not generar_traduccion:
                        st.subheader("Texto Original (Hebreo / Iídish)")
                        st.text_area("Contenido:", res['contenido'], height=350, key=f"orig_{idx}")
                    else:
                        col1, col2 = st.columns(2)
                        with col1:
                            st.subheader("Texto Original")
                            st.text_area("Contenido en hebreo/iídish:", res['contenido'], height=380, key=f"orig_{idx}")
                        
                        with col2:
                            st.subheader(f"Análisis e Interpretación ({idioma_destino})")
                            with st.spinner("🤖 Procesando análisis con IA..."):
                                traduccion = traducir_carta_premium(res['contenido'], idioma_destino, consulta_efectiva or filtro_fecha or "General")
                            st.markdown(traduccion)
        else:
            st.warning("No se encontraron coincidencias para la búsqueda especificada.")

# --- FOOTER CON MARCA DE AGUA ---
st.markdown("""
    <div class="footer">
        Hecho por: Ariel Lichinizer y Eitan Embon
    </div>
""", unsafe_allow_html=True)
