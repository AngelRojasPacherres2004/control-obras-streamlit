"""
Módulo de autenticación y pantalla inicial
"""
import streamlit as st
from util import set_background_responsive
from cookies_manager import cookies
import uuid
from firebase_admin import firestore


# ====== PANTALLA INICIAL ======
def mostrar_pantalla_inicial():
    # Fondo responsive
    set_background_responsive("Empresalogo_pc.jpg", "Empresalogo_movil.jpg")

    st.markdown("""
    <style>
    .contenedor-boton {
        margin-top: 45vh;
        width: 100%;
        display: flex;
        justify-content: center;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="contenedor-boton">', unsafe_allow_html=True)

    if st.button("Iniciar Sesión", use_container_width=True):
        st.session_state.show_login = True
        st.rerun()


# ====== LOGIN ======
def verificar_autenticacion(db):

    # ya autenticado → no mostrar login
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

    # ===== IDENTIDAD DEL NAVEGADOR =====
    if "browser_id" not in cookies:
        cookies["browser_id"] = str(uuid.uuid4())
        cookies.save()

    browser_id = cookies["browser_id"]

    # 🔥 cerrar sesiones previas de este navegador
    old_sessions = (
        db.collection("sessions")
        .where("browser_id", "==", browser_id)
        .stream()
    )

    for s in old_sessions:
        s.reference.delete()

    # ===== CREAR SESIÓN NUEVA =====
    session_id = str(uuid.uuid4())

    db.collection("sessions").document(session_id).set({
        "username": data["username"],
        "role": data["role"],
        "obra": data.get("obra"),
        "browser_id": browser_id,
        "created_at": firestore.SERVER_TIMESTAMP
    })

    # ===== GUARDAR COOKIE =====
    cookies["session_id"] = session_id
    cookies.save()

    # ===== ESTADO LOCAL =====
    st.session_state.clear()
    st.session_state["auth"] = {
        "username": data["username"],
        "role": data["role"],
        "obra": data.get("obra"),
        "session_id": session_id
    }
    st.session_state["show_login"] = True

    st.rerun()
