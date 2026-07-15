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
    
    # Si estamos en Streamlit Cloud, leemos desde Secrets
    if "gspread_credentials" in st.secrets:
        import json
        info_creds = json.loads(st.secrets["gspread_credentials"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(info_creds, scope)
    # Si estamos en local, leemos el archivo credenciales.json
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_name("credenciales.json", scope)
        
    cliente = gspread.authorize(creds)
    return cliente.open("Inventario_Empresa")

try:
    sh = conectar_google_sheets()
    hoja_insumos = sh.worksheet("Insumos")
    hoja_historial = sh.worksheet("Historial")
    hoja_usuarios = sh.worksheet("Usuarios") # Nueva pestaña de usuarios
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
    """Devuelve True si el usuario ingresó credenciales válidas y define su rol."""
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
        
        # Validar si el usuario y contraseña coinciden en la base de datos
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

# Si no pasa el login, detenemos la ejecución aquí
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
        df = pd.DataFrame(columns=["ID", "Nombre", "Categoría", "Cantidad", "Stock Mínimo"])
    return df

def registrar_insumo(nombre, categoria, cantidad, stock_minimo):
    df = obtener_insumos()
    nuevo_id = int(df["ID"].max() + 1) if not df.empty and pd.notna(df["ID"].max()) else 1
    hoja_insumos.append_row([nuevo_id, nombre, categoria, cantidad, stock_minimo])
    
    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    hoja_historial.append_row([fecha_actual, nombre, "Registro Inicial", cantidad, cantidad])

def actualizar_stock_sheet(id_insumo, nuevo_stock, nombre_insumo, tipo_mov, cant_movida):
    celda_id = hoja_insumos.find(str(id_insumo))
    if celda_id:
        hoja_insumos.update_cell(celda_id.row, 4, nuevo_stock)
        fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        hoja_historial.append_row([fecha_actual, nombre_insumo, tipo_mov, cant_movida, nuevo_stock])

# --- INTERFAZ DE USUARIO ---
st.title("📦 Sistema de Control de Inventario Cloud")
st.write(f"Conectado en tiempo real con Google Sheets. Sesión iniciada como **{st.session_state['rol_actual']}**.")

df_insumos = obtener_insumos()

# --- ALERTAS DE STOCK CRÍTICO (Solo para Admin y Secretaria) ---
if st.session_state["rol_actual"] in ["Administrador", "Secretaria"]:
    st.subheader("⚠️ Alertas de Stock Crítico")
    
    if not df_insumos.empty:
        # Creamos dos columnas o filas visuales para organizar el estado de todo el inventario
        for index, fila in df_insumos.iterrows():
            cant_actual = int(fila["Cantidad"])
            cant_minima = int(fila["Stock Mínimo"])
            
            if cant_actual <= cant_minima:
                st.error(f"🚨 **¡ALERTA DE STOCK BAJO!** El insumo **{fila['Nombre']}** ({fila['Categoría'] if 'Categoría' in fila else fila['Categoria']}) tiene **{cant_actual}** unidades. (Mínimo requerido: {cant_minima})")
            else:
                st.success(f"✅ **Stock Saludable:** El insumo **{fila['Nombre']}** ({fila['Categoría'] if 'Categoría' in fila else fila['Categoria']}) cuenta con **{cant_actual}** unidades. (Mínimo: {cant_minima})")
    else:
        st.info("No hay insumos registrados para analizar el stock.")
        
    st.markdown("---")
# --- SECCIÓN OPERATIVA (Diferenciada por Roles) ---
if st.session_state["rol_actual"] == "Técnico":
    st.warning("ℹ️ Tu cuenta de **Técnico** tiene permisos de 'Solo Lectura'. Puedes revisar las existencias y gráficos abajo.")
else:
    # Columnas para registrar insumos, modificar stock mínimo y movimientos
    col_izq, col_der = st.columns([1, 1])

    with col_izq:
        if st.session_state["rol_actual"] == "Administrador":
            # Pestañas internas para el Administrador
            tab_nuevo, tab_editar_min = st.tabs(["➕ Registrar Insumo", "✏️ Editar Stock Mínimo"])
            
            with tab_nuevo:
                st.write("**Registrar Nuevo Insumo**")
                with st.form("nuevo_insumo_form", clear_on_submit=True):
                    nombre = st.text_input("Nombre del Insumo", placeholder="Ej: Cajas de cartón")
                    categoria = st.text_input("Categoría", placeholder="Ej: Empaque")
                    cantidad_ini = st.number_input("Cantidad Inicial", min_value=0, step=1, value=0)
                    stock_min = st.number_input("Stock Mínimo (Alerta)", min_value=1, step=1, value=5)
                    guardado = st.form_submit_button("Guardar Insumo")

                if guardado:
                    if nombre.strip() == "":
                        st.error("Por favor, ingresa el nombre del insumo.")
                    elif not df_insumos.empty and nombre.lower() in df_insumos["Nombre"].str.lower().values:
                        st.warning("Ese insumo ya existe en la lista.")
                    else:
                        with st.spinner("Guardando en Google Sheets..."):
                            registrar_insumo(nombre, categoria, cantidad_ini, stock_min)
                        st.success(f"¡Insumo '{nombre}' registrado correctamente!")
                        st.cache_resource.clear()
                        st.rerun()
            
            with tab_editar_min:
                st.write("**Modificar Alerta de Stock Mínimo**")
                if not df_insumos.empty:
                    insumo_editar = st.selectbox("Selecciona el insumo a modificar:", df_insumos["Nombre"].tolist(), key="select_editar_min")
                    datos_insumo_editar = df_insumos[df_insumos["Nombre"] == insumo_editar].iloc[0]
                    id_insumo_editar = datos_insumo_editar["ID"]
                    min_actual = int(datos_insumo_editar["Stock Mínimo"])
                    
                    st.info(f"Stock mínimo actual para **{insumo_editar}**: {min_actual} unidades.")
                    
                    nuevo_minimo = st.number_input("Nuevo Stock Mínimo:", min_value=1, step=1, value=min_actual, key="num_nuevo_min")
                    
                    if st.button("Actualizar Stock Mínimo"):
                        celda_id = hoja_insumos.find(str(id_insumo_editar))
                        if celda_id:
                            # La columna 5 corresponde a "Stock Mínimo"
                            hoja_insumos.update_cell(celda_id.row, 5, nuevo_minimo)
                            st.success(f"¡Stock mínimo de '{insumo_editar}' actualizado a {nuevo_minimo}!")
                            st.cache_resource.clear()
                            st.rerun()
                else:
                    st.info("No hay insumos registrados para editar.")
        else:
            st.info("🔒 Las funciones de creación y edición de insumos están reservadas únicamente para el Administrador.")

    with col_der:
        st.subheader("🔄 Registrar Movimiento (Entrada/Salida)")
        if not df_insumos.empty:
            opciones = df_insumos["Nombre"].tolist()
            seleccionado = st.selectbox("Selecciona el insumo a modificar:", opciones, key="select_movimiento")
            
            if seleccionado:
                datos_insumo = df_insumos[df_insumos["Nombre"] == seleccionado].iloc[0]
                id_insumo = datos_insumo["ID"]
                cant_actual = int(datos_insumo["Cantidad"])
                
                st.info(f"Cantidad actual en bodega: **{cant_actual}** unidades.")
                
                tipo_movimiento = st.radio("Tipo de movimiento:", ["Agregar Stock (Entrada)", "Restar Stock (Salida)"], horizontal=True)
                cantidad_mov = st.number_input("Cantidad a mover:", min_value=1, step=1, value=1, key="num_cant_mover")
                
                if st.button("Aplicar Movimiento"):
                    if tipo_movimiento == "Agregar Stock (Entrada)":
                        nueva_cantidad = cant_actual + cantidad_mov
                        tipo_historial = "Entrada"
                    else:
                        nueva_cantidad = max(0, cant_actual - cantidad_mov)
                        tipo_historial = "Salida"
                    
                    with st.spinner("Actualizando datos en la nube..."):
                        actualizar_stock_sheet(id_insumo, nueva_cantidad, seleccionado, tipo_historial, cantidad_mov)
                    st.success(f"¡Stock actualizado! Ahora tienes {nueva_cantidad} unidades de '{seleccionado}'.")
                    st.cache_resource.clear()
                    st.rerun()
        else:
            st.info("Registra un insumo para habilitar los movimientos.")

    st.markdown("---")

# --- GRÁFICO VISUAL DE STOCK ---
if not df_insumos.empty:
    st.subheader("📊 Gráfico de Stock Actual")
    fig = px.bar(
        df_insumos, 
        x="Nombre", 
        y="Cantidad", 
        color="Categoría",
        title="Cantidad disponible por Insumo",
        text_auto=True,
        labels={"Cantidad": "Unidades Disponibles", "Nombre": "Insumo"}
    )
    fig.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# --- BUSCADOR Y EXPORTACIÓN ---
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
    
    # EXPORTACIÓN A EXCEL (Solo Admin y Secretaria)
    if st.session_state["rol_actual"] in ["Administrador", "Secretaria"]:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_insumos.to_excel(writer, sheet_name='Inventario Actual', index=False)
            try:
                registros_hist = hoja_historial.get_all_records()
                df_hist = pd.DataFrame(registros_hist)
                if not df_hist.empty:
                    df_hist.to_excel(writer, sheet_name='Historial Movimientos', index=False)
            except:
                pass
                
        st.download_button(
            label="📥 Descargar Reporte en Excel",
            data=buffer.getvalue(),
            file_name=f"Reporte_Inventario_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# --- PANEL DE ADMINISTRACIÓN DE USUARIOS (Exclusivo para Administrador) ---
if st.session_state["rol_actual"] == "Administrador":
    st.markdown("---")
    st.subheader("👥 Gestión de Usuarios y Roles")
    
    col_user_izq, col_user_der = st.columns([1, 1.5])
    
    with col_user_izq:
        st.write("➕ **Crear Nuevo Usuario**")
        with st.form("nuevo_usuario_form", clear_on_submit=True):
            nuevo_user = st.text_input("Nombre de Usuario", placeholder="Ej: maria.perez")
            nuevo_pass = st.text_input("Contraseña", type="password", placeholder="Ej: secre123")
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