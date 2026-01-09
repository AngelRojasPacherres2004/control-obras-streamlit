"""
auth.py
Autenticación segura por navegador (SIN cookies manuales)
Compatible con versiones antiguas de streamlit-authenticator
"""

import streamlit as st
import streamlit_authenticator as stauth
from util import set_background
from firebase_admin import firestore


def login_screen(db: firestore.Client):

    if "auth" in st.session_state:
        return None

    set_background("Empresalogo.jpg")

    st.markdown("<br><br>", unsafe_allow_html=True)
    st.title("CONTROL DE OBRAS 2025")

    # ===== CARGAR USUARIOS =====
    users = db.collection("users").stream()

    credentials = {"usernames": {}}

    for u in users:
        d = u.to_dict()
        credentials["usernames"][d["username"]] = {
            "name": d["username"],
            "password": d["password"],  # texto plano (luego se hashea)
            "role": d.get("role"),
            "obra": d.get("obra")
        }

    authenticator = stauth.Authenticate(
        credentials,
        cookie_name="control_obras_auth",
        key="control_obras_key",
        cookie_expiry_days=7
    )

    # 🔥 ÚNICA FORMA COMPATIBLE CON TU VERSIÓN
    name, auth_status, username = authenticator.login(
        "Iniciar sesión",
        "unrendered"
    )

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


def logout_button(authenticator):
    if authenticator:
        authenticator.logout("🚪 Cerrar sesión", "sidebar")
