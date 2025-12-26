import streamlit as st
import pandas as pd
from firebase_admin import firestore

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
        "username": d.to_dict().get("username"),
        "password": d.to_dict().get("password"),
        "role": d.to_dict().get("role"),
        "obra": d.to_dict().get("obra")
    } for d in docs]

def generar_id(username, obra):
    return f"{username.strip().lower()}-{obra.strip().lower()}"

# ================= CONTEXTO =================
auth = st.session_state["auth"]
OBRAS = obtener_obras()
OBRAS_OPCIONES = ["all"] + list(OBRAS.keys())

# ================= ADMIN =================
if auth["role"] == "jefe":
    st.header("👤 Gestión de Usuarios")

    # ---------- CREAR USUARIO ----------
    st.subheader("➕ Crear usuario")

    with st.form("crear_usuario"):
        username = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        role = st.selectbox("Rol", ["jefe", "pasante"])
        obra = st.selectbox("Obra asignada", options=OBRAS_OPCIONES)
        crear = st.form_submit_button("CREAR USUARIO")

    if crear:
        if not username or not password:
            st.error("Usuario y contraseña obligatorios")
        else:
            doc_id = generar_id(username, obra)
            ref = db.collection("users").document(doc_id)

            if ref.get().exists:
                st.error("Ese usuario ya existe para esa obra")
            else:
                ref.set({
                    "username": username,
                    "password": password,
                    "role": role,
                    "obra": obra
                })
                st.success("Usuario creado correctamente")
                st.rerun()

    # ---------- LISTAR USUARIOS ----------
    st.subheader("👤 Usuarios registrados")
    usuarios = obtener_usuarios()

    if usuarios:
        st.dataframe(
            pd.DataFrame(usuarios)[["username", "role", "obra"]],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No hay usuarios creados")

    # ---------- EDITAR / ELIMINAR ----------
    st.subheader("✏️ Editar / 🗑️ Eliminar usuario")

    if usuarios:
        user_sel = st.selectbox(
            "Selecciona un usuario",
            options=usuarios,
            format_func=lambda x: f"{x['username']} ({x['role']} - {x['obra']})"
        )

        with st.form("editar_usuario"):
            password_e = st.text_input("Contraseña", value=user_sel["password"], type="password")
            role_e = st.selectbox("Rol", ["jefe", "pasante"],
                                  index=["jefe", "pasante"].index(user_sel["role"]))
            obra_e = st.selectbox("Obra asignada", options=OBRAS_OPCIONES,
                                  index=OBRAS_OPCIONES.index(user_sel["obra"]))

            col1, col2 = st.columns(2)
            guardar = col1.form_submit_button("💾 Guardar cambios")
            borrar = col2.form_submit_button("🗑️ Eliminar usuario")

        if guardar:
            nuevo_id = generar_id(user_sel["username"], obra_e)

            if nuevo_id != user_sel["id"]:
                if db.collection("users").document(nuevo_id).get().exists:
                    st.error("Ya existe un usuario con esa obra")
                    st.stop()

                db.collection("users").document(nuevo_id).set({
                    "username": user_sel["username"],
                    "password": password_e,
                    "role": role_e,
                    "obra": obra_e
                })
                db.collection("users").document(user_sel["id"]).delete()
            else:
                db.collection("users").document(user_sel["id"]).update({
                    "password": password_e,
                    "role": role_e,
                    "obra": obra_e
                })

            st.success("Usuario actualizado")
            st.rerun()

        if borrar:
            db.collection("users").document(user_sel["id"]).delete()
            st.warning("Usuario eliminado")
            st.rerun()
