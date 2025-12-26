import streamlit as st
import pandas as pd
from datetime import datetime
from firebase_admin import firestore

# 1. Conexión a Base de Datos
db = firestore.client()

# 2. Protección de Ruta y Roles
if "auth" not in st.session_state:
    st.error("Por favor, inicia sesión."); st.stop()

auth = st.session_state["auth"]
if auth["role"] != "jefe":
    st.warning("No tienes permisos para gestionar el catálogo."); st.stop()

# 3. Estado de Selección
if "mat_edit" not in st.session_state:
    st.session_state.mat_edit = None

# 4. Funciones de Datos
def cargar_materiales():
    docs = db.collection("materiales").order_by("nombre").stream()
    return [{"id": d.id, **d.to_dict()} for d in docs]

def limpiar_y_recargar():
    st.session_state.mat_edit = None
    st.rerun()

# ================= INTERFAZ VISUAL =================
st.title("🧱 Catálogo de Materiales")

materiales = cargar_materiales()
df = pd.DataFrame(materiales)

# Layout de dos columnas: Tabla a la izquierda, Formulario a la derecha
col_izq, col_der = st.columns([1.6, 1], gap="medium")

with col_izq:
    st.subheader("📋 Lista de Insumos")
    
    # Buscador dinámico
    query = st.text_input("Buscar material...", placeholder="Ej: Cemento, Ladrillo...", label_visibility="collapsed")
    
    df_ver = df.copy()
    if query and not df_ver.empty:
        df_ver = df_ver[df_ver['nombre'].str.contains(query, case=False)]

    if not df_ver.empty:
        # Tabla interactiva con selección de fila única
        seleccion = st.dataframe(
            df_ver[["nombre", "unidad", "precio_unitario"]],
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row", 
            column_config={
                "nombre": "Descripción",
                "unidad": "Medida",
                "precio_unitario": st.column_config.NumberColumn("Precio", format="$ %.2f")
            }
        )

        # Detectar clic en fila
        if seleccion and "selection" in seleccion and seleccion["selection"]["rows"]:
            idx = seleccion["selection"]["rows"][0]
            id_real = df_ver.iloc[idx]["id"]
            st.session_state.mat_edit = next(m for m in materiales if m["id"] == id_real)
    else:
        st.info("No hay materiales registrados.")

with col_der:
    mat = st.session_state.mat_edit
    st.subheader("➕ " + ("Editar registro" if mat else "Nuevo material"))
    
    with st.container(border=True):
        nombre = st.text_input("Nombre del material", value=mat["nombre"] if mat else "")
        unidad = st.text_input("Unidad de medida", value=mat["unidad"] if mat else "")
        precio = st.number_input("Precio Unitario", min_value=0.0, step=0.01, 
                                value=float(mat["precio_unitario"]) if mat else 0.0)
        
        st.write("---")
        
        if mat:
            # BOTONES MODO EDICIÓN
            c1, c2 = st.columns(2)
            if c1.button("💾 Actualizar", type="primary", use_container_width=True):
                db.collection("materiales").document(mat["id"]).update({
                    "nombre": nombre, "unidad": unidad, "precio_unitario": precio
                })
                st.toast("✅ Cambios guardados"); limpiar_y_recargar()
            
            if c2.button("🗑️ Eliminar", use_container_width=True):
                db.collection("materiales").document(mat["id"]).delete()
                st.toast("🗑️ Material borrado"); limpiar_y_recargar()
            
            if st.button("✖️ Cancelar selección", use_container_width=True):
                limpiar_y_recargar()
        else:
            # BOTÓN MODO CREACIÓN
            if st.button("🚀 Crear Material", type="primary", use_container_width=True):
                if nombre and unidad:
                    db.collection("materiales").add({
                        "nombre": nombre, "unidad": unidad, 
                        "precio_unitario": precio, "creado": datetime.now()
                    })
                    st.toast("✨ Registro exitoso"); st.rerun()
                else:
                    st.error("Nombre y Unidad requeridos")


st.markdown("""
    <style>
    .stDataFrame { border: 1px solid #e6e9ef; border-radius: 8px; }
    div[data-testid="stForm"] { background-color: #f9f9f9; }
    </style>
    """, unsafe_allow_html=True)