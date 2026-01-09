"""
auth.py
Autenticación correcta por navegador
NO comparte sesión entre usuarios
"""

import streamlit as st
import streamlit_authenticator as stauth
from firebase_admin import firestore
from util import set_background


# ================= LOGIN SCREEN =================
def login_screen(db: firestore.Client):
    """
    Pantalla de login segura
    Cada navegador maneja su propia sesión
    """

    # Si ya está autenticado, no volver a mostrar login
    if "auth" in st.session_state:
        return None

    set_background("Empresalogo.jpg")

    st.markdown("<br><br>", unsafe_allow_html=True)
    st.title("CONTROL DE OBRAS 2025")

    # ===== CARGAR USUARIOS DESDE FIREBASE =====
    users_ref = db.collection("users").stream()

    credentials = {"usernames": {}}

    for u in users_ref:
        d = u.to_dict()
        credentials["usernames"][d["username"]] = {
            "name": d["username"],
            "password": d["password"],  # idealmente hash
            "role": d.get("role"),
            "obra": d.get("obra")
        }

    # ===== AUTHENTICATOR =====
    authenticator = stauth.Authenticate(
        credentials=credentials,
        cookie_name="control_obras_auth",
        key="control_obras_key",
        cookie_expiry_days=7
    )

    name, auth_status, username = authenticator.login("Iniciar sesión", "main")

    if auth_status is False:
        st.error("Usuario o contraseña incorrectos")
        return None

    if auth_status is None:
        st.info("Ingrese sus credenciales")
        return None

    if auth_status:
        user = credentials["usernames"][username]

        st.session_state["auth"] = {
            "username": username,
            "role": user.get("role"),
            "obra": user.get("obra")
        }

        st.rerun()

    return authenticator


# ================= LOGOUT =================
def logout_screen(authenticator):
    if authenticator:
        authenticator.logout("🚪 Cerrar sesión", location="sidebar")
