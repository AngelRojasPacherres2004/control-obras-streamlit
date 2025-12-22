# ================================
# CONTROL DE OBRAS 2025 – FINAL
# Firebase + Cloudinary
# ================================

import streamlit as st
import pandas as pd
from datetime import datetime, date

import firebase_admin
from firebase_admin import credentials, firestore

import cloudinary
import cloudinary.uploader

# ---------------- CONFIG STREAMLIT ----------------
st.set_page_config(page_title="Arq. Supervisor 2025", layout="wide")

# ---------------- OBRAS ----------------
OBRAS = {
    "rinconada": "La Rinconada – La Molina",
    "pachacutec": "Ciudad Pachacútec – Ventanilla"
}

# ---------------- FIREBASE ----------------
if not firebase_admin._apps:
    cred = credentials.Certificate(dict(st.secrets["firebase"]))
    firebase_admin.initialize_app(cred)

db = firestore.client()

# ---------------- CLOUDINARY ----------------
cloudinary.config(
    cloud_name=st.secrets["cloudinary"]["cloud_name"],
    api_key=st.secrets["cloudinary"]["api_key"],
    api_secret=st.secrets["cloudinary"]["api_secret"],
    secure=True
)

# ================== LOGIN ==================
def check_password():
    def password_entered():
        users = st.secrets["users"]
        if (
            st.session_state["password"] == users["jefe_pass"]
            and st.session_state["user"] == users["jefe_user"]
        ):
            st.session_state["auth"] = "jefe"
        elif (
            st.session_state["password"] == users["pasante_pass"]
            and st.session_state["user"].startswith(users["pasante_user_prefix"])
        ):
            st.session_state["auth"] = st.session_state["user"]
        else:
            st.session_state["auth"] = False

    if "auth" not in st.session_state:
        st.title("CONTROL DE OBRAS 2025")
        st.text_input("Usuario", key="user")
        st.text_input("Contraseña", type="password", key="password")
        st.button("INGRESAR", on_click=password_entered)
        return False

    if not st.session_state["auth"]:
        st.error("Usuario o contraseña incorrecta")
        return False

    return True


if not check_password():
    st.stop()

# ================== OBRA ACTUAL ==================
if st.session_state["auth"] == "jefe":
    obra_actual = st.sidebar.selectbox(
        "Seleccionar obra",
        options=list(OBRAS.keys()),
        format_func=lambda x: OBRAS[x],
    )
else:
    obra_actual = st.session_state["auth"].split("-")[1]
    st.sidebar.success(f"Obra asignada: {OBRAS[obra_actual]}")

# ================== INTERFAZ ==================
st.title(f"Obra: {OBRAS[obra_actual]}")

if st.session_state["auth"] == "jefe":
    st.sidebar.success("MODO JEFE – Acceso total")
else:
    st.sidebar.info("MODO PASANTE – Solo parte diario")

# ================== PARTE DIARIO ==================
st.header("Parte Diario del Día")

hoy = date.today()
responsable = st.text_input("Tu nombre", key="nombre_responsable")
avance = st.slider("Avance logrado hoy (%)", 0, 30, 5)
obs = st.text_area("Observaciones")
fotos = st.file_uploader(
    "Fotos del avance (mínimo 3)",
    accept_multiple_files=True,
    type=["jpg", "jpeg", "png"],
)

# ================== ENVIAR ==================
if st.button("ENVIAR PARTE DIARIO", type="primary"):

    if "pasante" in st.session_state["auth"] and len(fotos) < 3:
        st.error("¡Sube mínimo 3 fotos!")
    else:
        urls = []

        for foto in fotos:
            subida = cloudinary.uploader.upload(
                foto,
                folder=f"obras/{obra_actual}",
                public_id=f"{obra_actual}_{hoy}_{datetime.now().timestamp()}",
            )
            urls.append(subida["secure_url"])

        registro = {
            "obra": obra_actual,
            "fecha": str(hoy),
            "responsable": responsable,
            "avance": avance,
            "observaciones": obs,
            "fotos": urls,
            "created_at": firestore.SERVER_TIMESTAMP,
        }

        db.collection("avances").add(registro)

        st.success("¡Parte enviado correctamente!")
        st.balloons()
        st.rerun()

# ================== HISTORIAL ==================
st.header("Historial de Avances")

docs = (
    db.collection("avances")
    .where("obra", "==", obra_actual)
    .order_by("created_at", direction=firestore.Query.DESCENDING)
    .stream()
)

for doc in docs:
    d = doc.to_dict()
    with st.expander(
        f"Avance {d['fecha']} – {d['responsable']} ({d['avance']}%)"
    ):
        st.write(d["observaciones"])
        cols = st.columns(min(3, len(d["fotos"])))
        for i, url in enumerate(d["fotos"]):
            with cols[i % 3]:
                st.image(url, use_column_width=True)
