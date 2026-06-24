import streamlit as st
import pandas as pd
import random
import time
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

st.set_page_config(page_title="SaaS Business Intelligence", layout="wide")

# Inicializar base de datos compartida
if "db_compartida" not in st.session_state:
    st.session_state.db_compartida = pd.DataFrame(columns=[
        "Nombre del Negocio", "Dirección", "Teléfono", "Sitio Web", "Email", "Municipio", "Categoría"
    ])

# =====================================================================
# MOTOR GEOGRÁFICO DE DATOS REALES ABIERTOS (OVERPASS API)
# =====================================================================
def extraer_datos_reales_infraestructura(categoria, ciudad, limite, status_box, progress_bar):
    status_box.info(f"🛰️ Consultando red satelital pública para {categoria} en {ciudad}...")
    progress_bar.progress(20)
    
    # Mapeo de categorías comerciales a etiquetas globales de OpenStreetMap
    tags_mapeo = {
        "ópticas": "optician",
        "óptica": "optician",
        "farmacias": "pharmacy",
        "farmacia": "pharmacy",
        "restaurantes": "restaurant",
        "restaurante": "restaurant",
        "supermercados": "supermarket",
        "supermercado": "supermarket",
        "estaciones de servicio": "fuel",
        "gasolinera": "fuel"
    }
    
    tag_busqueda = tags_mapeo.get(categoria.lower(), "shop")
    
    # Query optimizada para el servidor Overpass (Busca comercios reales en la ciudad indicada)
    query_overpass = f"""
    [out:json][timeout:25];
    area["name"="{ciudad.title()}"]->.searchArea;
    (
      node["shop"="{tag_busqueda}"](area.searchArea);
      way["shop"="{tag_busqueda}"](area.searchArea);
      node["amenity"="{tag_busqueda}"](area.searchArea);
      way["amenity"="{tag_busqueda}"](area.searchArea);
    );
    out tags;
    """
    
    url = "https://overpass-api.de/api/interpreter"
    resultados = []
    
    try:
        response = requests.post(url, data={"data": query_overpass}, timeout=20)
        progress_bar.progress(70)
        
        if response.status_code == 200:
            datos = response.json()
            elementos = datos.get("elements", [])
            
            count = 0
            for el in elementos:
                if count >= limite:
                    break
                    
                tags = el.get("tags", {})
                nombre = tags.get("name", f"{categoria.title()} Local")
                
                # Obtener dirección estructurada real
                calle = tags.get("addr:street", "")
                numero = tags.get("addr:housenumber", "")
                direccion = f"{calle} {numero}".strip() if calle else "Dirección registrada en mapa central"
                
                # Obtener datos de contacto reales cargados por los comercios
                telefono = tags.get("phone", tags.get("contact:phone", "No disponible"))
                sitio_web = tags.get("website", tags.get("contact:website", "N/A"))
                
                # Email predictivo/registrado
                email_reg = tags.get("email", tags.get("contact:email", "N/A"))
                if email_reg == "N/A" and sitio_web != "N/A":
                    dominio = sitio_web.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
                    email_reg = f"contacto@{dominio}"
                
                resultados.append({
                    "Nombre del Negocio": nombre.title(),
                    "Dirección": direccion,
                    "Teléfono": telefono,
                    "Sitio Web": sitio_web,
                    "Email": email_reg,
                    "Municipio": ciudad.title(),
                    "Categoría": categoria.title()
                })
                count += 1
            
            if not resultados:
                status_box.warning(f"No encontramos registros con la etiqueta específica '{tag_busqueda}' en {ciudad}. Intenta escribiendo otra categoría como: Farmacias, Ópticas o Restaurantes.")
            else:
                status_box.success(f"¡Éxito! Se han localizado {len(resultados)} comercios registrados reales.")
                
        else:
            status_box.error(f"El servidor central de mapas está saturado (Código {response.status_code}). Reintenta en unos segundos.")
            
    except Exception as e:
        status_box.error(f"Error de red en la nube: {str(e)}")
        
    progress_bar.progress(100)
    return pd.DataFrame(resultados)

# =====================================================================
# INTERFAZ GRÁFICA TRABAJADA
# =====================================================================
st.title("🚀 SaaS Centralizado de Extracción y Marketing")
st.write("Conexión directa con bases de datos comerciales abiertas (Sin bloqueos de IP ni Captchas).")

pestana_extraccion, pestana_email = st.tabs(["🔍 Motor de Extracción Masiva", "📧 Central de Email Marketing (SMTP)"])

with pestana_extraccion:
    c1, c2 = st.columns([1, 2])
    with c1:
        st.header("Parámetros del Robot")
        entrada = st.text_input("¿Qué buscas? (Ej: Ópticas, Farmacias, Restaurantes):", value="Ópticas", key="q_in")
        ciudad = st.text_input("Ciudad / Ubicación Geográfica:", value="Madrid", key="c_in")
        limite = st.slider("Cantidad de registros:", 5, 50, 15)
        btn_run = st.button("Lanzar Robot en la Nube", use_container_width=True)
        
    with c2:
        st.header("Base de Datos Global")
        status = st.empty()
        progreso = st.progress(0)
        
        if btn_run:
            df_nuevos = extraer_datos_reales_infraestructura(entrada, ciudad, limite, status, progreso)
            if not df_nuevos.empty:
                db_combinada = pd.concat([st.session_state.db_compartida, df_nuevos], ignore_index=True)
                st.session_state.db_compartida = db_combinada.drop_duplicates(subset=['Nombre del Negocio', 'Teléfono'])
        
        st.dataframe(st.session_state.db_compartida, use_container_width=True)

with pestana_email:
    st.header("Central de Email Marketing (SMTP)")
    col_smtp1, col_smtp2 = st.columns(2)
    with col_smtp1:
        st.subheader("1. Credenciales SMTP")
        servidor = st.text_input("Servidor SMTP:", value="smtp.gmail.com")
        puerto = st.number_input("Puerto TLS:", value=587)
        usuario = st.text_input("Tu Correo:", value="tu_correo@gmail.com")
        clave = st.text_input("Contraseña de Aplicación:", type="password")
            
    with col_smtp2:
        st.subheader("2. Redacción")
        asunto = st.text_input("Asunto:", value="Propuesta comercial")
        cuerpo = st.text_area("Cuerpo (HTML):", value="<h1>¡Hola!</h1><p>Vimos tu negocio...</p>")
        
        emails_validos = [e for e in st.session_state.db_compartida['Email'].tolist() if e != 'N/A' and '@' in str(e)] if not st.session_state.db_compartida.empty else []
        st.metric("Destinatarios Listos", len(emails_validos))
        
        if st.button("📧 Enviar Campaña por Goteo", use_container_width=True):
            if not emails_validos:
                st.error("No hay correos válidos en la tabla.")
            elif not clave:
                st.error("Introduce tu contraseña de aplicación.")
            else:
                st.info("Iniciando envíos...")
                exitosos = 0
                for destino in emails_validos:
                    try:
                        msg = MIMEMultipart()
                        msg['From'], msg['To'], msg['Subject'] = usuario, destino, asunto
                        msg.attach(MIMEText(cuerpo, 'html'))
                        with smtplib.SMTP(servidor, puerto) as server:
                            server.starttls()
                            server.login(usuario, clave)
                            server.sendmail(usuario, destino, msg.as_string())
                        exitosos += 1
                        st.caption(f"✅ Enviado: {destino}")
                        time.sleep(2)
                    except Exception as e:
                        st.caption(f"❌ Error en {destino}: {str(e)}")
                st.success(f"¡Campaña finalizada! {exitosos} correos enviados.")
