import json
import os
import re
import zipfile
import gdown
import streamlit as st
from google import genai

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Igrot Kodesh - Buscador Inteligente",
    page_icon="📜",
    layout="wide"
)

# --- OBTENCIÓN SEGURA DE LA API KEY Y DATOS ---
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

# --- CARGA DE DATOS DESDE DRIVE ---
@st.cache_data
def cargar_datos_drive(file_id):
    archivo_local = "base_datos_descargada"
    
    if not os.path.exists(archivo_local):
        url_drive = f"https://drive.google.com/uc?id={file_id}"
        try:
            with st.spinner("Cargando base de datos por primera vez..."):
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

# --- CABECERA VISUAL CON LA IMAGEN ---
col_img1, col_img2, col_img3 = st.columns([1.5, 1, 1.5])
with col_img2:
    if os.path.exists("rebe.jpg"):
        st.image("rebe.jpg", caption="Menachem Mendel Schneerson - El Rebe de Lubavitch", use_container_width=True)
    elif os.path.exists("rebe.png"):
        st.image("rebe.png", caption="Menachem Mendel Schneerson - El Rebe de Lubavitch", use_container_width=True)
    else:
        st.warning("Para ver la imagen, guarda el archivo como 'rebe.jpg' en el repositorio de GitHub.")

st.markdown("<h1 style='text-align: center;'>📜 Buscador de Igrot Kodesh</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: gray;'>Explora la correspondencia del Rebe por tema, palabras clave, fecha o tomo.</p>", unsafe_allow_html=True)
st.divider()

# --- ESTADO DE SESIÓN ---
if "query_activa" not in st.session_state:
    st.session_state["query_activa"] = ""

# --- FILTROS PRINCIPALES Y BUSCADOR ---
col_f1, col_f2, col_f3, col_f4 = st.columns([2.5, 1.5, 1.2, 1])

tomos_disponibles = ["Todos"] + list(base_datos.keys()) if base_datos else ["Todos"]

with col_f1:
    query = st.text_input(
        "Ingrese tema, concepto o ID de carta:",
        value=st.session_state["query_activa"],
        placeholder="Ej: Educación, Salud, Bendición...",
        key="input_query"
    )

with col_f2:
    filtro_fecha = st.text_input("Filtrar por año/fecha:", placeholder="Ej: תש''ה, 1945...", key="input_fecha")

with col_f3:
    tomo_seleccionado = st.selectbox("Tomo:", tomos_disponibles)

with col_f4:
    cant_cartas = st.selectbox("Mostrar:", [3, 5, 10, 20, 50], index=1)

# Opciones secundarias
col_opt1, col_opt2 = st.columns([2, 2])
with col_opt1:
    generar_traduccion = st.checkbox("Traducción e Interpretación con IA", value=True)
with col_opt2:
    idioma_destino = st.selectbox(
        "Idioma de traducción:",
        ["Español", "Hebreo Moderno", "English", "Français", "Português", "Ruso"],
        disabled=not generar_traduccion
    )

# --- BOTONES DE BÚSQUEDA RÁPIDA ---
st.write("📌 **Búsquedas rápidas por tema:**")
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
if col_b6.button("📜 Limpiar", use_container_width=True):
    st.session_state["query_activa"] = ""
    st.rerun()

st.markdown("---")
btn_buscar = st.button("🔍 Buscar Cartas", type="primary", use_container_width=True)

# --- DICCIONARIO LOCAL Y FUNCIONES ---
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
    if client:
        prompt = f"""
        El usuario busca en cartas rabínicas (Igrot Kodesh) sobre: '{consulta}'.
        Genera 5 a 8 palabras o frases equivalentes en HEBREO e IÍDISH que suelan aparecer en este tipo de textos.
        Responde ÚNICAMENTE las palabras en hebreo separadas por comas.
        """
        try:
            res = client.models.generate_content(model='gemini-3.6-flash', contents=prompt)
            return [t.strip().lower() for t in res.text.split(',') if t.strip()]
        except Exception:
            pass

    consulta_clean = consulta.lower().strip()
    for clave, lista in DICCIONARIO_RESPALDO.items():
        if clave in consulta_clean:
            return lista
            
    return [consulta_clean]

@st.cache_data(show_spinner=False)
def traducir_carta_cached(contenido, idioma, tema):
    if not client:
        return "⚠️ *Servicio de IA no disponible. Configura la clave GEMINI_API_KEY en los Secrets de Streamlit Cloud.*"
        
    prompt = f"""
    Eres un experto erudito en hebreo clásico, hebreo rabínico e iídish.
    
    TEXTO ORIGINAL:
    {contenido[:3500]}

    Instrucciones para la respuesta en {idioma}:
    1. Comienza obligatoriamente con esta aclaración:
       "⚠️ *Nota de Traducción: Esta es una traducción abierta y libre asistida por IA. Debido a los términos conceptuales y modismos rabínicos del original en hebreo/iídish, no debe tomarse como una traducción literal ni un fallo halájico definitivo.*"
    2. Resumen breve del contenido de la carta y relación con el tema '{tema}'.
    3. Traducción abierta y fluida al {idioma}.
    4. Explica 2 o 3 términos clave en hebreo/iídish presentes en el texto.
    """
    try:
        res = client.models.generate_content(model='gemini-3.6-flash', contents=prompt)
        return res.text
    except Exception as e:
        return f"⚠️ Error de la API al traducir: {e}"

# --- LÓGICA DE BÚSQUEDA Y RESULTADOS ---
consulta_efectiva = query or st.session_state["query_activa"]

if btn_buscar or consulta_efectiva or filtro_fecha or tomo_seleccionado != "Todos":
    if not base_datos:
        st.error("La base de datos de cartas no está cargada.")
    else:
        es_hebreo = bool(re.search(r'[\u0590-\u05FF]', consulta_efectiva)) if consulta_efectiva else False
        terminos = [consulta_efectiva.lower()] if es_hebreo else obtener_conceptos_hebreo(consulta_efectiva)
        
        if consulta_efectiva:
            st.write(f"🎯 **Términos de búsqueda aplicados:** `{', '.join(terminos)}`")

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
            st.success(f"Se encontraron {len(resultados)} carta(s) coincidente(s).")
            
            for idx, res in enumerate(resultados, 1):
                with st.expander(f"📜 Carta {idx}: ID {res['id_carta']} | {res['tomo']}", expanded=True):
                    if not generar_traduccion:
                        st.subheader("Texto Original (Hebreo / Iídish)")
                        st.text_area("Contenido:", res['contenido'], height=350, key=f"orig_{idx}")
                    else:
                        col1, col2 = st.columns(2)
                        with col1:
                            st.subheader("Texto Original (Hebreo / Iídish)")
                            st.text_area("Contenido:", res['contenido'], height=350, key=f"orig_{idx}")
                        
                        with col2:
                            st.subheader(f"Traducción Abierta ({idioma_destino})")
                            with st.spinner("Interpretando texto..."):
                                traduccion = traducir_carta_cached(res['contenido'], idioma_destino, consulta_efectiva or filtro_fecha or "General")
                            st.markdown(traduccion)
        else:
            st.warning("No se encontraron cartas que coincidan con los criterios seleccionados.")

# --- FOOTER / MARCA DE AGUA ---
st.markdown("""
    <style>
    .footer {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background-color: rgba(15, 23, 42, 0.9);
        color: #94a3b8;
        text-align: center;
        padding: 8px 0px;
        font-size: 13px;
        font-weight: bold;
        letter-spacing: 0.5px;
        border-top: 1px solid #334155;
        z-index: 999;
    }
    </style>
    <div class="footer">
        Hecho por: Ariel Lichinizer y Eitan Embon
    </div>
""", unsafe_allow_html=True)
