"""
Módulo de autenticación y pantalla inicial
"""

import json
import streamlit as st
from util import set_background_responsive
from cookies_manager import cookies


# ====== PANTALLA INICIAL ======
def mostrar_pantalla_inicial():
    set_background_responsive("Empresalogo_pc_fondo.jpg", "Empresalogo_movil_fondo.jpg")

    st.markdown("""
        <style>
#MainMenu, footer, header {visibility: hidden;}
.main { padding: 0 !important; }

.block-container {
    padding-top: 2vh !important;
    display: flex !important;
    flex-direction: column !important;
    justify-content: center !important;
    align-items: center !important;
}

div[data-testid="stButton"] {
    width: 350px !important;
    max-width: 70% !important;
    margin: 0 auto !important;
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

div[data-testid="stImage"] img {
    max-width: 400px !important;
    margin: auto !important;
    display: block !important;
}

/* --- SOLUCIÓN MÓVIL --- */
@media (max-width: 768px) {
    .block-container {
        padding-left: 0 !important;  /* Elimina margen izquierdo */
        padding-right: 0 !important; /* Elimina margen derecho */
        width: 100% !important;      /* Fuerza ancho total */
        max-width: 100% !important;
        margin-left: 0 !important;
        margin-right: 0 !important;
    }
    
    div[data-testid="column"] {
        width: 100% !important;
        flex: none !important;
    }

    div[data-testid="stImage"] img {
        max-width: 200px !important;
    }
}
</style>
        """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("logo(1).png", use_container_width=True)

    st.markdown("<br><br><br><br>", unsafe_allow_html=True)

    if st.button("Iniciar Sesión", use_container_width=True, key="btn_pantalla_inicial"):
        st.session_state.show_login = True
        st.rerun()


# ====== LOGIN ======
def verificar_autenticacion(db):
    if "auth" not in st.session_state:
        set_background_responsive("Empresalogo_pc_fondo.jpg", "Empresalogo_movil_fondo.jpg")

        st.markdown("""
        <style>
#MainMenu, footer, header {visibility: hidden;}
.main { padding: 0 !important; }

.block-container {
    padding-top: 2vh !important;
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    max-width: 420px !important;
    margin: auto !important;
}

.stTextInput input {
    background-color: #000000 !important;
    color: #ffffff !important;
    border-radius: 10px !important;
    border: 2px solid #ffffff !important;
    padding: 14px 16px !important;
}

.stButton button {
    background-color: rgba(0, 0, 0, 0.9) !important;
    color: white !important;
    border: 2px solid white !important;
    border-radius: 8px !important;
    width: 100% !important;
}

/* --- SOLUCIÓN MÓVIL LOGIN --- */
@media (max-width: 768px) {
    .block-container {
        width: 90% !important; /* Centra el bloque de login al 90% del ancho del celular */
        max-width: 90% !important;
        padding-left: 0 !important;
        padding-right: 0 !important;
        margin-left: auto !important;
        margin-right: auto !important;
    }

    /* Centrar el logo que está dentro de columnas */
    div[data-testid="stHorizontalBlock"] {
        display: flex !important;
        justify-content: center !important;
    }
}
</style>
        """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.image("logo(1).png", use_container_width=True)

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