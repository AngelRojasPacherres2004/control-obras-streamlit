"auth.py"
"""
Módulo de autenticación y pantalla inicial
"""

import json
import streamlit as st
from util import set_background
from cookies_manager import cookies


# ====== PANTALLA INICIAL ======
def mostrar_pantalla_inicial():
    # Fondo
    set_background("Empresalogo.jpg")

    # Estilos (diseño del código A)
    st.markdown("""
        <style>
        /* Ocultar elementos Streamlit */
        #MainMenu, footer, header {visibility: hidden;}

        /* Reset */
        .main {
            padding: 0 !important;
        }

        /* CONTENEDOR GENERAL */
        .block-container {
            padding-top: 47vh !important;
            display: flex !important;
            justify-content: center !important;
            align-items: center !important;
        }

        /* CONTENEDOR DEL BOTÓN */
        div[data-testid="stButton"] {
            width: 350px !important;
            max-width: 70% !important;
        }

        /* BOTÓN */
        .stButton {
            display: flex !important;
            justify-content: flex-start !important; /* desktop */
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

        /* ====== CELULAR ====== */
        @media (max-width: 768px) {

            .block-container {
                padding-top: 32vh !important;
            }

            div[data-testid="stButton"] {
                max-width: 90% !important;
            }

            /* 🔥 AQUÍ SE CENTRA TODO EN CELULAR */
            .stButton {
                justify-content: center !important;
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
        set_background("Empresalogo.jpg")

        # Overlay oscuro + estilos del código A
        st.markdown("""
        <style>
        /* CONTENEDOR DE INPUTS */
        .login-box {
            background: rgba(255, 255, 255, 0.15);
            backdrop-filter: blur(8px);
            padding: 25px;
            border-radius: 14px;
            max-width: 420px;
            margin: auto;
            box-shadow: 0 8px 30px rgba(0,0,0,0.4);
        }

        /* INPUTS */
        .login-box input {
            background-color: #ffffff !important;
            color: #000000 !important;
            border-radius: 10px !important;
            border: 2px solid #000 !important;
            padding: 14px 16px !important;
            font-size: 16px !important;
        }

        /* LABELS */
        label, 
        div[data-testid="stTextInput"] label {
            color: #000000 !important;
            font-weight: 600;
        }

        /* ICONOS */
        .login-icon {
            font-size: 18px;
            margin-right: 6px;
        }
        </style>
        """, unsafe_allow_html=True)


        st.markdown("<br><br>", unsafe_allow_html=True)
        st.title("")

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

            # Guardar sesión
            st.session_state["auth"] = auth_data
            st.session_state["show_login"] = True

            # Guardar cookie
            cookies["auth"] = json.dumps(auth_data)
            cookies.save()

            st.rerun()

        return False
