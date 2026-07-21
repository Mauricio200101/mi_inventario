import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
# Importamos timezone y timedelta para ajustar la hora a Bolivia (UTC-4)
from datetime import datetime, timezone, timedelta 
import io
import plotly.express as px
import time

# Configuración de la página
st.set_page_config(page_title="Control de Inventario Cloud", page_icon="📦", layout="wide")

# --- AJUSTE DE ZONA HORARIA (BOLIVIA UTC-4) ---
def obtener_hora_local_bo():
    """Retorna la fecha y hora actual con la zona horaria de Bolivia (UTC-4)."""
    tz_bo = timezone(timedelta(hours=-4))
    return datetime.now(tz_bo)

# --- CONEXIÓN CON GOOGLE SHEETS (CON REINTENTOS AUTOMÁTICOS Y CACHÉ) ---
@st.cache_resource
def conectar_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    if "gspread_credentials" in st.secrets:
        import json
        info_creds = json.loads(st.secrets["gspread_credentials"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(info_creds, scope)
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_name("credenciales.json", scope)
        
    cliente = gspread.authorize(creds)
    return cliente.open("Inventario_Empresa")

# Inicializar pestañas guardándolas en st.session_state para no llamar a la API en cada rerun
def inicializar_pestanas_seguras():
    if "pestanas" not in st.session_state:
        max_intentos = 5
        for intento in range(max_intentos):
            try:
                sh = conectar_google_sheets()
                st.session_state["pestanas"] = {
                    "Insumos": sh.worksheet("Insumos"),
                    "Historial": sh.worksheet("Historial"),
                    "Usuarios": sh.worksheet("Usuarios"),
                    "Parametros": sh.worksheet("Parametros"),
                    "Ventas": sh.worksheet("Ventas"),
                    "Alquileres": sh.worksheet("Alquileres")
                }
                break # Éxito, salimos del bucle
            except gspread.exceptions.APIError as e:
                if "429" in str(e):
                    if intento < max_intentos - 1:
                        tiempo_espera = (intento + 1) * 3
                        st.warning(f"⚠️ Google Sheets saturado. Reintentando conexión en {tiempo_espera} segundos...")
                        time.sleep(tiempo_espera)
                        continue
                    else:
                        st.error("🚨 Se superó el límite de solicitudes a Google Sheets. Por favor, espera 30 segundos y recarga la página manualmente.")
                        st.stop()
            except Exception as e:
                st.error(f"❌ Error crítico de conexión: {e}")
                st.stop()
                
    return st.session_state["pestanas"]

# Inicializamos las hojas de trabajo de forma segura usando la sesión
pestanas_activas = inicializar_pestanas_seguras()
hoja_insumos = pestanas_activas["Insumos"]
hoja_historial = pestanas_activas["Historial"]
hoja_usuarios = pestanas_activas["Usuarios"]
hoja_parametros = pestanas_activas["Parametros"]
hoja_ventas = pestanas_activas["Ventas"]
hoja_alquileres = pestanas_activas["Alquileres"]

# --- FUNCIONES DE GESTIÓN DE USUARIOS ---
@st.cache_data(ttl=60)
def obtener_usuarios():
    try:
        datos = hoja_usuarios.get_all_values()
        if not datos or len(datos) <= 1:
            return pd.DataFrame(columns=["Usuario", "Contraseña", "Rol"])
        df = pd.DataFrame(datos[1:], columns=datos[0])
    except Exception as e:
        st.warning(f"Aviso al leer Usuarios: {e}")
        return pd.DataFrame(columns=["Usuario", "Contraseña", "Rol"])
    return df

def registrar_usuario(usuario, contrasenia, rol):
    hoja_usuarios.append_row([usuario, contrasenia, rol])

def editar_usuario(usuario_viejo, nuevo_usuario, nueva_contrasenia, nuevo_rol):
    """Edita un registro de usuario existente."""
    datos = hoja_usuarios.get_all_values()
    for i, fila in enumerate(datos):
        if fila[0] == usuario_viejo:
            fila_idx = i + 1
            hoja_usuarios.update_cell(fila_idx, 1, nuevo_usuario)
            hoja_usuarios.update_cell(fila_idx, 2, nueva_contrasenia)
            hoja_usuarios.update_cell(fila_idx, 3, nuevo_rol)
            break

def eliminar_usuario(usuario_a_eliminar):
    """Elimina un usuario de la hoja."""
    datos = hoja_usuarios.get_all_values()
    for i, fila in enumerate(datos):
        if fila[0] == usuario_a_eliminar:
            hoja_usuarios.delete_rows(i + 1)
            break

# --- FUNCIONES DE PARÁMETROS (EMPRESAS, ÁREAS Y AGENCIAS) ---
@st.cache_data(ttl=60)
def obtener_parametros():
    try:
        datos = hoja_parametros.get_all_values()
        if not datos or len(datos) <= 1:
            return ["Sin Registrar"], ["Sin Registrar"], ["Sin Registrar"]
            
        df = pd.DataFrame(datos[1:], columns=datos[0])
        
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
    registros = hoja_parametros.get_all_values()
    if not registros:
        hoja_parametros.append_row(["Empresa", "Agencia", "Area"])
        registros = [["Empresa", "Agencia", "Area"]]
        
    df = pd.DataFrame(registros[1:], columns=registros[0])
    
    if tipo == "Empresa":
        lista_actual = df["Empresa"].dropna().tolist()
        lista_actual = [x for x in lista_actual if x != ""]
        lista_actual.append(nuevo_valor)
        col_index = 1
        nueva_lista = lista_actual
    elif tipo == "Agencia":
        lista_actual = df["Agencia"].dropna().tolist() if "Agencia" in df.columns else []
        lista_actual = [x for x in lista_actual if x != ""]
        lista_actual.append(nuevo_valor)
        col_index = 2
        nueva_lista = lista_actual
    else: # Area
        lista_actual = df["Area"].dropna().tolist()
        lista_actual = [x for x in lista_actual if x != ""]
        lista_actual.append(nuevo_valor)
        col_index = 3
        nueva_lista = lista_actual

    row_to_write = len(nueva_lista) + 1
    hoja_parametros.update_cell(row_to_write, col_index, nuevo_valor)

def eliminar_parametro(valor_a_eliminar, tipo):
    """Elimina de forma segura un parámetro de la lista reescribiendo la columna sin dejar celdas fantasmas."""
    try:
        registros = hoja_parametros.get_all_values()
        if not registros:
            return
            
        cabeceras = registros[0]
        df = pd.DataFrame(registros[1:], columns=cabeceras)
        
        # Filtrado y estructuración por tipo
        if tipo == "Empresa" and "Empresa" in df.columns:
            lista_actual = df["Empresa"].dropna().astype(str).str.strip().tolist()
            lista_actual = [x for x in lista_actual if x != ""]
            if valor_a_eliminar in lista_actual:
                lista_actual.remove(valor_a_eliminar)
            col_index = 1
            col_letra = "A"
            nueva_lista = lista_actual
        elif tipo == "Agencia" and "Agencia" in df.columns:
            lista_actual = df["Agencia"].dropna().astype(str).str.strip().tolist()
            lista_actual = [x for x in lista_actual if x != ""]
            if valor_a_eliminar in lista_actual:
                lista_actual.remove(valor_a_eliminar)
            col_index = 3
            col_letra = "B"
            nueva_lista = lista_actual
        elif tipo == "Area" and "Area" in df.columns:
            lista_actual = df["Area"].dropna().astype(str).str.strip().tolist()
            lista_actual = [x for x in lista_actual if x != ""]
            if valor_a_eliminar in lista_actual:
                lista_actual.remove(valor_a_eliminar)
            col_index = 2
            col_letra = "C"
            nueva_lista = lista_actual
        else:
            return
            
        # 1. Limpiamos la columna entera del Google Sheet para evitar que queden datos duplicados abajo
        hoja_parametros.batch_clear([f"{col_letra}2:{col_letra}500"])
        
        # 2. Escribimos ordenadamente la nueva lista resultante
        for idx, val in enumerate(nueva_lista):
            hoja_parametros.update_cell(idx + 2, col_index, val)
            
    except Exception as e:
        st.error(f"Error al eliminar parámetro en base de datos: {e}")

# --- CONTROL DE ACCESO (LOGIN) ---
def check_password():
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False
        st.session_state["usuario_actual"] = ""
        st.session_state["rol_actual"] = ""

    if st.session_state["logged_in"]:
        return True

    st.subheader("🔑 Acceso al Sistema de Inventario")
    usuario_input = st.text_input("Usuario:")
    password_input = st.text_input("Contraseña:", type="password")
    
    if st.button("Ingresar"):
        df_users = obtener_usuarios()
        usuario_valido = df_users[(df_users["Usuario"] == usuario_input) & (df_users["Contraseña"] == str(password_input))]
        
        if not usuario_valido.empty:
            st.session_state["logged_in"] = True
            st.session_state["usuario_actual"] = usuario_input
            st.session_state["rol_actual"] = usuario_valido.iloc[0]["Rol"]
            st.success(f"¡Bienvenido, {usuario_input}! Rol: {st.session_state['rol_actual']}")
            st.rerun()
        else:
            st.error("❌ Usuario o contraseña incorrectos. Inténtalo de nuevo.")
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

# --- FUNCIONES DE SOPORTES DE INVENTARIO ---
@st.cache_data(ttl=15)
def obtener_insumos():
    try:
        datos = hoja_insumos.get_all_values()
        if not datos or len(datos) <= 1:
            return pd.DataFrame(columns=["ID", "Nombre", "Categoría", "Cantidad", "Stock Mínimo", "Precio Técnico", "Precio Cliente", "Precio Facturado"])
        
        df = pd.DataFrame(datos[1:], columns=datos[0])
    except Exception as e:
        st.warning(f"Aviso al leer Insumos: {e}")
        return pd.DataFrame(columns=["ID", "Nombre", "Categoría", "Cantidad", "Stock Mínimo", "Precio Técnico", "Precio Cliente", "Precio Facturado"])
        
    for col in ["Cantidad", "Stock Mínimo", "Precio Técnico", "Precio Cliente", "Precio Facturado"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

def registrar_insumo(nombre, categoria, cantidad, stock_minimo, p_tecnico, p_cliente, p_facturado):
    df = obtener_insumos()
    df["ID"] = pd.to_numeric(df["ID"], errors='coerce')
    
    # Calculamos el ID de forma segura
    max_id = df["ID"].max()
    nuevo_id = int(max_id) + 1 if pd.notna(max_id) else 1
    
    # Añadimos la fila y forzamos la limpieza de caché
    hoja_insumos.append_row([nuevo_id, nombre, categoria, cantidad, stock_minimo, p_tecnico, p_cliente, p_facturado])
    st.cache_data.clear()
    
    fecha_actual = obtener_hora_local_bo().strftime("%Y-%m-%d %H:%M:%S")
    hoja_historial.append_row([fecha_actual, nombre, "Registro Inicial", cantidad, cantidad, st.session_state["usuario_actual"], "Abastecimiento", "", ""])
def eliminar_insumo(id_insumo):
    """Elimina un insumo de la hoja por su ID."""
    celda = hoja_insumos.find(str(id_insumo))
    if celda:
        hoja_insumos.delete_rows(celda.row)
        st.cache_data.clear() 
        return True
    return False

# --- OBTENER ÚLTIMO REGISTRO DE ALQUILER PARA LOS CONTADORES ---
def obtener_ultimo_alquiler(insumo, empresa, agencia, area):
    """
    Busca en la pestaña de Alquileres el último registro que coincida 
    con el Insumo, la Empresa, el Área y la Agencia especificados para extraer su contador y su fecha.
    """
    try:
        datos = hoja_alquileres.get_all_values()
        if not datos or len(datos) <= 1:
            return None
        
        df_alq = pd.DataFrame(datos[1:], columns=datos[0])
        
        # Filtramos asegurándonos de contemplar la columna de Agencia Destino (si existe)
        if "Agencia Destino" in df_alq.columns:
            df_filtrado = df_alq[
                (df_alq["Insumo"].str.strip() == str(insumo).strip()) & 
                (df_alq["Empresa Destino"].str.strip() == str(empresa).strip()) & 
                (df_alq["Agencia Destino"].str.strip() == str(agencia).strip()) &
                (df_alq["Area Destino"].str.strip() == str(area).strip())
            ]
        else:
            # Fallback en caso de que la hoja de alquileres aún no tenga la columna Agencia Destino
            df_filtrado = df_alq[
                (df_alq["Insumo"].str.strip() == str(insumo).strip()) & 
                (df_alq["Empresa Destino"].str.strip() == str(empresa).strip()) & 
                (df_alq["Area Destino"].str.strip() == str(area).strip())
            ]
        
        if not df_filtrado.empty:
            ultimo_registro = df_filtrado.iloc[-1]
            return ultimo_registro
    except Exception as e:
        st.error(f"Error al buscar historial de contadores: {e}")
    return None

def actualizar_stock_sheet(id_insumo, nuevo_stock, nombre_insumo, tipo_mov, cant_movida, motivo="", empresa="", area_o_precio="", precio_unitario=0.0, contador_anterior=0, contador_actual=0, paginas=0, dias=0, agencia=""):
    try:
        df_local = obtener_insumos()
        idx_lista = df_local[df_local["ID"].astype(str) == str(id_insumo)].index
        
        if not idx_lista.empty:
            fila_sheet = int(idx_lista[0]) + 2
            
            hoja_insumos.update_cell(fila_sheet, 4, nuevo_stock)
            fecha_actual = obtener_hora_local_bo().strftime("%Y-%m-%d %H:%M:%S")
            
            # Separamos la agencia y el área de forma limpia para el historial
            agencia_para_historial = agencia if agencia else ""
            area_para_historial = area_o_precio if area_o_precio else ""
            
            hoja_historial.append_row([
                fecha_actual,
                nombre_insumo,
                tipo_mov,
                cant_movida,
                nuevo_stock,
                st.session_state["usuario_actual"],
                motivo,
                empresa,
                agencia_para_historial,
                area_para_historial
            ])
            
            if tipo_mov == "Salida":
                if motivo == "Venta":
                    total_venta = float(cant_movida) * float(precio_unitario)
                    hoja_ventas.append_row([
                        fecha_actual,
                        nombre_insumo,
                        cant_movida,
                        area_o_precio, 
                        total_venta,
                        st.session_state["usuario_actual"]
                    ])
                elif motivo == "Alquiler":
                    fila_registro = [
                    fecha_actual,
                    nombre_insumo,
                    cant_movida,
                    empresa,
                    str(agencia).split(" - ")[-1].strip(),       # Extrae solo la agencia final
                    str(area_o_precio).split(" - ")[-1].strip(), # Extrae solo el área final
                    st.session_state["usuario_actual"],
                    int(contador_anterior),
                    int(contador_actual),
                    int(paginas),
                    int(dias)
                    ]
                    hoja_alquileres.append_row(fila_registro)
            else:
                st.error("No se encontró el ID del insumo en la hoja de cálculo.")
    except Exception as e:
        st.error(f"Error al conectar con la base de datos: {e}")

# --- PESTAÑAS DEL SISTEMA ---
# Asegúrate de que esto esté totalmente a la izquierda (sin sangría/indentación)
df_insumos = obtener_insumos()
empresas_disponibles, areas_disponibles, agencias_disponibles = obtener_parametros()
tab_operaciones, tab_valorizacion, tab_rendimiento, tab_reportes, tab_usuarios = st.tabs([
    "Operaciones de Stock",
    "Valorización del Inventario",
    "Rendimiento de Insumos",
    "Reportes por Fecha / Edición",
    "Configuración y Usuarios"
])

# ==========================================
# 1. PESTAÑA DE OPERACIONES DE STOCK
# ==========================================
with tab_operaciones:
    if st.session_state["rol_actual"] in ["Administrador", "Secretaria"]:
        st.subheader("⚠️ Alertas de Stock Crítico")
        alertas_activas = False
        if not df_insumos.empty:
            for index, fila in df_insumos.iterrows():
                cant_actual = int(fila["Cantidad"])
                cant_minima = int(fila["Stock Mínimo"])
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
                    # Aquí mantienes tu código de registro actual (líneas 418 a 443)
                    st.write("**Registrar Nuevo Insumo**")
                    with st.form("nuevo_insumo_form", clear_on_submit=True):
                        nombre = st.text_input("Nombre del Insumo", placeholder="Ej: GPR-57")
                        categoria = st.text_input("Categoria", placeholder="Ej: Toner")
                        amount_ini = st.number_input("Cantidad Inicial", min_value=0, step=1, value=0)
                        stock_min = st.number_input("Stock Mínimo (Alerta)", min_value=1, step=1, value=5)
                        
                        st.markdown("**💰 Configuración de Precios (Bs.)**")
                        p_tecnico = st.number_input("Precio Técnico", min_value=0.0, step=0.1, value=0.0)
                        p_cliente = st.number_input("Precio Cliente", min_value=0.0, step=0.1, value=0.0)
                        p_faclurado = st.number_input("Precio Facturado", min_value=0.0, step=0.1, value=0.0)
                        
                        guardado = st.form_submit_button("Guardar Insumo")
                        
                        if guardado:
                            if nombre.strip() == "":
                                st.error("Por favor, ingresa el nombre del insumo.")
                            elif not df_insumos.empty and nombre.lower() in df_insumos["Nombre"].str.lower().values:
                                st.warning("Ese insumo ya existe en la lista.")
                            else:
                                with st.spinner("Guardando en Google Sheets..."):
                                    registrar_insumo(nombre, categoria, amount_ini, stock_min, p_tecnico, p_cliente, p_faclurado)
                                    st.success(f"Insumo {nombre} registrado correctamente!")
                                    st.rerun()

                # Solo si es Administrador, mostramos el contenido de la pestaña de edición
                if st.session_state["rol_actual"] == "Administrador":
                    with tab_edit:
                        st.write("**Modificar Alerta o Precios**")
                        # Aquí va el código que tenías para editar (líneas 446 a 472 de tu archivo original)
                        if not df_insumos.empty:
                            insumo_editar = st.selectbox("Selecciona el insumo a editar:", df_insumos["Nombre"].tolist(), key="sel_edit")
                            datos_insumo_editar = df_insumos[df_insumos["Nombre"] == insumo_editar].iloc[0]
                            
                            cel_id = datos_insumo_editar["ID"]
                            min_actual = int(datos_insumo_editar["Stock Mínimo"])
                            pt_act = float(datos_insumo_editar["Precio Técnico"])
                            pc_act = float(datos_insumo_editar["Precio Cliente"])
                            pf_act = float(datos_insumo_editar["Precio Facturado"])
                            
                            nuevo_minimo = st.number_input("Nuevo Stock Mínimo:", min_value=1, step=1, value=min_actual)
                            nuevo_pt = st.number_input("Nuevo Precio Técnico:", min_value=0.0, step=0.1, value=pt_act)
                            nuevo_pc = st.number_input("Nuevo Precio Cliente:", min_value=0.0, step=0.1, value=pc_act)
                            nuevo_pf = st.number_input("Nuevo Precio Facturado:", min_value=0.0, step=0.1, value=pf_act)
                            
                            if st.button("Actualizar Parámetros"):
                                celda_id = hoja_insumos.find(str(cel_id))
                                if celda_id:
                                    hoja_insumos.update_cell(celda_id.row, 5, nuevo_minimo)
                                    hoja_insumos.update_cell(celda_id.row, 6, nuevo_pt)
                                    hoja_insumos.update_cell(celda_id.row, 7, nuevo_pc)
                                    hoja_insumos.update_cell(celda_id.row, 8, nuevo_pf)
                                    st.success("¡Datos actualizados con éxito!")
                                    st.rerun()

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
                    id_insumo = datos_insumo["ID"]
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

    st.markdown("---")

    # --- LISTA DE EXISTENCIAS ---
    st.subheader("🔍 Buscador y Lista de Existencias")
    busqueda = st.text_input("Buscar insumo por nombre o categoría:", placeholder="Escribe aquí para buscar...")

    if not df_insumos.empty:
        df_filtrado = df_insumos[
            df_insumos["Nombre"].str.lower().str.contains(busqueda.lower()) | 
            df_insumos["Categoría"].str.lower().str.contains(busqueda.lower()) # <--- AQUÍ ESTABA EL ERROR
        ]
        
        # Bloque de eliminación solo para Administradores
        if st.session_state["rol_actual"] == "Administrador":
            with st.expander("🚨 Zona de Administración: Eliminar Insumos"):
                insumo_a_borrar = st.selectbox("Selecciona insumo a eliminar:", df_filtrado["Nombre"].tolist())
                if st.button("Confirmar Eliminación"):
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
        st.warning("No se encontraron insumos.")


# ==========================================
# 2. PESTAÑA DE VALORIZACIÓN DEL INVENTARIO
# ==========================================
with tab_valorizacion:
    if st.session_state["rol_actual"] == "Administrador":
        st.subheader("💰 Resumen Monetario del Inventario")
        if not df_insumos.empty:
            df_insumos["Val_Tecnico"] = df_insumos["Cantidad"] * df_insumos["Precio Técnico"]
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
            
            df_melted = df_insumos.melt(
                id_vars=["Nombre"], 
                value_vars=["Val_Tecnico", "Val_Cliente", "Val_Facturado"],
                var_name="Tipo de Precio", 
                value_name="Valor Total (Bs.)"
            )
            df_melted["Tipo de Precio"] = df_melted["Tipo de Precio"].replace({
                "Val_Tecnico": "Técnico", "Val_Cliente": "Cliente", "Val_Facturado": "Facturado"
            })
            
            fig_val = px.bar(
                df_melted, 
                x="Nombre", 
                y="Valor Total (Bs.)", 
                color="Tipo de Precio", 
                barmode="group",
                title="Valor total de existencias por esquema de precios",
                text_auto=True
            )
            st.plotly_chart(fig_val, use_container_width=True)
        else:
            st.info("No hay datos de insumos para calcular la valorización.")
    else:
        # Mensaje para la Secretaria o el Técnico
        st.warning("🔒 Esta sección es exclusiva para Administradores.")


# ==========================================
# 3. PESTAÑA DE RENDIMIENTO DE INSUMOS
# ==========================================
with tab_rendimiento:
    st.subheader("📈 Análisis de Rendimiento Promedio de Insumos")
    st.write("Esta sección calcula el rendimiento histórico del equipamiento/tóner en función de las copias realizadas y el tiempo útil de uso.")

    try:
        datos_rend = hoja_alquileres.get_all_values()
        if datos_rend and len(datos_rend) > 1:
            df_rend = pd.DataFrame(datos_rend[1:], columns=datos_rend[0])
            
            df_rend["Páginas Impresas"] = pd.to_numeric(df_rend["Páginas Impresas"], errors="coerce").fillna(0)
            df_rend["Días Transcurridos"] = pd.to_numeric(df_rend["Días Transcurridos"], errors="coerce").fillna(0)
            
            df_rend_filtrado = df_rend[(df_rend["Páginas Impresas"] > 0) | (df_rend["Días Transcurridos"] > 0)]
            
            if not df_rend_filtrado.empty:
                df_promedios = df_rend_filtrado.groupby("Insumo").agg(
                    Promedio_Paginas=("Páginas Impresas", "mean"),
                    Promedio_Dias=("Días Transcurridos", "mean"),
                    Total_Registros=("Insumo", "count")
                ).reset_index()
                
                df_promedios.columns = ["Insumo", "Páginas Promedio por Periodo", "Duración Promedio (Días)", "Nº Mediciones Realizadas"]
                
                st.write("📊 **Tabla de Rendimiento Promedio por Insumo**")
                
                df_promedios_con_num = df_promedios.copy()
                df_promedios_con_num.insert(0, "N°", range(1, len(df_promedios_con_num) + 1))
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
with tab_reportes:
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
            datos_hist = hoja_historial.get_all_values()
            if datos_hist and len(datos_hist) > 1:
                df_hist = pd.DataFrame(datos_hist[1:], columns=datos_hist[0])
            else:
                df_hist = pd.DataFrame(columns=["Fecha", "Insumo", "Movimiento", "Cantidad", "Stock Resultante", "Usuario", "Motivo", "Empresa/Precio", "Detalle"])
        except:
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
                            
                for col_area in ["Área Destino", "Area Destino", "Detalle"]:
                    if col_area in df_mostrar.columns:
                        df_mostrar[col_area] = df_mostrar[col_area].apply(
                            lambda x: str(x).split(" - ")[-1].strip() if " - " in str(x) else str(x)
                        )

                df_mostrar.insert(0, "N°", range(1, len(df_mostrar) + 1))
                st.dataframe(df_mostrar, use_container_width=True, hide_index=True)
                
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    df_mostrar.to_excel(writer, sheet_name='Historial_General', index=False)
                st.download_button("Descargar Reporte General (Excel)", data=buffer.getvalue(), file_name=f"Reporte_General_{fecha_inicio_gen}_a_{fecha_fin_gen}.xlsx")
        else:
            st.info("Historial vacío.")

    # --- 2. SUBPESTAÑA VENTAS ---
    with tab_rep_ventas:
        st.write("📆 **Segmentación Mensual de Ventas**")
        try:
            datos_v = hoja_ventas.get_all_values()
            if datos_v and len(datos_v) > 1:
                df_v = pd.DataFrame(datos_v[1:], columns=datos_v[0])
            else:
                df_v = pd.DataFrame(columns=["Fecha", "Insumo", "Cantidad", "Precio Aplicado", "Monto Total (Bs.)", "Usuario"])
        except:
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
            
            meses_del_ano = df_v[df_v["Año"] == ano_seleccionado]["Mes_Num"].unique()
            meses_opciones = [meses_es[m] for m in sorted(meses_del_ano)]
            
            with col_v2:
                mes_seleccionado = st.selectbox("Selecciona el Mes:", meses_opciones if meses_opciones else ["Ninguno"])
            
            mes_num_sel = [k for k, v in meses_es.items() if v == mes_seleccionado][0] if mes_seleccionado != "Ninguno" else None
            df_filtrado_v = df_v[(df_v["Año"] == ano_seleccionado) & (df_v["Mes_Num"] == mes_num_sel)]
            
            if df_filtrado_v.empty:
                st.warning(f"No se registraron ventas en {mes_seleccionado} del {ano_seleccionado}.")
            else:
                df_v_mostrar = df_filtrado_v.drop(columns=["Fecha_dt", "Año", "Mes_Num", "Mes"], errors='ignore').copy()
                suma_ventas = pd.to_numeric(df_v_mostrar["Monto Total (Bs.)"], errors='coerce').sum()
                st.success(f"💰 **Monto Total Facturado en {mes_seleccionado} del {ano_seleccionado}:** {suma_ventas:,.2f} Bs.")
                
                df_v_mostrar.insert(0, "N°", range(1, len(df_v_mostrar) + 1))
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
            st.info("No se han registrado ventas en la hoja 'Ventas' de Google Sheets todavía.")

    # --- 3. SUBPESTAÑA ALQUILERES ---
    with tab_rep_alquileres:
        st.write("🔍 **Búsqueda Filtrada de Alquileres**")
        try:
            datos_a = hoja_alquileres.get_all_values()
            df_a = pd.DataFrame(datos_a[1:], columns=datos_a[0]) if len(datos_a) > 1 else pd.DataFrame()
        except:
            df_a = pd.DataFrame()

        if not df_a.empty:
            # 1. Selector de Empresa
            lista_empresas = ["Todas"] + sorted(df_a["Empresa Destino"].unique().tolist())
            empresa_sel = st.selectbox("Seleccione Empresa:", lista_empresas)
            
            # Filtrado intermedio por Empresa
            df_temp = df_a if empresa_sel == "Todas" else df_a[df_a["Empresa Destino"] == empresa_sel]
            
            # 2. Selector de Agencia (Extraemos la agencia real del penúltimo segmento)
            agencias_raw = sorted(df_temp["Agencia Destino"].unique().tolist())
            agencias_limpias = sorted(list(set([str(a).split(" - ")[-2].strip() if " - " in str(a) and len(str(a).split(" - ")) >= 2 else str(a) for a in agencias_raw])))
            mapeo_agencias = { (str(a).split(" - ")[-2].strip() if " - " in str(a) and len(str(a).split(" - ")) >= 2 else str(a)): a for a in agencias_raw }
            
            agencia_display = st.selectbox("Seleccione Agencia:", ["Todas"] + agencias_limpias)
            agencia_sel = "Todas" if agencia_display == "Todas" else mapeo_agencias[agencia_display]
            
            # Filtrado final por Empresa y Agencia
            df_filtrado_a = df_temp if agencia_sel == "Todas" else df_temp[df_temp["Agencia Destino"] == agencia_sel]
            
            # 3. Fechas
            col_fa1, col_fa2 = st.columns(2)
            with col_fa1:
                fecha_inicio_alq = st.date_input("Desde:", value=obtener_hora_local_bo().date(), key="f_alq_ini_new")
            with col_fa2:
                fecha_fin_alq = st.date_input("Hasta:", value=obtener_hora_local_bo().date(), key="f_alq_fin_new")
                    
            # Filtro de fecha
            df_filtrado_a["Fecha_dt"] = pd.to_datetime(df_filtrado_a["Fecha"], errors='coerce')
            df_filtrado_a = df_filtrado_a[(df_filtrado_a["Fecha_dt"].dt.date >= fecha_inicio_alq) & 
                                        (df_filtrado_a["Fecha_dt"].dt.date <= fecha_fin_alq)]
            if df_filtrado_a.empty:
                st.warning("No se encontraron registros con los filtros seleccionados.")
            else:
                df_a_mostrar = df_filtrado_a.drop(columns=["Fecha_dt"], errors='ignore').copy()
                
                # --- LIMPIEZA LIMPIA PARA LA VISTA ---
                if "Agencia Destino" in df_a_mostrar.columns:
                    df_a_mostrar["Agencia Destino"] = df_a_mostrar["Agencia Destino"].apply(
                        lambda x: str(x).split(" - ")[-1].strip() if " - " in str(x) else str(x)
                    )
                
                if "Area Destino" in df_a_mostrar.columns:
                    df_a_mostrar["Area Destino"] = df_a_mostrar["Area Destino"].apply(
                        lambda x: str(x).split(" - ")[-1].strip() if " - " in str(x) else str(x)
                    )

                if "N°" in df_a_mostrar.columns:
                    df_a_mostrar = df_a_mostrar.drop(columns=["N°"])
                    
                df_a_mostrar.insert(0, "N°", range(1, len(df_a_mostrar) + 1))
                st.dataframe(df_a_mostrar, use_container_width=True, hide_index=True)
                
                buffer_a = io.BytesIO()
                with pd.ExcelWriter(buffer_a, engine='openpyxl') as writer:
                    df_a_mostrar.to_excel(writer, index=False)
                st.download_button("Descargar Reporte (Excel)", data=buffer_a.getvalue(), file_name="Reporte_Alquileres.xlsx")
        else:
            st.info("No hay datos en la pestaña de Alquileres.")

    # --- 4. SUBPESTAÑA ADM BORRADO / MODIFICACIÓN ---
    with tab_admin_borrado:
        if st.session_state["rol_actual"] == "Administrador":
            st.warning("🚨 **Zona de Edición Crítica:** Como Administrador, puedes depurar y eliminar registros del historial general, ventas o alquileres si hubo un error de transcripción.")
            
            tipo_tabla_editar = st.selectbox("Selecciona el Historial a depurar:", ["Alquileres", "Ventas", "Historial General"])
            
            try:
                if tipo_tabla_editar == "Alquileres":
                    hoja_activa_borrar = hoja_alquileres
                elif tipo_tabla_editar == "Ventas":
                    hoja_activa_borrar = hoja_ventas
                else:
                    hoja_activa_borrar = hoja_historial
                
                datos_crud = hoja_activa_borrar.get_all_values()
                
                if datos_crud and len(datos_crud) > 1:
                    df_crud = pd.DataFrame(datos_crud[1:], columns=datos_crud[0]).copy()
                    df_crud["Fila_Sheet"] = [i for i in range(2, len(df_crud) + 2)]
                    
                    st.write("Selecciona el registro que deseas eliminar permanentemente de Google Sheets:")
                    
                    df_crud_visual = df_crud.copy()
                    df_crud_visual.insert(0, "N°", range(1, len(df_crud_visual) + 1))
                    st.dataframe(df_crud_visual, use_container_width=True, hide_index=True)
                    
                    options_eliminar = []
                    for index, row in df_crud.iterrows():
                        fecha_r = row.get("Fecha", "Sin Fecha")
                        insumo_r = row.get("Insumo", "Sin Insumo")
                        det_r = row.get("Empresa Destino", row.get("Area Destino", row.get("Motivo", "")))
                        options_eliminar.append(f"Fila {row['Fila_Sheet']} | {fecha_r} | {insumo_r} | {det_r}")
                        
                    seleccion_borrado = st.selectbox("Selecciona fila a eliminar:", options_eliminar)
                    
                    if seleccion_borrado:
                        fila_eliminar_real = int(seleccion_borrado.split(" | ")[0].replace("Fila ", ""))
                        st.error(f"⚠️ ¿Estás completamente seguro de eliminar permanentemente la **Fila {fila_eliminar_real}** de Google Sheets?")
                        confirmacion_borrado = st.text_input("Escribe 'ELIMINAR' en mayúsculas para proceder:")
                        
                        if st.button("Proceder con la Eliminación"):
                            if confirmacion_borrado == "ELIMINAR":
                                with st.spinner("Eliminando fila en Google Sheets..."):
                                    hoja_activa_borrar.delete_rows(fila_eliminar_real)
                                st.success(f"¡Fila {fila_eliminar_real} eliminada exitosamente!")
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
with tab_usuarios:
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