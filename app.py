import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime
import io
import plotly.express as px

# Configuración de la página
st.set_page_config(page_title="Control de Inventario Cloud", page_icon="📦", layout="wide")

# --- CONEXIÓN CON GOOGLE SHEETS ---
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

try:
    sh = conectar_google_sheets()
    hoja_insumos = sh.worksheet("Insumos")
    hoja_historial = sh.worksheet("Historial")
    hoja_usuarios = sh.worksheet("Usuarios")
except Exception as e:
    st.error("❌ Error al conectar con Google Sheets. Verifica tus credenciales y pestañas.")
    st.stop()

# --- FUNCIONES DE GESTIÓN DE USUARIOS ---
def obtener_usuarios():
    registros = hoja_usuarios.get_all_records()
    df = pd.DataFrame(registros)
    if df.empty:
        df = pd.DataFrame(columns=["Usuario", "Contraseña", "Rol"])
    return df

def registrar_usuario(usuario, contrasenia, rol):
    hoja_usuarios.append_row([usuario, contrasenia, rol])

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
    st.rerun()

# --- FUNCIONES DE SOPORTE DE INVENTARIO ---
def obtener_insumos():
    registros = hoja_insumos.get_all_records()
    df = pd.DataFrame(registros)
    if df.empty:
        df = pd.DataFrame(columns=["ID", "Nombre", "Categoría", "Cantidad", "Stock Mínimo", "Precio Técnico", "Precio Cliente", "Precio Facturado"])
    # Asegurar tipos numéricos para cálculos
    for col in ["Cantidad", "Stock Mínimo", "Precio Técnico", "Precio Cliente", "Precio Facturado"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

def registrar_insumo(nombre, categoria, cantidad, stock_minimo, p_tecnico, p_cliente, p_facturado):
    df = obtener_insumos()
    nuevo_id = int(df["ID"].max() + 1) if not df.empty and pd.notna(df["ID"].max()) else 1
    hoja_insumos.append_row([nuevo_id, nombre, categoria, cantidad, stock_minimo, p_tecnico, p_cliente, p_facturado])
    
    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Guarda en el historial el registro inicial auditando el usuario activo
    hoja_historial.append_row([fecha_actual, nombre, "Registro Inicial", cantidad, cantidad, st.session_state["usuario_actual"], "Abastecimiento", "", ""])

def actualizar_stock_sheet(id_insumo, nuevo_stock, nombre_insumo, tipo_mov, cant_movida, motivo="", empresa="", area=""):
    celda_id = hoja_insumos.find(str(id_insumo))
    if celda_id:
        hoja_insumos.update_cell(celda_id.row, 4, nuevo_stock)
        fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Guarda en el historial auditando al usuario activo e incluyendo los nuevos campos de alquiler/venta
        hoja_historial.append_row([fecha_actual, nombre_insumo, tipo_mov, cant_movida, nuevo_stock, st.session_state["usuario_actual"], motivo, empresa, area])

# --- INTERFAZ PRINCIPAL ---
st.title("📦 Sistema de Control de Inventario Nube")
df_insumos = obtener_insumos()

# --- PESTAÑAS DEL SISTEMA ---
tab_operaciones, tab_valorizacion, tab_reportes, tab_usuarios = st.tabs([
    "⚙️ Operaciones de Stock", 
    "💰 Valorización del Inventario", 
    "📅 Reportes por Fecha", 
    "👥 Gestión de Usuarios"
])

# ==========================================
# 1. PESTAÑA DE OPERACIONES DE STOCK
# ==========================================
with tab_operaciones:
    # --- ALERTAS DE STOCK CRÍTICO ---
    if st.session_state["rol_actual"] in ["Administrador", "Secretaria"]:
        st.subheader("⚠️ Alertas de Stock Crítico")
        alertas_activas = False
        if not df_insumos.empty:
            for index, fila in df_insumos.iterrows():
                cant_actual = int(fila["Cantidad"])
                cant_minima = int(fila["Stock Mínimo"])
                if cant_actual <= cant_minima:
                    st.error(f"🚨 **¡ALERTA DE STOCK BAJO!** El insumo **{fila['Nombre']}** ({fila['Categoría'] if 'Categoría' in fila else fila['Categoria']}) tiene solo **{cant_actual}** unidades. (Mínimo: {cant_minima})")
                    alertas_activas = True
        if not alertas_activas:
            st.success("✅ ¡Todos los insumos tienen niveles de stock saludables!")
        st.markdown("---")

    if st.session_state["rol_actual"] == "Técnico":
        st.warning("ℹ️ Tu cuenta de **Técnico** tiene permisos de 'Solo Lectura'. Puedes revisar las existencias abajo.")
    else:
        col_izq, col_der = st.columns([1, 1])

        with col_izq:
            if st.session_state["rol_actual"] == "Administrador":
                tab_reg, tab_edit = st.tabs(["➕ Registrar Insumo", "✏️ Editar Stock Mínimo/Precios"])
                
                with tab_reg:
                    st.write("**Registrar Nuevo Insumo**")
                    with st.form("nuevo_insumo_form", clear_on_submit=True):
                        nombre = st.text_input("Nombre del Insumo", placeholder="Ej: GPR-57")
                        categoria = st.text_input("Categoría", placeholder="Ej: Toner")
                        cantidad_ini = st.number_input("Cantidad Inicial", min_value=0, step=1, value=0)
                        stock_min = st.number_input("Stock Mínimo (Alerta)", min_value=1, step=1, value=5)
                        
                        st.markdown("**💰 Configuración de Precios (Bs.)**")
                        p_tecnico = st.number_input("Precio Técnico", min_value=0.0, step=0.1, value=0.0)
                        p_cliente = st.number_input("Precio Cliente", min_value=0.0, step=0.1, value=0.0)
                        p_facturado = st.number_input("Precio Facturado", min_value=0.0, step=0.1, value=0.0)
                        
                        guardado = st.form_submit_button("Guardar Insumo")

                    if guardado:
                        if nombre.strip() == "":
                            st.error("Por favor, ingresa el nombre del insumo.")
                        elif not df_insumos.empty and nombre.lower() in df_insumos["Nombre"].str.lower().values:
                            st.warning("Ese insumo ya existe en la lista.")
                        else:
                            with st.spinner("Guardando en Google Sheets..."):
                                registrar_insumo(nombre, categoria, cantidad_ini, stock_min, p_tecnico, p_cliente, p_facturado)
                            st.success(f"¡Insumo '{nombre}' registrado correctamente!")
                            st.cache_resource.clear()
                            st.rerun()
                
                with tab_edit:
                    st.write("**Modificar Alerta o Precios**")
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
                                # Actualizar en cascada en Google Sheets
                                hoja_insumos.update_cell(celda_id.row, 5, nuevo_minimo)
                                hoja_insumos.update_cell(celda_id.row, 6, nuevo_pt)
                                hoja_insumos.update_cell(celda_id.row, 7, nuevo_pc)
                                hoja_insumos.update_cell(celda_id.row, 8, nuevo_pf)
                                st.success("¡Datos actualizados con éxito!")
                                st.cache_resource.clear()
                                st.rerun()
            else:
                st.info("🔒 Las funciones de creación o edición de parámetros son exclusivas del Administrador.")

        with col_der:
            st.subheader("🔄 Registrar Movimiento (Entrada/Salida)")
            
            st.markdown("📷 **Lector de Códigos QR/Barra**")
            foto_codigo = st.camera_input("Toma una foto al código de barra para escanearlo")
            insumo_detectado = None
            
            if foto_codigo is not None:
                st.success("¡Código capturado con éxito!")
                insumo_detectado = st.selectbox("🔍 Confirmar insumo detectado por la cámara:", df_insumos["Nombre"].tolist())

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
                    
                    # --- Lógica Dinámica de Alquiler / Venta ---
                    motivo_salida = ""
                    empresa_destino = ""
                    area_destino = ""
                    
                    if tipo_movimiento == "Restar Stock (Salida)":
                        col_mot1, col_mot2 = st.columns(2)
                        with col_mot1:
                            motivo_salida = st.selectbox("Motivo de la Salida:", ["Venta", "Alquiler"])
                        
                        if motivo_salida == "Alquiler":
                            with col_mot2:
                                empresa_destino = st.text_input("🏢 Empresa de Destino:", placeholder="Ej: Constructora Alfa")
                            area_destino = st.text_input("📍 Área de Destino:", placeholder="Ej: Obra Central")
                    
                    cantidad_mov = st.number_input("Cantidad a mover:", min_value=1, step=1, value=1)
                    
                    if st.button("Aplicar Movimiento"):
                        es_valido = True
                        if tipo_movimiento == "Restar Stock (Salida)" and cantidad_mov > cant_actual:
                            st.error(f"❌ Error: No puedes retirar {cantidad_mov} unidades porque solo quedan {cant_actual} en stock.")
                            es_valido = False
                        
                        if tipo_movimiento == "Restar Stock (Salida)" and motivo_salida == "Alquiler":
                            if not empresa_destino.strip() or not area_destino.strip():
                                st.error("❌ Error: Para registrar un alquiler debes ingresar la Empresa y el Área de destino.")
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
                                    area=area_destino
                                )
                            st.success(f"¡Stock actualizado! Ahora tienes {nueva_cantidad} unidades de '{seleccionado}'.")
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
            df_insumos["Categoría"].str.lower().str.contains(busqueda.lower())
        ]
    else:
        df_filtrado = df_insumos

    if df_filtrado.empty:
        st.warning("No se encontraron insumos.")
    else:
        st.dataframe(df_filtrado, use_container_width=True, hide_index=True)

# ==========================================
# 2. PESTAÑA DE VALORIZACIÓN DEL INVENTARIO
# ==========================================
with tab_valorizacion:
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

# ==========================================
# 3. PESTAÑA DE REPORTES Y AUDITORÍA POR FECHA
# ==========================================
with tab_reportes:
    st.subheader("📅 Filtro de Auditoría y Movimientos por Rango de Fecha")
    
    try:
        registros_hist = hoja_historial.get_all_records()
        df_hist = pd.DataFrame(registros_hist)
    except Exception as e:
        df_hist = pd.DataFrame()
        
    if not df_hist.empty and "Fecha" in df_hist.columns:
        df_hist["Fecha_dt"] = pd.to_datetime(df_hist["Fecha"], errors='coerce')
        
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            fecha_inicio = st.date_input("Desde:", value=datetime.today())
        with col_f2:
            fecha_fin = st.date_input("Hasta:", value=datetime.today())
            
        df_filtrado_fecha = df_hist[
            (df_hist["Fecha_dt"].dt.date >= fecha_inicio) & 
            (df_hist["Fecha_dt"].dt.date <= fecha_fin)
        ]
        
        if df_filtrado_fecha.empty:
            st.warning("No se registraron movimientos en el rango de fechas seleccionado.")
        else:
            df_mostrar = df_filtrado_fecha.drop(columns=["Fecha_dt"], errors='ignore')
            
            st.write(f"📝 Se encontraron **{len(df_mostrar)}** movimientos registrados:")
            st.dataframe(df_mostrar, use_container_width=True, hide_index=True)
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_mostrar.to_excel(writer, sheet_name='Movimientos Filtrados', index=False)
                
            st.download_button(
                label="📥 Descargar Reporte de este Rango (Excel)",
                data=buffer.getvalue(),
                file_name=f"Reporte_{fecha_inicio}_a_{fecha_fin}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        st.info("ℹ️ El historial de movimientos se encuentra vacío o la pestaña 'Historial' no tiene la columna 'Fecha'. Realiza un movimiento (Entrada/Salida) para comenzar a ver registros aquí.")

# ==========================================
# 4. PESTAÑA DE GESTIÓN DE USUARIOS (Exclusivo Admin)
# ==========================================
with tab_usuarios:
    if st.session_state["rol_actual"] == "Administrador":
        st.subheader("👥 Configuración de Cuentas del Sistema")
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
                    st.rerun()
                    
        with col_user_der:
            st.write("📋 **Usuarios Registrados**")
            df_lista_usuarios = obtener_usuarios()
            st.dataframe(df_lista_usuarios[["Usuario", "Rol"]], use_container_width=True, hide_index=True)
    else:
        st.warning("🔒 Esta sección es exclusiva para el Administrador de la plataforma.")