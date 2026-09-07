import streamlit as st
#import gspread
#from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
# Importamos timezone y timedelta para ajustar la hora a Bolivia (UTC-4)
from datetime import datetime, timezone, timedelta 
import io
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.utils import get_column_letter
import plotly.express as px
import time
import hashlib
import requests
import base64
import streamlit as st
import os
import urllib.parse
import streamlit as st
import pandas as pd
from supabase import create_client, Client

# ---------------------------------------------------------
# 1. CONEXIÓN A SUPABASE (Se ejecuta una sola vez gracias a la caché)
# ---------------------------------------------------------
@st.cache_resource
def conectar_supabase() -> Client:
    # Intenta leer de st.secrets (Local); si no existe, lee de os.getenv (Render/Nube)
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
    except Exception:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        
    return create_client(url, key)

# ---------------------------------------------------------
# 2. FUNCIÓN PARA LEER TABLAS CON CACHÉ DE RÁPIDO ACCESO
# ---------------------------------------------------------
@st.cache_data(ttl=300)
def obtener_datos_tabla(nombre_tabla: str):
    try:
        cliente = conectar_supabase()
        response = cliente.table(nombre_tabla).select("*").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        print(f"Error al leer {nombre_tabla} desde Supabase: {e}")
        return pd.DataFrame()  # Devuelve una tabla vacía en lugar de None

# 1. Configuración de página
st.set_page_config(
    page_title="Copias y etc. - Iniciar Sesión",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="collapsed" # Oculta el sidebar en la pantalla de login
)

# 2. Convertir imágenes a base64 para el CSS
def get_base64(path):
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return ""

bg_base64 = get_base64("fondo.jpg")


# --- AJUSTE DE ZONA HORARIA (BOLIVIA UTC-4) ---
def obtener_hora_local_bo():
    """Retorna la fecha y hora actual con la zona horaria de Bolivia (UTC-4)."""
    tz_bo = timezone(timedelta(hours=-4))
    return datetime.now(tz_bo)

# --- FUNCIÓN DE NOTIFICACIONES TELEGRAM (TEXTOS LIMPIOS) ---
def enviar_notificacion_telegram(empresa, agencia, area, problema, tecnico):
    TOKEN_BOT = "8920856005:AAEgKI6dfghTS2sNLMrDeG8ENPoaO5oISWc"
    CHAT_ID = "-5394039789"
    
    # Limpiamos los textos para que no repitan la Empresa ni la Agencia
    agencia_limpia = agencia.split(" - ")[-1] if " - " in agencia else agencia
    area_limpia = area.split(" - ")[-1] if " - " in area else area
    
    mensaje = f"""
🚨 *NUEVO SERVICIO TÉCNICO PENDIENTE* 🚨

🏢 *Empresa:* {empresa}
📍 *Agencia:* {agencia_limpia}
🏢 *Área:* {area_limpia}
👤 *Registrado por:* {tecnico}

🛠️ *Problema o Falla:*
{problema}

📌 _Por favor ingresar al sistema para atender la solicitud._
    """
    
    url = f"https://api.telegram.org/bot{TOKEN_BOT}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": mensaje,
        "parse_mode": "Markdown"
    }
    
    try:
        requests.post(url, data=payload, timeout=5)
    except Exception as e:
        print(f"Error al enviar notificación a Telegram: {e}")

# Inicializar tablas de Supabase guardándolas en st.session_state
def inicializar_pestanas_seguras():
    if "pestanas" not in st.session_state:
        tablas = [
            "Insumos", "Historial", "Usuarios", "Parametros", 
            "Ventas", "Alquileres", "Backup", "Servicios"
        ]
        st.session_state["pestanas"] = {}
        for tabla in tablas:
            try:
                st.session_state["pestanas"][tabla] = obtener_datos_tabla(tabla)
            except Exception as e:
                print(f"Error al cargar la tabla {tabla} desde Supabase: {e}")
                st.session_state["pestanas"][tabla] = None
                
    return st.session_state["pestanas"]

# Inicializamos las hojas de trabajo de forma segura usando la sesión
pestanas_activas = inicializar_pestanas_seguras()
hoja_insumos = pestanas_activas["Insumos"]
hoja_historial = pestanas_activas["Historial"]
hoja_usuarios = pestanas_activas["Usuarios"]
hoja_parametros = pestanas_activas["Parametros"]
hoja_ventas = pestanas_activas["Ventas"]
hoja_alquileres = pestanas_activas["Alquileres"]
hoja_respaldo = pestanas_activas["Backup"]
hoja_servicios = pestanas_activas["Servicios"]

# --- FUNCIONES DE GESTIÓN DE USUARIOS ---
def encriptar_password(password_plano):
    """Convierte una contraseña en texto plano a un hash SHA-256 encriptado."""
    return hashlib.sha256(str(password_plano).encode()).hexdigest()
@st.cache_data(ttl=60)
def obtener_usuarios():
    try:
        supabase = conectar_supabase()
        response = supabase.table("Usuarios").select("*").execute()
        df = pd.DataFrame(response.data)
        return df
    except Exception as e:
        st.error(f"Error de conexión con Supabase: {e}")
        return pd.DataFrame()

def registrar_usuario(usuario, contrasena, rol):
    pass_encriptado = encriptar_password(contrasena)
    supabase = conectar_supabase()
    supabase.table("Usuarios").insert({
        "Usuario": usuario, 
        "Contraseña": pass_encriptado, 
        "Rol": rol
    }).execute()

def editar_usuario(usuario_viejo, nuevo_usuario, nueva_contrasena, nuevo_rol):
    """Edita un registro de usuario existente en Supabase."""
    pass_encriptado = encriptar_password(nueva_contrasena)
    supabase = conectar_supabase()
    supabase.table("Usuarios").update({
        "Usuario": nuevo_usuario,
        "Contraseña": pass_encriptado,
        "Rol": nuevo_rol
    }).eq("Usuario", usuario_viejo).execute()

def eliminar_usuario(usuario_a_eliminar):
    """Elimina un usuario de Supabase."""
    supabase = conectar_supabase()
    supabase.table("Usuarios").delete().eq("Usuario", usuario_a_eliminar).execute()

# --- FUNCIONES DE PARÁMETROS (EMPRESAS, ÁREAS Y AGENCIAS) ---
@st.cache_data(ttl=60)
def obtener_parametros():
    try:
        df_parametros = st.session_state["pestanas"].get("Parametros", pd.DataFrame())
        if df_parametros.empty:
            return ["Sin Registrar"], ["Sin Registrar"], ["Sin Registrar"]

        df = df_parametros

        lista_empresas = df["Empresa"].dropna().astype(str).str.strip().tolist() if "Empresa" in df.columns else []
        lista_areas = df["Area"].dropna().astype(str).str.strip().tolist() if "Area" in df.columns else []
        lista_agencias = df["Agencia"].dropna().astype(str).str.strip().tolist() if "Agencia" in df.columns else []
        
        lista_empresas = [x for x in lista_empresas if x != ""]
        lista_areas = [x for x in lista_areas if x != ""]
        lista_agencias = [x for x in lista_agencias if x != ""]
    except Exception as e:
        lista_empresas = ["Sin Registrar"]
        lista_areas = ["Sin Registrar"]
        lista_agencias = ["Sin Registrar"]
        
    return lista_empresas, lista_areas, lista_agencias

def registrar_parametro(nuevo_valor, tipo):
    """Registra un nuevo parámetro en la tabla Parametros de Supabase."""
    try:
        supabase = conectar_supabase()
        supabase.table("Parametros").insert({tipo: nuevo_valor}).execute()
    except Exception as e:
        st.error(f"Error al registrar parámetro: {e}")

def eliminar_parametro(valor_a_eliminar, tipo):
    """Elimina un parámetro de la tabla Parametros en Supabase."""
    try:
        supabase = conectar_supabase()
        supabase.table("Parametros").delete().eq(tipo, valor_a_eliminar).execute()
    except Exception as e:
        st.error(f"Error al eliminar parámetro: {e}")

# --- CONTROL DE ACCESO (LOGIN) ---
def check_password():
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False
        st.session_state["usuario_actual"] = ""
        st.session_state["rol_actual"] = ""

    if st.session_state["logged_in"]:
        return True

    # Estilos para la tarjeta centrada y elegante + nitidez del logo
    st.markdown("""
    <style>
        #MainMenu, footer, header {visibility: hidden;}

        div[data-testid="stForm"] {
            max-width: 420px !important;
            margin: 20px auto !important;
            background-color: rgba(255, 255, 255, 0.95) !important;
            border-radius: 18px !important;
            padding: 25px 30px 30px 30px !important;
            border: 2px solid #e60000 !important;
            box-shadow: 0px 0px 25px rgba(230, 0, 0, 0.4) !important;
        }

        .login-title {
            text-align: center;
            color: #1f2937;
            font-size: 18px;
            font-weight: 700;
            margin-top: 10px;
            margin-bottom: 20px;
        }

        /* Fuerza la nitidez del logo */
        [data-testid="stImage"] > img {
            width: 150px;
            image-rendering: -webkit-optimize-contrast;
            image-rendering: crispedges;
        }
    </style>
    """, unsafe_allow_html=True)

    col_izq, col_central, col_der = st.columns([1, 2, 1])

    with col_central:
        with st.form("form_login"):
            # Logo centrado en alta definición
            l_col1, l_col2, l_col3 = st.columns([1, 2, 1])
            with l_col2:
                if os.path.exists("logo.png"):
                    st.image("logo.png", use_container_width=True)

            st.markdown("<div class='login-title'>🔑 Acceso al Sistema de Inventario</div>", unsafe_allow_html=True)

            # Campos de texto y botón
            usuario_input = st.text_input("Usuario:", placeholder="Ingresa tu usuario")
            password_input = st.text_input("Contraseña:", type="password", placeholder="••••••••")

            if st.form_submit_button("INGRESAR", use_container_width=True):
                df_users = obtener_usuarios()
                if df_users is not None and not df_users.empty:
                    df_users["Usuario"] = df_users["Usuario"].astype(str).str.strip().str.lower()
                    df_users["Contraseña"] = df_users["Contraseña"].astype(str).str.strip()
                    
                    u_ingresado = usuario_input.strip().lower()
                    p_ingresado = password_input.strip()
                    
                    user_match = df_users[(df_users["Usuario"] == u_ingresado) & (df_users["Contraseña"] == p_ingresado)]
                    if not user_match.empty:
                        st.session_state["logged_in"] = True
                        st.session_state["usuario_actual"] = user_match.iloc[0]["Usuario"]
                        st.session_state["rol_actual"] = user_match.iloc[0]["Rol"]
                        st.rerun()
                    else:
                        st.error("❌ Usuario o contraseña incorrectos")
                else:
                    st.error("⚠️ No se pudo consultar la base de datos de usuarios")

    return False

if not check_password():
    st.stop()

# --- MENÚ LATERAL ---
st.sidebar.write(f"👤 **Usuario:** {st.session_state['usuario_actual']}")
st.sidebar.write(f"⚙️ **Rol:** {st.session_state['rol_actual']}")

if st.sidebar.button("Cerrar Sesión"):
    st.session_state["logged_in"] = False
    st.session_state["usuario_actual"] = ""
    st.session_state["rol_actual"] = ""
    st.cache_data.clear()
    if "pestanas" in st.session_state:
        del st.session_state["pestanas"]
    st.rerun()


# --- FUNCIONES DE GESTIÓN DE EQUIPOS Y CONTADORES ---
@st.cache_data(ttl=60)
def obtener_equipos():
    try:
        supabase = conectar_supabase()
        response = supabase.table("Equipos").select("*").order("id", desc=False).execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.warning(f"Aviso al leer Equipos: {e}")
        return pd.DataFrame()


def _valor_opcional(valor):
    if valor is None:
        return None
    valor = str(valor).strip()
    return valor if valor else None


def registrar_equipo(empresa, agencia, area, marca, modelo, numero_serie, tipo,
                     ip, modalidad, estado, contador_actual, fecha_instalacion,
                     observaciones):
    try:
        supabase = conectar_supabase()
        registro = {
            "Empresa": _valor_opcional(empresa),
            "Agencia": _valor_opcional(agencia),
            "Area": _valor_opcional(area),
            "Marca": _valor_opcional(marca),
            "Modelo": _valor_opcional(modelo),
            "Numero Serie": _valor_opcional(numero_serie),
            "Tipo": _valor_opcional(tipo),
            "IP": _valor_opcional(ip),
            "Modalidad": _valor_opcional(modalidad),
            "Estado": _valor_opcional(estado),
            "Contador Actual": int(contador_actual or 0),
            "Fecha Instalacion": fecha_instalacion.isoformat() if fecha_instalacion else None,
            "Observaciones": _valor_opcional(observaciones),
        }
        supabase.table("Equipos").insert(registro).execute()
        st.cache_data.clear()
        return True, None
    except Exception as e:
        return False, str(e)



def generar_plantilla_equipos_excel(empresas, agencias, areas, df_equipos):
    """Genera una plantilla Excel para carga masiva con listas desplegables."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Equipos"
    listas = wb.create_sheet("Listas")

    columnas = [
        "Empresa", "Agencia", "Área", "Marca", "Modelo", "Número de serie",
        "Tipo", "IP", "Modalidad", "Estado", "Contador actual",
        "Fecha de instalación", "Observaciones"
    ]
    ws.append(columnas)

    # Valores para listas: parámetros actuales + valores existentes en Equipos.
    def unicos(valores):
        resultado = []
        vistos = set()
        for valor in valores:
            if valor is None:
                continue
            texto = str(valor).strip()
            if texto and texto not in vistos:
                vistos.add(texto)
                resultado.append(texto)
        return resultado

    marcas_actuales = df_equipos["Marca"].tolist() if "Marca" in df_equipos.columns else []
    modelos_actuales = df_equipos["Modelo"].tolist() if "Modelo" in df_equipos.columns else []
    tipos_actuales = df_equipos["Tipo"].tolist() if "Tipo" in df_equipos.columns else []

    marcas = unicos(marcas_actuales + ["Canon", "Ricoh", "Kyocera", "Konica Minolta", "Xerox", "HP", "Epson", "Brother", "Sharp", "Lexmark"])
    modelos = unicos(modelos_actuales)
    tipos = unicos(tipos_actuales + ["FOTOCOPIADORA", "MULTIFUNCIONAL", "IMPRESORA", "PLOTTER", "ESCANER", "OTRO"])
    modalidades = ["Alquiler", "Venta", "Propio", "Otro"]
    estados = ["Activo", "Mantenimiento", "Baja", "Retirado"]

    listas_data = {
        "Empresas": unicos(empresas),
        "Agencias": unicos(agencias),
        "Areas": unicos(areas),
        "Marcas": marcas,
        "Modelos": modelos,
        "Tipos": tipos,
        "Modalidades": modalidades,
        "Estados": estados,
    }

    for col_idx, (titulo, valores) in enumerate(listas_data.items(), start=1):
        listas.cell(row=1, column=col_idx, value=titulo)
        for row_idx, valor in enumerate(valores, start=2):
            listas.cell(row=row_idx, column=col_idx, value=valor)

    # Estilo de la hoja principal.
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = "A1:M501"
    ws.row_dimensions[1].height = 24

    anchos = [24, 28, 24, 20, 24, 24, 22, 18, 16, 18, 18, 22, 35]
    for i, ancho in enumerate(anchos, start=1):
        ws.column_dimensions[get_column_letter(i)].width = ancho

    # Crea 500 filas preparadas para carga.
    for fila in range(2, 502):
        ws.cell(fila, 11).value = 0
        ws.cell(fila, 12).number_format = "yyyy-mm-dd"

    # Listas desplegables basadas en la hoja oculta "Listas".
    for col_idx, valores in enumerate(listas_data.values(), start=1):
        if not valores:
            continue
        letra = get_column_letter(col_idx)
        max_fila = len(valores) + 1
        dv = DataValidation(type="list", formula1=f"=Listas!${letra}$2:${letra}${max_fila}", allow_blank=True)
        dv.error = "Selecciona un valor de la lista o deja la celda vacía."
        dv.errorTitle = "Valor no válido"
        ws.add_data_validation(dv)
        dv.add(f"{letra}2:{letra}501")

    # Validación numérica para contador.
    dv_cont = DataValidation(type="whole", operator="greaterThanOrEqual", formula1="0", allow_blank=True)
    dv_cont.error = "El contador debe ser un número entero igual o mayor a 0."
    dv_cont.errorTitle = "Contador no válido"
    ws.add_data_validation(dv_cont)
    dv_cont.add("K2:K501")

    # Hoja de instrucciones.
    listas.sheet_state = "hidden"
    info = wb.create_sheet("Instrucciones", 0)
    info["A1"] = "CARGA MASIVA DE EQUIPOS"
    info["A1"].font = Font(bold=True, size=16)
    instrucciones = [
        "1. Completa la hoja 'Equipos'. Una fila corresponde a una máquina.",
        "2. Usa las listas desplegables para Empresa, Agencia, Área, Marca, Modelo, Tipo, Modalidad y Estado.",
        "3. Número de serie identifica la máquina y debe evitar duplicados.",
        "4. IP y Observaciones pueden quedar vacíos si no corresponde.",
        "5. Si Contador actual queda vacío, la aplicación lo tomará como 0.",
        "6. Si Fecha de instalación queda vacía, la aplicación usará la fecha actual.",
        "7. Guarda el archivo como .xlsx y súbelo en la pestaña 'Importar desde Excel'.",
    ]
    for i, texto in enumerate(instrucciones, start=3):
        info.cell(i, 1, texto)
    info.column_dimensions["A"].width = 115
    return wb


def bytes_plantilla_equipos(empresas, agencias, areas, df_equipos):
    wb = generar_plantilla_equipos_excel(empresas, agencias, areas, df_equipos)
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


def validar_dataframe_equipos(df_importado, df_equipos_existentes):
    """Valida el Excel y devuelve filas válidas y un reporte de errores."""
    columnas_excel = [
        "Empresa", "Agencia", "Área", "Marca", "Modelo", "Número de serie",
        "Tipo", "IP", "Modalidad", "Estado", "Contador actual",
        "Fecha de instalación", "Observaciones"
    ]
    faltantes = [c for c in columnas_excel if c not in df_importado.columns]
    if faltantes:
        return pd.DataFrame(), pd.DataFrame(), [f"Faltan columnas: {', '.join(faltantes)}"]

    df = df_importado[columnas_excel].copy()
    df = df.dropna(how="all")
    errores = []
    series_existentes = set()
    if not df_equipos_existentes.empty and "Numero Serie" in df_equipos_existentes.columns:
        series_existentes = {
            str(x).strip().lower() for x in df_equipos_existentes["Numero Serie"].dropna()
            if str(x).strip()
        }
    series_archivo = set()
    filas_validas = []
    filas_error = []

    for indice, fila in df.iterrows():
        numero_fila = int(indice) + 2
        registro = fila.to_dict()
        fila_errores = []

        for campo in ["Empresa", "Agencia", "Área", "Marca", "Modelo", "Número de serie", "Tipo"]:
            if pd.isna(registro[campo]) or not str(registro[campo]).strip():
                fila_errores.append(f"{campo} vacío")

        serie = "" if pd.isna(registro["Número de serie"]) else str(registro["Número de serie"]).strip()
        serie_key = serie.lower()
        if serie_key:
            if serie_key in series_existentes:
                fila_errores.append("Número de serie ya existe en Equipos")
            if serie_key in series_archivo:
                fila_errores.append("Número de serie duplicado dentro del Excel")
            series_archivo.add(serie_key)

        modalidad = "Alquiler" if pd.isna(registro["Modalidad"]) or not str(registro["Modalidad"]).strip() else str(registro["Modalidad"]).strip()
        estado = "Activo" if pd.isna(registro["Estado"]) or not str(registro["Estado"]).strip() else str(registro["Estado"]).strip()
        if modalidad not in ["Alquiler", "Venta", "Propio", "Otro"]:
            fila_errores.append(f"Modalidad no válida: {modalidad}")
        if estado not in ["Activo", "Mantenimiento", "Baja", "Retirado"]:
            fila_errores.append(f"Estado no válido: {estado}")

        contador = registro["Contador actual"]
        if pd.isna(contador) or str(contador).strip() == "":
            contador = 0
        try:
            contador = int(float(contador))
            if contador < 0:
                raise ValueError
        except Exception:
            fila_errores.append("Contador actual no válido")
            contador = 0

        fecha = registro["Fecha de instalación"]
        if pd.isna(fecha) or str(fecha).strip() == "":
            fecha = datetime.now().date()
        else:
            fecha_convertida = pd.to_datetime(fecha, errors="coerce")
            if pd.isna(fecha_convertida):
                fila_errores.append("Fecha de instalación no válida")
                fecha = datetime.now().date()
            else:
                fecha = fecha_convertida.date()

        if fila_errores:
            registro["Fila"] = numero_fila
            registro["Errores"] = "; ".join(fila_errores)
            filas_error.append(registro)
        else:
            filas_validas.append({
                "Empresa": str(registro["Empresa"]).strip(),
                "Agencia": str(registro["Agencia"]).strip(),
                "Area": str(registro["Área"]).strip(),
                "Marca": str(registro["Marca"]).strip(),
                "Modelo": str(registro["Modelo"]).strip(),
                "Numero Serie": serie,
                "Tipo": str(registro["Tipo"]).strip(),
                "IP": None if pd.isna(registro["IP"]) or not str(registro["IP"]).strip() else str(registro["IP"]).strip(),
                "Modalidad": modalidad,
                "Estado": estado,
                "Contador Actual": contador,
                "Fecha Instalacion": fecha.isoformat(),
                "Observaciones": None if pd.isna(registro["Observaciones"]) or not str(registro["Observaciones"]).strip() else str(registro["Observaciones"]).strip(),
            })

    return pd.DataFrame(filas_validas), pd.DataFrame(filas_error), errores


def importar_equipos_masivo(df_validos):
    try:
        if df_validos.empty:
            return 0, "No hay filas válidas para importar."
        supabase = conectar_supabase()
        registros = df_validos.to_dict(orient="records")
        for inicio in range(0, len(registros), 100):
            supabase.table("Equipos").insert(registros[inicio:inicio + 100]).execute()
        st.cache_data.clear()
        return len(registros), None
    except Exception as e:
        return 0, str(e)


def actualizar_equipo(equipo_id, empresa, agencia, area, marca, modelo, numero_serie,
                      tipo, ip, modalidad, estado, contador_actual,
                      fecha_instalacion, observaciones):
    try:
        supabase = conectar_supabase()
        cambios = {
            "Empresa": _valor_opcional(empresa),
            "Agencia": _valor_opcional(agencia),
            "Area": _valor_opcional(area),
            "Marca": _valor_opcional(marca),
            "Modelo": _valor_opcional(modelo),
            "Numero Serie": _valor_opcional(numero_serie),
            "Tipo": _valor_opcional(tipo),
            "IP": _valor_opcional(ip),
            "Modalidad": _valor_opcional(modalidad),
            "Estado": _valor_opcional(estado),
            "Contador Actual": int(contador_actual or 0),
            "Fecha Instalacion": fecha_instalacion.isoformat() if fecha_instalacion else None,
            "Observaciones": _valor_opcional(observaciones),
        }
        supabase.table("Equipos").update(cambios).eq("id", int(equipo_id)).execute()
        st.cache_data.clear()
        return True, None
    except Exception as e:
        return False, str(e)


def eliminar_equipo(equipo_id):
    try:
        supabase = conectar_supabase()
        supabase.table("Equipos").delete().eq("id", int(equipo_id)).execute()
        st.cache_data.clear()
        return True, None
    except Exception as e:
        return False, str(e)


def obtener_lecturas_equipo(equipo_id):
    try:
        supabase = conectar_supabase()
        response = (
            supabase.table("Lecturas_Contadores")
            .select("*")
            .eq("equipo_id", int(equipo_id))
            .order("Fecha", desc=True)
            .execute()
        )
        return pd.DataFrame(response.data)
    except Exception as e:
        st.warning(f"Aviso al leer contadores: {e}")
        return pd.DataFrame()


def registrar_lectura_equipo(equipo_id, contador, fuente, usuario, observaciones):
    try:
        supabase = conectar_supabase()
        supabase.table("Lecturas_Contadores").insert({
            "equipo_id": int(equipo_id),
            "Fecha": obtener_hora_local_bo().isoformat(),
            "Contador": int(contador),
            "Fuente": _valor_opcional(fuente),
            "Usuario": _valor_opcional(usuario),
            "Observaciones": _valor_opcional(observaciones),
        }).execute()

        supabase.table("Equipos").update({
            "Contador Actual": int(contador)
        }).eq("id", int(equipo_id)).execute()

        st.cache_data.clear()
        return True, None
    except Exception as e:
        return False, str(e)


# --- FUNCIONES DE SOPORTES DE INVENTARIO ---

@st.cache_data(ttl=60)
def obtener_insumos():
    try:
        supabase = conectar_supabase()
        response = supabase.table("Insumos").select("*").execute()
        df = pd.DataFrame(response.data)
        
        cols_estandar = ["ID", "Nombre", "Categoria", "Cantidad", "Stock Minimo", "Precio Técnico", "Precio Cliente", "Precio Facturado"]
        
        if df.empty:
            return pd.DataFrame(columns=cols_estandar)
            
        for col in ["Cantidad", "Stock Minimo", "Precio Técnico", "Precio Cliente", "Precio Facturado"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                
        return df
    except Exception as e:
        st.warning(f"Aviso al leer Insumos: {e}")
        return pd.DataFrame(columns=["ID", "Nombre", "Categoria", "Cantidad", "Stock Minimo", "Precio Técnico", "Precio Cliente", "Precio Facturado"])


def registrar_insumo(nombre, categoria, cantidad, stock_minimo, p_tecnico, p_cliente, p_facturado):
    try:
        supabase = conectar_supabase()
        
        # Mapeo con nombres exactos de Supabase y conversión a entero (int)
        nuevo_registro = {
            "Nombre": str(nombre).strip(),
            "Categoria": str(categoria).strip().upper(),
            "Cantidad": int(cantidad),
            "Stock Minimo": int(stock_minimo),
            "Precio Técnico": int(round(float(p_tecnico))),
            "Precio Cliente": int(round(float(p_cliente))),
            "Precio Facturado": int(round(float(p_facturado)))
        }
        
        # Inserción principal en Insumos
        res = supabase.table("Insumos").insert(nuevo_registro).execute()
        
        # Intento opcional de registro en Historial
        try:
            fecha_actual = obtener_hora_local_bo().strftime("%Y-%m-%d %H:%M:%S")
            supabase.table("Historial").insert({
                "Fecha": fecha_actual,
                "Insumo": nombre,
                "Accion": "Registro Inicial",
                "Cantidad": int(cantidad),
                "Stock Final": int(cantidad),
                "Usuario": st.session_state.get("usuario_actual", "admin"),
                "Motivo": "Abastecimiento"
            }).execute()
        except Exception as e_hist:
            pass # Si falla el historial, no detiene el registro principal

        # Limpiar caché de datos para que el buscador lea el nuevo insumo
        st.cache_data.clear()
        return True, "✅ ¡Insumo registrado correctamente en Supabase!"

    except Exception as e:
        return False, f"❌ Error de Supabase: {e}"

# --- OBTENER ÚLTIMO REGISTRO DE ALQUILER PARA LOS CONTADORES ---
def obtener_ultimo_alquiler(insumo, empresa, agencia, area):
    """Busca en la tabla Alquileres de Supabase asignando correctamente Agencia y Área."""
    try:
        supabase = conectar_supabase()
        response = supabase.table("Alquileres").select("*").execute()
        if not response.data:
            return None

        df = pd.DataFrame(response.data)
        if df.empty:
            return None

        busq_insumo = str(insumo).strip().lower()
        busq_empresa = str(empresa).strip().lower()
        busq_agencia = str(agencia).split(" - ")[-1].strip().lower() if agencia else ""
        busq_area = str(area).split(" - ")[-1].strip().lower() if area else ""

        for _, fila in df.iloc[::-1].iterrows():
            r_insumo = str(fila.get("Insumo", "")).strip().lower()
            r_empresa = str(fila.get("Empresa", "")).strip().lower()

            r_agencia = str(fila.get("Agencia", "")).split(" - ")[-1].strip().lower()
            r_area = str(fila.get("Area", "")).split(" - ")[-1].strip().lower()

            coincide_sitio = (
                (r_agencia == busq_agencia and r_area == busq_area) or
                (r_agencia == busq_area and r_area == busq_agencia)
            )

            if r_insumo == busq_insumo and r_empresa == busq_empresa and coincide_sitio:
                return fila

        return None
    except Exception as e:
        st.error(f"Error al buscar historial de contadores: {e}")
        return None


def actualizar_stock_sheet(id_insumo, nuevo_stock, nombre_insumo, tipo_mov, cant_movida, motivo="", empresa="", area_o_precio="", precio_unitario=0.0, contador_anterior=0, contador_actual=0, paginas=0, dias=0, agencia=""):
    try:
        supabase = conectar_supabase()

        # 1. Actualizar el stock en la tabla Insumos
        supabase.table("Insumos").update({"Cantidad": nuevo_stock}).eq("id", id_insumo).execute()

        fecha_actual = obtener_hora_local_bo().strftime("%Y-%m-%d %H:%M:%S")

        agencia_para_historial = agencia if agencia else ""
        area_para_historial = area_o_precio if area_o_precio else ""

        # 2. Registrar el movimiento en la tabla Historial
        supabase.table("Historial").insert({
            "Fecha": fecha_actual,
            "Nombre Insumo": nombre_insumo,
            "Tipo de Movimiento": tipo_mov,
            "Cantidad Movida": str(cant_movida),
            "Stock Resultante": str(nuevo_stock),
            "Usuario": st.session_state.get("usuario_actual", ""),
            "Motivo": motivo,
            "Empresa Destino": empresa,
            "Agencia Destino": agencia_para_historial,
            "Área Destino": area_para_historial
        }).execute()

       # 3. Registrar en Ventas o Alquileres según corresponda
        if tipo_mov == "Salida":
            if str(motivo).strip().lower() == "venta":
                total_venta = float(cant_movida) * float(precio_unitario)
                supabase.table("Ventas").insert({
                    "Fecha": fecha_actual,
                    "Insumo": nombre_insumo,
                    "Cantidad": str(cant_movida),
                    "Precio Aplicado": str(precio_unitario),
                    "Monto Total (Bs.)": str(total_venta)
                }).execute()

            elif "alquiler" in str(motivo).strip().lower():
                try:
                    agencia_limpia = str(agencia).split(" - ")[-1].strip() if agencia else ""
                    area_limpia = str(area_o_precio).split(" - ")[-1].strip() if area_o_precio else ""

                    supabase.table("Alquileres").insert({
                        "Fecha": fecha_actual,
                        "Insumo": nombre_insumo,
                        "Cantidad": str(cant_movida),
                        "Empresa Destino": empresa,
                        "Agencia Destino": agencia_limpia,
                        "Area Destino": area_limpia
                    }).execute()
                except Exception as e_alq:
                    st.error(f"❌ Error al insertar en Alquileres: {e_alq}")
                    st.stop()
    except Exception as e:
        st.error(f"Error al conectar con la base de datos: {e}")

# --- FONDO VECTORIAL (NUNCA SE PIXELA) ---
def aplicar_fondo_vectorial():
    # Código SVG que recrea tu diseño exacto con nitidez vectorial infinita
    svg_background = """
    <svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1920 1080' preserveAspectRatio='none'>
      <defs>
        <linearGradient id='bg' x1='0%' y1='0%' x2='100%' y2='100%'>
          <stop offset='0%' stop-color='#ffffff'/>
          <stop offset='60%' stop-color='#f8fafc'/>
          <stop offset='100%' stop-color='#e2e8f0'/>
        </linearGradient>
        <linearGradient id='redGrad' x1='0%' y1='0%' x2='100%' y2='100%'>
          <stop offset='0%' stop-color='#b91c1c'/>
          <stop offset='100%' stop-color='#7f1d1d'/>
        </linearGradient>
        <linearGradient id='darkGrad' x1='0%' y1='0%' x2='100%' y2='100%'>
          <stop offset='0%' stop-color='#1e293b'/>
          <stop offset='100%' stop-color='#0f172a'/>
        </linearGradient>
        <filter id='shadow' x='-10%' y='-10%' width='120%' height='120%'>
          <feDropShadow dx='0' dy='-4' stdDeviation='10' flood-color='#000000' flood-opacity='0.15'/>
        </filter>
      </defs>
      <rect width='1920' height='1080' fill='url(#bg)'/>
      <!-- Rayos de luz suaves en la parte superior -->
      <path d='M0,0 L700,0 L350,600 Z' fill='#ffffff' opacity='0.5'/>
      <path d='M960,0 L1600,0 L1100,700 Z' fill='#ffffff' opacity='0.4'/>
      
      <!-- Franja Gris Oscura -->
      <path d='M-100,680 Q500,920 1920,580 L1920,1080 L-100,1080 Z' fill='url(#darkGrad)' filter='url(#shadow)'/>
      
      <!-- Franja Roja Principal -->
      <path d='M-100,850 Q600,1080 1920,640 L1920,1080 L-100,1080 Z' fill='url(#redGrad)' filter='url(#shadow)'/>
      
      <!-- Franja Gris Inferior de Solape -->
      <path d='M350,1080 Q1100,820 2020,810 L2020,1080 Z' fill='url(#darkGrad)' filter='url(#shadow)'/>
    </svg>
    """
    import urllib.parse
    encoded_svg = urllib.parse.quote(svg_background)
    
    st.markdown(
        f"""
        <style>
        .stApp, [data-testid="stAppViewContainer"], .main {{
            background-image: url("data:image/svg+xml;utf8,{encoded_svg}");
            background-size: cover !important;
            background-position: center center !important;
            background-repeat: no-repeat !important;
            background-attachment: fixed !important;
        }}
        [data-testid="stHeader"] {{
            background-color: rgba(0,0,0,0) !important;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )


# --- FUNCIÓN PARA EL FONDO DE LA BARRA LATERAL HD ---
def aplicar_fondo_sidebar_hd():
    sidebar_svg = """
    <svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 350 1080' preserveAspectRatio='none'>
      <defs>
        <linearGradient id='redSide' x1='0%' y1='0%' x2='100%' y2='100%'>
          <stop offset='0%' stop-color='#b91c1c'/>
          <stop offset='100%' stop-color='#7f1d1d'/>
        </linearGradient>
        <linearGradient id='darkSide' x1='0%' y1='0%' x2='100%' y2='100%'>
          <stop offset='0%' stop-color='#111827'/>
          <stop offset='100%' stop-color='#030712'/>
        </linearGradient>
        <linearGradient id='lightSide' x1='0%' y1='0%' x2='100%' y2='100%'>
          <stop offset='0%' stop-color='#f8fafc'/>
          <stop offset='100%' stop-color='#cbd5e1'/>
        </linearGradient>
      </defs>

      <rect width='350' height='1080' fill='url(#lightSide)'/>
      <path d='M0,0 L180,0 L125,600 L0,1080 Z' fill='url(#darkSide)'/>
      <path d='M0,550 L350,1080 L0,1080 Z' fill='url(#darkSide)'/>
      <path d='M0,0 L190,0 L125,600 Z' fill='url(#redSide)'/>
    </svg>
    """
    
    encoded_svg = urllib.parse.quote(sidebar_svg)

    st.markdown(
        f"""
        <style>
        [data-testid="stSidebar"] {{
            background-image: url("data:image/svg+xml;utf8,{encoded_svg}") !important;
            background-size: 100% 100% !important;
            background-position: center !important;
            background-repeat: no-repeat !important;
            border-right: none !important;
        }}

        [data-testid="stSidebar"] p, 
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] label {{
            color: #0f172a !important;
            font-weight: 700 !important;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

# Llamamos a la función
aplicar_fondo_sidebar_hd()

if "menu_activo" not in st.session_state:
    st.session_state["menu_activo"] = "Inicio"

# Estilo CSS para tarjetas grandes y contenedor deslizable horizontal (scroll)
# --- ESTILOS CSS CORREGIDOS ---
st.markdown("""
<style>
    /* 1. BOTÓN DE CERRAR SESIÓN EN LA BARRA LATERAL (MÁS PEQUEÑO Y ELEGANTE) */
    [data-testid="stSidebar"] div.stButton > button {
        height: auto !important;
        min-width: unset !important;
        width: 100% !important;
        padding: 8px 15px !important;
        font-size: 14px !important;
        font-weight: 500 !important;
        border-radius: 10px !important;
        background-color: #f3f4f6 !important;
        color: #374151 !important;
        border: 1px solid #e5e7eb !important;
        box-shadow: none !important;
        transform: none !important;
    }
    [data-testid="stSidebar"] div.stButton > button:hover {
        background-color: #fee2e2 !important;
        color: #dc2626 !important;
        border-color: #fca5a5 !important;
    }

    /* 2. CONTENEDOR HORIZONTAL SIN ENCIMAMIENTO (SCROLL FLUIDO) */
    [data-testid="stHorizontalBlock"] {
        overflow-x: auto !important;
        flex-wrap: nowrap !important;
        padding: 15px 5px !important;
        gap: 20px !important;
    }
    
    /* Ancho fijo para cada columna para que no se amontonen ni se traslapen */
    [data-testid="stHorizontalBlock"] > [data-testid="column"] {
        min-width: 280px !important;
        flex: 0 0 280px !important;
    }

    /* Barra de desplazamiento estética */
    [data-testid="stHorizontalBlock"]::-webkit-scrollbar {
        height: 8px;
    }
    [data-testid="stHorizontalBlock"]::-webkit-scrollbar-thumb {
        background: #cbd5e1;
        border-radius: 4px;
    }

    /* 3. TARJETAS MÁS GRANDES EN EL ÁREA PRINCIPAL */
    [data-testid="stHorizontalBlock"] div.stButton > button {
    background-color: white;
    color: #1f2937;
    padding: 20px 10px;
    border-radius: 18px;
    box-shadow: 0 8px 25px rgba(0, 0, 0, 0.07);
    border: 1px solid #e5e7eb;
    width: 100% !important;
    height: 160px !important;
    font-size: 15px !important;
    font-weight: 600;
    transition: all 0.3s ease;
    white-space: pre-wrap;
}

    [data-testid="stHorizontalBlock"] div.stButton > button:hover {
    transform: translateY(-6px);
    box-shadow: 0 12px 30px rgba(230, 0, 0, 0.18);
    border-color: #e60000;
    color: #c60000;
    background-color: white;
}
</style>
""", unsafe_allow_html=True)

df_insumos = obtener_insumos()
empresas_disponibles, areas_disponibles, agencias_disponibles = obtener_parametros()

if st.session_state["menu_activo"] == "Inicio":
    aplicar_fondo_vectorial()
    st.markdown("<h2 style='text-align: center; color: #1f2937;'>📋 Menú Principal del Sistema</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #6b7280; margin-bottom: 20px;'>Desliza hacia la derecha para ver todas las opciones y haz clic en una tarjeta</p>", unsafe_allow_html=True)

    # --- AQUÍ EMPIEZA LO NUEVO PARA SEPARAR POR ROL ---
    rol = st.session_state.get("rol_actual", "Administrador")
    
    if rol == "Administrador":
        col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
        
        with col1:
            if st.button("📦 Operaciones\nde Stock\n\nEntradas y alertas", key="card_stock"):
                st.session_state["menu_activo"] = "Operaciones de Stock"
                st.rerun()
        with col2:
            if st.button("📊 Valorización\ndel Inventario\n\nCostos y activos", key="card_val"):
                st.session_state["menu_activo"] = "Valorización del Inventario"
                st.rerun()
        with col3:
            if st.button("📈 Rendimiento\nde Insumos\n\nMétricas de uso", key="card_rend"):
                st.session_state["menu_activo"] = "Rendimiento de Insumos"
                st.rerun()
        with col4:
            if st.button("🛠️ Insumos\nde Respaldo\n\nAlternativas", key="card_respaldo"):
                st.session_state["menu_activo"] = "Insumos de Respaldo (Backup)"
                st.rerun()
        with col5:
            if st.button("⚙️ Servicios\ny Soporte\n\nMantenimiento", key="card_soporte"):
                st.session_state["menu_activo"] = "Servicios y Soporte"
                st.rerun()
        with col6:
            if st.button("📋 Reportes\ny Edición\n\nFiltros por fecha", key="card_rep"):
                st.session_state["menu_activo"] = "Reportes por Fecha / Edición"
                st.rerun()
        with col7:
            if st.button("👥 Configuración\ny Usuarios\n\nRoles y ajustes", key="card_config"):
                st.session_state["menu_activo"] = "Configuración y Gestión de Usuarios"
                st.rerun()


        # --- GESTIÓN DE EQUIPOS ---
        st.markdown("---")
        st.subheader("🖨️ Gestión de Equipos y Contadores")
        col_eq1, col_eq2, col_eq3 = st.columns(3)

        with col_eq1:
            if st.button("🖨️ Equipos\n\nClientes y máquinas", key="card_equipos"):
                st.session_state["menu_activo"] = "Gestión de Equipos"
                st.rerun()
    else:
        # --- VISTA PARA EL TÉCNICO (Solo 3 tarjetas) ---
        col_t1, col_t2, col_t3 = st.columns(3)
        
        with col_t1:
            if st.button("🛠️ Insumos\nde Respaldo\n\nAlternativas", key="card_respaldo_tec"):
                st.session_state["menu_activo"] = "Insumos de Respaldo (Backup)"
                st.rerun()
        with col_t2:
            if st.button("⚙️ Servicios\ny Soporte\n\nMantenimiento", key="card_soporte_tec"):
                st.session_state["menu_activo"] = "Servicios y Soporte"
                st.rerun()
        with col_t3:
            if st.button("📋 Reportes\ny Edición\n\nFiltros por fecha", key="card_rep_tec"):
                st.session_state["menu_activo"] = "Reportes por Fecha / Edición"
                st.rerun()

    # --- PEGA AQUÍ EL BUSCADOR (Línea 753) ---
    st.markdown("---")
    st.subheader("🔍 Buscador Rápido de Insumos")

    busqueda_menu = st.text_input(
        "Buscar insumo por nombre o categoría:", 
        placeholder="Escribe aquí para buscar...", 
        key="busqueda_inicio"
    )

    if busqueda_menu.strip():
        if not df_insumos.empty:
            df_filtrado = df_insumos[
                df_insumos["Nombre"].astype(str).str.lower().str.contains(busqueda_menu.lower()) |
                df_insumos["Categoría"].astype(str).str.lower().str.contains(busqueda_menu.lower())
            ]
            
            if not df_filtrado.empty:
                if st.session_state.get("rol_actual") == "Administrador":
                    with st.expander("🚨 Zona de Administración: Eliminar Insumos"):
                        insumo_a_borrar = st.selectbox("Selecciona insumo a eliminar:", df_filtrado["Nombre"].tolist(), key="del_menu_insumo")
                        if st.button("Confirmar Eliminación", key="btn_del_menu"):
                            id_a_borrar = df_filtrado[df_filtrado["Nombre"] == insumo_a_borrar]["ID"].values[0]
                            if eliminar_insumo(id_a_borrar):
                                st.success(f"Insumo '{insumo_a_borrar}' eliminado.")
                                st.rerun()
                            else:
                                st.error("No se pudo eliminar.")

                df_filtrado_con_num = df_filtrado.copy()
                df_filtrado_con_num.insert(0, "N°", range(1, len(df_filtrado_con_num) + 1))
                st.dataframe(df_filtrado_con_num, use_container_width=True, hide_index=True)
            else:
                st.warning("No se encontraron insumos que coincidan con la búsqueda.")

else:
    # Fuerza a que todos los botones de subpáginas (incluyendo Volver) sean compactos
    st.markdown("""
        <style>
        div.stButton > button {
            height: auto !important;
            width: auto !important;
            padding: 8px 16px !important;
            font-size: 14px !important;
            border-radius: 8px !important;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1) !important;
        }
        </style>
    """, unsafe_allow_html=True)

    if st.button("🏠 Volver al Menú Principal"):
        st.session_state["menu_activo"] = "Inicio"
        st.rerun()
    
    st.divider()

    seccion = st.session_state["menu_activo"]

# ----------------------------------------------------------------------------------
# 1.    OPERACIONES DE STOCK (ENTRADAS, SALIDAS Y ALERTAS)
# ----------------------------------------------------------------------------------
    if seccion == "Gestión de Equipos":
        st.subheader("🖨️ Gestión de Equipos")
        st.caption("Administra clientes, máquinas, datos de red, estado y contadores.")

        df_equipos = obtener_equipos()

        tab_dashboard, tab_lista, tab_nuevo, tab_importar, tab_contador = st.tabs([
            "📊 Dashboard",
            "📋 Equipos registrados",
            "➕ Registrar equipo",
            "📥 Importar desde Excel",
            "🔢 Registrar contador"
        ])

        with tab_dashboard:
            st.markdown("### 📊 Resumen de equipos")
            st.caption("Vista rápida del parque de equipos registrado en el sistema.")

            if df_equipos.empty:
                st.info("Todavía no hay equipos registrados para mostrar estadísticas.")
            else:
                df_dash = df_equipos.copy()
                for col in ["Empresa", "Agencia", "Marca", "Modelo", "Tipo", "Modalidad", "Estado"]:
                    if col not in df_dash.columns:
                        df_dash[col] = "Sin registrar"
                    df_dash[col] = df_dash[col].fillna("Sin registrar").astype(str).str.strip()
                    df_dash.loc[df_dash[col] == "", col] = "Sin registrar"

                df_dash["Contador Actual"] = pd.to_numeric(
                    df_dash.get("Contador Actual", 0), errors="coerce"
                ).fillna(0)

                total_equipos = len(df_dash)
                activos = int((df_dash["Estado"].str.lower() == "activo").sum())
                alquileres = int((df_dash["Modalidad"].str.lower() == "alquiler").sum())
                contador_total = int(df_dash["Contador Actual"].sum())

                k1, k2, k3, k4 = st.columns(4)
                k1.metric("🖨️ Equipos registrados", total_equipos)
                k2.metric("✅ Equipos activos", activos)
                k3.metric("💼 En alquiler", alquileres)
                k4.metric("🔢 Contador acumulado", f"{contador_total:,}".replace(",", "."))

                st.markdown("---")
                g1, g2 = st.columns(2)

                with g1:
                    resumen_estado = (
                        df_dash.groupby("Estado", dropna=False)
                        .size().reset_index(name="Cantidad")
                        .sort_values("Cantidad", ascending=False)
                    )
                    fig_estado = px.bar(
                        resumen_estado, x="Estado", y="Cantidad",
                        title="Equipos por estado", text="Cantidad"
                    )
                    fig_estado.update_layout(margin=dict(l=10, r=10, t=50, b=10))
                    st.plotly_chart(fig_estado, use_container_width=True, key="grafico_estado_equipos")

                with g2:
                    resumen_modalidad = (
                        df_dash.groupby("Modalidad", dropna=False)
                        .size().reset_index(name="Cantidad")
                        .sort_values("Cantidad", ascending=False)
                    )
                    fig_modalidad = px.bar(
                        resumen_modalidad, x="Modalidad", y="Cantidad",
                        title="Equipos por modalidad", text="Cantidad"
                    )
                    fig_modalidad.update_layout(margin=dict(l=10, r=10, t=50, b=10))
                    st.plotly_chart(fig_modalidad, use_container_width=True, key="grafico_modalidad_equipos")

                st.markdown("### 🏢 Distribución por empresa")
                resumen_empresa = (
                    df_dash.groupby("Empresa", dropna=False)
                    .size().reset_index(name="Cantidad")
                    .sort_values("Cantidad", ascending=False)
                )
                st.dataframe(resumen_empresa, use_container_width=True, hide_index=True)

                st.markdown("### 🖨️ Equipos con mayor contador")
                columnas_top = [c for c in ["Empresa", "Agencia", "Marca", "Modelo", "Numero Serie", "Contador Actual"] if c in df_dash.columns]
                top_contadores = df_dash.sort_values("Contador Actual", ascending=False).head(10)
                st.dataframe(
                    top_contadores[columnas_top],
                    use_container_width=True, hide_index=True,
                    column_config={"Contador Actual": st.column_config.NumberColumn("Contador", format="%d")}
                )

        with tab_lista:
            if df_equipos.empty:
                st.info("No hay equipos registrados todavía.")
            else:
                busqueda_eq = st.text_input(
                    "🔍 Buscar equipo",
                    placeholder="Empresa, agencia, marca, modelo o número de serie...",
                    key="buscar_equipos"
                )

                df_mostrar = df_equipos.copy()
                if busqueda_eq.strip():
                    texto = df_mostrar.fillna("").astype(str).agg(" ".join, axis=1)
                    df_mostrar = df_mostrar[
                        texto.str.contains(busqueda_eq.strip(), case=False, na=False)
                    ]

                columnas_visibles = [
                    "id", "Empresa", "Agencia", "Area", "Marca", "Modelo",
                    "Numero Serie", "Tipo", "IP", "Modalidad", "Estado",
                    "Contador Actual", "Fecha Instalacion", "Observaciones"
                ]
                columnas_visibles = [c for c in columnas_visibles if c in df_mostrar.columns]
                st.dataframe(
                    df_mostrar[columnas_visibles],
                    use_container_width=True,
                    hide_index=True
                )

                st.markdown("### ✏️ Editar / eliminar equipo")
                opciones = {
                    f'#{int(row["id"])} — {row.get("Marca", "")} {row.get("Modelo", "")} — {row.get("Numero Serie", "")}': int(row["id"])
                    for _, row in df_mostrar.iterrows()
                }

                if opciones:
                    equipo_sel_label = st.selectbox(
                        "Selecciona el equipo:",
                        list(opciones.keys()),
                        key="equipo_editar_sel"
                    )
                    equipo_id = opciones[equipo_sel_label]
                    fila = df_equipos[df_equipos["id"] == equipo_id].iloc[0]

                    with st.expander("✏️ Editar datos del equipo"):
                        e1, e2, e3 = st.columns(3)

                        with e1:
                            empresa_e = st.text_input("Empresa", value=str(fila.get("Empresa") or ""), key="ed_emp")
                            agencia_e = st.text_input("Agencia", value=str(fila.get("Agencia") or ""), key="ed_ag")
                            area_e = st.text_input("Área", value=str(fila.get("Area") or ""), key="ed_area")
                            marca_e = st.text_input("Marca", value=str(fila.get("Marca") or ""), key="ed_marca")
                            modelo_e = st.text_input("Modelo", value=str(fila.get("Modelo") or ""), key="ed_modelo")

                        with e2:
                            serie_e = st.text_input("Número de serie", value=str(fila.get("Numero Serie") or ""), key="ed_serie")
                            tipo_e = st.text_input("Tipo", value=str(fila.get("Tipo") or ""), key="ed_tipo")
                            ip_e = st.text_input("IP", value=str(fila.get("IP") or ""), key="ed_ip")

                            modalidades = ["Alquiler", "Venta", "Propio", "Otro"]
                            modalidad_actual = str(fila.get("Modalidad") or "")
                            modalidad_e = st.selectbox(
                                "Modalidad",
                                modalidades,
                                index=modalidades.index(modalidad_actual) if modalidad_actual in modalidades else 0,
                                key="ed_modalidad"
                            )

                            estados = ["Activo", "Mantenimiento", "Baja", "Retirado"]
                            estado_actual = str(fila.get("Estado") or "")
                            estado_e = st.selectbox(
                                "Estado",
                                estados,
                                index=estados.index(estado_actual) if estado_actual in estados else 0,
                                key="ed_estado"
                            )

                        with e3:
                            try:
                                contador_base = int(fila.get("Contador Actual") or 0)
                            except Exception:
                                contador_base = 0

                            contador_e = st.number_input(
                                "Contador actual",
                                min_value=0,
                                value=contador_base,
                                step=1,
                                key="ed_contador"
                            )

                            try:
                                fecha_e = pd.to_datetime(fila.get("Fecha Instalacion")).date()
                            except Exception:
                                fecha_e = datetime.now().date()

                            fecha_e = st.date_input(
                                "Fecha de instalación",
                                value=fecha_e,
                                key="ed_fecha"
                            )

                            observaciones_e = st.text_area(
                                "Observaciones",
                                value=str(fila.get("Observaciones") or ""),
                                key="ed_obs"
                            )

                        b1, b2 = st.columns(2)
                        with b1:
                            if st.button("💾 Guardar cambios", key="guardar_equipo_editado", use_container_width=True):
                                ok, err = actualizar_equipo(
                                    equipo_id, empresa_e, agencia_e, area_e, marca_e, modelo_e,
                                    serie_e, tipo_e, ip_e, modalidad_e, estado_e,
                                    contador_e, fecha_e, observaciones_e
                                )
                                if ok:
                                    st.success("✅ Equipo actualizado correctamente.")
                                    st.rerun()
                                else:
                                    st.error(f"❌ No se pudo actualizar: {err}")

                        with b2:
                            if st.button("🗑️ Eliminar equipo", key="eliminar_equipo", use_container_width=True):
                                st.session_state["confirmar_eliminacion_equipo"] = equipo_id

                    if st.session_state.get("confirmar_eliminacion_equipo") == equipo_id:
                        st.warning("Se eliminará el equipo seleccionado.")
                        c1, c2 = st.columns(2)

                        with c1:
                            if st.button("Sí, eliminar definitivamente", key="confirmar_borrado_equipo"):
                                ok, err = eliminar_equipo(equipo_id)
                                if ok:
                                    st.session_state.pop("confirmar_eliminacion_equipo", None)
                                    st.success("🗑️ Equipo eliminado.")
                                    st.rerun()
                                else:
                                    st.error(f"❌ No se pudo eliminar: {err}")

                        with c2:
                            if st.button("Cancelar", key="cancelar_borrado_equipo"):
                                st.session_state.pop("confirmar_eliminacion_equipo", None)
                                st.rerun()

        with tab_nuevo:
            st.markdown("### ➕ Registrar nuevo equipo")
            n1, n2, n3 = st.columns(3)

            # Listas desplegables alimentadas desde Parametros y desde los equipos ya registrados.
            def _opciones_unicas(valores, incluir_seleccione=True):
                resultado = []
                for valor in valores:
                    if pd.isna(valor):
                        continue
                    texto = str(valor).strip()
                    if texto and texto not in resultado and texto != "Sin Registrar":
                        resultado.append(texto)
                resultado.sort(key=lambda x: x.lower())
                return (["— Seleccionar —"] + resultado) if incluir_seleccione else resultado

            empresas_eq = _opciones_unicas(empresas_disponibles)
            areas_eq = _opciones_unicas(areas_disponibles)
            agencias_eq_todas = _opciones_unicas(agencias_disponibles)

            # Marca, modelo y tipo se toman de los equipos existentes para evitar escribirlos repetidamente.
            marcas_base = [
                "Canon", "HP", "Epson", "Brother", "Ricoh", "Kyocera",
                "Xerox", "Konica Minolta", "Lexmark", "Sharp"
            ]
            tipos_base = [
                "Multifuncional", "Impresora", "Escáner", "Plotter"
            ]
            marcas_existentes = _opciones_unicas(
                list(df_equipos.get("Marca", pd.Series(dtype=str)).tolist()) + marcas_base
            )
            tipos_existentes = _opciones_unicas(
                list(df_equipos.get("Tipo", pd.Series(dtype=str)).tolist()) + tipos_base
            )

            with n1:
                empresa_n_sel = st.selectbox("Empresa", empresas_eq, key="nuevo_eq_empresa")

                if empresa_n_sel == "— Seleccionar —":
                    agencias_filtradas_eq = []
                else:
                    agencias_filtradas_eq = [
                        ag for ag in agencias_disponibles
                        if str(ag).strip().lower().startswith(empresa_n_sel.strip().lower())
                    ]
                    # Si Parametros no tiene la empresa como prefijo, dejamos las agencias disponibles
                    # para no bloquear el registro.
                    if not agencias_filtradas_eq:
                        agencias_filtradas_eq = agencias_disponibles

                # Mostramos nombres cortos para que el formulario sea limpio, pero
                # conservamos el valor original de Parametros al guardar en Supabase.
                def _nombre_corto(valor, cantidad_prefijos=1):
                    texto = str(valor).strip()
                    partes = [p.strip() for p in texto.split(" - ") if p.strip()]
                    if len(partes) > cantidad_prefijos:
                        return " - ".join(partes[cantidad_prefijos:])
                    return texto

                agencias_eq_originales = _opciones_unicas(agencias_filtradas_eq)
                mapa_agencias_eq = {
                    _nombre_corto(ag): ag for ag in agencias_eq_originales
                    if ag != "— Seleccionar —"
                }
                agencias_eq = ["— Seleccionar —"] + list(mapa_agencias_eq.keys())
                agencia_n_visible = st.selectbox("Agencia", agencias_eq, key="nuevo_eq_agencia")
                agencia_n_sel = mapa_agencias_eq.get(agencia_n_visible, "— Seleccionar —")

                if agencia_n_visible == "— Seleccionar —":
                    areas_filtradas_eq = []
                else:
                    areas_filtradas_eq = [
                        ar for ar in areas_disponibles
                        if str(ar).strip().lower().startswith(agencia_n_sel.strip().lower())
                    ]
                    if not areas_filtradas_eq:
                        # Compatibilidad con Parametros donde Área puede no llevar el prefijo de Agencia.
                        areas_filtradas_eq = areas_disponibles

                areas_eq_originales = _opciones_unicas(areas_filtradas_eq)
                mapa_areas_eq = {
                    _nombre_corto(ar, cantidad_prefijos=2): ar for ar in areas_eq_originales
                    if ar != "— Seleccionar —"
                }
                areas_eq = ["— Seleccionar —"] + list(mapa_areas_eq.keys())
                area_n_visible = st.selectbox("Área", areas_eq, key="nuevo_eq_area")
                area_n_sel = mapa_areas_eq.get(area_n_visible, "— Seleccionar —")

                marca_n_sel = st.selectbox("Marca", marcas_existentes, key="nuevo_eq_marca")

            with n2:
                serie_n = st.text_input("Número de serie", key="nuevo_eq_serie")

                # El modelo se filtra por la marca elegida cuando ya existen modelos para esa marca.
                if marca_n_sel != "— Seleccionar —" and "Marca" in df_equipos.columns and "Modelo" in df_equipos.columns:
                    modelos_filtrados_eq = df_equipos.loc[
                        df_equipos["Marca"].fillna("").astype(str).str.strip().str.lower() == marca_n_sel.strip().lower(),
                        "Modelo"
                    ].tolist()
                else:
                    modelos_filtrados_eq = df_equipos.get("Modelo", pd.Series(dtype=str)).tolist()

                modelos_eq = _opciones_unicas(modelos_filtrados_eq)
                if len(modelos_eq) > 1:
                    modelo_n_sel = st.selectbox("Modelo", modelos_eq, key="nuevo_eq_modelo")
                else:
                    st.caption("No hay modelos registrados todavía; puedes escribir el primero.")
                    modelo_n_sel = st.text_input("Modelo", key="nuevo_eq_modelo_manual")

                tipo_n_sel = st.selectbox(
                    "Tipo",
                    tipos_existentes,
                    key="nuevo_eq_tipo"
                )
                ip_n = st.text_input("IP", key="nuevo_eq_ip")
                modalidad_n = st.selectbox("Modalidad", ["Alquiler", "Venta", "Propio", "Otro"], key="nuevo_eq_modalidad")
                estado_n = st.selectbox("Estado", ["Activo", "Mantenimiento", "Baja", "Retirado"], key="nuevo_eq_estado")

                # Convertimos el valor visual de la lista a texto vacío para Supabase.
                agencia_n = "" if agencia_n_sel == "— Seleccionar —" else agencia_n_sel
                area_n = "" if area_n_sel == "— Seleccionar —" else area_n_sel
                empresa_n = "" if empresa_n_sel == "— Seleccionar —" else empresa_n_sel
                marca_n = "" if marca_n_sel == "— Seleccionar —" else marca_n_sel
                modelo_n = "" if modelo_n_sel == "— Seleccionar —" else modelo_n_sel
                tipo_n = "" if tipo_n_sel == "— Seleccionar —" else tipo_n_sel

            with n3:
                contador_n = st.number_input("Contador actual", min_value=0, value=0, step=1, key="nuevo_eq_contador")
                fecha_n = st.date_input("Fecha de instalación", value=datetime.now().date(), key="nuevo_eq_fecha")
                observaciones_n = st.text_area("Observaciones", key="nuevo_eq_obs")

            if st.button("💾 Registrar equipo", type="primary", use_container_width=True, key="registrar_equipo"):
                ok, err = registrar_equipo(
                    empresa_n, agencia_n, area_n, marca_n, modelo_n, serie_n, tipo_n,
                    ip_n, modalidad_n, estado_n, contador_n, fecha_n, observaciones_n
                )
                if ok:
                    st.success("🎉 Equipo registrado correctamente.")
                    st.rerun()
                else:
                    st.error(f"❌ No se pudo registrar el equipo: {err}")

        with tab_importar:
            st.markdown("### 📥 Carga masiva de equipos desde Excel")
            st.caption("Ideal para cargar los más de 150 equipos de la empresa de una sola vez.")

            plantilla_bytes = bytes_plantilla_equipos(
                empresas_disponibles,
                agencias_disponibles,
                areas_disponibles,
                df_equipos
            )
            c_imp1, c_imp2 = st.columns(2)
            with c_imp1:
                st.download_button(
                    "📄 Descargar plantilla Excel",
                    data=plantilla_bytes,
                    file_name="Plantilla_Carga_Equipos.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key="descargar_plantilla_equipos"
                )
            with c_imp2:
                st.info("💡 La plantilla ya trae listas desplegables y se actualiza con las Empresas, Agencias y Áreas de tu sistema.")

            archivo_equipos = st.file_uploader(
                "📎 Sube el Excel completado",
                type=["xlsx"],
                key="archivo_importacion_equipos",
                help="Usa la plantilla descargada y conserva los nombres de las columnas."
            )

            if archivo_equipos is not None:
                try:
                    df_importado = pd.read_excel(archivo_equipos, sheet_name="Equipos")
                    df_validos, df_errores, errores_estructura = validar_dataframe_equipos(
                        df_importado, df_equipos
                    )

                    if errores_estructura:
                        for mensaje_error in errores_estructura:
                            st.error(f"❌ {mensaje_error}")
                    else:
                        st.markdown("#### Vista previa de la importación")
                        m1, m2, m3 = st.columns(3)
                        m1.metric("Filas del Excel", len(df_importado.dropna(how="all")))
                        m2.metric("✅ Listas para importar", len(df_validos))
                        m3.metric("⚠️ Con errores", len(df_errores))

                        if not df_validos.empty:
                            st.success(f"Se encontraron {len(df_validos)} equipos listos para cargar.")
                            st.dataframe(
                                df_importado.loc[df_importado.index.isin(
                                    df_importado.index[:len(df_importado)]
                                )].head(10),
                                use_container_width=True,
                                hide_index=True
                            )

                        if not df_errores.empty:
                            st.warning("Hay filas que no se importarán hasta corregirlas.")
                            st.dataframe(
                                df_errores[["Fila", "Número de serie", "Errores"]],
                                use_container_width=True,
                                hide_index=True
                            )

                        if not df_validos.empty:
                            confirmar = st.checkbox(
                                f"Confirmo que quiero importar {len(df_validos)} equipos válidos.",
                                key="confirmar_importacion_equipos"
                            )
                            if st.button(
                                "🚀 Importar equipos a Supabase",
                                type="primary",
                                use_container_width=True,
                                disabled=not confirmar,
                                key="importar_equipos_masivo"
                            ):
                                with st.spinner("Importando equipos..."):
                                    cantidad_importada, error_importacion = importar_equipos_masivo(df_validos)
                                if error_importacion:
                                    st.error(f"❌ No se pudo completar la importación: {error_importacion}")
                                else:
                                    st.success(f"🎉 Se importaron {cantidad_importada} equipos correctamente.")
                                    st.rerun()
                except Exception as e:
                    st.error(f"❌ No se pudo leer el Excel: {e}")

        with tab_contador:
            if df_equipos.empty:
                st.info("Primero registra al menos un equipo.")
            else:
                opciones_cont = {
                    f'#{int(row["id"])} — {row.get("Marca", "")} {row.get("Modelo", "")} — Serie: {row.get("Numero Serie", "")} — Contador: {row.get("Contador Actual", 0)}': int(row["id"])
                    for _, row in df_equipos.iterrows()
                }

                equipo_cont_label = st.selectbox(
                    "Selecciona el equipo",
                    list(opciones_cont.keys()),
                    key="equipo_contador_sel"
                )
                equipo_cont_id = opciones_cont[equipo_cont_label]

                # Cargamos el historial antes de registrar una nueva lectura para
                # poder mostrar el último contador y calcular automáticamente el consumo.
                df_lecturas = obtener_lecturas_equipo(equipo_cont_id)
                fila_equipo_cont = df_equipos[df_equipos["id"] == equipo_cont_id].iloc[0]
                try:
                    contador_actual_equipo = int(fila_equipo_cont.get("Contador Actual") or 0)
                except Exception:
                    contador_actual_equipo = 0

                ultima_lectura = None
                ultima_fecha = None
                if not df_lecturas.empty and "Contador" in df_lecturas.columns:
                    try:
                        ultima_lectura = int(pd.to_numeric(df_lecturas.iloc[0]["Contador"]))
                        ultima_fecha = df_lecturas.iloc[0].get("Fecha")
                    except Exception:
                        ultima_lectura = None

                # Si ya existen lecturas, usamos la última como referencia.
                # Si no existen, mostramos el contador actual del equipo como referencia informativa.
                contador_referencia = ultima_lectura if ultima_lectura is not None else contador_actual_equipo

                m1, m2, m3 = st.columns(3)
                with m1:
                    st.metric("🔢 Contador actual", f"{contador_actual_equipo:,}".replace(",", "."))
                with m2:
                    if ultima_lectura is not None:
                        st.metric("📅 Última lectura", f"{ultima_lectura:,}".replace(",", "."))
                    else:
                        st.metric("📅 Última lectura", "Sin historial")
                with m3:
                    st.metric("📈 Lecturas registradas", len(df_lecturas))

                st.markdown("#### ➕ Registrar nueva lectura")
                fc1, fc2 = st.columns(2)
                with fc1:
                    contador_nuevo = st.number_input(
                        "Nuevo contador",
                        min_value=max(0, contador_referencia),
                        value=max(0, contador_referencia),
                        step=1,
                        key="nuevo_contador"
                    )
                    fuente_nueva = st.selectbox(
                        "Fuente",
                        ["Lectura física", "Lectura remota", "Reporte cliente", "Otro"],
                        key="fuente_contador"
                    )

                with fc2:
                    usuario_lectura = st.text_input(
                        "Usuario",
                        value=st.session_state.get("usuario_actual", ""),
                        key="usuario_contador"
                    )
                    obs_lectura = st.text_area("Observaciones", key="obs_contador")

                incremento = int(contador_nuevo) - int(contador_referencia)
                if ultima_lectura is not None:
                    st.info(
                        f"📊 **Incremento desde la última lectura:** "
                        f"{incremento:,} impresiones".replace(",", ".")
                    )
                else:
                    st.caption(
                        f"Primera lectura del historial. El contador actual del equipo es "
                        f"{contador_actual_equipo:,}.".replace(",", ".")
                    )

                if st.button("🔢 Registrar lectura", type="primary", use_container_width=True, key="registrar_lectura"):
                    if contador_nuevo < contador_referencia:
                        st.error("❌ El nuevo contador no puede ser menor que la lectura anterior.")
                    else:
                        ok, err = registrar_lectura_equipo(
                            equipo_cont_id, contador_nuevo, fuente_nueva,
                            usuario_lectura, obs_lectura
                        )
                        if ok:
                            st.success("✅ Lectura registrada y contador actualizado.")
                            st.rerun()
                        else:
                            st.error(f"❌ No se pudo registrar la lectura: {err}")

                st.markdown("### 📊 Historial de lecturas")
                if df_lecturas.empty:
                    st.info("Este equipo todavía no tiene lecturas registradas.")
                else:
                    historial = df_lecturas.copy()
                    if "Fecha" in historial.columns:
                        historial["Fecha"] = pd.to_datetime(historial["Fecha"], errors="coerce")
                        historial = historial.sort_values("Fecha", ascending=False)

                    if "Contador" in historial.columns:
                        historial["Contador"] = pd.to_numeric(historial["Contador"], errors="coerce")
                        historial["Incremento"] = historial["Contador"].diff(-1)
                        historial["Incremento"] = historial["Incremento"].fillna(0).astype(int)

                    columnas_historial = [
                        "Fecha", "Contador", "Incremento", "Fuente", "Usuario", "Observaciones"
                    ]
                    columnas_historial = [c for c in columnas_historial if c in historial.columns]
                    st.dataframe(
                        historial[columnas_historial],
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Fecha": st.column_config.DatetimeColumn("Fecha", format="DD/MM/YYYY HH:mm"),
                            "Contador": st.column_config.NumberColumn("Contador", format="%d"),
                            "Incremento": st.column_config.NumberColumn("Impresiones", format="%d"),
                        }
                    )

    if seccion == "Operaciones de Stock":
        if st.session_state["rol_actual"] in ["Administrador", "Secretaria"]:
            st.subheader("⚠️ Alertas de Stock Crítico")
            # (Aquí sigue tu código original)
            alertas_activas = False
            if not df_insumos.empty:
                for index, fila in df_insumos.iterrows():
                    cant_actual = int(fila["Cantidad"])
                    cant_minima = int(fila["Stock Minimo"])
                    if cant_actual <= cant_minima:
                        st.error(f"🚨 **¡ALERTA DE STOCK BAJO!** El insumo **{fila['Nombre']}** tiene solo **{cant_actual}** unidades. (Mínimo: {cant_minima})")
                        alertas_activas = True
            if not alertas_activas:
                st.success("✅ ¡Todos los insumos tienen niveles de stock saludables!")
            st.markdown("---")

        if st.session_state["rol_actual"] == "Técnico":
            st.warning("ℹ️ Tu cuenta de **Técnico** tiene permisos de 'Solo Lectura'. Puedes revisar las existencias abajo.")
        else:
            col_izq, col_der = st.columns([1, 1])

            with col_izq:
                if st.session_state["rol_actual"] in ["Administrador", "Secretaria"]:
                    if st.session_state["rol_actual"] == "Administrador":
                        tab_reg, tab_edit = st.tabs(["➕ Registrar Insumo", "✏️ Editar Stock Mínimo/Precios"])
                    else:
                        tab_reg = st.tabs(["➕ Registrar Insumo"])[0]
                    
                    with tab_reg:
                        with st.form("nuevo_insumo_form", clear_on_submit=True):
                            st.subheader("Registrar Nuevo Insumo")
                            
                            nombre = st.text_input("Nombre del Insumo", placeholder="Ej: GPR-57")
                            categoria = st.text_input("Categoría", placeholder="Ej: TONER")
                            amount_ini = st.number_input("Cantidad Inicial", min_value=0, value=0, step=1)
                            stock_min = st.number_input("Stock Mínimo (Alerta)", min_value=0, value=5, step=1)
                            
                            st.markdown("💰 **Configuración de Precios (Bs.)**")
                            p_tecnico = st.number_input("Precio Técnico", min_value=0, value=0, step=1)
                            p_cliente = st.number_input("Precio Cliente", min_value=0, value=0, step=1)
                            p_facturado = st.number_input("Precio Facturado", min_value=0, value=0, step=1)
                            
                            guardado = st.form_submit_button("💾 Guardar Insumo")

                        if guardado:
                            if not nombre.strip():
                                st.warning("⚠️ Por favor, ingresa el nombre del insumo.")
                            elif not df_insumos.empty and nombre.strip().lower() in df_insumos["Nombre"].astype(str).str.lower().values:
                                st.warning("⚠️ Ese insumo ya existe en el inventario.")
                            else:
                                with st.spinner("Guardando en Supabase..."):
                                    exito, mensaje = registrar_insumo(
                                        nombre, categoria, amount_ini, stock_min, p_tecnico, p_cliente, p_facturado
                                    )
                                    if exito:
                                        st.success(mensaje)
                                    else:
                                        st.error(mensaje)
                    # Solo si es Administrador, mostramos el contenido de la pestaña de edición
                    if st.session_state["rol_actual"] == "Administrador":
                        with tab_edit:
                            st.write("**Modificar Alerta o Precios**")
                            if not df_insumos.empty:
                                insumo_editar = st.selectbox("Selecciona el insumo a editar:", df_insumos["Nombre"].tolist(), key="sel_edit")
                                datos_insumo_editar = df_insumos[df_insumos["Nombre"] == insumo_editar].iloc[0]
                                
                                cel_id = datos_insumo_editar["id"]
                                min_actual = int(datos_insumo_editar["Stock Minimo"])
                                pt_act = float(datos_insumo_editar["Precio Técnico"])
                                pc_act = float(datos_insumo_editar["Precio Cliente"])
                                pf_acl = float(datos_insumo_editar["Precio Facturado"])

                                # Campo para editar el nombre del insumo
                                nuevo_nombre = st.text_input("Nuevo Nombre del Insumo:", value=insumo_editar)
                                
                                nuevo_minimo = st.number_input("Nuevo Stock Mínimo:", min_value=1, step=1, value=min_actual)
                                nuevo_pt = st.number_input("Nuevo Precio Técnico:", min_value=0.0, step=0.1, value=pt_act)
                                nuevo_pc = st.number_input("Nuevo Precio Cliente:", min_value=0.0, step=0.1, value=pc_act)
                                nuevo_pf = st.number_input("Nuevo Precio Facturado:", min_value=0.0, step=0.1, value=pf_acl)

                                if st.button("Actualizar Parámetros"):
                                    try:
                                        supabase = conectar_supabase()
                                        datos_actualizados = {
                                            "Nombre": str(nuevo_nombre).strip(),
                                            "Stock Minimo": int(nuevo_minimo),
                                            "Precio Técnico": int(round(float(nuevo_pt))),
                                            "Precio Cliente": int(round(float(nuevo_pc))),
                                            "Precio Facturado": int(round(float(nuevo_pf)))
                                        }
                                        supabase.table("Insumos").update(datos_actualizados).eq("id", cel_id).execute()
                                        st.cache_data.clear()
                                        st.success("✅ ¡Datos actualizados con éxito!")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"❌ Error al actualizar en Supabase: {e}")

            with col_der:
                st.subheader("🔄 Registrar Movimiento (Entrada/Salida)")
                
                st.markdown("📷 **Lector de Códigos QR/Barra**")
                
                if "camara_activa" not in st.session_state:
                    st.session_state["camara_activa"] = False
                    
                st.session_state["camara_activa"] = st.checkbox(
                    "🎥 Activar / Encender Cámara", 
                    value=st.session_state["camara_activa"]
                )
                
                insumo_detectado = None
                
                if st.session_state["camara_activa"]:
                    foto_codigo = st.camera_input("Toma una foto al código de barra para escanearlo")
                    if foto_codigo is not None:
                        st.success("¡Código capturado con éxito!")
                        insumo_detectado = st.selectbox("🔍 Confirmar insumo detectado por la cámara:", df_insumos["Nombre"].tolist())
                else:
                    st.info("📷 La cámara está actualmente apagada. Marca la casilla de arriba para encenderla.")

                st.markdown("---")
                if not df_insumos.empty:
                    opciones = df_insumos["Nombre"].tolist()
                    
                    indice_defecto = opciones.index(insumo_detectado) if insumo_detectado in opciones else 0
                    seleccionado = st.selectbox("Selecciona el insumo a modificar:", opciones, index=indice_defecto, key="sel_mov")
                    
                    if seleccionado:
                        datos_insumo = df_insumos[df_insumos["Nombre"] == seleccionado].iloc[0]
                        id_insumo = datos_insumo["id"]
                        cant_actual = int(datos_insumo["Cantidad"])
                        
                        st.info(f"Cantidad actual en bodega: **{cant_actual}** unidades.")
                        st.markdown(f"💰 **Precios:** Técnico: *{datos_insumo['Precio Técnico']} Bs.* | Cliente: *{datos_insumo['Precio Cliente']} Bs.* | Facturado: *{datos_insumo['Precio Facturado']} Bs.*")
                        
                        tipo_movimiento = st.radio("Tipo de movimiento:", ["Agregar Stock (Entrada)", "Restar Stock (Salida)"], horizontal=True)
                        
                        motivo_salida = ""
                        empresa_destino = ""
                        area_o_precio_destino = ""
                        agencia_destino = ""
                        val_unit = 0.0
                        
                        cont_anterior = 0
                        cont_actual = 0
                        paginas_calculadas = 0
                        dias_calculados = 0
                        
                        if tipo_movimiento == "Restar Stock (Salida)":
                            col_mot1, col_mot2 = st.columns(2)
                            with col_mot1:
                                motivo_salida = st.selectbox("Motivo de la Salida:", ["Venta", "Alquiler"])
                            
                            if motivo_salida == "Venta":
                                with col_mot2:
                                    tipo_precio_aplicado = st.selectbox(
                                        "🏷️ Esquema de Precio Aplicado:",
                                        ["Precio Técnico", "Precio Cliente", "Precio Facturado"]
                                    )
                                    area_o_precio_destino = tipo_precio_aplicado
                                    
                                    if tipo_precio_aplicado == "Precio Técnico":
                                        val_unit = float(datos_insumo['Precio Técnico'])
                                    elif tipo_precio_aplicado == "Precio Cliente":
                                        val_unit = float(datos_insumo['Precio Cliente'])
                                    else:
                                        val_unit = float(datos_insumo['Precio Facturado'])
                                    st.caption(f"Valor Unitario: *{val_unit} Bs.*")
                            
                            elif motivo_salida == "Alquiler":
                                # Estas columnas SOLO se crean si el motivo es Alquiler
                                col_al_dest1, col_al_dest2 = st.columns(2)
                
                                with col_al_dest1:
                                    empresa_destino = st.selectbox("🏢 Empresa:", empresas_disponibles)
                                    agencias_filtradas = [ag for ag in agencias_disponibles if ag.startswith(empresa_destino.strip())]
                                    agencia_destino = st.selectbox(
                                    "🏢 Agencia:", 
                                    agencias_filtradas, 
                                    format_func=lambda x: x.replace(empresa_destino + " - ", "")
                                    )

                                with col_al_dest2:
                                    areas_filtradas = [ar for ar in areas_disponibles if ar.startswith(agencia_destino)]
                                    area_o_precio_destino = st.selectbox(
                                    "📍 Área:", 
                                    areas_filtradas, 
                                    format_func=lambda x: x.replace(agencia_destino + " - ", "")
                                    )
                    
                                st.markdown("---")
                                st.markdown("📊 **Control de Contadores (Alquiler)**")
                
                                # Solo buscar el historial si el motivo es Alquiler
                                ultimo_registro_alq = obtener_ultimo_alquiler(seleccionado, empresa_destino, area_o_precio_destino, agencia_destino)
                                
                                # Buscar historial de contadores filtrando por Empresa, Área y Agencia de manera precisa
                                ultimo_registro_alq = obtener_ultimo_alquiler(seleccionado, empresa_destino, area_o_precio_destino, agencia_destino)
                                
                                sugerencia_anterior = 0
                                fecha_ultimo_alquiler = None
                                
                                if ultimo_registro_alq is not None:
                                    try:
                                        sugerencia_anterior = int(ultimo_registro_alq["Contador Actual"])
                                        fecha_ultimo_alquiler = pd.to_datetime(ultimo_registro_alq["Fecha"], errors='coerce')
                                        st.success(f"🔍 ¡Historial Encontrado! Último contador registrado: **{sugerencia_anterior}** el {ultimo_registro_alq['Fecha']}")
                                    except:
                                        pass
                                else:
                                    st.warning("⚠️ No se encontró un alquiler previo idéntico para este Insumo, Empresa, Área y Agencia. Se iniciará con contador base 0.")
                                
                                # --- CONTROL DE SEGURIDAD PARA CONTADOR ANTERIOR ---
                                col_c1, col_c2 = st.columns(2)
                                with col_c1:
                                    if st.session_state["rol_actual"] == "Administrador":
                                        cont_anterior = st.number_input(
                                            "Contador Anterior (Editable - Admin):", 
                                            min_value=0, 
                                            step=1, 
                                            value=int(sugerencia_anterior)
                                        )
                                    else:
                                        cont_anterior = sugerencia_anterior
                                        st.metric(label="Contador Anterior (Bloqueado)", value=cont_anterior)
                                        st.caption("🔒 El contador anterior es automático. Solo un Administrador puede cambiarlo.")
                                
                                with col_c2:
                                    cont_actual = st.number_input(
                                        "Contador Actual (Lectura de hoy):", 
                                        min_value=int(cont_anterior), 
                                        step=1, 
                                        value=int(cont_anterior)
                                    )
                                
                                paginas_calculadas = cont_actual - cont_anterior
                                
                                hoy = obtener_hora_local_bo()
                                if fecha_ultimo_alquiler is not None and not pd.isna(fecha_ultimo_alquiler):
                                    if fecha_ultimo_alquiler.tzinfo is None:
                                        fecha_ultimo_alquiler = fecha_ultimo_alquiler.replace(tzinfo=timezone(timedelta(hours=-4)))
                                    dif_tiempo = hoy - fecha_ultimo_alquiler
                                    dias_calculados = max(0, dif_tiempo.days)
                                else:
                                    dias_calculados = 0 
                                    
                                st.info(f"📑 **Páginas Impresas:** {paginas_calculadas} págs. | 📅 **Duración del Periodo:** {dias_calculados} días.")
                        
                        cantidad_mov = st.number_input("Cantidad a mover:", min_value=1, step=1, value=1)
                        
                        if tipo_movimiento == "Restar Stock (Salida)" and motivo_salida == "Venta":
                            st.write(f"💵 **Total de la Venta Estimado:** {val_unit * cantidad_mov:,.2f} Bs.")
                        
                        if st.button("Aplicar Movimiento"):
                            es_valido = True
                            if tipo_movimiento == "Restar Stock (Salida)" and cantidad_mov > cant_actual:
                                st.error(f"❌ Error: No puedes retirar {cantidad_mov} unidades porque solo quedan {cant_actual} en stock.")
                                es_valido = False
                            
                            if tipo_movimiento == "Restar Stock (Salida)" and motivo_salida == "Alquiler":
                                if not str(empresa_destino).strip() or not str(area_o_precio_destino).strip():
                                    st.error("❌ Error: Para registrar un alquiler debes seleccionar la Empresa y el Área de destino.")
                                    es_valido = False
                                    
                            if es_valido:
                                if tipo_movimiento == "Agregar Stock (Entrada)":
                                    nueva_cantidad = cant_actual + cantidad_mov
                                    tipo_historial = "Entrada"
                                    motivo_final = "Abastecimiento"
                                else:
                                    nueva_cantidad = cant_actual - cantidad_mov
                                    tipo_historial = "Salida"
                                    motivo_final = motivo_salida
                                
                                with st.spinner("Actualizando datos en la nube..."):
                                    actualizar_stock_sheet(
                                        id_insumo, 
                                        nueva_cantidad, 
                                        seleccionado, 
                                        tipo_historial, 
                                        cantidad_mov,
                                        motivo=motivo_final,
                                        empresa=empresa_destino,
                                        area_o_precio=area_o_precio_destino,
                                        precio_unitario=val_unit,
                                        contador_anterior=cont_anterior,
                                        contador_actual=cont_actual,
                                        paginas=paginas_calculadas,
                                        dias=dias_calculados,
                                        agencia=agencia_destino
                                    )
                                st.success(f"¡Stock actualizado! Ahora tienes {nueva_cantidad} unidades de '{seleccionado}'.")
                                st.cache_data.clear()
                                st.cache_resource.clear()
                                st.rerun()
                else:
                    st.info("Registra un insumo para habilitar los movimientos.")
                # --- TABLA Y BUSCADOR EXCLUSIVOS DE OPERACIONES DE STOCK ---
                st.markdown("---")
                st.subheader("🔍 Buscador y Lista de Existencias")
                busqueda = st.text_input("Buscar insumo por nombre o categoría:", placeholder="Escribe aquí para buscar...")

                if not df_insumos.empty:
                    df_filtrado = df_insumos[
                        df_insumos["Nombre"].astype(str).str.lower().str.contains(busqueda.lower()) |
                        df_insumos["Categoria"].astype(str).str.lower().str.contains(busqueda.lower())
                    ]

                    st.dataframe(df_filtrado, use_container_width=True)

                    if st.session_state.get("rol_actual") == "Administrador":
                        with st.expander("🚨 Zona de Administración: Eliminar Insumos"):
                            insumo_a_borrar = st.selectbox("Selecciona insumo a eliminar:", df_filtrado["Nombre"].tolist())
                            if st.button("Confirmar Eliminación"):
                                id_a_borrar = df_filtrado[df_filtrado["Nombre"] == insumo_a_borrar]["ID"].values[0]
                                if eliminar_insumo(id_a_borrar):
                                    st.success(f"Insumo '{insumo_a_borrar}' eliminado.")
                                    st.rerun()
                                else:
                                    st.error("No se pudo eliminar.")
# ----------------------------------------------------------------------------------
# 2. PESTAÑA DE VALORIZACIÓN DEL INVENTARIO
# ----------------------------------------------------------------------------------
if st.session_state.get("menu_activo") == "Valorización del Inventario":
    if st.session_state.get("rol_actual") == "Administrador":
        st.subheader("💰 Resumen Monetario del Inventario")

        try:
            supabase = conectar_supabase()
            res_ins = supabase.table("Insumos").select("*").execute()
            datos_ins = res_ins.data

            if datos_ins:
                df_insumos = pd.DataFrame(datos_ins)

                # Convertir columnas a tipo numérico de forma segura
                cols_numericas = ["Cantidad", "Precio Tecnico", "Precio Cliente", "Precio Facturado"]
                for col in cols_numericas:
                    if col in df_insumos.columns:
                        df_insumos[col] = pd.to_numeric(df_insumos[col], errors='coerce').fillna(0)
                    else:
                        df_insumos[col] = 0.0

                df_insumos["Val_Tecnico"] = df_insumos["Cantidad"] * df_insumos["Precio Tecnico"]
                df_insumos["Val_Cliente"] = df_insumos["Cantidad"] * df_insumos["Precio Cliente"]
                df_insumos["Val_Facturado"] = df_insumos["Cantidad"] * df_insumos["Precio Facturado"]

                total_tecnico = df_insumos["Val_Tecnico"].sum()
                total_cliente = df_insumos["Val_Cliente"].sum()
                total_facturado = df_insumos["Val_Facturado"].sum()

                c1, c2, c3 = st.columns(3)
                c1.metric(label="Total Valor Técnico", value=f"{total_tecnico:,.2f} Bs.")
                c2.metric(label="Total Valor Cliente", value=f"{total_cliente:,.2f} Bs.")
                c3.metric(label="Total Valor Facturado", value=f"{total_facturado:,.2f} Bs.")

                st.markdown("---")
                st.write("📊 **Comparativa de Valorización por Insumo**")

                col_nombre = "Nombre" if "Nombre" in df_insumos.columns else df_insumos.columns[0]

                df_melted = df_insumos.melt(
                    id_vars=[col_nombre],
                    value_vars=["Val_Tecnico", "Val_Cliente", "Val_Facturado"],
                    var_name="Tipo de Precio",
                    value_name="Valor Total (Bs.)"
                )

                df_melted["Tipo de Precio"] = df_melted["Tipo de Precio"].replace({
                    "Val_Tecnico": "Técnico",
                    "Val_Cliente": "Cliente",
                    "Val_Facturado": "Facturado"
                })

                fig_val = px.bar(
                    df_melted,
                    x=col_nombre,
                    y="Valor Total (Bs.)",
                    color="Tipo de Precio",
                    barmode="group",
                    title="Valor total de existencias por esquema de precios",
                    text_auto=True
                )

                st.plotly_chart(fig_val, use_container_width=True)
            else:
                st.info("No hay datos de insumos para calcular la valorización.")
        except Exception as e:
            st.error(f"Error al obtener la valorización desde Supabase: {e}")
    else:
        st.warning("🔒 Esta sección es exclusiva para Administradores.")


# ==========================================
# 3. PESTAÑA DE RENDIMIENTO DE INSUMOS
# ==========================================
if st.session_state["menu_activo"] == "Rendimiento de Insumos":
    st.subheader("📊 Análisis de Rendimiento Promedio de Insumos")
    st.write("Esta sección calcula el rendimiento histórico del equipamiento/tóner en función de las copias realizadas y el tiempo útil de uso.")

    try:
        supabase = conectar_supabase()
        response = supabase.table("Alquileres").select("*").execute()
        df_rend = pd.DataFrame(response.data)

        if not df_rend.empty:
            df_rend["Páginas Impresas"] = pd.to_numeric(df_rend.get("Páginas Impresas", 0), errors="coerce").fillna(0)
            df_rend["Días Transcurridos"] = pd.to_numeric(df_rend.get("Días Transcurridos", 0), errors="coerce").fillna(0)

            df_rend_filtrado = df_rend[(df_rend["Páginas Impresas"] > 0) | (df_rend["Días Transcurridos"] > 0)]

            if not df_rend_filtrado.empty:
                # --- Selector / Buscador de Insumo ---
                lista_insumos_disponibles = ["Todos"] + sorted(df_rend_filtrado["Insumo"].dropna().unique().tolist())
                insumo_seleccionado = st.selectbox("Filtrar por Insumo:", lista_insumos_disponibles, key="filtro_rendimiento_insumo")

                if insumo_seleccionado != "Todos":
                    df_rend_filtrado = df_rend_filtrado[df_rend_filtrado["Insumo"] == insumo_seleccionado]

                df_promedios = df_rend_filtrado.groupby("Insumo").agg(
                    Promedio_Paginas=("Páginas Impresas", "mean"),
                    Promedio_Dias=("Días Transcurridos", "mean"),
                    Total_Registros=("Insumo", "count")
                ).reset_index()

                df_promedios.columns = ["Insumo", "Páginas Promedio por Periodo", "Duración Promedio (Días)", "Nº Mediciones Realizadas"]

                st.write("📊 **Tabla de Rendimiento Promedio por Insumo**")

                df_promedios_con_num = df_promedios.copy()
                df_promedios_con_num.insert(0, "#", range(1, len(df_promedios_con_num) + 1))
                st.dataframe(df_promedios_con_num, use_container_width=True, hide_index=True)

                st.markdown("---")
                col_graf1, col_graf2 = st.columns(2)

                with col_graf1:
                    fig_pag = px.bar(
                        df_promedios,
                        x="Insumo",
                        y="Páginas Promedio por Periodo",
                        title="Promedio de Páginas Impresas por Insumo",
                        labels={"Páginas Promedio por Periodo": "Páginas Promedio"},
                        text_auto='.0f',
                        color="Insumo"
                    )
                    st.plotly_chart(fig_pag, use_container_width=True)

                with col_graf2:
                    fig_dias = px.bar(
                        df_promedios,
                        x="Insumo",
                        y="Duración Promedio (Días)",
                        title="Duración Promedio en Destino (Días)",
                        labels={"Duración Promedio (Días)": "Días Promedio"},
                        text_auto='.1f',
                        color="Insumo"
                    )
                    st.plotly_chart(fig_dias, use_container_width=True)
            else:
                st.warning("Aún no existen registros de alquiler con lecturas mayores a cero para realizar el análisis de rendimiento.")
        else:
            st.info("No se encontraron registros en la pestaña de Alquileres.")
    except Exception as e:
        st.error(f"No se pudo cargar el análisis de rendimiento: {e}")


# ==========================================
# 4. PESTAÑA DE REPORTES Y EDICIÓN/ELIMINACIÓN
# ==========================================
if st.session_state["menu_activo"] == "Reportes por Fecha / Edición":
    st.subheader("📅 Reportes de Inventario y Herramientas de Edición")
    
    tab_rep_general, tab_rep_ventas, tab_rep_alquileres, tab_admin_borrado = st.tabs([
        "📊 Historial General", 
        "💵 Historial de Ventas", 
        "🏗️ Historial de Alquileres",
        "🚨 Edición y Borrado (Admin)"
    ])
    
    # --- 1. SUBPESTAÑA GENERAL ---
    with tab_rep_general:
        st.write("🔍 **Filtro por Rango de Fechas**")
        col_fg1, col_fg2 = st.columns(2)
        with col_fg1:
            fecha_inicio_gen = st.date_input("Desde (General):", value=obtener_hora_local_bo().date(), key="f_gen_ini")
        with col_fg2:
            fecha_fin_gen = st.date_input("Hasta (General):", value=obtener_hora_local_bo().date(), key="f_gen_fin")

        try:
            supabase = conectar_supabase()
            response = supabase.table("Historial").select("*").execute()
            df_hist = pd.DataFrame(response.data)
        except Exception as e:
            st.error(f"Error al obtener el historial: {e}")
            df_hist = pd.DataFrame()

        if not df_hist.empty and "Fecha" in df_hist.columns:
            df_hist["Fecha_dt"] = pd.to_datetime(df_hist["Fecha"], errors='coerce')
            df_filtrado_fecha = df_hist[(df_hist["Fecha_dt"].dt.date >= fecha_inicio_gen) & (df_hist["Fecha_dt"].dt.date <= fecha_fin_gen)]

            if df_filtrado_fecha.empty:
                st.warning("No se registraron movimientos en este rango.")
            else:
                df_mostrar = df_filtrado_fecha.drop(columns=["Fecha_dt"], errors='ignore').copy()

                # --- LIMPIEZA INTELIGENTE PARA AGENCIA Y ÁREA EN HISTORIAL ---
                for col_agencia in ["Agencia Destino", "Agencia"]:
                    if col_agencia in df_mostrar.columns:
                        df_mostrar[col_agencia] = df_mostrar[col_agencia].apply(
                            lambda x: str(x).split(" - ")[-1].strip() if " - " in str(x) else str(x)
                        )

                for col_area in ["Area Destino", "Area", "Detalle"]:
                    if col_area in df_mostrar.columns:
                        df_mostrar[col_area] = df_mostrar[col_area].apply(
                            lambda x: str(x).split(" - ")[-1].strip() if " - " in str(x) else str(x)
                        )

                df_mostrar.insert(0, "#", range(1, len(df_mostrar) + 1))
                st.dataframe(df_mostrar, use_container_width=True, hide_index=True)

                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    df_mostrar.to_excel(writer, sheet_name='Historial_General', index=False)
                st.download_button("Descargar Reporte General (Excel)", data=buffer.getvalue(), file_name=f"Reporte_General_{fecha_inicio_gen}_a_{fecha_fin_gen}.xlsx")
        else:
            st.info("Historial vacío.")

    # --- 2. SUBPESTAÑA VENTAS ---
    with tab_rep_ventas:
        st.write("📅 **Segmentación Mensual de Ventas**")
        try:
            supabase = conectar_supabase()
            response = supabase.table("Ventas").select("*").execute()
            df_v = pd.DataFrame(response.data)
        except Exception as e:
            st.error(f"Error al obtener los datos de ventas: {e}")
            df_v = pd.DataFrame()

        if not df_v.empty and "Fecha" in df_v.columns:
            df_v["Fecha_dt"] = pd.to_datetime(df_v["Fecha"], errors='coerce')
            df_v["Año"] = df_v["Fecha_dt"].dt.year
            df_v["Mes_Num"] = df_v["Fecha_dt"].dt.month

            meses_es = {
                1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
                7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
            }
            df_v["Mes"] = df_v["Mes_Num"].map(meses_es)
            anos_disponibles = sorted(df_v["Año"].dropna().unique().astype(int).tolist(), reverse=True)

            col_v1, col_v2 = st.columns(2)
            with col_v1:
                ano_seleccionado = st.selectbox("Selecciona el Año:", anos_disponibles if anos_disponibles else [obtener_hora_local_bo().year])

            meses_del_ano = df_v[df_v["Año"] == ano_seleccionado]["Mes_Num"].dropna().unique()
            meses_opciones = [meses_es[m] for m in sorted(meses_del_ano) if m in meses_es]

            with col_v2:
                mes_seleccionado = st.selectbox("Selecciona el Mes:", meses_opciones if meses_opciones else ["Ninguno"])

            mes_num_sel = [k for k, v in meses_es.items() if v == mes_seleccionado][0] if mes_seleccionado != "Ninguno" else None
            df_filtrado_v = df_v[(df_v["Año"] == ano_seleccionado) & (df_v["Mes_Num"] == mes_num_sel)]

            if df_filtrado_v.empty:
                st.warning(f"No se registraron ventas en {mes_seleccionado} del {ano_seleccionado}.")
            else:
                df_v_mostrar = df_filtrado_v.drop(columns=["Fecha_dt", "Año", "Mes_Num", "Mes"], errors='ignore').copy()
                
                col_monto = "Total Venta" if "Total Venta" in df_v_mostrar.columns else ("Monto Total (Bs.)" if "Monto Total (Bs.)" in df_v_mostrar.columns else None)
                suma_ventas = pd.to_numeric(df_v_mostrar[col_monto], errors='coerce').sum() if col_monto else 0.0

                st.success(f"💰 **Monto Total Facturado en {mes_seleccionado} del {ano_seleccionado}:** {suma_ventas:,.2f} Bs.")

                df_v_mostrar.insert(0, "#", range(1, len(df_v_mostrar) + 1))
                st.dataframe(df_v_mostrar, use_container_width=True, hide_index=True)

                buffer_v = io.BytesIO()
                with pd.ExcelWriter(buffer_v, engine='openpyxl') as writer:
                    df_v_mostrar.to_excel(writer, sheet_name=f'Ventas_{mes_seleccionado}_{ano_seleccionado}', index=False)
                st.download_button(
                    label=f"📥 Descargar Ventas de {mes_seleccionado} - {ano_seleccionado} (Excel)",
                    data=buffer_v.getvalue(),
                    file_name=f"Ventas_{mes_seleccionado}_{ano_seleccionado}.xlsx"
                )
        else:
            st.info("No se han registrado ventas en la base de datos todavía.")

    # --- 3. SUBPESTAÑA ALQUILERES ---
    with tab_rep_alquileres:
        st.write("🔍 **Búsqueda Filtrada de Alquileres**")
        try:
            supabase = conectar_supabase()
            response = supabase.table("Alquileres").select("*").execute()
            df_a = pd.DataFrame(response.data)
        except Exception as e:
            st.error(f"Error al obtener los alquileres: {e}")
            df_a = pd.DataFrame()

        if not df_a.empty:
            st.write("📊 Total de filas leídas de la base de datos:", len(df_a))

            col_empresa = "Empresa" if "Empresa" in df_a.columns else ("Empresa Destino" if "Empresa Destino" in df_a.columns else None)
            col_agencia = "Agencia" if "Agencia" in df_a.columns else ("Agencia Destino" if "Agencia Destino" in df_a.columns else None)

            # # 1. Selector de Empresa
            if col_empresa:
                lista_empresas = ["Todas"] + sorted(df_a[col_empresa].dropna().astype(str).unique().tolist())
                empresa_sel = st.selectbox("Seleccione Empresa:", lista_empresas)
                df_temp = df_a if empresa_sel == "Todas" else df_a[df_a[col_empresa] == empresa_sel]
            else:
                empresa_sel = "Todas"
                df_temp = df_a.copy()

            # # 2. Selector de Agencia
            if col_agencia and not df_temp.empty:
                agencias_raw = sorted(df_temp[col_agencia].dropna().astype(str).unique().tolist())
                agencias_limpias = sorted(list(set([str(a).split(" - ")[-1].strip() if " - " in str(a) else str(a) for a in agencias_raw])))
                mapeo_agencias = {str(a).split(" - ")[-1].strip() if " - " in str(a) else str(a): a for a in agencias_raw}

                agencia_display = st.selectbox("Seleccione Agencia:", ["Todas"] + agencias_limpias)
                agencia_sel = "Todas" if agencia_display == "Todas" else mapeo_agencias.get(agencia_display, agencia_display)
                df_filtrado_a = df_temp if agencia_display == "Todas" else df_temp[df_temp[col_agencia] == agencia_sel]
            else:
                df_filtrado_a = df_temp.copy()

            # # 3. Fechas
            col_fa1, col_fa2 = st.columns(2)
            with col_fa1:
                fecha_inicio_alq = st.date_input("Desde:", value=obtener_hora_local_bo().date(), key="f_alq_ini_new")
            with col_fa2:
                fecha_fin_alq = st.date_input("Hasta:", value=obtener_hora_local_bo().date(), key="f_alq_fin_new")

            # Filtro de fecha
            if "Fecha" in df_filtrado_a.columns:
                df_filtrado_a["Fecha_dt"] = pd.to_datetime(df_filtrado_a["Fecha"], errors='coerce')
                df_filtrado_a = df_filtrado_a[
                    (df_filtrado_a["Fecha_dt"].dt.date >= fecha_inicio_alq) &
                    (df_filtrado_a["Fecha_dt"].dt.date <= fecha_fin_alq)
                ]

            if df_filtrado_a.empty:
                st.warning("No se encontraron registros con los filtros seleccionados.")
            else:
                df_a_mostrar = df_filtrado_a.drop(columns=["Fecha_dt"], errors='ignore').copy()

                # --- LIMPIEZA LIMPIA PARA LA VISTA ---
                for c_ag in ["Agencia", "Agencia Destino"]:
                    if c_ag in df_a_mostrar.columns:
                        df_a_mostrar[c_ag] = df_a_mostrar[c_ag].apply(
                            lambda x: str(x).split(" - ")[-1].strip() if " - " in str(x) else str(x)
                        )

                for c_ar in ["Area", "Area Destino"]:
                    if c_ar in df_a_mostrar.columns:
                        df_a_mostrar[c_ar] = df_a_mostrar[c_ar].apply(
                            lambda x: str(x).split(" - ")[-1].strip() if " - " in str(x) else str(x)
                        )

                if "Nº" in df_a_mostrar.columns:
                    df_a_mostrar = df_a_mostrar.drop(columns=["Nº"])

                df_a_mostrar.insert(0, "#", range(1, len(df_a_mostrar) + 1))
                st.dataframe(df_a_mostrar, use_container_width=True, hide_index=True)

                buffer_a = io.BytesIO()
                with pd.ExcelWriter(buffer_a, engine='openpyxl') as writer:
                    df_a_mostrar.to_excel(writer, index=False)
                st.download_button("Descargar Reporte (Excel)", data=buffer_a.getvalue(), file_name="Reporte_Alquileres.xlsx")
        else:
            st.info("No hay datos en la pestaña de Alquileres.")

    # --- 4. SUBPESTAÑA ADM BORRADO / MODIFICACIÓN ---
    with tab_admin_borrado:
        if st.session_state.get("rol_actual") == "Administrador":
            st.warning("⚠️ **Zona de Edición Crítica:** Como Administrador, puedes depurar y eliminar registros del historial general, ventas o alquileres si hubo un error.")

            tipo_tabla_editar = st.selectbox("Selecciona el Historial a depurar:", ["Alquileres", "Ventas", "Historial General"])

            mapeo_tablas = {
                "Alquileres": "Alquileres",
                "Ventas": "Ventas",
                "Historial General": "Historial"
            }
            tabla_nombre = mapeo_tablas[tipo_tabla_editar]

            try:
                supabase = conectar_supabase()
                response = supabase.table(tabla_nombre).select("*").execute()
                datos_crud = response.data

                if datos_crud:
                    df_crud = pd.DataFrame(datos_crud)

                    st.write("Selecciona el registro que deseas eliminar permanentemente de Supabase:")

                    df_crud_visual = df_crud.copy()
                    df_crud_visual.insert(0, "#", range(1, len(df_crud_visual) + 1))
                    st.dataframe(df_crud_visual, use_container_width=True, hide_index=True)

                    options_eliminar = {}
                    for index, row in df_crud.iterrows():
                        reg_id = row.get("id", index)
                        fecha_r = row.get("Fecha", "Sin Fecha")
                        insumo_r = row.get("Insumo", "Sin Insumo")
                        det_r = row.get("Empresa", row.get("Empresa Destino", row.get("Area Destino", row.get("Motivo", ""))))
                        label = f"ID: {reg_id} | {fecha_r} | {insumo_r} | {det_r}"
                        options_eliminar[label] = row

                    seleccion_label = st.selectbox("Selecciona la fila a eliminar:", list(options_eliminar.keys()))

                    if seleccion_label:
                        registro_sel = options_eliminar[seleccion_label]
                        st.error(f"🚨 ¿Estás completamente seguro de eliminar permanentemente este registro de **{tipo_tabla_editar}**?")
                        confirmacion_borrado = st.text_input("Escribe 'ELIMINAR' en mayúsculas para proceder:")

                        if st.button("Proceder con la Eliminación"):
                            if confirmacion_borrado == "ELIMINAR":
                                with st.spinner("Eliminando registro en Supabase..."):
                                    if "id" in registro_sel and pd.notna(registro_sel["id"]):
                                        supabase.table(tabla_nombre).delete().eq("id", registro_sel["id"]).execute()
                                    else:
                                        query = supabase.table(tabla_nombre).delete()
                                        if "Fecha" in registro_sel:
                                            query = query.eq("Fecha", registro_sel["Fecha"])
                                        if "Insumo" in registro_sel:
                                            query = query.eq("Insumo", registro_sel["Insumo"])
                                        query.execute()

                                    st.success("¡Registro eliminado exitosamente!")
                                    st.cache_data.clear()
                                    st.cache_resource.clear()
                                    st.rerun()
                            else:
                                st.error("Debes ingresar la palabra 'ELIMINAR' para confirmar.")
                else:
                    st.info("No hay datos disponibles en este historial para depurar.")
            except Exception as e:
                st.error(f"Error al cargar herramientas de borrado: {e}")
        else:
            st.info("🔒 Solo la cuenta de Administrador tiene privilegios de eliminación de registros.")

# ==========================================
# 5. PESTAÑA DE CONFIGURACIÓN Y USUARIOS
# ==========================================
if st.session_state["menu_activo"] == "Configuración y Gestión de Usuarios":
    if st.session_state["rol_actual"] == "Administrador":
        
        st.subheader("⚙️ Configuración y Gestión de Usuarios")
        
        tab_sub_usuarios, tab_sub_parametros = st.tabs(["👥 Cuentas de Usuarios", "🏢 Parámetros de Alquiler (Empresas/Áreas/Agencias)"])
        
        with tab_sub_usuarios:
            col_user_izq, col_user_der = st.columns([1, 1.5])
            
            with col_user_izq:
                st.write("➕ **Crear Nuevo Usuario**")
                with st.form("nuevo_usuario_form", clear_on_submit=True):
                    nuevo_user = st.text_input("Nombre de Usuario", placeholder="Ej: tecnico.juan")
                    nuevo_pass = st.text_input("Contraseña", type="password", placeholder="Ej: t1234")
                    nuevo_rol = st.selectbox("Asignar Rol:", ["Administrador", "Secretaria", "Técnico"])
                    crear_user_btn = st.form_submit_button("Crear Usuario")
                    
                if crear_user_btn:
                    df_actual_users = obtener_usuarios()
                    if nuevo_user.strip() == "" or nuevo_pass.strip() == "":
                        st.error("Todos los campos son obligatorios.")
                    elif nuevo_user in df_actual_users["Usuario"].values:
                        st.warning("Este nombre de usuario ya está registrado.")
                    else:
                        with st.spinner("Registrando nuevo usuario..."):
                            registrar_usuario(nuevo_user, nuevo_pass, nuevo_rol)
                        st.success(f"¡Usuario '{nuevo_user}' registrado exitosamente como '{nuevo_rol}'!")
                        st.cache_data.clear()
                        st.rerun()
                        
            st.write("📋 **Gestionar Usuarios**")
            df_usuarios = obtener_usuarios()
            
            # Selector para elegir el usuario a gestionar
            user_sel = st.selectbox("Selecciona usuario para gestionar:", df_usuarios["Usuario"].tolist())
            
            if user_sel:
                datos_user = df_usuarios[df_usuarios["Usuario"] == user_sel].iloc[0]
                
                with st.expander("✏️ Editar Usuario"):
                    with st.form("form_editar_user"):
                        new_u = st.text_input("Nuevo Nombre", value=datos_user["Usuario"])
                        new_p = st.text_input("Nueva Contraseña", value=datos_user["Contraseña"])
                        new_r = st.selectbox("Nuevo Rol", ["Administrador", "Secretaria", "Técnico"], 
                                           index=["Administrador", "Secretaria", "Técnico"].index(datos_user["Rol"]))
                        
                        if st.form_submit_button("Guardar Cambios"):
                            editar_usuario(user_sel, new_u, new_p, new_r)
                            st.success("Usuario actualizado")
                            st.rerun()

                if st.button("🗑️ Eliminar este usuario"):
                    if user_sel == st.session_state["usuario_actual"]:
                        st.error("No puedes eliminar tu propio usuario mientras estás conectado.")
                    else:
                        eliminar_usuario(user_sel)
                        st.warning(f"Usuario {user_sel} eliminado")
                        st.rerun()
                
        with tab_sub_parametros:
            col_param_izq, col_param_der = st.columns([1.2, 2.0])
            
            # --- COLUMNA IZQUIERDA: FORMULARIOS DE REGISTRO INTELIGENTE (RELACIONAL) ---
            with col_param_izq:
                st.write("### ➕ Añadir Nuevo Destino")
                
                # 1. FORMULARIO EMPRESA
                with st.form("nueva_empresa_form", clear_on_submit=True):
                    st.write("**1. Nueva Empresa / Cliente**")
                    nueva_emp = st.text_input("Nombre de la Empresa:", placeholder="Ej: Constructora Gamma")
                    guardar_emp_btn = st.form_submit_button("Añadir Empresa")
                    
                if guardar_emp_btn:
                    if nueva_emp.strip() == "":
                        st.error("Por favor, escribe un nombre válido.")
                    elif nueva_emp.strip() in empresas_disponibles:
                        st.warning("Esta empresa ya se encuentra registrada.")
                    else:
                        with st.spinner("Guardando empresa..."):
                            registrar_parametro(nueva_emp.strip(), "Empresa")
                        st.success(f"¡Empresa '{nueva_emp}' añadida correctamente!")
                        st.cache_data.clear()
                        st.rerun()
                        
                st.markdown("---")
                
                # 2. FORMULARIO AGENCIA (RELACIONADO CON EMPRESA)
                empresas_para_seleccion = [e for e in empresas_disponibles if e not in ["Sin Registrar", ""]]
                with st.form("nueva_agencia_form", clear_on_submit=True):
                    st.write("**2. Nueva Agencia (Relacionada con Empresa)**")
                    if empresas_para_seleccion:
                        empresa_seleccionada_ag = st.selectbox("Selecciona a qué Empresa corresponde:", empresas_para_seleccion)
                        nueva_ag_nombre = st.text_input("Nombre de la Agencia:", placeholder="Ej: Sucursal Norte")
                        guardar_ag_btn = st.form_submit_button("Añadir Agencia")
                    else:
                        st.info("⚠️ Registra una empresa primero para poder agregar agencias.")
                        guardar_ag_btn = False
                    
                if guardar_ag_btn:
                    if nueva_ag_nombre.strip() == "":
                        st.error("Por favor, escribe un nombre de agencia válido.")
                    else:
                        nueva_ag_completa = f"{empresa_seleccionada_ag} - {nueva_ag_nombre.strip()}"
                        if nueva_ag_completa in agencias_disponibles:
                            st.warning("Esta agencia ya se encuentra registrada para esta empresa.")
                        else:
                            with st.spinner("Guardando agencia..."):
                                registrar_parametro(nueva_ag_completa, "Agencia")
                            st.success(f"¡Agencia '{nueva_ag_completa}' añadida correctamente!")
                            st.cache_data.clear()
                            st.rerun()
                
                st.markdown("---")
                
                # 3. FORMULARIO ÁREA (RELACIONADO CON AGENCIA)
                agencias_para_seleccion = [ag for ag in agencias_disponibles if ag not in ["Sin Registrar", ""]]
                with st.form("nueva_area_form", clear_on_submit=True):
                    st.write("**3. Nueva Área / Obra (Relacionada con Agencia)**")
                    if agencias_para_seleccion:
                        agencia_seleccionada_ar = st.selectbox("Selecciona a qué Agencia corresponde:", agencias_para_seleccion)
                        nueva_ar_nombre = st.text_input("Nombre del Área / Obra:", placeholder="Ej: Proyecto Piso 2")
                        guardar_ar_btn = st.form_submit_button("Añadir Área")
                    else:
                        st.info("⚠️ Registra una agencia primero para poder asociar un área.")
                        guardar_ar_btn = False
                    
                if guardar_ar_btn:
                    if nueva_ar_nombre.strip() == "":
                        st.error("Por favor, escribe un nombre de área válido.")
                    else:
                        nueva_ar_completa = f"{agencia_seleccionada_ar} - {nueva_ar_nombre.strip()}"
                        if nueva_ar_completa in areas_disponibles:
                            st.warning("Esta área ya se encuentra registrada para esta agencia.")
                        else:
                            with st.spinner("Guardando área..."):
                                registrar_parametro(nueva_ar_completa, "Area")
                            st.success(f"¡Área '{nueva_ar_completa}' añadida correctamente!")
                            st.cache_data.clear()
                            st.rerun()

            # --- COLUMNA DERECHA: EDICIÓN Y ELIMINACIÓN DIRECTA DESDE LOS DESTINOS ---
            with col_param_der:
                st.write("### 📋 Destinos Actuales y Configuración de Borrado")
                st.info("💡 **Acción directa:** Selecciona y elimina cualquier destino que ya no utilices directamente desde su respectiva columna.")
                
                c_emp, c_age, c_are = st.columns(3)
                
                # COLUMNA DE EMPRESAS
                with c_emp:
                    st.markdown("🏢 **Empresa**")
                    empresas_filtradas = [e for e in empresas_disponibles if e not in ["Sin Registrar", ""]]
                    for e in empresas_filtradas:
                        st.markdown(f"• {e}")
                    
                    st.markdown("---")
                    if empresas_filtradas:
                        empresa_a_borrar = st.selectbox("Eliminar Empresa:", empresas_filtradas, key="del_emp_sel")
                        conf_emp = st.checkbox("Confirmar borrado", key="conf_emp_check")
                        if st.button("🗑️ Eliminar", key="del_emp_btn"):
                            if conf_emp:
                                with st.spinner("Borrando..."):
                                    eliminar_parametro(empresa_a_borrar, "Empresa")
                                st.success("Empresa eliminada.")
                                st.cache_data.clear()
                                st.cache_resource.clear()
                                st.rerun()
                            else:
                                st.error("Confirma la casilla primero.")
                    else:
                        st.caption("No hay empresas registradas.")

                # COLUMNA DE AGENCIAS
                with c_age:
                    st.markdown("🏢 **Agencia**")
                    agencias_filtradas = [ag for ag in agencias_disponibles if ag not in ["Sin Registrar", ""]]
                    for ag in agencias_filtradas:
                        st.markdown(f"• {ag}")
                        
                    st.markdown("---")
                    if agencias_filtradas:
                        agencia_a_borrar = st.selectbox("Eliminar Agencia:", agencias_filtradas, key="del_ag_sel")
                        conf_ag = st.checkbox("Confirmar borrado", key="conf_ag_check")
                        if st.button("🗑️ Eliminar", key="del_ag_btn"):
                            if conf_ag:
                                with st.spinner("Borrando..."):
                                    eliminar_parametro(agencia_a_borrar, "Agencia")
                                st.success("Agencia eliminada.")
                                st.cache_data.clear()
                                st.cache_resource.clear()
                                st.rerun()
                            else:
                                st.error("Confirma la casilla primero.")
                    else:
                        st.caption("No hay agencias registradas.")

                # COLUMNA DE ÁREAS
                with c_are:
                    st.markdown("📍 **Área**")
                    areas_filtradas = [a for a in areas_disponibles if a not in ["Sin Registrar", ""]]
                    for a in areas_filtradas:
                        st.markdown(f"• {a}")
                        
                    st.markdown("---")
                    if areas_filtradas:
                        area_a_borrar = st.selectbox("Eliminar Área:", areas_filtradas, key="del_ar_sel")
                        conf_ar = st.checkbox("Confirmar borrado", key="conf_ar_check")
                        if st.button("🗑️ Eliminar", key="del_ar_btn"):
                            if conf_ar:
                                with st.spinner("Borrando..."):
                                    eliminar_parametro(area_a_borrar, "Area")
                                st.success("Área eliminada.")
                                st.cache_data.clear()
                                st.cache_resource.clear()
                                st.rerun()
                            else:
                                st.error("Confirma la casilla primero.")
                    else:
                        st.caption("No hay áreas registradas.")
                        
    else:
        st.warning("🔒 Esta sección es exclusiva para el Administrador de la plataforma.")
# ----------------------------------------------------------------------------------
# 6. PESTAÑA DE INSUMOS DE RESPALDO (BACKUP)
# ----------------------------------------------------------------------------------
if st.session_state.get("menu_activo") == "Insumos de Respaldo (Backup)":
    with st.expander("➕ Registrar Nuevo Insumo de Respaldo"):
        with st.form("form_nuevo_backup"):
            lista_insumos = df_insumos["Nombre"].tolist() if "df_insumos" in locals() and not df_insumos.empty else []
            insumo_nuevo_bk = st.selectbox("Seleccionar Insumo:", lista_insumos)
            cantidad_bk = st.number_input("Cantidad:", min_value=1, step=1, value=1)
            lista_empresas_avail = empresas_disponibles if 'empresas_disponibles' in locals() else []
            empresa_bk = st.selectbox("Empresa Destino:", lista_empresas_avail)

            btn_guardar_bk = st.form_submit_button("💾 Guardar Respaldo")

            if btn_guardar_bk:
                fecha_bk = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
                usuario_bk = st.session_state.get("usuario_actual", "admin")
                estado_bk = "Disponible"

                try:
                    supabase = conectar_supabase()

                    # 1. Consultar el stock actual en el inventario principal
                    res_insumo = supabase.table("Insumos").select("*").eq("Nombre", insumo_nuevo_bk).execute()

                    if res_insumo.data:
                        stock_actual = int(res_insumo.data[0].get("Cantidad", 0))

                        # 2. Validar que exista suficiente stock
                        if cantidad_bk > stock_actual:
                            st.error(f"⚠️ Stock insuficiente. Solo quedan {stock_actual} unidades de {insumo_nuevo_bk}.")
                        else:
                            # 3. Insertar el registro en la tabla Respaldo
                            registro_bk = {
                                "Fecha": fecha_bk,
                                "Insumo": insumo_nuevo_bk,
                                "Cantidad": cantidad_bk,
                                "Empresa Destino": empresa_bk,
                                "Usuario": usuario_bk,
                                "Estado": estado_bk
                            }
                            supabase.table("Respaldo").insert(registro_bk).execute()

                            # 4. Restar del stock principal en la tabla Insumos
                            nuevo_stock = stock_actual - cantidad_bk
                            supabase.table("Insumos").update({"Cantidad": nuevo_stock}).eq("Nombre", insumo_nuevo_bk).execute()

                            st.success(f"✅ Se registraron {cantidad_bk} unidades en Respaldo y se descontaron del inventario (Quedan: {nuevo_stock}).")
                            st.cache_data.clear()
                            st.rerun()
                    else:
                        st.error("No se encontró el insumo seleccionado en la base de datos.")

                except Exception as e:
                    st.error(f"Error al registrar respaldo en Supabase: {e}")

    st.subheader("📌 Gestión de Insumos de Respaldo (Backup por Empresa)")
    st.write("Consulta los insumos en stock de respaldo y asígnales Agencia, Área y contadores al momento de utilizarlos.")

    try:
        supabase = conectar_supabase()
        res_resp = supabase.table("Respaldo").select("*").execute()
        datos_resp = res_resp.data

        if datos_resp:
            df_resp = pd.DataFrame(datos_resp)

            col_estado = "Estado" if "Estado" in df_resp.columns else None
            col_empresa_dest = "Empresa Destino" if "Empresa Destino" in df_resp.columns else ("Empresa" if "Empresa" in df_resp.columns else None)

            if col_estado:
                df_disponibles = df_resp[df_resp[col_estado].astype(str).str.strip().str.lower() == "disponible"]
            else:
                df_disponibles = df_resp.copy()

            if not df_disponibles.empty and col_empresa_dest:
                empresas_backup = sorted(df_disponibles[col_empresa_dest].dropna().astype(str).unique().tolist())
                empresa_elegida = st.selectbox("Selecciona la Empresa para ver su Respaldo:", empresas_backup, key="busq_empresa_backup")

                df_filtrado_empresa = df_disponibles[df_disponibles[col_empresa_dest] == empresa_elegida].copy()

                st.markdown(f"### Insumos de Respaldo disponibles en: {empresa_elegida}")
                st.dataframe(df_filtrado_empresa, use_container_width=True, hide_index=True)

                st.markdown("---")
                st.subheader("🔄 Activar y Asignar Destino (Enviar a Alquileres)")

                with st.container():
                    opciones_map = {}
                    for idx, row in df_filtrado_empresa.iterrows():
                        reg_id = row.get("id", idx)
                        lbl = f"ID: {reg_id} - Insumo: {row.get('Insumo', '')} (Cantidad: {row.get('Cantidad', 0)})"
                        opciones_map[lbl] = row

                    item_a_usar = st.selectbox("Selecciona el insumo de respaldo a utilizar:", list(opciones_map.keys()))
                    respaldo_sel = opciones_map[item_a_usar]
                    cant_max = int(respaldo_sel.get("Cantidad", 1))

                    # 1. Filtrado de Agencias según la Empresa elegida
                    agencias_avail = agencias_disponibles if 'agencias_disponibles' in locals() else []
                    agencias_filtradas = [ag for ag in agencias_avail if str(ag).startswith(empresa_elegida.strip())]
                    if not agencias_filtradas:
                        agencias_filtradas = [f"{empresa_elegida} - Principal"]

                    col1, col2, col3 = st.columns(3)

                    with col1:
                        agencia_destino_uso = st.selectbox(
                            "Agencia:",
                            agencias_filtradas,
                            format_func=lambda x: str(x).replace(empresa_elegida.strip() + " - ", "").strip(),
                            key="backup_agencia_destino"
                        )

                    # 2. Filtrado de Áreas según la Agencia seleccionada
                    areas_avail = areas_disponibles if 'areas_disponibles' in locals() else []
                    areas_filtradas = [ar for ar in areas_avail if str(ar).startswith(agencia_destino_uso.strip())]
                    if not areas_filtradas:
                        areas_filtradas = [f"{agencia_destino_uso} - General"]

                    with col2:
                        area_destino_uso = st.selectbox(
                            "Área:",
                            areas_filtradas,
                            format_func=lambda x: str(x).replace(agencia_destino_uso.strip() + " - ", "").strip(),
                            key="backup_area_destino"
                        )

                    with col3:
                        cant_a_usar = st.number_input(
                            "Cantidad a Usar:",
                            min_value=1,
                            max_value=cant_max,
                            value=1,
                            step=1,
                            key="backup_cant_usar"
                        )

                    st.markdown("#### Control por Fechas y Duración:")

                    # Buscamos fecha anterior
                    fecha_anterior_sugerida = pd.Timestamp.now().strftime("%Y-%m-%d")
                    dias_duracion_calculados = 0

                    try:
                        insumo_temp = str(respaldo_sel.get("Insumo", ""))
                        res_alq = supabase.table("Alquileres").select("*").execute()
                        if res_alq.data:
                            df_alq_hist = pd.DataFrame(res_alq.data)
                            ins_buscado = insumo_temp.strip().lower()
                            ag_buscada = str(agencia_destino_uso).split("-")[-1].strip().lower()
                            ar_buscada = str(area_destino_uso).split("-")[-1].strip().lower()

                            def coincide_registro(row):
                                val_ins = str(row.get("Insumo", "")).strip().lower()
                                val_ag = str(row.get("Agencia Destino", "")).strip().lower()
                                val_ar = str(row.get("Area Destino", "")).strip().lower()
                                match_ins = (ins_buscado == val_ins)
                                match_ag = (ag_buscada in val_ag) or (val_ag in str(agencia_destino_uso).lower())
                                match_ar = (ar_buscada in val_ar) or (val_ar in str(area_destino_uso).lower())
                                return match_ins and match_ag and match_ar

                            df_match = df_alq_hist[df_alq_hist.apply(coincide_registro, axis=1)]
                            if not df_match.empty:
                                ultimo_registro = df_match.iloc[-1]
                                fecha_str = str(ultimo_registro.get("Fecha", "")).strip()
                                fecha_anterior_sugerida = fecha_str.split(" ")[0]
                    except Exception:
                        pass

                    st.info(f"Última fecha de cambio registrada para este insumo: **{fecha_anterior_sugerida}**")

                    col_f1, col_f2 = st.columns(2)
                    with col_f1:
                        f_anterior = st.date_input("Fecha del Cambio Anterior:", value=pd.to_datetime(fecha_anterior_sugerida).date())
                    with col_f2:
                        f_actual = st.date_input("Fecha de Hoy (Instalación de Respaldo):", value=pd.Timestamp.now().date())

                    dias_duracion_calculados = max(0, (pd.to_datetime(f_actual) - pd.to_datetime(f_anterior)).days)
                    st.success(f"⏱️ Tiempo estimado que duró el insumo anterior: **{dias_duracion_calculados} días**")

                    btn_activar = st.button("🚀 Dar de Baja en Backup y Registrar en Alquileres")

                    if btn_activar:
                        try:
                            insumo_bk = respaldo_sel.get("Insumo", "")
                            cant_disponible = int(respaldo_sel.get("Cantidad", 0))
                            empresa_bk = respaldo_sel.get("Empresa Destino", respaldo_sel.get("Empresa", ""))

                            cant_usar = int(cant_a_usar)
                            fecha_actual_str = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
                            usuario_actual = st.session_state.get("usuario_actual", "admin")

                            nueva_fila_alquiler = {
                                "Fecha": fecha_actual_str,
                                "Insumo": insumo_bk,
                                "Cantidad": cant_usar,
                                "Empresa Destino": empresa_bk,
                                "Agencia Destino": agencia_destino_uso,
                                "Area Destino": area_destino_uso,
                                "Usuario": usuario_actual,
                                "Lectura Anterior": 0,
                                "Lectura Actual": 0,
                                "Duración Días": dias_duracion_calculados
                            }

                            supabase.table("Alquileres").insert(nueva_fila_alquiler).execute()

                            # Actualizar o cambiar estado en Respaldo
                            reg_id = respaldo_sel.get("id")
                            if cant_usar >= cant_disponible:
                                if reg_id is not None:
                                    supabase.table("Respaldo").update({"Estado": "Utilizado"}).eq("id", reg_id).execute()
                                else:
                                    supabase.table("Respaldo").update({"Estado": "Utilizado"}).eq("Insumo", insumo_bk).eq("Empresa Destino", empresa_bk).execute()
                            else:
                                nueva_cant = cant_disponible - cant_usar
                                if reg_id is not None:
                                    supabase.table("Respaldo").update({"Cantidad": nueva_cant}).eq("id", reg_id).execute()
                                else:
                                    supabase.table("Respaldo").update({"Cantidad": nueva_cant}).eq("Insumo", insumo_bk).eq("Empresa Destino", empresa_bk).execute()

                            st.success(f"¡Se asignaron {cant_usar} unidad(es) de {insumo_bk} a {agencia_destino_uso} ({area_destino_uso})!")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e_act:
                            st.error(f"Error al activar respaldo: {e_act}")
            else:
                st.info("No hay insumos de respaldo disponibles para esta empresa.")
        else:
            st.info("Aún no hay registros en la sección de respaldo.")
    except Exception as e:
        st.error(f"Error al cargar la gestión de respaldos: {e}")

# =========================================================
# PESTAÑA: SERVICIOS Y SOPORTE TÉCNICO (3 ETAPAS)
# =========================================================
if st.session_state["menu_activo"] in ["Servicios y Soporte", "Servicios y Soporte Técnico"]:
    st.header("📋 Gestión de Servicios y Soporte Técnico")

    subtab_solicitar, subtab_atender, subtab_historial = st.tabs([
        "1️⃣ Registrar Solicitud (Pendiente)", 
        "2️⃣ Atender Servicio Pendiente", 
        "3️⃣ Historial de Servicios"
    ])

# ---------------------------------------------------------
# PARTE 1: REGISTRAR SOLICITUD DE SERVICIO
# ---------------------------------------------------------
    with subtab_solicitar:
        st.subheader("➕ Registrar Nueva Solicitud de Atención")
        st.caption("Llena este formulario cuando una agencia reporte un problema.")

        empresa_servicio = st.selectbox("Empresa Solicitante:", empresas_disponibles, key="serv_empresa_sol")

        agencias_serv_filtradas = [ag for ag in agencias_disponibles if ag.startswith(empresa_servicio.strip())]
        if not agencias_serv_filtradas:
            agencias_serv_filtradas = [f"{empresa_servicio} - Principal"]

        col_s1, col_s2 = st.columns(2)

    with col_s1:
        agencia_servicio = st.selectbox(
            "Agencia:", 
            agencias_serv_filtradas, 
            format_func=lambda x: x.split(" - ")[-1] if " - " in x else x,
            key="serv_agencia_sol"
        )

        areas_serv_filtradas = [ar for ar in areas_disponibles if ar.startswith(agencia_servicio.strip())]
        if not areas_serv_filtradas:
            areas_serv_filtradas = [f"{agencia_servicio} - General"]

        area_servicio = st.selectbox(
            "Área:", 
            areas_serv_filtradas, 
            format_func=lambda x: x.split(" - ")[-1] if " - " in x else x,
            key="serv_area_sol"
        )

    with col_s2:
        # Seleccionamos Fecha y Hora
        col_fecha, col_hora = st.columns(2)
        with col_fecha:
            fecha_solicitud = st.date_input("Fecha de Solicitud:", value=obtener_hora_local_bo().date(), key="serv_fecha_sol")
        with col_hora:
            hora_solicitud = st.time_input("Hora:", value=obtener_hora_local_bo().time(), key="serv_hora_sol")
            
        quien_registro = st.session_state.get("usuario_actual", "Secretaría")

    problema_falla = st.text_area(
        "Descripción del Problema o Falla Reportada:", 
        placeholder="Ejemplo: Impresora no enciende, ruido extraño, atasco de papel...",
        key="serv_problema_sol"
    )

    btn_guardar_solicitud = st.button("🚨 Registrar y Notificar Solicitud")

    if btn_guardar_solicitud:
        if not problema_falla.strip():
            st.warning("⚠️ Por favor ingresa el detalle del problema.")
        else:
            # Concatenamos fecha y hora
            fecha_hora_completa = f"{fecha_solicitud} {hora_solicitud.strftime('%H:%M')}"
            
            # Servicios ahora se guarda directamente en Supabase.
            # Antes este bloque usaba gspread/Google Sheets (append_row).
            supabase = conectar_supabase()
            nuevo_servicio = {
                "Fecha Solicitud": fecha_hora_completa,
                "Empresa": empresa_servicio,
                "Agencia": agencia_servicio,
                "Área": area_servicio,
                "Problema": problema_falla,
                "Técnico": "Sin asignar",
                "Insumos": "Ninguno",
                "Fecha Realizado": "Pendiente",
                "Estado": "Pendiente",
                "Registrado Por": quien_registro
            }
            supabase.table("Servicios").insert(nuevo_servicio).execute()
            
            enviar_notificacion_telegram(
                empresa_servicio,
                agencia_servicio,
                area_servicio,
                problema_falla,
                quien_registro
            )
            
            st.success(f"✅ Solicitud registrada con hora **{hora_solicitud.strftime('%H:%M')}** y notificada a Telegram.")
            st.rerun()

    # ---------------------------------------------------------
    # PARTE 2: ATENDER SERVICIO PENDIENTE (CON CONTADORES Y REGISTRO EN ALQUILERES)
    # ---------------------------------------------------------
    with subtab_atender:
        st.subheader("🛠️ Finalizar o Registrar Trabajo Realizado")
        st.caption("Selecciona un servicio pendiente, define el tipo de trabajo y completa la información requerida.")

        @st.cache_data(ttl=60)
        def obtener_datos_servicios_cacheados():
            # hoja_servicios es un DataFrame porque proviene de Supabase.
            # No usar get_all_records(), que pertenece a gspread.
            return obtener_datos_tabla("Servicios")

        df_todos = obtener_datos_servicios_cacheados()

        if df_todos.empty:
            st.info("No hay servicios registrados en la base de datos.")
        else:
            col_estado = [c for c in df_todos.columns if "estado" in str(c).lower()]
            col_estado_nombre = col_estado[0] if col_estado else "Estado"

            if col_estado_nombre in df_todos.columns:
                df_pendientes = df_todos[df_todos[col_estado_nombre] == "Pendiente"]
            else:
                df_pendientes = pd.DataFrame()

            if df_pendientes.empty:
                st.success("🎉 ¡Excelente! No hay servicios técnicos pendientes.")
            else:
                opciones_pendientes = []
                indices_servicios = []
                
                for idx, fila in df_pendientes.iterrows():
                    indices_servicios.append(fila.get("id"))
                    empresa_val = str(fila.get('Empresa', 'N/A'))
                    agencia_val = str(fila.get('Agencia', 'N/A'))
                    area_val = str(fila.get('Área', fila.get('Area', 'N/A')))
                    
                    ag_limpia = agencia_val.split(" - ")[-1] if " - " in agencia_val else agencia_val
                    ar_limpia = area_val.split(" - ")[-1] if " - " in area_val else area_val
                    problema_val = str(fila.get('Problema', fila.get('Problema o Falla', fila.iloc[4] if len(fila) > 4 else 'Sin detalle')))
                    
                    etiqueta = f"Fila {idx+2} | {empresa_val} ➔ {ag_limpia} ({ar_limpia}) | {problema_val[:30]}..."
                    opciones_pendientes.append(etiqueta)

                seleccion_idx = st.selectbox(
                    "Selecciona el Servicio Pendiente a Completar:",
                    options=range(len(opciones_pendientes)),
                    format_func=lambda i: opciones_pendientes[i],
                    key="select_servicio_atender"
                )

                servicio_seleccionado = df_pendientes.iloc[seleccion_idx]
                servicio_id = servicio_seleccionado.get("id")

                emp_sel = str(servicio_seleccionado.get('Empresa', 'N/A'))
                ag_raw = str(servicio_seleccionado.get('Agencia', 'N/A'))
                ar_raw = str(servicio_seleccionado.get('Área', servicio_seleccionado.get('Area', 'N/A')))
                
                ag_sel = ag_raw.split(" - ")[-1] if " - " in ag_raw else ag_raw
                ar_sel = ar_raw.split(" - ")[-1] if " - " in ar_raw else ar_raw

                fec_sel = servicio_seleccionado.get('Fecha Solicitud', 'N/A')
                prob_sel = str(servicio_seleccionado.get('Problema', 'N/A'))

                st.markdown("---")
                st.markdown("### 📌 Detalle de la Solicitud Seleccionada")
                st.write(f"🏢 **Empresa:** {emp_sel} | 📍 **Agencia:** {ag_sel} | 🚪 **Área:** {ar_sel}")
                st.write(f"📅 **Fecha y Hora de Solicitud:** {fec_sel}")
                st.warning(f"🛠️ **Problema Reportado:** {prob_sel}")

                st.markdown("### 📝 Datos de la Atención Técnica")
                
                col_t1, col_t2 = st.columns(2)
                
                with col_t1:
                    lista_usuarios_sistema = []
                    if 'hoja_usuarios' in locals():
                        try:
                            df_u = hoja_usuarios.copy() if isinstance(hoja_usuarios, pd.DataFrame) else pd.DataFrame()
                            if not df_u.empty and "Usuario" in df_u.columns:
                                lista_usuarios_sistema = df_u["Usuario"].tolist()
                        except:
                            pass
                    
                    usr_actual = st.session_state.get("usuario_actual", "admin")
                    if usr_actual not in lista_usuarios_sistema:
                        lista_usuarios_sistema.append(usr_actual)
                    
                    idx_def = lista_usuarios_sistema.index(usr_actual) if usr_actual in lista_usuarios_sistema else 0

                    tecnico_atendio = st.selectbox(
                        "Técnico Responsable:",
                        options=lista_usuarios_sistema,
                        index=idx_def,
                        key="tec_nombre_select"
                    )

                    tipo_operacion = st.selectbox(
                        "Tipo de Operación / Destino:",
                        options=["Servicio Técnico Regular", "Venta de Insumo/Repuesto", "Alquiler de Equipo/Insumo"],
                        key="tec_tipo_operacion"
                    )

                with col_t2:
                    col_f_trab, col_h_trab = st.columns(2)
                    with col_f_trab:
                        fecha_trabajo = st.date_input("Fecha:", value=obtener_hora_local_bo().date(), key="tec_fecha")
                    with col_h_trab:
                        hora_trabajo = st.time_input("Hora:", value=obtener_hora_local_bo().time(), key="tec_hora")

                lista_insumos_disponibles = df_insumos["Nombre"].tolist() if 'df_insumos' in locals() and not df_insumos.empty else []
                
                insumos_usados = st.multiselect(
                    "Insumos / Repuestos Utilizados:",
                    options=lista_insumos_disponibles,
                    placeholder="Selecciona uno o varios repuestos...",
                    key="tec_insumos_multi"
                )

                insumos_texto = ", ".join(insumos_usados) if insumos_usados else "Ninguno"

                # 📊 CAMPOS DINÁMICOS QUE SE ACTIVAN SI ELIGE ALQUILER
                cnt_ant, cnt_act, paginas_impresas, precio_facturado, dias_calculados = 0, 0, 0, 0.0, 0

                if "Alquiler" in tipo_operacion:
                    st.markdown("---")
                    st.markdown("### 📊 Control de Contadores (Alquiler)")

                    # 1. Tomamos el primer insumo seleccionado para buscar su historial
                    insumo_ref = insumos_usados[0] if insumos_usados else ""
                    
                    sugerencia_ant = 0
                    if insumo_ref:
                        ultimo_reg = obtener_ultimo_alquiler(insumo_ref, emp_sel, ag_sel, ar_sel)
                        
                        if ultimo_reg is not None:
                            try:
                                sugerencia_ant = int(ultimo_reg["Contador Actual"])
                                # Calcular días transcurridos automáticamente
                                fecha_ult = pd.to_datetime(ultimo_reg["Fecha"], errors='coerce')
                                hoy = obtener_hora_local_bo()
                                if pd.notna(fecha_ult):
                                    if fecha_ult.tzinfo is None:
                                        fecha_ult = fecha_ult.replace(tzinfo=timezone(timedelta(hours=-4)))
                                    dias_calculados = max(0, (hoy - fecha_ult).days)
                                
                                st.success(f"🔍 ¡Historial Encontrado! Último contador para **{insumo_ref}**: **{sugerencia_ant}**")
                            except Exception:
                                sugerencia_ant = 0
                        else:
                            st.warning(f"⚠️ No se encontró historial previo de **{insumo_ref}** en {emp_sel} - {ag_sel} ({ar_sel}). Se iniciará en 0.")
                    else:
                        st.info("💡 Selecciona un insumo arriba para buscar su contador anterior automáticamente.")

                    # 2. Renderizamos los inputs con la sugerencia (claves dinámicas)
                    col_alq1, col_alq2, col_alq3 = st.columns(3)
                    
                    # Claves dinámicas que cambian según el insumo y la solicitud
                    clave_anterior = f"tec_cnt_ant_{insumo_ref}_{seleccion_idx}"
                    clave_actual = f"tec_cnt_act_{insumo_ref}_{seleccion_idx}"
                    clave_precio = f"tec_precio_alq_{insumo_ref}_{seleccion_idx}"

                    with col_alq1:
                        cnt_ant = st.number_input("Contador Anterior:", min_value=0, value=int(sugerencia_ant), key=clave_anterior)
                        
                    with col_alq2:
                        cnt_act = st.number_input("Contador Actual (Lectura de hoy):", min_value=int(cnt_ant), value=int(cnt_ant), key=clave_actual)
                        
                    with col_alq3:
                        precio_facturado = st.number_input("Precio Facturado (Bs.):", min_value=0.0, value=0.0, step=10.0, key=clave_precio)
                    
                    paginas_impresas = max(0, cnt_act - cnt_ant)
                    st.info(f"📄 **Páginas Impresas Calculadas:** {paginas_impresas} págs.")

                st.markdown("---")
                btn_completar_servicio = st.button("✅ Marcar Servicio como COMPLETADO y Registrar Movimiento")

                if btn_completar_servicio:
                    # Formato de fecha para los reportes
                    fecha_str_limpia = fecha_trabajo.strftime('%Y-%m-%d')
                    fecha_hora_realizado = f"{fecha_str_limpia} {hora_trabajo.strftime('%H:%M')}"
                    
                    # 1️⃣ Actualizar Servicio en Supabase
                    if servicio_id is None or pd.isna(servicio_id):
                        st.error("❌ No se encontró el ID del servicio seleccionado. No se realizó la actualización.")
                        st.stop()

                    supabase = conectar_supabase()
                    supabase.table("Servicios").update({
                        "Técnico": tecnico_atendio,
                        "Insumos": f"[{tipo_operacion}] {insumos_texto}",
                        "Fecha Realizado": fecha_hora_realizado,
                        "Estado": "Completado"
                    }).eq("id", servicio_id).execute()

                    # 2️⃣ Descontar TODOS los insumos seleccionados en el stock
                    stock_actualizado = 0
                    if insumos_usados and isinstance(hoja_insumos, pd.DataFrame):
                        try:
                            for insumo_nom in insumos_usados:
                                coincidencias = hoja_insumos[
                                    hoja_insumos["Nombre"].astype(str).str.strip().str.lower() == insumo_nom.strip().lower()
                                ] if "Nombre" in hoja_insumos.columns else pd.DataFrame()

                                if not coincidencias.empty:
                                    fila_ins = coincidencias.iloc[0]
                                    id_insumo = fila_ins.get("id")
                                    stock_valor = pd.to_numeric(fila_ins.get("Cantidad", 0), errors="coerce")
                                    stock_actual = int(stock_valor) if pd.notna(stock_valor) else 0
                                    nuevo_stock = max(0, stock_actual - 1)
                                    stock_actualizado = nuevo_stock

                                    if id_insumo is not None and not pd.isna(id_insumo):
                                        supabase.table("Insumos").update({"Cantidad": nuevo_stock}).eq("id", id_insumo).execute()
                        except Exception as e:
                            st.error(f"⚠️ Error al actualizar stock: {e}")

                    # 3️⃣ Registrar en la Hoja de Alquileres, Ventas e Historial General
                    try:
                        cant_descontada = len(insumos_usados) if insumos_usados else 1

                        # A) Si eligió Alquiler -> guardar directamente en Supabase
                        if "Alquiler" in tipo_operacion:
                            fecha_hora_realizado = f"{fecha_trabajo} {hora_trabajo.strftime('%H:%M:%S')}"
                            supabase.table("Alquileres").insert({
                                "Fecha": fecha_hora_realizado,
                                "Insumo": insumos_texto,
                                "Cantidad": cant_descontada,
                                "Empresa": emp_sel,
                                "Agencia": ag_sel,
                                "Area": ar_sel,
                                "Usuario": tecnico_atendio,
                                "Contador Anterior": int(cnt_ant),
                                "Contador Actual": int(cnt_act),
                                "Páginas Impresas": int(paginas_impresas),
                                "Días Transcurridos": int(dias_calculados)
                            }).execute()

                        # B) Si eligió Venta -> guardar directamente en Supabase
                        elif "Venta" in tipo_operacion:
                            total_venta = float(precio_facturado) * cant_descontada
                            supabase.table("Ventas").insert({
                                "Fecha": fecha_hora_realizado,
                                "Insumo": insumos_texto,
                                "Cantidad": cant_descontada,
                                "Precio Aplicado": float(precio_facturado),
                                "Monto Total (Bs.)": total_venta,
                                "Usuario": tecnico_atendio
                            }).execute()

                        # C) Siempre enviar copia al Historial General
                        if insumos_usados:
                            supabase.table("Historial").insert({
                                "Fecha": fecha_hora_realizado,
                                "Nombre Insumo": insumos_texto,
                                "Tipo de Movimiento": "Salida",
                                "Cantidad Movida": str(cant_descontada),
                                "Stock Resultante": str(stock_actualizado),
                                "Usuario": tecnico_atendio,
                                "Motivo": tipo_operacion,
                                "Empresa Destino": emp_sel,
                                "Agencia Destino": ag_sel,
                                "Área Destino": ar_sel
                            }).execute()

                    except Exception as e:
                        st.warning(f"⚠️ Nota al guardar en reportes: {e}")

                    st.success("🎉 ¡Servicio completado! Se registraron los datos correctamente en los Historiales correspondientes y se actualizó el stock.")
                    time.sleep(1.5)
                    st.cache_data.clear()
                    st.rerun()

    # ---------------------------------------------------------
    # PARTE 3: HISTORIAL GENERAL DE SERVICIOS (LIMPIO Y VISUAL)
    # ---------------------------------------------------------
    with subtab_historial:
        st.subheader("📊 Historial Completo de Servicios")
        st.caption("Consulta el estado general de todas las atenciones registradas.")

        datos_historial = obtener_datos_tabla("Servicios")
        df_historial = datos_historial.copy() if isinstance(datos_historial, pd.DataFrame) else pd.DataFrame(datos_historial)

        if df_historial.empty:
            st.info("No hay atenciones técnicas registradas aún.")
        else:
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                filtro_estado = st.selectbox("Filtrar por Estado:", ["Todos", "Pendiente", "Completado"], key="filtro_est_hist")
            with col_f2:
                filtro_empresa = st.selectbox("Filtrar por Empresa:", ["Todas"] + list(df_historial["Empresa"].unique()), key="filtro_emp_hist")

            df_filtrado = df_historial.copy()

            if filtro_estado != "Todos":
                df_filtrado = df_filtrado[df_filtrado["Estado"] == filtro_estado]

            if filtro_empresa != "Todas":
                df_filtrado = df_filtrado[df_filtrado["Empresa"] == filtro_empresa]

            # --- LIMPIEZA VISUAL DE DATOS PARA LA TABLA ---
            if "Agencia" in df_filtrado.columns:
                df_filtrado["Agencia"] = df_filtrado["Agencia"].astype(str).apply(lambda x: x.split(" - ")[-1] if " - " in x else x)
            
            col_area_name = "Área" if "Área" in df_filtrado.columns else "Area" if "Area" in df_filtrado.columns else None
            if col_area_name:
                df_filtrado[col_area_name] = df_filtrado[col_area_name].astype(str).apply(lambda x: x.split(" - ")[-1] if " - " in x else x)

            # --- APLICAR EMOJIS AL ESTADO ---
            if "Estado" in df_filtrado.columns:
                df_filtrado["Estado"] = df_filtrado["Estado"].apply(
                    lambda x: "🔴 Pendiente" if x == "Pendiente" else ("✅ Completado" if x == "Completado" else x)
                )

            # Mostrar la tabla final limpia y visual
            st.dataframe(df_filtrado, use_container_width=True, hide_index=True)

