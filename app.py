import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime
import io
import plotly.express as px

# Configuración de la página
st.set_page_config(page_title="Control de Inventario Cloud", page_icon="📦", layout="wide")

# --- CONTROL DE ACCESO (LOGIN) ---
def check_password():
    """Devuelve True si el usuario ingresó la contraseña correcta."""
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False

    if st.session_state["logged_in"]:
        return True

    st.subheader("🔑 Acceso al Sistema de Inventario")
    password = st.text_input("Introduce la contraseña de acceso:", type="password")
    
    if st.button("Ingresar"):
        # Puedes cambiar estas contraseñas por las que tú quieras
        if password == "admin123" or password == "equipo123":
            st.session_state["logged_in"] = True
            st.success("¡Acceso concedido!")
            st.rerun()
        else:
            st.error("❌ Contraseña incorrecta. Inténtalo de nuevo.")
    return False

# Si no pasa la contraseña, detenemos la ejecución aquí
if not check_password():
    st.stop()

# --- BOTÓN DE CERRAR SESIÓN ---
st.sidebar.write("**Sesión Activa**")
if st.sidebar.button("Cerrar Sesión"):
    st.session_state["logged_in"] = False
    st.rerun()

# --- CONEXIÓN CON GOOGLE SHEETS ---
@st.cache_resource
def conectar_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credenciales.json", scope)
    cliente = gspread.authorize(creds)
    return cliente.open("Inventario_Empresa")

try:
    sh = conectar_google_sheets()
    hoja_insumos = sh.worksheet("Insumos")
    hoja_historial = sh.worksheet("Historial")
except Exception as e:
    st.error("❌ Error al conectar con Google Sheets. Verifica tus credenciales.")
    st.stop()

# --- FUNCIONES DE SOPORTE ---
def obtener_insumos():
    registros = hoja_insumos.get_all_records()
    df = pd.DataFrame(registros)
    if df.empty:
        df = pd.DataFrame(columns=["ID", "Nombre", "Categoria", "Cantidad", "Stock Mínimo"])
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
st.write("Conectado en tiempo real con Google Sheets.")

df_insumos = obtener_insumos()

# --- ALERTAS DE STOCK CRÍTICO ---
st.subheader("⚠️ Alertas de Stock Crítico")
alertas_activas = False

if not df_insumos.empty:
    for index, fila in df_insumos.iterrows():
        if int(fila["Cantidad"]) <= int(fila["Stock Mínimo"]):
            st.error(f"🚨 **¡ALERTA DE STOCK BAJO!** El insumo **{fila['Nombre']}** ({fila['Categoria']}) tiene solo **{fila['Cantidad']}** unidades. (Mínimo: {fila['Stock Mínimo']})")
            alertas_activas = True

if not alertas_activas:
    st.success("✅ ¡Todos los insumos tienen niveles de stock saludables!")

st.markdown("---")

col_izq, col_der = st.columns([1, 1])

with col_izq:
    st.subheader("➕ Registrar Nuevo Insumo")
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

with col_der:
    st.subheader("🔄 Registrar Movimiento (Entrada/Salida)")
    if not df_insumos.empty:
        opciones = df_insumos["Nombre"].tolist()
        seleccionado = st.selectbox("Selecciona el insumo a modificar:", opciones)
        
        if seleccionado:
            datos_insumo = df_insumos[df_insumos["Nombre"] == seleccionado].iloc[0]
            id_insumo = datos_insumo["ID"]
            cant_actual = int(datos_insumo["Cantidad"])
            
            st.info(f"Cantidad actual en bodega: **{cant_actual}** unidades.")
            
            tipo_movimiento = st.radio("Tipo de movimiento:", ["Agregar Stock (Entrada)", "Restar Stock (Salida)"], horizontal=True)
            cantidad_mov = st.number_input("Cantidad a mover:", min_value=1, step=1, value=1)
            
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
        st.info("Registra un insumo a la izquierda para habilitar los movimientos.")

st.markdown("---")

# --- GRÁFICO VISUAL DE STOCK ---
if not df_insumos.empty:
    st.subheader("📊 Gráfico de Stock Actual")
    # Creamos un gráfico de barras interactivo con Plotly
    fig = px.bar(
        df_insumos, 
        x="Nombre", 
        y="Cantidad", 
        color="Categoria",
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
        df_insumos["Categoria"].str.lower().str.contains(busqueda.lower())
    ]
else:
    df_filtrado = df_insumos

if df_filtrado.empty:
    st.warning("No se encontraron insumos.")
else:
    st.dataframe(df_filtrado, use_container_width=True, hide_index=True)
    
    # EXPORTAR A EXCEL
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