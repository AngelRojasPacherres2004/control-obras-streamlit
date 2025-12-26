import streamlit as st
import pandas as pd
from datetime import datetime
from firebase_admin import firestore

st.set_page_config(page_title="Materiales", layout="wide")

# Inicializar Firestore y Auth
db = firestore.client()
if "auth" not in st.session_state:
    st.error("Inicia sesión primero"); st.stop()

auth = st.session_state["auth"]
if auth["role"] != "jefe":
    st.warning("Acceso restringido"); st.stop()

# ================= ESTADO DE LA APP =================
# Usamos session_state para saber si estamos editando o creando
if "edit_mat" not in st.session_state:
    st.session_state.edit_mat = None # Almacenará el dict del material seleccionado

# ================= FUNCIONES =================
def obtener_materiales():
    docs = db.collection("materiales").order_by("nombre").stream()
    return [{"id": d.id, **d.to_dict()} for d in docs]

def limpiar_seleccion():
    st.session_state.edit_mat = None
    st.rerun()

# ================= DISEÑO DE INTERFAZ =================
st.title("🧱 Administración de Materiales")

# Cargamos datos
materiales = obtener_materiales()
df = pd.DataFrame(materiales)

# Layout de dos columnas
col_tabla, col_form = st.columns([1.8, 1], gap="large")

# --- COLUMNA IZQUIERDA: LISTADO ---
with col_tabla:
    st.subheader("📋 Inventario General")
    
    # Buscador rápido
    busqueda = st.text_input("🔍 Buscar material...", placeholder="Escribe el nombre...")
    if busqueda and not df.empty:
        df = df[df['nombre'].str.contains(busqueda, case=False)]

    if not df.empty:
        # Mostramos la tabla. Usamos st.dataframe con selección.
        selected_rows = st.dataframe(
            df[["nombre", "unidad", "precio_unitario"]],
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single",
            column_config={
                "precio_unitario": st.column_config.NumberColumn("Precio", format="$ %.2f")
            }
        )

        # Si el usuario hace clic en una fila de la tabla
        if len(selected_rows["selection"]["rows"]) > 0:
            idx = selected_rows["selection"]["rows"][0]
            st.session_state.edit_mat = materiales[idx]
    else:
        st.info("No se encontraron materiales.")

# --- COLUMNA DERECHA: FORMULARIO DINÁMICO ---
with col_form:
    edit_data = st.session_state.edit_mat
    
    # Título dinámico
    if edit_data:
        st.subheader("📝 Editar Material")
        st.caption(f"ID: {edit_data['id']}")
    else:
        st.subheader("➕ Nuevo Material")
    
    # Formulario Único
    with st.container(border=True):
        nombre = st.text_input("Nombre", value=edit_data["nombre"] if edit_data else "")
        unidad = st.text_input("Unidad", value=edit_data["unidad"] if edit_data else "")
        precio = st.number_input("Precio Unitario", min_value=0.0, step=0.01, 
                                value=float(edit_data["precio_unitario"]) if edit_data else 0.0)
        
        st.write("---")
        
        if edit_data:
            # Botones para modo EDICIÓN
            c1, c2 = st.columns(2)
            if c1.button("💾 Actualizar", type="primary", use_container_width=True):
                db.collection("materiales").document(edit_data["id"]).update({
                    "nombre": nombre, "unidad": unidad, "precio_unitario": precio
                })
                st.toast("Material actualizado"); limpiar_seleccion()
            
            if c2.button("🗑️ Eliminar", type="secondary", use_container_width=True):
                db.collection("materiales").document(edit_data["id"]).delete()
                st.toast("Material eliminado"); limpiar_seleccion()
            
            if st.button("✖️ Cancelar", use_container_width=True):
                limpiar_seleccion()
        else:
            # Botón para modo CREACIÓN
            if st.button("🚀 Crear Material", type="primary", use_container_width=True):
                if nombre and unidad:
                    db.collection("materiales").add({
                        "nombre": nombre, "unidad": unidad, 
                        "precio_unitario": precio, "creado": datetime.now()
                    })
                    st.toast("Material creado"); st.rerun()
                else:
                    st.error("Completa los campos")

st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 1.5rem; }
    .stButton button { border-radius: 8px; }
    </style>
    """, unsafe_allow_width=True)