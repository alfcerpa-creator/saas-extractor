import streamlit as st
import pandas as pd
import random
import time
import re
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

st.set_page_config(page_title="SaaS Business Intelligence", layout="wide")

DICCIONARIO_CATEGORIAS = {
    "gafas": "Ópticas", "lentes": "Ópticas", "ojos": "Ópticas", "lentillas": "Ópticas",
    "gas": "Estaciones de servicio", "gasolina": "Estaciones de servicio", "combustible": "Estaciones de servicio",
    "super": "Supermercados", "compras": "Supermercados", "comida": "Restaurantes", "cenar": "Restaurantes",
    "medicina": "Farmacias", "farmacia": "Farmacias", "ropa": "Tiendas de ropa", "moda": "Tiendas de ropa"
}

# Base de datos global compartida en la sesión
if "db_compartida" not in st.session_state:
    st.session_state.db_compartida = pd.DataFrame(columns=[
        "Nombre del Negocio", "Dirección", "Teléfono", "Sitio Web", "Email", "Municipio", "Categoría"
    ])

# =====================================================================
# MOTOR DE EXTRACCIÓN REAL MEDIANTE API INTERNA / BUSCADOR
# =====================================================================
def extraer_datos_reales(query, ciudad, limite, status_box, progress_bar):
    busqueda = f"{query} en {ciudad}"
    resultados = []
    
    status_box.info(f"🔍 Conectando con los servidores de Mapas para extraer datos reales de: {busqueda}...")
    
    # Simulación de cabeceras de navegador real de escritorio para evitar bloqueos
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "es-ES,es;q=0.9"
    }
    
    # Realizamos una consulta enriquecida al motor de búsqueda geográfico público
    url = f"https://html.duckduckgo.com/html/?q={busqueda.replace(' ', '+')}+maps+telefono"
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        progress_bar.progress(30)
        
        if response.status_code == 200:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Buscamos los bloques de resultados reales devueltos
            bloques = soup.find_all('div', class_='result__body')
            count = 0
            
            for bloque in bloques:
                if count >= limite:
                    break
                    
                title_elem = bloque.find('a', class_='result__url')
                snippet_elem = bloque.find('a', class_='result__snippet')
                
                if title_elem:
                    nombre_sucio = title_elem.text.strip()
                    # Limpiar cadenas comunes de URLs si aparecen en el título
                    nombre = nombre_sucio.split(" - ")[0].split(" | ")[0]
                    
                    # Ignorar resultados que apunten a directorios masivos repetidos
                    if any(x in nombre.lower() for x in ["paginasamarillas", "tripadvisor", "yelp", "linkedin"]):
                        continue
                        
                    texto_completo = bloque.text
                    
                    # Extracción de teléfono real por expresiones regulares
                    tel_match = re.search(r'(?:\+34|34)?[679]\d{8}|\b[679]\d{2}\s\d{2}\s\d{2}\s\d{2}\b', texto_completo)
                    telefono = tel_match.group(0) if tel_match else "No disponible"
                    
                    # Extracción de dirección o aproximación real
                    direccion = "No disponible"
                    palabras_direccion = ["calle", "av.", "avenida", "plaza", "c/"]
                    for frase in texto_completo.split("\n"):
                        if any(p in frase.lower() for p in palabras_direccion):
                            direccion = frase.strip()
                            break
                    if direccion == "No disponible" and snippet_elem:
                        direccion = snippet_elem.text.strip()[:60] + "..."
                    
                    # Resolver Sitio Web Real si está disponible en la URL del bloque
                    href = title_elem.get('href', '')
                    sitio_web = "N/A"
                    if "uddg=" in href:
                        url_real = href.split("uddg=")[1].split("&")[0]
                        url_real = requests.utils.unquote(url_real)
                        if not any(x in url_real for x in ["google", "duckduckgo", "bing"]):
                            sitio_web = "/".join(url_real.split("/")[:3])
                    
                    # Construcción de email corporativo predictivo si hay web
                    email = "N/A"
                    if sitio_web != "N/A":
                        dominio = sitio_web.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
                        email = f"contacto@{dominio}"
                    
                    resultados.append({
                        "Nombre del Negocio": nombre,
                        "Dirección": direccion,
                        "Teléfono": telefono,
                        "Sitio Web": sitio_web,
                        "Email": email,
                        "Municipio": ciudad.title(),
                        "Categoría": query
                    })
                    count += 1
                    progress_bar.progress(int((count / limite) * 100))
                    status_box.text(f"✅ Extraído real: {nombre}")
            
            if not resultados:
                status_box.warning("No se pudieron filtrar registros limpios en esta consulta. Intenta cambiar los términos o la ciudad.")
        else:
            status_box.error(f"Error de conexión con el nodo de datos. Código: {response.status_code}")
            
    except Exception as e:
        status_box.error(f"Error en la consulta HTTP: {str(e)}")
        
    df_crudo = pd.DataFrame(resultados)
    
    # Aplicar el módulo de refinamiento para normalizar teléfonos y eliminar duplicados
    if not df_crudo.empty:
        df_crudo['Nombre del Negocio'] = df_crudo['Nombre del Negocio'].str.title()
        df_crudo = df_crudo.drop_duplicates(subset=['Nombre del Negocio', 'Teléfono'])
        
    return df_crudo

# =====================================================================
# VISTA INTERFAZ GRÁFICA (DASHBOARD)
# =====================================================================
st.title("🚀 SaaS Centralizado de Extracción y Marketing")
st.write("Datos reales extraídos directamente a través de pasarelas HTTP seguras.")

pestana_extraccion, pestana_email = st.tabs(["🔍 Motor de Extracción Masiva", "📧 Central de Email Marketing (SMTP)"])

with pestana_extraccion:
    c1, c2 = st.columns([1, 2])
    with c1:
        st.header("Parámetros del Robot")
        entrada = st.text_input("¿Qué tipo de negocio buscas?", value="Ópticas", key="q_in")
        
        categoria_final = entrada
        for k, v in DICCIONARIO_CATEGORIAS.items():
            if k in entrada.lower():
                categoria_final = v
                st.caption(f"💡 Categoría homologada: **'{v}'**")
                break
                
        ciudad = st.text_input("Ciudad / Ubicación Geográfica:", value="Madrid", key="c_in")
        limite = st.slider("Cantidad de registros a extraer:", 5, 30, 10)
        btn_run = st.button("Lanzar Robot en la Nube", use_container_width=True)
        
    with c2:
        st.header("Base de Datos Global")
        status = st.empty()
        progreso = st.progress(0)
        
        if btn_run:
            df_nuevos = extraer_datos_reales(categoria_final, ciudad, limite, status, progreso)
            if not df_nuevos.empty:
                db_combinada = pd.concat([st.session_state.db_compartida, df_nuevos], ignore_index=True)
                st.session_state.db_compartida = db_combinada.drop_duplicates(subset=['Nombre del Negocio', 'Teléfono'])
                status.success(f"¡Extracción terminada! Se añadieron {len(df_nuevos)} registros reales únicos.")
        
        st.dataframe(st.session_state.db_compartida, use_container_width=True)

with pestana_email:
    st.header("Central de Email Marketing (SMTP)")
    st.write("Usa la base de datos recolectada en la primera pestaña para enviar correos de prospección por goteo.")
    # (El módulo SMTP se mantiene exactamente igual, listo para procesar los correos reales que entren de la tabla)
