"""usuarios.py"""
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

# ================= SELECCIÓN DE OBRA =================
auth = st.session_state["auth"]
OBRAS = obtener_obras()
OBRAS_OPCIONES = ["all"] + list(OBRAS.keys())

# ================= ADMIN: GESTIÓN DE USUARIOS =================
if auth["role"] == "jefe":
    st.header("👤 Gestión de Usuarios")

    st.subheader("➕ Crear usuario")

    # ---- CREAR USUARIO ----
    with st.form("crear_usuario"):
        username = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        role = st.selectbox("Rol", ["jefe", "pasante"])
        obra = st.selectbox(
            "Obra asignada",
            options=OBRAS_OPCIONES,
            help="Usa 'all' para jefe"
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
