"""
Módulo de autenticación y pantalla inicial
"""
import streamlit as st
from util import set_background
from cookies_manager import cookies
import uuid
from firebase_admin import firestore


# ======================================================
# PANTALLA INICIAL
# ======================================================
def mostrar_pantalla_inicial():
    set_background("Empresalogo.jpg")

    st.markdown("""
    <style>
    #MainMenu, footer, header {visibility: hidden;}

    .main {
        padding: 0 !important;
    }

    .block-container {
        padding-top: 47vh !important;
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
    }

    div[data-testid="stButton"] {
        width: 350px !important;
        max-width: 70% !important;
    }

    .stButton button {
        background-color: rgba(0, 0, 0, 0.8) !important;
        color: white !important;
        border: 2px solid white !important;
        font-size: 18px !important;
        padding: 12px 24px !important;
        border-radius: 8px !important;
        width: 100% !important;
    }

    @media (max-width: 768px) {
        .block-container {
            padding-top: 32vh !important;
        }

        div[data-testid="stButton"] {
            max-width: 85% !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)

    if st.button("Iniciar Sesión", use_container_width=True):
        st.session_state.show_login = True
        st.rerun()


# ======================================================
# LOGIN + AUTENTICACIÓN SEGURA
# ======================================================
def verificar_autenticacion(db):

    # Evitar doble render
    if "auth" in st.session_state:
        return

    set_background("Empresalogo.jpg")

    st.markdown("""
    <style>
    .stApp::after {
        content: "";
        position: fixed;
        inset: 0;
        background-color: rgba(0, 0, 0, 0.6);
        z-index: 0;
        pointer-events: none;
    }

    section[data-testid="stAppViewContainer"] > .main {
        position: relative;
        z-index: 1;
    }

    input {
        background-color: #ffffff !important;
        color: #000000 !important;
    }

    label {
        color: #ffffff !important;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<br><br>", unsafe_allow_html=True)
    st.title("CONTROL DE OBRAS 2025")

    username = st.text_input("Usuario")
    password = st.text_input("Contraseña", type="password")

    if not st.button("INGRESAR"):
        return

    # ==================================================
    # VALIDAR USUARIO
    # ==================================================
    user_doc = db.collection("users").document(username).get()

    if not user_doc.exists:
        st.error("Usuario no existe")
        return

    data = user_doc.to_dict()

    if password != data.get("password"):
        st.error("Contraseña incorrecta")
        return

    # ==================================================
    # IDENTIDAD DEL NAVEGADOR
    # ==================================================
    if not cookies.get("browser_id"):
        cookies["browser_id"] = str(uuid.uuid4())
        cookies.save()

    browser_id = cookies["browser_id"]

    # ==================================================
    # ELIMINAR SESIÓN ANTERIOR (MISMO NAVEGADOR)
    # ==================================================
    if cookies.get("session_id"):
        db.collection("sessions").document(cookies["session_id"]).delete()
        del cookies["session_id"]
        cookies.save()

    # ==================================================
    # CREAR NUEVA SESIÓN
    # ==================================================
    session_id = str(uuid.uuid4())

    db.collection("sessions").document(session_id).set({
        "username": data["username"],
        "role": data["role"],
        "obra": data.get("obra"),
        "browser_id": browser_id,
        "created_at": firestore.SERVER_TIMESTAMP
    })

    cookies["session_id"] = session_id
    cookies.save()

    # ==================================================
    # GUARDAR SESIÓN EN STREAMLIT
    # ==================================================
    st.session_state["auth"] = {
        "username": data["username"],
        "role": data["role"],
        "obra": data.get("obra"),
        "session_id": session_id
    }

    st.session_state.show_login = True

    st.rerun()
