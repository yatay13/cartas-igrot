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

# --- OBTENCIÓN SEGURA DE LA API KEY ---
# Busca la clave en los Secrets de Streamlit o en variables de entorno local
API_KEY = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
ID_DRIVE = "1ARt_qkxwuGIKeA7LkKSITbzo4Q_w7Pzk"

# Inicializar cliente Gemini de forma transparente
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
            with st.spinner("Descargando base de datos por primera vez..."):
                gdown.download(url_drive, archivo_local, quiet=False)
        except Exception as e:
            return {}, f"Error al descargar desde Drive: {e}"

    # 1. Intentar leer JSON
    try:
        with open(archivo_local, "r", encoding="utf-8") as f:
            return json.load(f), "Google Drive (JSON)"
    except Exception:
        pass

    # 2. Intentar leer ZIP
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
col_img1, col_img2, col_img3 = st.columns([1, 2, 1])
with col_img2:
    st.image(
        "https://upload.wikimedia.org/wikipedia/commons/e/e6/Rabbi_Menachem_Mendel_Schneerson.jpg",
        caption="Menachem Mendel Schneerson - El Rebe de Lubavitch",
        use_container_width=True
    )

st.markdown("<h1 style='text-align: center;'>📜 Buscador de Igrot Kodesh</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: gray;'>Explora la correspondencia del Rebe por tema, palabras clave, fecha o tomo.</p>", unsafe_allow_html=True)
st.divider()

# --- BARRA LATERAL: CONFIGURACIÓN Y FILTROS ---
st.sidebar.header("⚙️ Opciones de Consulta")

generar_traduccion = st.sidebar.checkbox("Traducción e Interpretación con IA", value=True)

idioma_destino = "Español"
if generar_traduccion:
    idioma_destino = st.sidebar.selectbox(
        "Idioma de traducción:",
        ["Español", "Hebreo Moderno", "English", "Français", "Português", "Ruso"]
    )

cant_cartas = st.sidebar.selectbox("Cantidad de cartas a traer:", [3, 5, 10, 20], index=1)

st.sidebar.header("📁 Filtros Adicionales")
tomos_disponibles = ["Todos"] + list(base_datos.keys()) if base_datos else ["Todos"]
tomo_seleccionado = st.sidebar.selectbox("Filtrar por Tomo:", tomos_disponibles)

if base_datos:
    st.sidebar.success(f"Base de datos activa: {len(base_datos)} tomos cargados.")
else:
    st.sidebar.error("Error al cargar la base de datos.")

# --- FUNCIONES DE BÚSQUEDA E IA ---
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

# --- BUSCADOR PRINCIPAL CON FILTRO DE FECHAS ---
col_search1, col_search2 = st.columns([3, 1.5])

with col_search1:
    query = st.text_input("Ingrese tema, concepto o palabras clave:", placeholder="Ej: Educación, Salud, Bendición...")

with col_search2:
    filtro_fecha = st.text_input("Filtrar por año/fecha (Opcional):", placeholder="Ej: תש''ה, 1945...")

btn_buscar = st.button("🔍 Buscar y Analizar", type="primary", use_container_width=True)

# --- LÓGICA DE BÚSQUEDA Y RESULTADOS ---
if btn_buscar:
    if not query and not filtro_fecha:
        st.warning("Por favor ingrese un término de búsqueda o un filtro por fecha.")
    elif not base_datos:
        st.error("La base de datos de cartas no está cargada.")
    else:
        st.info("Buscando coincidencias...")
        
        es_hebreo = bool(re.search(r'[\u0590-\u05FF]', query)) if query else False
        terminos = [query.lower()] if es_hebreo or not query else obtener_conceptos_hebreo(query)
        
        if query:
            st.write(f"🎯 **Términos conceptuales buscados:** {', '.join(terminos)}")

        resultados = []
        for tomo, info in base_datos.items():
            if tomo_seleccionado != "Todos" and tomo != tomo_seleccionado:
                continue
            
            for carta in info.get("cartas", []):
                texto = carta.get("contenido", "")
                texto_lower = texto.lower()
                id_carta = carta.get("id_carta", "")
                
                coincide_termino = any(t in texto_lower or t == id_carta.lower() for t in terminos) if query else True
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
                            traduccion = traducir_carta(res['contenido'], idioma_destino, query or filtro_fecha)
                            st.markdown(traduccion)
        else:
            st.warning("No se encontraron cartas que coincidan con los criterios ingresados.")
