"""
Módulo de autenticación y pantalla inicial
"""
import json
import streamlit as st
from util import set_background
from cookies_manager import cookies


# ====== PANTALLA INICIAL ======
def mostrar_pantalla_inicial():
    # Mismo fondo que código A
    set_background("Empresalogo.jpg", "Empresalogo_mobile.jpg")

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

    if st.button("Iniciar Sesión", use_container_width=True, key="btn_pantalla_inicial"):
        st.session_state.show_login = True
        st.rerun()


# ====== LOGIN ======
def verificar_autenticacion(db):
    if "auth" not in st.session_state:
        set_background("Empresalogo.jpg", "Empresalogo_mobile.jpg")

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

        if st.button("INGRESAR", key="btn_login"):
            user_doc = db.collection("users").document(username).get()

            if not user_doc.exists:
                st.error("Usuario no existe")
                return False

            data = user_doc.to_dict()

            if password != data.get("password"):
                st.error("Contraseña incorrecta")
                return False

            auth_data = {
                "username": data["username"],
                "role": data["role"],
                "obra": data.get("obra")
            }

            st.session_state["auth"] = auth_data
            st.session_state["show_login"] = True

            # Guardar cookie (lógica B intacta)
            cookies["auth"] = json.dumps(auth_data)
            cookies.save()

            st.rerun()

        return False
