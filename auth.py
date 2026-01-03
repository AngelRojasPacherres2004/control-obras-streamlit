"""
Módulo de autenticación y pantalla inicial
"""

import streamlit as st
from util import set_background


# ====== PANTALLA INICIAL ======
def mostrar_pantalla_inicial():
    set_background("Empresalogo.jpg")

    # CSS para mover el botón con porcentaje
    st.markdown("""
    <style>
    .contenedor-boton {
        margin-top: 45vh;   /* 🔽 AJUSTA ESTE VALOR */
        width: 100%;
        display: flex;
        justify-content: center;
    }
    </style>
    """, unsafe_allow_html=True)

    # Contenedor del botón
    st.markdown('<div class="contenedor-boton">', unsafe_allow_html=True)

    if st.button("Iniciar Sesión", use_container_width=True):
        st.session_state.show_login = True
        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


# ====== LOGIN CON FIREBASE ======
def verificar_autenticacion(db):
    if "auth" not in st.session_state:
        set_background("Empresalogo.jpg")

        st.markdown("""
        <style>
        .stApp::after {
            content: "";
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.6);
            z-index: 0;
            pointer-events: none;
        }
        h1, label {
            color: white !important;
        }
        </style>
        """, unsafe_allow_html=True)

        st.markdown("<br><br>", unsafe_allow_html=True)
        st.title("CONTROL DE OBRAS 2025")

        username = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")

        if st.button("INGRESAR"):
            user_doc = db.collection("users").document(username).get()

            if not user_doc.exists:
                st.error("Usuario no existe")
                return False

            data = user_doc.to_dict()

            if password != data.get("password"):
                st.error("Contraseña incorrecta")
                return False

            st.session_state["auth"] = {
                "username": data["username"],
                "role": data["role"],
                "obra": data.get("obra")
            }
            st.rerun()

        return False

    return True


# ====== ESTADO ======
def inicializar_estado_auth():
    if "show_login" not in st.session_state:
        st.session_state.show_login = False


def debe_mostrar_pantalla_inicial():
    return not st.session_state.show_login
