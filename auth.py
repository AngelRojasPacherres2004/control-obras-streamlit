"""
Módulo de autenticación y pantalla inicial
"""

import json
import base64
import streamlit as st
from util import set_background_responsive
from cookies_manager import cookies
import uuid
from firebase_admin import firestore


# ====== HELPER ======
def _get_image_base64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


# ====== PANTALLA INICIAL ======
def mostrar_pantalla_inicial():
    set_background_responsive("Empresalogo_pc_fondo.jpg", "Empresalogo_movil_fondo.jpg")

    logo_b64 = _get_image_base64("logo(1).png")

    st.markdown(f"""
        <style>
        #MainMenu, footer, header {{visibility: hidden;}}
        .main {{ padding: 0 !important; }}

        .block-container {{
            padding-top: 2vh !important;
            display: flex !important;
            flex-direction: column !important;
            justify-content: center !important;
            align-items: center !important;
        }}

        div[data-testid="stButton"] {{
            width: 350px !important;
            max-width: 70% !important;
            margin: 0 auto !important;
        }}

        .stButton button {{
            background-color: rgba(0, 0, 0, 0.8) !important;
            color: white !important;
            border: 2px solid white !important;
            font-size: 18px !important;
            padding: 12px 24px !important;
            border-radius: 8px !important;
            width: 100% !important;
        }}

        /* logo sizing rules */
        .app-logo {{
            display: block;
            margin: 0 auto;
        }}
        /* wrapper to control vertical placement */
        .logo-wrapper {{
            display:flex;
            justify-content:center;
            width:100%;
            margin-bottom:10px;
            padding:0;
        }}
        @media (min-width: 769px) {{
            .logo-wrapper {{
                margin-top: 6vh !important;
            }}
        }}
        @media (max-width: 768px) {{
            .logo-wrapper {{
                margin-top: 2vh !important;
            }}
        }}
        @media (min-width: 769px) {{
            .app-logo {{
                max-width: 400px !important;
                width: 60% !important;
            }}
        }}
        @media (max-width: 768px) {{
            .app-logo {{
                max-width: 250px !important;
                width: 80% !important;
            }}
        }}

        @media (max-width: 768px) {{
            .block-container {{
                width: 100% !important;
                max-width: 100% !important;
                padding-left: 1rem !important;
                padding-right: 1rem !important;
                margin: 0 auto !important;
            }}
            div[data-testid="stButton"] {{
                max-width: 90% !important;
            }}
            /* mobile: lower logo and add space before button */
            .logo-wrapper {{
                margin-top: 8vh !important;
            }}
            div[data-testid="stButton"] {{
                margin-top: 4vh !important;
            }}
        }}
        </style>

        <div class="logo-wrapper">
            <img class="app-logo" src="data:image/png;base64,{logo_b64}">
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br><br><br>", unsafe_allow_html=True)

    if st.button("Iniciar Sesión", use_container_width=True, key="btn_pantalla_inicial"):
        st.session_state.show_login = True
        st.rerun()


# ====== LOGIN ======
def verificar_autenticacion(db):
    if "auth" not in st.session_state:
        set_background_responsive("Empresalogo_pc_fondo.jpg", "Empresalogo_movil_fondo.jpg")

        logo_b64 = _get_image_base64("logo(1).png")

        st.markdown(f"""
        <style>
        #MainMenu, footer, header {{visibility: hidden;}}
        .main {{ padding: 0 !important; }}

        .block-container {{
            padding-top: 2vh !important;
            display: flex !important;
            flex-direction: column !important;
            align-items: center !important;
            max-width: 420px !important;
            margin: auto !important;
        }}
        /* larger container on desktop so logo doesn't shrink after login */
        @media (min-width: 769px) {{
            .block-container {{
                max-width: 60% !important;
            }}
        }}

        .stTextInput input {{
            background-color: #000000 !important;
            color: #ffffff !important;
            border-radius: 10px !important;
            border: 2px solid #ffffff !important;
            padding: 14px 16px !important;
            font-size: 16px !important;
        }}

        label,
        div[data-testid="stTextInput"] label {{
            color: #ffffff !important;
            font-weight: 600;
            font-size: 15px !important;
        }}

        .stButton {{
            display: flex !important;
            justify-content: center !important;
            width: 100% !important;
        }}

        .stButton button {{
            background-color: rgba(0, 0, 0, 0.9) !important;
            color: white !important;
            border: 2px solid white !important;
            font-size: 18px !important;
            padding: 12px 24px !important;
            border-radius: 8px !important;
            width: 100% !important;
            margin-top: 10px !important;
        }}

        .stButton button:hover {{
            background-color: rgba(255, 255, 255, 0.2) !important;
        }}

        /* logo sizing */
        .app-logo {{
            display: block;
            margin: 0 auto;
        }}
        /* wrapper to control vertical placement */
        .logo-wrapper {{
            display:flex;
            justify-content:center;
            width:100%;
            margin-bottom:10px;
            padding:0;
        }}
        @media (min-width: 769px) {{
            .app-logo {{
                max-width: 400px !important;
                width: 60% !important;
            }}
            .logo-wrapper {{
                margin-top: 6vh !important;
            }}
        }}
        @media (max-width: 768px) {{
            .app-logo {{
                max-width: 250px !important;
                width: 80% !important;
            }}
            .logo-wrapper {{
                margin-top: 2vh !important;
            }}
        }}

        @media (max-width: 768px) {{
            .block-container {{
                width: 100% !important;
                max-width: 100% !important;
                padding-left: 1rem !important;
                padding-right: 1rem !important;
                margin: 0 auto !important;
            }}
            .stTextInput input {{
                font-size: 18px !important;
            }}
            label {{
                font-size: 16px !important;
            }}
            /* mobile: lower logo and add space before buttons in login */
            .logo-wrapper {{
                margin-top: 8vh !important;
            }}
            .stButton, div[data-testid="stButton"] {{
                margin-top: 4vh !important;
            }}
        }}
        /* reapply desktop logo sizing to keep consistent after rerun */
        @media (min-width: 769px) {{
            .app-logo {{
                max-width: 400px !important;
                width: 60% !important;
            }}
        }}
        </style>

        <div class="logo-wrapper">
            <img class="app-logo" src="data:image/png;base64,{logo_b64}">
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

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

            cookies["auth"] = json.dumps(auth_data)
            cookies.save()

            st.rerun()

        return False
