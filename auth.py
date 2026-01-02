"""
Módulo de autenticación y pantalla inicial
Contiene las funciones para:
- Mostrar pantalla inicial con logo
- Manejar el login con Firebase
"""

import streamlit as st
from util import set_background

# ====== PANTALLA INICIAL ======
def mostrar_pantalla_inicial():
    """
    Muestra la pantalla de bienvenida con el logo BOSS de fondo
    y un botón para iniciar sesión.
    """
    set_background("Empresalogo.jpg")
    st.markdown("<br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col2:
        if st.button("Iniciar Sesión", use_container_width=True):
            st.session_state.show_login = True
            st.rerun()


# ====== LOGIN CON FIREBASE ======
def verificar_autenticacion(db):
    """
    Maneja el proceso de autenticación con Firebase.
    """
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
        h1 {
            color: white !important;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.8);
        }
        label {
            color: white !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        st.markdown("<br><br><br><br>", unsafe_allow_html=True)
        
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


# ====== INICIALIZAR ESTADO ======
def inicializar_estado_auth():
    """
    Inicializa las variables de sesión necesarias para la autenticación.
    """
    if "show_login" not in st.session_state:
        st.session_state.show_login = False


# ====== VERIFICAR SI MOSTRAR PANTALLA INICIAL ======
def debe_mostrar_pantalla_inicial():
    """
    Verifica si se debe mostrar la pantalla inicial.
    """
    return not st.session_state.show_login
