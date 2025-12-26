import streamlit as st
import pandas as pd
from datetime import datetime
from firebase_admin import firestore

# Configuración de página
st.set_page_config(page_title="Materiales", layout="wide")

# Inicializar Firestore
db = firestore.client()

# Verificar autenticación
if "auth" not in st.session_state:
    st.error("Inicia sesión primero"); st.stop()

auth = st.session_state["auth"]
if auth["role"] != "jefe":
    st.warning("Acceso restringido"); st.stop()

# ================= ESTADO DE LA APP =================
if "edit_mat" not in st.session_state:
    st.session_state.edit_mat = None

# ================= FUNCIONES =================
def obtener_materiales():
    docs = db.collection("materiales").order_by("nombre").stream()
    return [{"id": d.id, **d.to_dict()} for d in docs]

def limpiar_seleccion():
    st.session_state.edit_mat = None
    st.rerun()

# ================= INTERFAZ =================
st.title("🧱 Administración de Materiales")

materiales = obtener_materiales()
df = pd.DataFrame(materiales)

col_tabla, col_form = st.columns([1.8, 1], gap="large")

# --- COLUMNA IZQUIERDA: LISTADO ---
with col_tabla:
    st.subheader("📋 Inventario General")
    
    busqueda = st.text_input("🔍 Buscar material...", placeholder="Ej: Cemento, Ladrillo...")
    
    filtered_df = df.copy()
    if busqueda and not filtered_df.empty:
        filtered_df = filtered_df[filtered_df['nombre'].str.contains(busqueda, case=False)]

    if not filtered_df.empty:
        # CORRECCIÓN AQUÍ: selection_mode="single-row"
        event = st.dataframe(
            filtered_df[["nombre", "unidad", "precio_unitario"]],
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row", 
            column_config={
                "nombre": "Material",
                "unidad": "Und",
                "precio_unitario": st.column_config.NumberColumn("Precio", format="$ %.2f")
            }
        )

        # Manejo de selección de fila
        # El evento devuelve un diccionario con los índices de las filas seleccionadas
        if event and "selection" in event and event["selection"]["rows"]:
            idx = event["selection"]["rows"][0]
            # Mapeamos el índice filtrado de vuelta al material original
            selected_id = filtered_df.iloc[idx]["id"]
            st.session_state.edit_mat = next(m for m in materiales if m["id"] == selected_id)
    else:
        st.info("No hay materiales que coincidan.")

# --- COLUMNA DERECHA: FORMULARIO ---
with col_form:
    edit_data = st.session_state.edit_mat
    
    st.subheader("📝 Gestión de Datos")
    
    with st.container(border=True):
        if edit_data:
            st.caption(f"Editando: {edit_data['nombre']}")
        else:
            st.caption("Crear nuevo registro")

        nombre = st.text_input("Nombre", value=edit_data["nombre"] if edit_data else "")
        unidad = st.text_input("Unidad", value=edit_data["unidad"] if edit_data else "")
        precio = st.number_input("Precio Unitario", min_value=0.0, step=0.01, 
                                value=float(edit_data["precio_unitario"]) if edit_data else 0.0)
        
        st.write("---")
        
        if edit_data:
            c1, c2 = st.columns(2)
            if c1.button("💾 Actualizar", type="primary", use_container_width=True):
                db.collection("materiales").document(edit_data["id"]).update({
                    "nombre": nombre, "unidad": unidad, "precio_unitario": precio
                })
                st.toast("✅ Actualizado"); limpiar_seleccion()
            
            if c2.button("🗑️ Borrar", use_container_width=True):
                db.collection("materiales").document(edit_data["id"]).delete()
                st.toast("🗑️ Eliminado"); limpiar_seleccion()
            
            if st.button("✖️ Cancelar Selección", use_container_width=True):
                limpiar_seleccion()
        else:
            if st.button("🚀 Guardar Nuevo Material", type="primary", use_container_width=True):
                if nombre and unidad:
                    db.collection("materiales").add({
                        "nombre": nombre, "unidad": unidad, 
                        "precio_unitario": precio, "creado": datetime.now()
                    })
                    st.toast("✨ Creado correctamente"); st.rerun()
                else:
                    st.error("Nombre y Unidad son obligatorios")