"""
auth.py
Autenticación segura con streamlit-authenticator
Cada navegador / incógnito maneja su propia sesión
"""

import streamlit as st
import streamlit_authenticator as stauth
from firebase_admin import firestore
from util import set_background
import yaml


# ================= PANTALLA INICIAL =================
def mostrar_pantalla_inicial():
    set_background("Empresalogo.jpg")

    st.markdown("""
    <style>
    #MainMenu, footer, header {visibility: hidden;}
    .main { padding: 0 !important; }
    .block-container {
        padding-top: 45vh !important;
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
    }
    </style>
    """, unsafe_allow_html=True)

    if st.button("Iniciar Sesión", use_container_width=True):
        st.session_state.show_login = True
        st.rerun()


# ================= LOGIN =================
def verificar_autenticacion(db: firestore.Client):
    """
    Login seguro por navegador usando cookies propias de streamlit-authenticator
    """

    if "auth" in st.session_state:
        return

    set_background("Empresalogo.jpg")

    st.markdown("<br><br>", unsafe_allow_html=True)
    st.title("CONTROL DE OBRAS 2025")

    # ================= OBTENER USUARIOS DE FIRESTORE =================
    users_ref = db.collection("users").stream()

    credentials = {"usernames": {}}

    for u in users_ref:
        d = u.to_dict()
        credentials["usernames"][d["username"]] = {
            "name": d["username"],
            "password": d["password"],  # ⚠️ idealmente hash
            "role": d.get("role"),
            "obra": d.get("obra")
        }

    # ================= AUTHENTICATOR =================
    authenticator = stauth.Authenticate(
        credentials=credentials,
        cookie_name="control_obras_auth",
        key="control_obras_key",
        cookie_expiry_days=7
    )

    name, auth_status, username = authenticator.login(location="main")

    # ================= RESULTADOS =================
    if auth_status is False:
        st.error("Usuario o contraseña incorrectos")

    elif auth_status is None:
        st.info("Ingrese sus credenciales")

    elif auth_status:
        user_data = credentials["usernames"][username]

        st.session_state["auth"] = {
            "username": username,
            "role": user_data.get("role"),
            "obra": user_data.get("obra")
        }

        st.session_state.show_login = True
        st.rerun()


# ================= LOGOUT =================
def cerrar_sesion(authenticator):
    authenticator.logout("🚪 Cerrar sesión", location="sidebar")
