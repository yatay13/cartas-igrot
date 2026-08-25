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

client = None
if API_KEY:
    try:
        client = genai.Client(api_key=API_KEY.strip())
    except Exception:
        client = None

# --- CARGA DE DATOS DESDE DRIVE ---
@st.cache_data
def cargar_datos_drive(file_id):
    archivo_local = "base_datos_descargada"
    
    if not os.path.exists(archivo_local):
        url_drive = f"https://drive.google.com/uc?id={file_id}"
        try:
            with st.spinner("Descargando base de datos..."):
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
col_img1, col_img2, col_img3 = st.columns([1.5, 1, 1.5])
with col_img2:
    # URL directa e incrustada para evitar bloqueos de imagen
    st.image(
        "https://raw.githubusercontent.com/streamlit/30days-site/main/static/favicon.png", # Reemplazar si tienes assets locales
        caption="Menachem Mendel Schneerson - El Rebe de Lubavitch",
        use_container_width=True
    )

st.markdown("<h1 style='text-align: center;'>📜 Buscador de Igrot Kodesh</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: gray;'>Explora la correspondencia del Rebe por tema, palabras clave, fecha o tomo.</p>", unsafe_allow_html=True)
st.divider()

# --- FILTROS PRINCIPALES Y BUSCADOR (SIN BARRA LATERAL) ---
col_f1, col_f2, col_f3, col_f4 = st.columns([2, 1.5, 1, 1])

tomos_disponibles = ["Todos"] + list(base_datos.keys()) if base_datos else ["Todos"]

with col_f1:
    query = st.text_input("Ingrese tema, concepto o ID de carta:", placeholder="Ej: Educación, Salud, Bendición...", key="input_query")

with col_f2:
    filtro_fecha = st.text_input("Filtrar por año/fecha:", placeholder="Ej: תש''ה, 1945...", key="input_fecha")

with col_f3:
    tomo_seleccionado = st.selectbox("Tomo:", tomos_disponibles)

with col_f4:
    cant_cartas = st.selectbox("Mostrar:", [3, 5, 10, 20, 50], index=1)

# Opciones secundarias alineadas
col_opt1, col_opt2 = st.columns([2, 2])
with col_opt1:
    generar_traduccion = st.checkbox("Traducción e Interpretación con IA", value=True)
with col_opt2:
    idioma_destino = st.selectbox(
        "Idioma de traducción:",
        ["Español", "Hebreo Moderno", "English", "Français", "Português", "Ruso"],
        disabled=not generar_traduccion
    )

# --- BOTONES DE BÚSQUEDA RÁPIDA POR TEMAS POPULARES ---
st.write("📌 **Búsquedas rápidas:**")
col_b1, col_b2, col_b3, col_b4, col_b5, col_b6 = st.columns(6)

tema_rapido = None
if col_b1.button("🩺 Salud", use_container_width=True):
    tema_rapido = "Salud"
if col_b2.button("🎓 Educación", use_container_width=True):
    tema_rapido = "Educacion"
if col_b3.button("✨ Bendición", use_container_width=True):
    tema_rapido = "Bendicion"
if col_b4.button("💼 Trabajo", use_container_width=True):
    tema_rapido = "Trabajo"
if col_b5.button("💍 Matrimonio", use_container_width=True):
    tema_rapido = "Matrimonio"
if col_b6.button("📜 Ver Todas", use_container_width=True):
    tema_rapido = ""

# Determinar consulta activa
consulta_activa = tema_rapido if tema_rapido is not None else query

# --- BOTÓN DE BÚSQUEDA ---
st.markdown("---")
btn_buscar = st.button("🔍 Buscar Cartas", type="primary", use_container_width=True)

# --- DICCIONARIO LOCAL Y FUNCIONES DE PRECISIÓN ---
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

def traducir_carta(contenido, idioma, tema):
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
if btn_buscar or tema_rapido is not None:
    if not base_datos:
        st.error("La base de datos de cartas no está cargada.")
    else:
        st.info("Buscando coincidencias...")
        
        es_hebreo = bool(re.search(r'[\u0590-\u05FF]', consulta_activa)) if consulta_activa else False
        terminos = [consulta_activa.lower()] if es_hebreo else obtener_conceptos_hebreo(consulta_activa)
        
        if consulta_activa:
            st.write(f"🎯 **Términos de búsqueda aplicados:** {', '.join(terminos)}")

        resultados = []
        for tomo, info in base_datos.items():
            if tomo_seleccionado != "Todos" and tomo != tomo_seleccionado:
                continue
            
            for carta in info.get("cartas", []):
                texto = carta.get("contenido", "")
                texto_lower = texto.lower()
                id_carta = str(carta.get("id_carta", "")).lower()
                
                # Precisión: Búsqueda por término/ID o flexible si no hay texto
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
                            traduccion = traducir_carta(res['contenido'], idioma_destino, consulta_activa or filtro_fecha or "General")
                            st.markdown(traduccion)
        else:
            st.warning("No se encontraron cartas que coincidan con los criterios seleccionados.")
