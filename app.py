import json
import os
import re
import html
import zipfile
import base64
import gdown
import streamlit as st
import streamlit.components.v1 as components
from google import genai

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Igrot Kodesh - AI Premium",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- CODIFICACIÓN BASE64 SEGURA PARA EL FONDO DE PANTALLA ---
@st.cache_data(show_spinner=False)
def obtener_imagen_base64():
    try:
        for nombre in ["rebe.jpg", "rebe.jpeg", "rebe.png"]:
            if os.path.exists(nombre):
                ext = nombre.split(".")[-1]
                with open(nombre, "rb") as image_file:
                    encoded_string = base64.b64encode(image_file.read()).decode()
                return f"data:image/{ext};base64,{encoded_string}"
    except Exception as e:
        st.warning(f"No se pudo cargar la imagen local del Rebe: {e}")
    
    # Imagen de respaldo online por si no encuentra el archivo local
    return "https://images.unsplash.com/photo-1507842217343-583bb7270b66?q=80&w=2000&auto=format&fit=crop"

bg_image_data = obtener_imagen_base64()

# --- ESTILOS CSS CON FONDO DE LA FOTO DEL REBE Y CONTRASTE ---
st.markdown(f"""
    <style>
    .stApp {{
        background: linear-gradient(rgba(15, 23, 42, 0.88), rgba(15, 23, 42, 0.95)), 
                    url("{bg_image_data}");
        background-size: cover !important;
        background-position: center top !important;
        background-repeat: no-repeat !important;
        background-attachment: fixed !important;
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
    </style>
""", unsafe_allow_html=True)

# --- INICIALIZACIÓN DE ESTADOS DE SESIÓN ---
if "cache_tags" not in st.session_state:
    st.session_state["cache_tags"] = {}

if "query_activa" not in st.session_state:
    st.session_state["query_activa"] = ""

# --- SANITIZACIÓN DE TEXTO Y CONSULTAS ---
def sanitizar_texto(texto: str) -> str:
    if not texto: return ""
    try:
        clean = html.escape(str(texto).strip())
        clean = re.sub(r'[^\w\s\u0590-\u05FF\'"\-\.\,]', '', clean)
        return clean[:200]
    except Exception:
        return ""

# --- CONFIGURACIÓN Y CLIENTE GEMINI CON CONTROL DE ERRORES ---
API_KEY = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
ID_DRIVE = "1ARt_qkxwuGIKeA7LkKSITbzo4Q_w7Pzk"

@st.cache_resource
def obtener_cliente_gemini(api_key):
    if api_key:
        try:
            return genai.Client(api_key=api_key.strip())
        except Exception as e:
            st.error(f"Error al inicializar cliente GenAI: {e}")
            return None
    return None

client = obtener_cliente_gemini(API_KEY)

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

def ejecutar_gemini(prompt):
    if not client:
        return None, "Cliente IA no inicializado. Verifique la clave GEMINI_API_KEY en Secrets."
    
    modelos_api = obtener_modelos_dinamicos()
    candidatos = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"]
    modelos_a_probar = list(dict.fromkeys([m for m in modelos_api if "flash" in m or "pro" in m] + candidatos))
    
    ultimo_error = "Ningún modelo de IA respondió a la solicitud."
    for m in modelos_a_probar:
        try:
            res = client.models.generate_content(model=m, contents=prompt)
            if res and res.text:
                return res.text, None
        except Exception as e:
            ultimo_error = str(e)
            continue
            
    return None, ultimo_error

# --- CARGA DEFENSIVA DE BASE DE DATOS ---
@st.cache_data(ttl=3600, show_spinner=False)
def cargar_datos_drive(file_id):
    archivo_local = "base_datos_descargada"
    if not os.path.exists(archivo_local):
        url_drive = f"https://drive.google.com/uc?id={file_id}"
        try:
            with st.spinner("📦 Cargando base de datos por única vez..."):
                gdown.download(url_drive, archivo_local, quiet=False)
        except Exception as e:
            return {}, f"Error al descargar la base de datos: {e}"

    if not os.path.exists(archivo_local):
        return {}, "El archivo descargado no existe en el disco."

    try:
        with open(archivo_local, "r", encoding="utf-8") as f:
            return json.load(f), "JSON Directo"
    except Exception:
        pass

    try:
        with zipfile.ZipFile(archivo_local, 'r') as z:
            nombres_json = [f for f in z.namelist() if f.endswith('.json') and not f.startswith('__MACOSX')]
            if nombres_json:
                with z.open(nombres_json[0]) as f:
                    return json.load(f), "ZIP Extraído"
    except Exception as e:
        return {}, f"Error extrayendo JSON/ZIP: {e}"

    return {}, "Formato de base de datos no válido."

base_datos, origen_datos = cargar_datos_drive(ID_DRIVE)

# --- CABECERA DE LA APLICACIÓN ---
st.markdown("<h1 style='text-align: center;'>📜 Buscador de Igrot Kodesh</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #94a3b8;'>Plataforma Inteligente de Búsqueda y Traducción Erudita.</p>", unsafe_allow_html=True)

# --- REPRODUCTOR DE MÚSICA DE FONDO (REPRODUCCIÓN AUTOMÁTICA + BOTÓN PAUSAR/REPRODUCIR) ---
YOUTUBE_ID = "aL-L6hQAXcY"

components.html(
    f"""
    <div style="background: rgba(30, 41, 59, 0.85); padding: 12px; border-radius: 10px; border: 1px solid #334155; text-align: center;">
        <span style="color: #cbd5e1; font-family: system-ui, sans-serif; font-size: 14px; display: block; margin-bottom: 8px;">
            🎼 <b>Música Chassídica Instrumental de Fondo</b>
        </span>
        <button id="toggleBtn" onclick="toggleAudio()" style="background-color: #ef4444; color: white; border: none; padding: 8px 18px; border-radius: 6px; cursor: pointer; font-weight: bold; font-size: 13px; transition: 0.2s;">
            ⏸️ Detener / Pausar Música
        </button>
        <!-- Reproductor oculto en Autoplay por defecto -->
        <iframe 
            id="yt-player"
            width="0" 
            height="0" 
            src="https://www.youtube.com/embed/{YOUTUBE_ID}?enablejsapi=1&autoplay=1&mute=0&loop=1&playlist={YOUTUBE_ID}" 
            frameborder="0" 
            allow="autoplay">
        </iframe>
    </div>

    <script>
      var isPlaying = true;

      function toggleAudio() {{
        var iframe = document.getElementById('yt-player');
        var btn = document.getElementById('toggleBtn');
        
        if (isPlaying) {{
          iframe.contentWindow.postMessage('{{\"event\":\"command\",\"func\":\"pauseVideo\",\"args\":\"\"}}', '*');
          btn.innerText = "▶️ Reanudar Música";
          btn.style.backgroundColor = "#10b981";
          isPlaying = false;
        }} else {{
          iframe.contentWindow.postMessage('{{\"event\":\"command\",\"func\":\"playVideo\",\"args\":\"\"}}', '*');
          btn.innerText = "⏸️ Detener / Pausar Música";
          btn.style.backgroundColor = "#ef4444";
          isPlaying = true;
        }}
      }}
    </script>
    """,
    height=90
)

st.divider()

# --- FILTROS Y CONTROLES DE BÚSQUEDA ---
col_f1, col_f2, col_f3, col_f4 = st.columns([2.5, 1.5, 1.2, 1])
tomos_disponibles = ["Todos"] + list(base_datos.keys()) if isinstance(base_datos, dict) and base_datos else ["Todos"]

with col_f1:
    raw_query = st.text_input("Ingrese tema, concepto o ID:", value=st.session_state.get("query_activa", ""), placeholder="Ej: Educación, Salud, Bendición...", key="input_query")
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
    generar_traduccion = st.checkbox("Interpretación Erudita con IA", value=True)
with col_opt2:
    idioma_destino = st.selectbox("Idioma de traducción:", ["Español", "Hebreo Moderno", "English", "Français", "Português", "Ruso"], disabled=not generar_traduccion)

# --- BOTONES DE CATEGORÍAS RÁPIDAS ---
st.write("📌 **Categorías Rápidas:**")
col_b1, col_b2, col_b3, col_b4, col_b5, col_b6 = st.columns(6)
if col_b1.button("🩺 Salud", use_container_width=True): st.session_state["query_activa"] = "Salud"
if col_b2.button("🎓 Educación", use_container_width=True): st.session_state["query_activa"] = "Educación"
if col_b3.button("✨ Bendición", use_container_width=True): st.session_state["query_activa"] = "Bendición"
if col_b4.button("💼 Trabajo", use_container_width=True): st.session_state["query_activa"] = "Trabajo"
if col_b5.button("💍 Matrimonio", use_container_width=True): st.session_state["query_activa"] = "Matrimonio"
if col_b6.button("🧹 Limpiar", use_container_width=True): st.session_state["query_activa"] = ""

st.markdown("---")

btn_buscar = st.button("🔍 Realizar Búsqueda Avanzada", type="primary", use_container_width=True)

# --- DICCIONARIO BASE EN HEBREO ---
DICCIONARIO_RESPALDO = {
    "salud": ["רפואה", "רפואה שלימה", "בריאות", "רופא", "חולה"],
    "educacion": ["חינוך", "חינוך ילדים", "תלמוד תורה", "מלמד"],
    "educación": ["חינוך", "חינוך ילדים", "תלמוד תורה", "מלמד"],
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
    if not contenido or not str(contenido).strip():
        return "⚠️ *El texto de esta carta está vacío.*", []

    prompt = f"""
    Eres un Rabino y erudito lingüista. Analiza la siguiente carta original del Rebe de Lubavitch:
    
    TEXTO ORIGINAL:
    {str(contenido)[:4000]}

    Genera una respuesta estructurada estrictamente en {idioma}:
    1. Aclaración inicial: "⚠️ *Nota de Traducción: Interpretación asistida por IA.*"
    2. **Etiquetas_Clave**: Genera de 3 a 5 palabras clave temáticas. Escríbelas así: ETIQUETAS: tag1, tag2, tag3
    3. **Contexto & Esencia**: Breve síntesis.
    4. **Traducción Contextual Fluida**: Traduce respetando el tono pastoral.
    5. **Glosario**: Explica 2-3 términos rabínicos clave.
    """
    
    res_text, err = ejecutar_gemini(prompt)
        
    if not res_text:
        return f"⚠️ *Error al procesar con IA: {err}*", []

    tags_extraidos = []
    try:
        match = re.search(r'ETIQUETAS:\s*(.*)', res_text, re.IGNORECASE)
        if match:
            tags_raw = match.group(1).split(',')
            tags_extraidos = [t.strip().lower() for t in tags_raw if t.strip()]
            st.session_state["cache_tags"][id_carta] = tags_extraidos
    except Exception:
        pass

    return res_text, tags_extraidos

# --- MOTOR DE BÚSQUEDA EXCLUSIVO AL HACER CLIC ---
if btn_buscar:
    consulta_efectiva = query or st.session_state.get("query_activa", "")
    
    if not isinstance(base_datos, dict) or not base_datos:
        st.error(f"Base de datos no disponible o inválida. Status: {origen_datos}")
    else:
        try:
            es_hebreo = bool(re.search(r'[\u0590-\u05FF]', consulta_efectiva)) if consulta_efectiva else False
            terminos = [consulta_efectiva.lower()] if es_hebreo else obtener_conceptos_hebreo(consulta_efectiva)
            
            if consulta_efectiva:
                badges_html = "".join([f"<span class='badge'>{t}</span>" for t in terminos])
                st.markdown(f"🎯 **Términos de Búsqueda:** {badges_html}", unsafe_allow_html=True)

            resultados = []
            for tomo, info in base_datos.items():
                if tomo_seleccionado != "Todos" and tomo != tomo_seleccionado:
                    continue
                
                cartas_lista = info.get("cartas", []) if isinstance(info, dict) else []
                for carta in cartas_lista:
                    if not isinstance(carta, dict): continue
                    
                    texto = carta.get("contenido", "")
                    if not texto or not str(texto).strip(): continue
                        
                    texto_lower = str(texto).lower()
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
                    
                    coincide_fecha = (filtro_fecha.lower() in texto_lower or filtro_fecha.lower() in str(tomo).lower()) if filtro_fecha else True
                    
                    if coincide_termino and coincide_fecha:
                        resultados.append({
                            "tomo": os.path.basename(str(tomo)),
                            "id_carta": id_carta,
                            "contenido": texto,
                            "tags": cached_tags
                        })
                        if len(resultados) >= cant_cartas: break
                if len(resultados) >= cant_cartas: break

            if resultados:
                st.success(f"Se encontraron **{len(resultados)}** cartas.")
                
                for idx, res in enumerate(resultados, 1):
                    with st.expander(f"📜 Carta {idx} | ID: {res['id_carta']} | {res['tomo']}", expanded=True):
                        if res["tags"]:
                            tags_html = "".join([f"<span class='badge-tag'>🏷️ {t}</span>" for t in res["tags"]])
                            st.markdown(f"**Etiquetas:** {tags_html}", unsafe_allow_html=True)
                            st.write("")

                        if not generar_traduccion:
                            st.subheader("Texto Original")
                            st.text_area("Contenido:", res['contenido'], height=350, key=f"orig_{idx}")
                        else:
                            col1, col2 = st.columns(2)
                            with col1:
                                st.subheader("Texto Original")
                                st.text_area("Contenido:", res['contenido'], height=380, key=f"orig_{idx}")
                            
                            with col2:
                                st.subheader(f"Análisis ({idioma_destino})")
                                with st.spinner("🤖 Procesando análisis..."):
                                    traduccion, _ = traducir_y_etiquetar(
                                        res['contenido'], 
                                        idioma_destino, 
                                        consulta_efectiva or filtro_fecha or "General",
                                        res['id_carta']
                                    )
                                st.markdown(traduccion)
            else:
                st.warning("No se encontraron cartas que coincidan con los filtros aplicados.")
        except Exception as err_proc:
            st.error(f"Ocurrió un fallo durante el procesamiento de la búsqueda: {err_proc}")

# --- PIE DE PÁGINA ---
st.markdown("""
    <div class="footer">
        Hecho por: Ariel Lichinizer y Eitan Embon
    </div>
""", unsafe_allow_html=True)
