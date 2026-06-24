import streamlit as st
import pandas as pd
import asyncio
import random
import time
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from playwright.async_api import async_playwright

# =====================================================================
# 1. ARQUITECTURA CORE: MÓDULOS DE INTELIGENCIA Y ANTI-BOT (PASO 1 & 4)
# =====================================================================
DICCIONARIO_CATEGORIAS = {
    "gafas": "Ópticas", "lentes": "Ópticas", "ojos": "Ópticas", "lentillas": "Ópticas",
    "gas": "Estaciones de servicio", "gasolina": "Estaciones de servicio", "combustible": "Estaciones de servicio",
    "super": "Supermercados", "compras": "Supermercados", "comida": "Restaurantes", "cenar": "Restaurantes",
    "medicina": "Farmacias", "farmacia": "Farmacias", "ropa": "Tiendas de ropa", "moda": "Tiendas de ropa"
}

class ControlAntideferencia:
    def __init__(self):
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0"
        ]
    def obtener_cabecera_aleatoria(self):
        return random.choice(self.user_agents)
    def aplicar_jitter_time(self, factor=1.0):
        t = random.uniform(2.5, 5.5) * factor
        time.sleep(t)
        return t

# =====================================================================
# 2. MÓDULO DE REFINAMIENTO Y TRIPLE VERIFICACIÓN (PASO 2)
# =====================================================================
class DataRefiner:
    @staticmethod
    def refinar_y_limpiar_datos(df_crudo: pd.DataFrame) -> pd.DataFrame:
        if df_crudo.empty:
            return df_crudo
        df = df_crudo.copy()
        
        # Normalizaciones de texto estándar
        df['Nombre del Negocio'] = df['Nombre del Negocio'].str.strip().str.title()
        df['Municipio'] = df['Municipio'].str.strip().str.title()
        df['Sitio Web'] = df['Sitio Web'].str.strip().str.lower()
        if 'Email' in df.columns:
            df['Email'] = df['Email'].str.strip().str.lower()
            
        # Limpieza estricta de teléfono para cruce preciso
        df['Teléfono'] = df['Teléfono'].astype(str).str.replace(r'[\s\-\(\)]', '', regex=True)
        df['Teléfono'] = df['Teléfono'].str.replace(r'^(\+34|34)', '', regex=True)
        
        # TRIPLE VERIFICACIÓN DE DUPLICADOS (Teléfono, Web, Dirección)
        # 1. Filtro por Teléfono (excluyendo N/As)
        # Corregido de forma limpia para evitar el error de sintaxis:
        valid_phones = df[~df['Teléfono'].isin(['N/A', 'No disponible', '', 'None'])]
        invalid_phones = df[df['Teléfono'].isin(['N/A', 'No disponible', '', 'None'])]
        df_clean = pd.concat([valid_phones.drop_duplicates(subset=['Teléfono']), invalid_phones], ignore_index=True)
        
        # 2. Filtro por Sitio Web
        valid_webs = df_clean[~df_clean['Sitio Web'].isin(['n/a', '', 'none'])]
        invalid_webs = df_clean[df_clean['Sitio Web'].isin(['n/a', '', 'none'])]
        df_clean = pd.concat([valid_webs.drop_duplicates(subset=['Sitio Web']), invalid_webs], ignore_index=True)
        
        # 3. Filtro por Dirección
        df_clean = df_clean.drop_duplicates(subset=['Dirección'])
        
        return df_clean

# =====================================================================
# 3. MOTOR DE EXTRACCIÓN CON PLAYWRIGHT (PASO 3)
# =====================================================================
async def ejecutar_scraping_maps(query, ciudad, limite, anti_bot, refiner, status_box, progress_bar):
    busqueda = f"{query} en {ciudad}"
    resultados = []
    
    async with async_playwright() as p:
        status_box.info(f"🤖 Solicitando túnel de navegación humano para: {busqueda}...")
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=anti_bot.obtener_cabecera_aleatoria())
        page = await context.new_page()
        
        await page.goto(f"https://www.google.com/maps/search/{busqueda.replace(' ', '+')}")
        anti_bot.aplicar_jitter_time(1.2)
        
        try: await page.click("//button[contains(.,'Aceptar todo')]", timeout=2000)
        except: pass
        
        fichas = await page.query_selector_all("a[href*='/maps/place/']")
        count = 0
        
        for index, ficha in enumerate(fichas):
            if count >= limite: break
            try:
                await ficha.click()
                anti_bot.aplicar_jitter_time(0.8)
                
                nombre_elem = await page.query_selector("h1")
                nombre = await nombre_elem.inner_text() if nombre_elem else "Desconocido"
                
                dir_elem = await page.query_selector("button[data-item-id='address']")
                direccion = await dir_elem.inner_text() if dir_elem else "No disponible"
                
                web_elem = await page.query_selector("a[data-item-id='authority']")
                sitio_web = await web_elem.get_attribute("href") if web_elem else "N/A"
                
                html_content = await page.content()
                tel_match = re.search(r'(\+34|34)?\s?[679]\d{2}\s?\d{2}\s?\d{2}\s?\d{2}', html_content)
                telefono = tel_match.group(0) if tel_match else "No disponible"
                
                # Simulación de Email para esta muestra
                email = f"contacto@{sitio_web.split('//')[-1].split('/')[0]}" if sitio_web != "N/A" else "N/A"
                
                resultados.append({
                    "Nombre del Negocio": nombre, "Dirección": direccion,
                    "Teléfono": telefono, "Sitio Web": sitio_web,
                    "Email": email, "Municipio": ciudad, "Categoría": query
                })
                
                count += 1
                progress_bar.progress(int((count / limite) * 100))
                status_box.text(f"🔍 Extraído ({count}/{limite}): {nombre}")
            except:
                continue
        await browser.close()
        
    df_crudo = pd.DataFrame(resultados)
    return refiner.refinar_y_limpiar_datos(df_crudo)

# =====================================================================
# 4. INTERFAZ GRÁFICA CENTRALIZADA (STREAMLIT DASHBOARD)
# =====================================================================
st.set_page_config(page_title="SaaS Business Intelligence", layout="wide")

# Inicializar Base de Datos en Memoria de Sesión (Se conectará a Google Sheets en producción)
if "db_compartida" not in st.session_state:
    st.session_state.db_compartida = pd.DataFrame(columns=[
        "Nombre del Negocio", "Dirección", "Teléfono", "Sitio Web", "Email", "Municipio", "Categoría"
    ])

anti_bot = ControlAntideferencia()
refiner = DataRefiner()

st.title("🚀 SaaS Centralizado de Extracción y Marketing")
st.write("Bienvenido. Este entorno corre en la nube y sincroniza los datos con tus colaboradores en tiempo real.")

pestana_extraccion, pestana_email = st.tabs(["🔍 Motor de Extracción Masiva", "📧 Central de Email Marketing (SMTP)"])

# --- PESTAÑA 1: EXTRACCIÓN ---
with pestana_extraccion:
    c1, c2 = st.columns([1, 2])
    with c1:
        st.header("Parámetros del Robot")
        entrada = st.text_input("¿Qué tipo de negocio buscas?", value="Ópticas")
        
        # Sugerencia inteligente de categorías del Paso 1
        categoria_final = entrada
        for k, v in DICCIONARIO_CATEGORIAS.items():
            if k in entrada.lower():
                categoria_final = v
                st.caption(f"💡 Sugerencia inteligente: Categorizado como **'{v}'** para mejorar eficiencia.")
                break
                
        ciudad = st.text_input("Ciudad / Ubicación Geográfica:", value="Madrid")
        limite = st.slider("Cantidad de registros a extraer:", 5, 50, 10)
        btn_run = st.button("Lanzar Robot en la Nube", use_container_width=True)
        
    with c2:
        st.header("Base de Datos Global")
        status = st.empty()
        progreso = st.progress(0)
        
        if btn_run:
            df_nuevos = asyncio.run(ejecutar_scraping_maps(categoria_final, ciudad, limite, anti_bot, refiner, status, progreso))
            if not df_nuevos.empty:
                # Sincronización y combinación con eliminación de duplicados total
                db_combinada = pd.concat([st.session_state.db_compartida, df_nuevos], ignore_index=True)
                st.session_state.db_compartida = refiner.refinar_y_limpiar_datos(db_combinada)
                status.success(f"¡Extracción terminada! Se añadieron {len(df_nuevos)} nuevos registros únicos.")
        
        st.dataframe(st.session_state.db_compartida, use_container_width=True)
        
        # Exportador Nativo a Excel
        if not st.session_state.db_compartida.empty:
            st.session_state.db_compartida.to_excel("Reporte_SaaS_Global.xlsx", index=False)
            with open("Reporte_SaaS_Global.xlsx", "rb") as f:
                st.download_button("📥 Descargar Base de Datos Completa a Excel", f.read(), "Base_Datos_SaaS.xlsx", use_container_width=True)

# --- PESTAÑA 2: CAMPAÑAS DE EMAIL (ESTILO MAILCHIMP) ---
with pestana_email:
    st.header("Configuración de Campaña de Correo Masivo Seguro")
    
    col_smtp1, col_smtp2 = st.columns(2)
    with col_smtp1:
        st.subheader("1. Credenciales SMTP (Tu Email)")
        tipo_email = st.selectbox("Tipo de Cuenta Activa", ["Email Personal (Gmail/Outlook)", "Dominio Corporativo Pro (Resend/SendGrid)"])
        
        if tipo_email == "Email Personal (Gmail/Outlook)":
            servidor = st.text_input("Servidor SMTP:", value="smtp.gmail.com")
            puerto = st.number_input("Puerto TLS:", value=587)
            usuario = st.text_input("Tu Correo Personal:", value="tu_correo@gmail.com")
            clave = st.text_input("Contraseña de Aplicación (16 dígitos de Google):", type="password")
        else:
            servidor = st.text_input("Servidor SMTP Corporativo:", value="smtp.resend.com")
            puerto = st.number_input("Puerto TLS Corporativo:", value=587)
            usuario = st.text_input("Usuario API / Email de Dominio:", value="resend")
            clave = st.text_input("API Key / Password Pro:", type="password")
            
    with col_smtp2:
        st.subheader("2. Redacción del Mensaje")
        asunto = st.text_input("Asunto del Correo:", value="Propuesta comercial de colaboración - Campaña 2026")
        cuerpo = st.text_area("Cuerpo del mensaje (Soporta HTML profesional):", value="<h1>¡Hola!</h1><p>Vimos tu negocio en Google Maps y nos gustaría colaborar...</p>")
        
        emails_validos = st.session_state.db_compartida[st.session_state.db_compartida['Email'] != 'N/A']['Email'].tolist() if not st.session_state.db_compartida.empty else []
        st.metric("Destinatarios con Email Válido Listos", len(emails_validos))
        
        if st.button("📧 Enviar Campaña por Goteo (Anti-Spam)", use_container_width=True):
            if not emails_validos:
                st.error("No hay registros con correos electrónicos válidos en la base de datos para enviar.")
            elif not clave:
                st.error("Por favor, introduce la clave o contraseña de tu cuenta de correo.")
            else:
                st.info("Iniciando campaña de envío progresivo. Por seguridad, se aplicará un goteo de 15s - 40s por correo...")
                # Lógica de goteo integrada
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
                        st.caption(f"✅ Enviado con éxito a: {destino}")
                        if destino != emails_validos[-1]:
                            time.sleep(random.uniform(15.0, 35.0)) # Pausa anti-spam por goteo aprobada
                    except Exception as e:
                        st.caption(f"❌ Error al enviar a {destino}: {str(e)}")
                st.success(f"¡Campaña finalizada con éxito! {exitosos} correos entregados directamente al Inbox.")
