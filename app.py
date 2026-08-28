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

# --- DETECCION DE RUTA DE IMAGEN DEL REBE PARA EL FONDO ---
imagen_fondo = ""
if os.path.exists("rebe.jpg"):
    imagen_fondo = "rebe.jpg"
elif os.path.exists("rebe.png"):
    imagen_fondo = "rebe.png"
else:
    imagen_fondo = "https://images.unsplash.com/photo-1507842217343-583bb7270b66?q=80&w=2000&auto=format&fit=crop"

# --- ESTILOS CSS CON FONDO DE LA FOTO DEL REBE ---
st.markdown(f"""
    <style>
    /* Fondo principal usando la imagen del Rebe con superposición oscura */
    .stApp {{
        background: linear-gradient(rgba(15, 23, 42, 0.88), rgba(15, 23, 42, 0.94)), 
                    url("{imagen_fondo}");
        background-size: cover;
        background-position: center top;
        background-attachment: fixed;
        color: #f8fafc;
    }}
    
    .badge {{
        background-color: #3b82f6; color: white; padding: 4px 10px;
        border-radius: 6px; font-size: 12px; font-weight: 600;
        display: inline-block; margin-right: 5px; margin-bottom: 5px;
    }}
    .badge-tag {{
        background-color: #10b981; color: white; padding: 3px 8px;
        border-radius: 4px; font-size: 11px; font-weight: 600;
        display: inline-block; margin-right: 4px;
    }}
    .footer {{
        position: fixed; left: 0; bottom: 0; width: 100%;
        background-color: rgba(15, 23, 42, 0.95); color: #94a3b8;
        text-align: center; padding: 10px 0px; font-size: 13px;
        font-weight: 600; border-top: 1px solid #334155;
        backdrop-filter: blur(8px); z-index: 999;
    }}
    .audio-container {{
        background: rgba(30, 41, 59, 0.7);
        padding: 12px 20px;
        border-radius: 10px;
        border: 1px solid #334155;
        margin-bottom: 20px;
    }}
    </style>
""", unsafe_allow_html=True)

# --- INICIALIZACIÓN DE CACHÉ EN SESIÓN ---
if "cache_tags" not in st.session_state:
    st.session_state["cache_tags"] = {}

if "query_activa" not in st.session_state:
    st.session_state["query_activa"] = ""

# --- SANITIZACIÓN ---
def sanitizar_texto(texto: str) -> str:
    if not texto: return ""
    clean = html.escape(texto.strip())
    clean = re.sub(r'[^\w\s\u0590-\u05FF\'"\-\.\,]', '', clean)
    return clean[:200]

# --- OBTENCIÓN DE API KEY Y CLIENTE ---
API_KEY = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
ID_DRIVE = "1ARt_qkxwuGIKeA7LkKSITbzo4Q_w7Pzk"

@st.cache_resource
def obtener_cliente_gemini(api_key):
    if api_key:
        try: return genai.Client(api_key=api_key.strip())
        except Exception: return None
    return None

client = obtener_cliente_gemini(API_KEY)

# --- OBTENER MODELOS VÁLIDOS DE LA API ---
@st.cache_resource
def obtener_modelos_dinamicos():
    if not client: return []
    try:
        modelos_disponibles = []
        for m in client.models.list():
            nombre = m.name.split("/")[-1] if "/" in m.name else m.name
            modelos_disponibles.append(nombre)
        return modelos_disponibles
    except Exception:
        return []

# --- EJECUTOR GEMINI CON RESPALDO ---
def ejecutar_gemini(prompt):
    if not client:
        return None, "Cliente no inicializado. Revisa la GEMINI_API_KEY en Secrets."
    
    modelos_api = obtener_modelos_dinamicos()
    candidatos_por_defecto = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"]
    modelos_a_probar = [m for m in modelos_api if "flash" in m or "pro" in m] + candidatos_por_defecto
    modelos_unicos = list(dict.fromkeys(modelos_a_probar))
    
    ultimo_error = ""
    for m in modelos_unicos:
        try:
            res = client.models.generate_content(model=m, contents=prompt)
            if res and res.text:
                return res.text, None
        except Exception as e:
            ultimo_error = str(e)
            continue
            
    return None, ultimo_error

# --- CARGA DE DATOS ---
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
    except Exception: pass

    try:
        with zipfile.ZipFile(archivo_local, 'r') as z:
            nombres_json = [f for f in z.namelist() if f.endswith('.json') and not f.startswith('__MACOSX')]
            if nombres_json:
                with z.open(nombres_json[0]) as f:
                    return json.load(f), "Google Drive (ZIP)"
    except Exception as e:
        return {}, f"Error: {e}"

    return {}, "Formato no compatible"

base_datos, origen_datos = cargar_datos_drive(ID_DRIVE)

# --- CABECERA ---
st.markdown("<h1 style='text-align: center;'>📜 Buscador de Igrot Kodesh</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #94a3b8;'>Plataforma Inteligente con Selección Precisa de Cartas.</p>", unsafe_allow_html=True)

# --- PLAYLIST DE NIGUNIM TRANQUILOS (ACTIVADA POR DEFECTO) ---
PLAYLIST_NIGUNIM = {
    "Tzama Lecha Nafshi (Meditación Chassidica)": "https://ia801406.us.archive.org/5/items/lp_nhaha-niguni-hasidi-habd_lubavitcher-chassidim/track_07.mp3",
    "Nigun D'veikus (Conexión Profunda)": "https://ia800206.us.archive.org/30/items/lp_chabad-nigunim-vol2_lubavitcher-chassidim/track_04.mp3",
    "Rostover Nigun (Melodía de Rostov)": "https://ia800206.us.archive.org/30/items/lp_chabad-nigunim-vol2_lubavitcher-chassidim/track_05.mp3",
    "Ach Leilokim Domi Nafshi": "https://ia801406.us.archive.org/5/items/lp_nhaha-niguni-hasidi-habd_lubavitcher-chassidim/track_12.mp3"
}

col_audio1, col_audio2 = st.columns([1, 2])
with col_audio1:
    nigun_seleccionado = st.selectbox("🎵 Playlist Nigunim de Jabad:", list(PLAYLIST_NIGUNIM.keys()))

with col_audio2:
    url_pista = PLAYLIST_NIGUNIM[nigun_seleccionado]
    # Embebido con autoplay directo en la interfaz principal
    st.markdown(f"""
        <div class="audio-container">
            <audio controls autoplay style="width: 100%;">
                <source src="{url_pista}" type="audio/mp3">
                Tu navegador no soporta el elemento de audio.
            </audio>
        </div>
    """, unsafe_allow_html=True)

st.divider()

# --- CONTROLES DE BÚSQUEDA ---
col_f1, col_f2, col_f3, col_f4 = st.columns([2.5, 1.5, 1.2, 1])
tomos_disponibles = ["Todos"] + list(base_datos.keys()) if base_datos else ["Todos"]

with col_f1:
    raw_query = st.text_input("Ingrese tema, concepto o ID:", value=st.session_state["query_activa"], placeholder="Ej: Educación, Salud, Bendición...", key="input_query")
    query = sanitizar_texto(raw_query)

with col_f2:
    raw_fecha = st.text_input("Filtrar por año/fecha:", placeholder="Ej: תש''ה, 1945...", key="input_fecha")
    filtro_fecha = sanitizar_texto(raw_fecha)

with col_f3:
    tomo_seleccionado = st.selectbox("Tomo:", tomos_disponibles)

with col_f4:
    cant_cartas = st.selectbox("Mostrar:", [3, 5, 10, 20, 50], index=1)

col_opt1, col_opt2 = st.columns([2, 2])
with col_opt1:
    generar_traduccion = st.checkbox("Interpretación Erudita con IA (Modelo Pro)", value=True)
with col_opt2:
    idioma_destino = st.selectbox("Idioma de traducción:", ["Español", "Hebreo Moderno", "English", "Français", "Português", "Ruso"], disabled=not generar_traduccion)

# --- BOTONES DE ACCESO RÁPIDO ---
st.write("📌 **Categorías Principales:**")
col_b1, col_b2, col_b3, col_b4, col_b5, col_b6 = st.columns(6)
if col_b1.button("🩺 Salud", use_container_width=True): st.session_state["query_activa"] = "Salud"
if col_b2.button("🎓 Educación", use_container_width=True): st.session_state["query_activa"] = "Educación"
if col_b3.button("✨ Bendición", use_container_width=True): st.session_state["query_activa"] = "Bendición"
if col_b4.button("💼 Trabajo", use_container_width=True): st.session_state["query_activa"] = "Trabajo"
if col_b5.button("💍 Matrimonio", use_container_width=True): st.session_state["query_activa"] = "Matrimonio"
if col_b6.button("🧹 Limpiar", use_container_width=True): st.session_state["query_activa"] = ""

st.markdown("---")

# BOTÓN ÚNICO DE ACTIVACIÓN DE BÚSQUEDA
btn_buscar = st.button("🔍 Realizar Búsqueda Avanzada", type="primary", use_container_width=True)

# --- DICCIONARIO BASE ENRIQUECIDO ---
DICCIONARIO_RESPALDO = {
    "salud": ["רפואה", "רפואה שלימה", "בריאות", "רופא", "חולה"],
    "educacion": ["חינוך", "חינוך ילדים", "תלמוד תורה", "מלמד", "בית ספר"],
    "educación": ["חינוך", "חינוך ילדים", "תלמוד תורה", "מלמד", "בית ספר"],
    "bendicion": ["ברכה", "ברכה והצלחה", "אגרת", "בברכה"],
    "bendición": ["ברכה", "ברכה והצלחה", "אגרת", "בברכה"],
    "trabajo": ["פרנסה", "עבודה", "מסחר", "עסק"],
    "matrimonio": ["שידוך", "חתונה", "זיווג", "חתן", "כלה"]
}

def obtener_conceptos_hebreo(consulta):
    if not consulta: return []
    consulta_clean = consulta.lower().strip()
    
    if consulta_clean in DICCIONARIO_RESPALDO:
        return DICCIONARIO_RESPALDO[consulta_clean]

    prompt = f"Proporciona entre 4 y 7 términos clave en HEBREO asociados a '{consulta}' en las cartas del Rebe de Lubavitch. Responde SOLO palabras en hebreo separadas por comas."
    res_text, _ = ejecutar_gemini(prompt)
    if res_text:
        return [t.strip().lower() for t in res_text.split(',') if t.strip()]

    return [consulta_clean]

def traducir_y_etiquetar(contenido, idioma, tema, id_carta):
    if not contenido or not contenido.strip():
        return "⚠️ *El texto de esta carta está vacío en la base de datos JSON original.*", []

    prompt = f"""
    Eres un Rabino y erudito lingüista. Analiza la siguiente carta original del Rebe de Lubavitch:
    
    TEXTO ORIGINAL:
    {contenido[:4000]}

    Genera una respuesta estructurada strictly en {idioma}:
    1. Aclaración inicial: "⚠️ *Nota de Traducción: Interpretación asistida por IA.*"
    2. **Etiquetas_Clave**: Genera de 3 a 5 palabras clave temáticas descriptivas de la carta (ejemplo: Salud, Parnasá, Educación, Bitajón). Escríbelas en la línea exactamente así: ETIQUETAS: tag1, tag2, tag3
    3. **Contexto & Esencia**: Breve síntesis.
    4. **Traducción Contextual Fluida**: Traduce respetando el tono pastoral.
    5. **Glosario**: Explica 2-3 términos rabínicos clave.
    """
    
    res_text, err = ejecutar_gemini(prompt)
        
    if not res_text:
        return f"⚠️ *Error al procesar la carta con el motor de IA: {err}*", []

    tags_extraidos = []
    match = re.search(r'ETIQUETAS:\s*(.*)', res_text, re.IGNORECASE)
    if match:
        tags_raw = match.group(1).split(',')
        tags_extraidos = [t.strip().lower() for t in tags_raw if t.strip()]
        st.session_state["cache_tags"][id_carta] = tags_extraidos

    return res_text, tags_extraidos

# --- MOTOR DE BÚSQUEDA EXCLUSIVO POR BOTÓN ---
if btn_buscar:
    consulta_efectiva = query or st.session_state["query_activa"]
    
    if not base_datos:
        st.error("Base de datos no disponible.")
    else:
        es_hebreo = bool(re.search(r'[\u0590-\u05FF]', consulta_efectiva)) if consulta_efectiva else False
        terminos = [consulta_efectiva.lower()] if es_hebreo else obtener_conceptos_hebreo(consulta_efectiva)
        
        if consulta_efectiva:
            badges_html = "".join([f"<span class='badge'>{t}</span>" for t in terminos])
            st.markdown(f"🎯 **Términos de Búsqueda Aplicados:** {badges_html}", unsafe_allow_html=True)

        resultados = []
        for tomo, info in base_datos.items():
            if tomo_seleccionado != "Todos" and tomo != tomo_seleccionado:
                continue
            
            for carta in info.get("cartas", []):
                texto = carta.get("contenido", "")
                
                if not texto or not texto.strip():
                    continue
                    
                texto_lower = texto.lower()
                id_carta = str(carta.get("id_carta", "")).lower()
                cached_tags = st.session_state["cache_tags"].get(id_carta, [])
                
                coincide_termino = False
                if terminos:
                    coincide_termino = (
                        any(t in texto_lower or t in id_carta for t in terminos) or
                        any(c_tag in consulta_efectiva.lower() for c_tag in cached_tags)
                    )
                else:
                    coincide_termino = True
                
                coincide_fecha = (filtro_fecha.lower() in texto_lower or filtro_fecha.lower() in tomo.lower()) if filtro_fecha else True
                
                if coincide_termino and coincide_fecha:
                    resultados.append({
                        "tomo": os.path.basename(tomo),
                        "id_carta": id_carta,
                        "contenido": texto,
                        "tags": cached_tags
                    })
                    if len(resultados) >= cant_cartas: break
            if len(resultados) >= cant_cartas: break

        if resultados:
            st.success(f"Se encontraron **{len(resultados)}** cartas relevantes con contenido real.")
            
            for idx, res in enumerate(resultados, 1):
                with st.expander(f"📜 Carta {idx} | ID: {res['id_carta']} | {res['tomo']}", expanded=True):
                    if res["tags"]:
                        tags_html = "".join([f"<span class='badge-tag'>🏷️ {t}</span>" for t in res["tags"]])
                        st.markdown(f"**Etiquetas en Caché:** {tags_html}", unsafe_allow_html=True)
                        st.write("")

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
                            with st.spinner("🤖 Procesando análisis y generando etiquetas..."):
                                traduccion, nuevos_tags = traducir_y_etiquetar(
                                    res['contenido'], 
                                    idioma_destino, 
                                    consulta_efectiva or filtro_fecha or "General",
                                    res['id_carta']
                                )
                            st.markdown(traduccion)
        else:
            st.warning("No se encontraron cartas que contengan los términos o temas especificados.")

# --- FOOTER ---
st.markdown("""
    <div class="footer">
        Hecho por: Ariel Lichinizer y Eitan Embon
    </div>
""", unsafe_allow_html=True)
