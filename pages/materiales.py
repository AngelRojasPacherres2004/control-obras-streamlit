import streamlit as st
import pandas as pd
from datetime import datetime
from firebase_admin import firestore

# 1. Configuración y Seguridad
db = firestore.client()

if "auth" not in st.session_state:
    st.error("Sesión no iniciada"); st.stop()

auth = st.session_state["auth"]
if auth["role"] != "jefe":
    st.warning("No tienes permisos de administrador"); st.stop()

# 2. Estado de selección
if "material_seleccionado" not in st.session_state:
    st.session_state.material_seleccionado = None

# 3. Funciones de datos
def obtener_materiales():
    docs = db.collection("materiales").order_by("nombre").stream()
    return [{"id": d.id, **d.to_dict()} for d in docs]

def reset_form():
    st.session_state.material_seleccionado = None
    st.rerun()

# ================= INTERFAZ =================
st.title("🧱 Catálogo de Materiales")

materiales = obtener_materiales()
df = pd.DataFrame(materiales)

# Layout: Lista (Izquierda) | Formulario (Derecha)
col_lista, col_form = st.columns([1.5, 1], gap="medium")

with col_lista:
    st.subheader("📦 Existencias")
    
    # Buscador integrado
    search = st.text_input("🔍 Buscar...", label_visibility="collapsed", placeholder="Buscar material...")
    
    df_display = df.copy()
    if search:
        df_display = df_display[df_display['nombre'].str.contains(search, case=False)]

    # TABLA INTERACTIVA (CORREGIDA)
    # Usamos "single-row" para evitar el error de la API
    seleccion = st.dataframe(
        df_display[["nombre", "unidad", "precio_unitario"]],
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

    # Lógica para detectar selección
    if seleccion and seleccion["selection"]["rows"]:
        idx = seleccion["selection"]["rows"][0]
        # Obtenemos el ID real del material seleccionado
        selected_id = df_display.iloc[idx]["id"]
        st.session_state.material_seleccionado = next(m for m in materiales if m["id"] == selected_id)

with col_form:
    mat = st.session_state.material_seleccionado
    
    # Encabezado dinámico
    st.subheader("📝 " + ("Editar" if mat else "Nuevo"))
    
    with st.container(border=True):
        nombre = st.text_input("Nombre", value=mat["nombre"] if mat else "")
        unidad = st.text_input("Unidad", value=mat["unidad"] if mat else "")
        precio = st.number_input("Precio Unitario", min_value=0.0, step=0.01, 
                                value=float(mat["precio_unitario"]) if mat else 0.0)
        
        st.divider()
        
        if mat:
            # MODO EDICIÓN
            c1, c2 = st.columns(2)
            if c1.button("💾 Guardar", type="primary", use_container_width=True):
                db.collection("materiales").document(mat["id"]).update({
                    "nombre": nombre, "unidad": unidad, "precio_unitario": precio
                })
                st.toast("Actualizado ✅"); reset_form()
            
            if c2.button("🗑️ Borrar", use_container_width=True):
                db.collection("materiales").document(mat["id"]).delete()
                st.toast("Eliminado 🗑️"); reset_form()
                
            if st.button("➕ Crear uno nuevo", use_container_width=True):
                reset_form()
        else:
            # MODO CREACIÓN
            if st.button("🚀 Registrar Material", type="primary", use_container_width=True):
                if nombre and unidad:
                    db.collection("materiales").add({
                        "nombre": nombre, "unidad": unidad, 
                        "precio_unitario": precio, "creado": datetime.now()
                    })
                    st.toast("Creado con éxito ✨"); st.rerun()
                else:
                    st.error("Completa los datos")

# Estilo CSS para mejorar el diseño compacto
st.markdown("""
    <style>
    .stDataFrame { border: 1px solid #f0f2f6; border-radius: 10px; }
    div[data-testid="stExpander"] { border: none !important; }
    </style>
    """, unsafe_allow_html=True)