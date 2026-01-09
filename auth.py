"""
auth.py
Login manual seguro por navegador (NO comparte sesión)
"""

import streamlit as st
from util import set_background
from cookies_manager import cookies
import uuid
from firebase_admin import firestore


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
    </style>
    """, unsafe_allow_html=True)

    if st.button("Iniciar Sesión", use_container_width=True):
        st.session_state.show_login = True
        st.rerun()


# ================= LOGIN =================
def verificar_autenticacion(db):

    # ===== IDENTIDAD DEL NAVEGADOR =====
    if "browser_id" not in cookies:
        cookies["browser_id"] = str(uuid.uuid4())
        cookies.save()

    browser_id = cookies["browser_id"]

    # ===== RESTAURAR SESIÓN SOLO SI COINCIDE EL NAVEGADOR =====
    if cookies.get("session_id") and "auth" not in st.session_state:
        session_doc = db.collection("sessions").document(
            cookies["session_id"]
        ).get()

        if session_doc.exists:
            session = session_doc.to_dict()

            # 🔥 VALIDACIÓN CLAVE
            if session.get("browser_id") == browser_id:
                st.session_state["auth"] = {
                    "username": session["username"],
                    "role": session["role"],
                    "obra": session.get("obra"),
                    "session_id": cookies["session_id"]
                }
                return
            else:
                # sesión NO pertenece a este navegador
                db.collection("sessions").document(
                    cookies["session_id"]
                ).delete()
                del cookies["session_id"]
                cookies.save()

    # ===== FORMULARIO LOGIN =====
    set_background("Empresalogo.jpg")

    st.title("CONTROL DE OBRAS 2025")

    username = st.text_input("Usuario")
    password = st.text_input("Contraseña", type="password")

    if not st.button("INGRESAR"):
        return

    user_doc = db.collection("users").document(username).get()
    if not user_doc.exists:
        st.error("Usuario no existe")
        return

    data = user_doc.to_dict()

    if password != data.get("password"):
        st.error("Contraseña incorrecta")
        return

    # ===== CREAR SESIÓN SEGURA =====
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

    st.session_state["auth"] = {
        "username": data["username"],
        "role": data["role"],
        "obra": data.get("obra"),
        "session_id": session_id
    }

    st.rerun()
