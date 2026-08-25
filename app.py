import json
import os
import re
import streamlit as st
from google import genai

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Buscador Inteligente - Igrot Kodesh",
    page_icon="📜",
    layout="wide"
)

st.title("📜 Buscador y Traductor de Igrot Kodesh")
st.caption("Consulte las cartas por tema, palabras clave, fecha o tomo con interpretación y traducción asistida por IA.")

# --- CARGA DE DATOS ---
@st.cache_data
def cargar_datos():
    # Ajusta la ruta a tu archivo JSON local o de servidor
    ruta = "igrot_kodesh_cartas.json" 
    if os.path.exists(ruta):
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

base_datos = cargar_datos()

# --- BARRA LATERAL: CONFIGURACIÓN DE API KEY E IDIOMA ---
st.sidebar.header("🔑 Configuración")
api_key_input = st.sidebar.text_input("Gemini API Key:", type="password", help="Ingresa tu clave de Google AI Studio")
idioma_destino = st.sidebar.selectbox("Idioma de traducción:", ["Español", "English", "Français", "Português", "Ruso", "Hebreo Moderno"])

client = None
if api_key_input:
    try:
        client = genai.Client(api_key=api_key_input)
        st.sidebar.success("API Key conectada")
    except Exception as e:
        st.sidebar.error("Error en la API Key")

# --- BARRA LATERAL: FILTROS ---
st.sidebar.header("🔍 Filtros de Búsqueda")
tomos_disponibles = ["Todos"] + list(base_datos.keys())
tomo_seleccionado = st.sidebar.selectbox("Filtrar por Tomo:", tomos_disponibles)
filtro_fecha = st.sidebar.text_input("Filtrar por rango de fechas/años (opcional):", placeholder="Ej: תש''ה o 1945")

# --- FUNCIONES DE IA Y BÚSQUEDA ---
def obtener_conceptos_hebreo(consulta):
    if not client:
        return [consulta]
    prompt = f"""
    El usuario busca en una colección de cartas rabínicas (Igrot Kodesh) sobre: '{consulta}'.
    Genera 5 a 8 palabras o frases equivalentes en HEBREO e IÍDISH que suelan aparecer en este tipo de textos.
    Responde ÚNICAMENTE las palabras en hebreo separadas por comas.
    """
    try:
        res = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return [t.strip().lower() for t in res.text.split(',') if t.strip()]
    except Exception:
        return [consulta]

def traducir_carta(contenido, idioma, tema):
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
        res = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return res.text
    except Exception as e:
        return f"Error al traducir: {e}"

# --- INTERFAZ PRINCIPAL DE BÚSQUEDA ---
query = st.text_input("Ingrese tema, concepto, número de carta o palabras clave:", placeholder="Ej: Educación de los hijos, Salud, Bendición...")

if st.button("🔎 Buscar y Analizar", type="primary"):
    if not query:
        st.warning("Por favor ingrese un término de búsqueda.")
    elif not base_datos:
        st.error("No se encontró el archivo JSON con los datos.")
    else:
        st.info("Procesando búsqueda...")
        
        # Mapeo semántico si la consulta no es hebreo
        es_hebreo = bool(re.search(r'[\u0590-\u05FF]', query))
        terminos = [query.lower()] if es_hebreo else obtener_conceptos_hebreo(query)
        
        st.write(f"🎯 **Términos de búsqueda aplicados:** {', '.join(terminos)}")

        # Búsqueda en el JSON
        resultados = []
        for tomo, info in base_datos.items():
            if tomo_seleccionado != "Todos" and tomo != tomo_seleccionado:
                continue
            
            for carta in info.get("cartas", []):
                texto = carta.get("contenido", "")
                texto_lower = texto.lower()
                id_carta = carta.get("id_carta", "")
                
                # Filtro por término y por fecha si se especificó
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

        st.success(f"Se encontraron {len(resultados)} cartas coincidentes.")

        # Despliegue de resultados
        for idx, res in enumerate(resultados, 1):
            with st.expander(f"📜 Carta {idx}: ID {res['id_carta']} | {res['tomo']}", expanded=True):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("Texto Original (Hebreo / Iídish)")
                    st.text_area("Contenido:", res['contenido'], height=300, key=f"orig_{idx}")
                
                with col2:
                    st.subheader(f"Traducción Abierta e Interpretación ({idioma_destino})")
                    if client:
                        traduccion = traducir_carta(res['contenido'], idioma_destino, query)
                        st.markdown(traduccion)
                    else:
                        st.warning("Ingrese su Gemini API Key en la barra lateral para ver la traducción.")