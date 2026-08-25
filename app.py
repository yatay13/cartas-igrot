import json
import os
import re
import zipfile
import urllib.request
import streamlit as st
from google import genai

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Buscador Inteligente - Igrot Kodesh",
    page_icon="📜",
    layout="wide"
)

st.title("📜 Traductor de Igrot Kodesh")
st.caption("Consulte las cartas por tema, palabras clave, fecha o tomo con interpretación y traducción asistida por IA.")

# ⚠️ PEGA AQUÍ EL ID DE TU ARCHIVO DE GOOGLE DRIVE:
ID_DRIVE = "TU_ID_DE_GOOGLE_DRIVE_AQUI" 

@st.cache_data
def cargar_datos_drive(file_id):
    if file_id == "1ARt_qkxwuGIKeA7LkKSITbzo4Q_w7Pzk":
        return {}, "Falta ingresar el ID de Google Drive"
        
    url_descarga = f"https://drive.google.com/uc?export=download&id={file_id}"
    archivo_local = "base_datos_descargada"
    
    # Descargar si no existe localmente en el servidor
    if not os.path.exists(archivo_local):
        with st.spinner("Descargando base de datos por primera vez (esto puede tomar unos segundos)..."):
            try:
                urllib.request.urlretrieve(url_descarga, archivo_local)
            except Exception as e:
                return {}, f"Error al descargar desde Drive: {e}"
                
    # Intentar leer como JSON directo
    try:
        with open(archivo_local, "r", encoding="utf-8") as f:
            return json.load(f), "Google Drive (JSON)"
    except Exception:
        pass

    # Intentar leer como ZIP
    try:
        with zipfile.ZipFile(archivo_local, 'r') as z:
            nombres_json = [f for f in z.namelist() if f.endswith('.json') and not f.startswith('__MACOSX')]
            if nombres_json:
                with z.open(nombres_json[0]) as f:
                    return json.load(f), "Google Drive (ZIP)"
    except Exception as e:
        return {}, f"El archivo descargado no es un JSON ni ZIP válido: {e}"

    return {}, "Formato desconocido"

base_datos, origen_datos = cargar_datos_drive(ID_DRIVE)

# --- BARRA LATERAL: CONFIGURACIÓN ---
st.sidebar.header("🔑 Configuración")
api_key_input = st.sidebar.text_input("Gemini API Key:", type="password", help="Pega aquí tu clave que empieza por AIzaSy...")
idioma_destino = st.sidebar.selectbox("Idioma de traducción:", ["Hebreo Moderno", "Español", "English", "Français", "Português", "Ruso"])

client = None
if api_key_input:
    try:
        client = genai.Client(api_key=api_key_input.strip())
        st.sidebar.success("API Key conectada")
    except Exception as e:
        st.sidebar.error("Error al inicializar la API Key")

st.sidebar.header("🔍 Filtros de Búsqueda")
tomos_disponibles = ["Todos"] + list(base_datos.keys()) if base_datos else ["Todos"]
tomo_seleccionado = st.sidebar.selectbox("Filtrar por Tomo:", tomos_disponibles)
filtro_fecha = st.sidebar.text_input("Filtrar por rango de fechas/años (opcional):", placeholder="Ej: תש''ה o 1945")

if base_datos:
    st.sidebar.info(f"📁 Base de datos cargada: {len(base_datos)} tomos desde `{origen_datos}`")
else:
    st.sidebar.error(f"⚠️ {origen_datos}")

# --- DICCIONARIO LOCAL DE RESPALDO ---
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
        El usuario busca en una colección de cartas rabínicas (Igrot Kodesh) sobre: '{consulta}'.
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
        return "⚠️ *Verifica tu Gemini API Key en el panel lateral para ver la traducción asistida por IA.*"
        
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

# --- INTERFAZ PRINCIPAL DE BÚSQUEDA ---
query = st.text_input("Ingrese tema, concepto, número de carta o palabras clave:", placeholder="Ej: Educación, Salud, Bendición...")

if st.button("🔍 Buscar y Analizar", type="primary"):
    if not query:
        st.warning("Por favor ingrese un término de búsqueda.")
    elif not base_datos:
        st.error("No se pudo cargar la base de datos de cartas.")
    else:
        st.info("Procesando búsqueda...")
        
        es_hebreo = bool(re.search(r'[\u0590-\u05FF]', query))
        terminos = [query.lower()] if es_hebreo else obtener_conceptos_hebreo(query)
        
        st.write(f"🎯 **Términos de búsqueda aplicados:** {', '.join(terminos)}")

        resultados = []
        for tomo, info in base_datos.items():
            if tomo_seleccionado != "Todos" and tomo != tomo_seleccionado:
                continue
            
            for carta in info.get("cartas", []):
                texto = carta.get("contenido", "")
                texto_lower = texto.lower()
                id_carta = carta.get("id_carta", "")
                
                coincide_termino = any(t in texto_lower or t == id_carta.lower() for t in terminos)
                coincide_fecha = (filtro_fecha.lower() in texto_lower or filtro_fecha.lower() in tomo.lower()) if filtro_fecha else True
                
                if coincide_termino and coincide_fecha:
                    resultados.append({
                        "tomo": os.path.basename(tomo),
                        "id_carta": id_carta,
                        "contenido": texto
                    })
                    if len(resultados) >= 5:
                        break

        if resultados:
            st.success(f"Se encontraron {len(resultados)} cartas coincidentes.")
            for idx, res in enumerate(resultados, 1):
                with st.expander(f"📜 Carta {idx}: ID {res['id_carta']} | {res['tomo']}", expanded=True):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.subheader("Texto Original (Hebreo / Iídish)")
                        st.text_area("Contenido:", res['contenido'], height=300, key=f"orig_{idx}")
                    
                    with col2:
                        st.subheader(f"Traducción Abierta ({idioma_destino})")
                        traduccion = traducir_carta(res['contenido'], idioma_destino, query)
                        st.markdown(traduccion)
        else:
            st.warning("No se encontraron cartas coincidentes. Intente con otro término de búsqueda.")
