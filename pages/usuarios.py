import streamlit as st
import pandas as pd
from datetime import datetime, date
import cloudinary
import cloudinary.uploader
import firebase_admin
from firebase_admin import credentials, firestore


st.set_page_config(page_title="Usuarios", layout="wide")

st.title("👷 CRUD de Usuarios")

st.info("Aquí se administrarán los usuarios")

db = firestore.client()

# ================= FUNCIONES =================
def obtener_obras():
    return {d.id: d.to_dict()["nombre"] for d in db.collection("obras").stream()}

def obtener_usuarios():
    docs = db.collection("users").stream()
    return [{
        "id": d.id,
        "obra": d.to_dict()["obra"],
        "password": d.to_dict()["password"],
        "username": d.to_dict()["username"],
        "role": d.to_dict()["role"]
    } for d in docs]

# ================= SELECCIÓN DE OBRA SINCRONIZADA =================
OBRAS = obtener_obras()
lista_ids = list(OBRAS.keys())
OBRAS_OPCIONES = ["all"] + lista_ids

# 1. Recuperar la selección global para el selector del sidebar
if "obra_id_global" not in st.session_state and lista_ids:
    st.session_state["obra_id_global"] = lista_ids[0]

indice_actual_sidebar = 0
if st.session_state.get("obra_id_global") in lista_ids:
    indice_actual_sidebar = lista_ids.index(st.session_state["obra_id_global"])

# 2. Selector en Sidebar (para no perder la sincronización al navegar)
obra_id_contexto = st.sidebar.selectbox(
    "Seleccionar obra (Navegación)",
    options=lista_ids,
    format_func=lambda x: OBRAS.get(x, x),
    index=indice_actual_sidebar,
    key="selector_usuarios_nav"
)
st.session_state["obra_id_global"] = obra_id_contexto

st.sidebar.divider()
st.sidebar.info("💡 La selección del menú lateral sincroniza tu vista en las otras pestañas.")

# ================= ADMIN: GESTIÓN DE USUARIOS =================
auth = st.session_state["auth"]

if auth["role"] == "jefe":
    st.header("👤 Gestión de Usuarios")
    st.subheader("➕ Crear usuario")

    # ---- CREAR USUARIO ----
    with st.form("crear_usuario"):
        username = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        role = st.selectbox("Rol", ["jefe", "pasante"])
        
        # 3. Predeterminamos la obra del formulario con la del sidebar para ahorrar tiempo
        idx_defecto_form = OBRAS_OPCIONES.index(obra_id_contexto) if obra_id_contexto in OBRAS_OPCIONES else 0
        
        obra = st.selectbox(
            "Obra asignada",
            options=OBRAS_OPCIONES,
            index=idx_defecto_form,
            help="Usa 'all' para administradores"
        )
        crear_user = st.form_submit_button("CREAR USUARIO")
    if crear_user:
        if not username or not password:
            st.error("Nombre y contraseña obligatorios")
        else:
            db.collection("users").document(username).set({
                "obra": obra,
                "password": password,
                "username": username,
                "role": role
            })
            st.success("Usuario creado")
            st.rerun()
    # ---- LISTA USUARIOS REGISTRADOS ----
    st.subheader("👤 Usuarios registrados")
    usuarios = obtener_usuarios()
    if usuarios:
        st.dataframe(
            pd.DataFrame(usuarios)[["username", "password", "role", "obra"]],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No hay usuarios creados")

    # ---- ACTUALIZAR USUARIOS ----
    st.subheader("✏️ Editar / 🗑️ Eliminar usuario")

    if not usuarios:
        st.info("No hay usuarios para editar")
    else:
        user_sel = st.selectbox(
            "Selecciona un usuarios",
            options=usuarios,
            format_func=lambda x: f"{x['username']} ({x['role']})"
        )

    with st.form("editar_usuario"):
        username_e = st.text_input("Usuario",
            value=user_sel["username"],
            disabled=True)
        password_e = st.text_input("Contraseña",
            value=user_sel["password"],
            type="password")
        role_e = st.selectbox("Rol",
            ["jefe", "pasante"],
            index=["jefe", "pasante"].index(user_sel["role"]))
        obra_e = st.selectbox("Obra asignada",
            options=OBRAS_OPCIONES,
            index=OBRAS_OPCIONES.index(user_sel["obra"])
            if user_sel["obra"] in OBRAS_OPCIONES else 0)
        
        col1, col2 = st.columns(2)
        guardar = col1.form_submit_button("💾 Guardar cambios")
        borrar = col2.form_submit_button("🗑️ Eliminar usuario")

    if guardar:
        db.collection("users").document(user_sel["id"]).update({
            "username": username_e,
            "password": password_e,
            "role": role_e,
            "obra": obra_e
        })
        st.success("Usuario actualizado")
        st.rerun()
    
    if borrar:
        st.warning("Usuario eliminado")
        db.collection("users").document(user_sel["id"]).delete()
        st.rerun()
