"""
Módulo de autenticación y pantalla inicial
"""

import json
import streamlit as st
from util import set_background_responsive
from cookies_manager import cookies


# ====== PANTALLA INICIAL ======
def mostrar_pantalla_inicial():
    # Fondo responsive
    set_background_responsive("Empresalogo_pc.jpg", "Empresalogo_movil.jpg")

    # Estilos
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
            margin: 0 auto !important;  /* 🔥 CENTRADO ADICIONAL */
        }

        /* BOTÓN - CENTRADO */
        .stButton {
            display: flex !important;
            justify-content: center !important;
            width: 100% !important;  /* 🔥 ASEGURA ANCHO COMPLETO */
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
        # Fondo responsive
        set_background_responsive("Empresalogo_pc.jpg", "Empresalogo_movil.jpg")

        st.markdown("""
        <style>
        /* Ocultar elementos Streamlit */
        #MainMenu, footer, header {visibility: hidden;}

        /* Reset */
        .main {
            padding: 0 !important;
        }

        /* CONTENEDOR PRINCIPAL */
        .block-container {
            padding-top: 25vh !important;
            display: flex !important;
            flex-direction: column !important;
            align-items: center !important;
        }

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
        .stTextInput input {
            background-color: #000000 !important;
            color: #ffffff !important;
            border-radius: 10px !important;
            border: 2px solid #ffffff !important;
            padding: 14px 16px !important;
            font-size: 16px !important;
        }

        /* LABELS */
        label, 
        div[data-testid="stTextInput"] label {
            color: #ffffff !important;
            font-weight: 600;
            font-size: 15px !important;
        }

        /* BOTÓN INGRESAR - CENTRADO */
        .stButton {
            display: flex !important;
            justify-content: center !important;  /* 🔥 CENTRADO */
            width: 100% !important;
        }

        .stButton button {
            background-color: rgba(0, 0, 0, 0.9) !important;
            color: white !important;
            border: 2px solid white !important;
            font-size: 18px !important;
            padding: 12px 24px !important;
            border-radius: 8px !important;
            width: 100% !important;
            margin-top: 10px !important;
        }

        .stButton button:hover {
            background-color: rgba(255, 255, 255, 0.2) !important;
        }

        /* ====== RESPONSIVE MÓVIL ====== */
        @media (max-width: 768px) {
            .block-container {
                padding-top: 5vh !important;
            }

            .login-box {
                max-width: 90% !important;
                padding: 20px !important;
            }

            .stTextInput input {
                font-size: 18px !important;
            }

            label {
                font-size: 16px !important;
            }
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