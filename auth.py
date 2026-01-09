import streamlit as st
from cookies_manager import cookies
from firebase_admin import firestore
import uuid
from util import set_background

# ================= PANTALLA INICIAL =================
def mostrar_pantalla_inicial():
    set_background("Empresalogo.jpg")

    st.markdown("""
    <style>
    #MainMenu, footer, header {visibility: hidden;}

    .block-container {
        padding-top: 45vh !important;
        display: flex;
        justify-content: center;
    }

    .stButton button {
        background-color: rgba(0,0,0,0.8);
        color: white;
        font-size: 18px;
        padding: 12px;
        width: 300px;
        border-radius: 8px;
    }
    </style>
    """, unsafe_allow_html=True)

    if st.button("Iniciar Sesión"):
        st.session_state.show_login = True
        st.rerun()


# ================= LOGIN =================
def verificar_autenticacion(db):

    if "auth" in st.session_state:
        return

    set_background("Empresalogo.jpg")

    st.markdown("<br><br>", unsafe_allow_html=True)
    st.title("CONTROL DE OBRAS 2025")

    username = st.text_input("Usuario")
    password = st.text_input("Contraseña", type="password")

    if not st.button("INGRESAR"):
        return

    # ===== VALIDAR USUARIO =====
    user_doc = db.collection("users").document(username).get()

    if not user_doc.exists:
        st.error("Usuario no existe")
        return

    data = user_doc.to_dict()

    if password != data.get("password"):
        st.error("Contraseña incorrecta")
        return

    # ===== IDENTIFICAR NAVEGADOR =====
    if "browser_id" not in cookies:
        cookies["browser_id"] = str(uuid.uuid4())
        cookies.save()

    browser_id = cookies["browser_id"]

    # ===== ELIMINAR SESIÓN PREVIA DE ESTE NAVEGADOR =====
    if cookies.get("session_id"):
        db.collection("sessions").document(cookies["session_id"]).delete()
        del cookies["session_id"]
        cookies.save()

    # ===== CREAR NUEVA SESIÓN =====
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

    # ===== SESSION STATE =====
    st.session_state["auth"] = {
        "username": data["username"],
        "role": data["role"],
        "obra": data.get("obra"),
        "session_id": session_id
    }

    st.session_state.show_login = True
    st.rerun()
