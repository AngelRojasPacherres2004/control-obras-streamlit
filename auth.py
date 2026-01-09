import streamlit as st
from util import set_background
from cookies_manager import cookies
import uuid
from firebase_admin import firestore

def mostrar_pantalla_inicial():
    set_background("Empresalogo.jpg")

    if st.button("Iniciar Sesión", use_container_width=True):
        st.session_state.show_login = True
        st.rerun()


def verificar_autenticacion(db):

    if "auth" in st.session_state:
        return

    set_background("Empresalogo.jpg")
    st.title("CONTROL DE OBRAS 2025")

    username = st.text_input("Usuario", key="login_user")
    password = st.text_input("Contraseña", type="password", key="login_pass")

    if not st.button("INGRESAR"):
        return

    # ===== VALIDAR USUARIO =====
    user_doc = db.collection("users").document(username).get()
    if not user_doc.exists:
        st.error("Usuario no existe")
        return

    data = user_doc.to_dict()
    if password != data.get("password"):
        st.error("Contraseña incorrecta")
        return

    # ===== BROWSER ID =====
    if "browser_id" not in cookies:
        cookies["browser_id"] = str(uuid.uuid4())

    browser_id = cookies["browser_id"]

    # ===== ELIMINAR SESIÓN ANTERIOR =====
    if cookies.get("session_id"):
        db.collection("sessions").document(cookies["session_id"]).delete()

    # ===== CREAR NUEVA SESIÓN =====
    session_id = str(uuid.uuid4())

    db.collection("sessions").document(session_id).set({
        "username": data["username"],
        "role": data["role"],
        "obra": data.get("obra"),
        "browser_id": browser_id,
        "created_at": firestore.SERVER_TIMESTAMP
    })

    # 🔴 GUARDAR COOKIE SOLO UNA VEZ
    cookies["session_id"] = session_id
    cookies.save()

    # ===== SESIÓN STREAMLIT =====
    st.session_state.clear()
    st.session_state["auth"] = {
        "username": data["username"],
        "role": data["role"],
        "obra": data.get("obra"),
        "session_id": session_id
    }
    st.session_state["show_login"] = True

    st.rerun()
