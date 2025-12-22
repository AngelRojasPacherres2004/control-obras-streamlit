import streamlit as st
import pandas as pd
from datetime import datetime, date

# Firebase
import firebase_admin
from firebase_admin import credentials, firestore

# Cloudinary
import cloudinary
import cloudinary.uploader

# ---------------- CONFIG APP ----------------
st.set_page_config(page_title="Arq. Supervisor 2025", layout="wide")

OBRAS = {
    "rinconada": "La Rinconada – La Molina",
    "pachacutec": "Ciudad Pachacútec – Ventanilla"
}

# ---------------- FIREBASE INIT ----------------
if not firebase_admin._apps:
    cred = credentials.Certificate(dict(st.secrets["firebase"]))
    firebase_admin.initialize_app(cred)

db = firestore.client()

# ---------------- CLOUDINARY INIT ----------------
cloudinary.config(
    cloud_name=st.secrets["cloudinary"]["cloud_name"],
    api_key=st.secrets["cloudinary"]["api_key"],
    api_secret=st.secrets["cloudinary"]["api_secret"]
)

# ---------------- LOGIN ----------------
def check_password():

    def password_entered():
        user = st.session_state["user"]
        password = st.session_state["password"]

        doc = db.collection("users").document(user).get()

        if not doc.exists:
            st.session_state["auth"] = False
            return

        data = doc.to_dict()

        if password == data["password"]:
            st.session_state["auth"] = data
            st.session_state["auth"]["username"] = user
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

auth = st.session_state["auth"]

# ---------------- OBRA ACTUAL ----------------
if auth["role"] == "jefe":
    obra_actual = st.sidebar.selectbox(
        "Seleccionar obra",
        options=list(OBRAS.keys()),
        format_func=lambda x: OBRAS[x]
    )
    st.sidebar.success("MODO JEFE – Acceso total")
else:
    obra_actual = auth["obra"]
    st.sidebar.info(f"MODO PASANTE – {OBRAS[obra_actual]}")

# ---------------- UI ----------------
st.title(f"Obra: {OBRAS[obra_actual]}")
st.header("Parte Diario del Día")

hoy = date.today()
responsable = st.text_input("Tu nombre")
avance = st.slider("Avance logrado hoy (%)", 0, 30, 5)
obs = st.text_area("Observaciones")
fotos = st.file_uploader(
    "Fotos del avance (mínimo 3)",
    accept_multiple_files=True,
    type=["jpg", "png", "jpeg"]
)

# ---------------- ENVIAR PARTE ----------------
if st.button("ENVIAR PARTE DIARIO", type="primary"):

    if auth["role"] == "pasante" and len(fotos) < 3:
        st.error("Debes subir mínimo 3 fotos")
        st.stop()

    urls = []

    for f in fotos:
        upload = cloudinary.uploader.upload(
            f,
            folder=f"obras/{obra_actual}/{hoy}"
        )
        urls.append(upload["secure_url"])

    db.collection("obras").document(obra_actual).collection("avances").add({
        "fecha": str(hoy),
        "responsable": responsable,
        "avance": avance,
        "obs": obs,
        "fotos": urls,
        "usuario": auth["username"],
        "timestamp": firestore.SERVER_TIMESTAMP
    })

    st.success("Parte enviado correctamente")
    st.balloons()
    st.rerun()

# ---------------- HISTORIAL ----------------
st.header("Historial de Avances")

docs = (
    db.collection("obras")
    .document(obra_actual)
    .collection("avances")
    .order_by("timestamp", direction=firestore.Query.DESCENDING)
    .stream()
)

for d in docs:
    r = d.to_dict()
    with st.expander(f"{r['fecha']} - {r['responsable']} ({r['avance']}%)"):
        st.write(r["obs"])
        cols = st.columns(min(3, len(r["fotos"])))
        for i, url in enumerate(r["fotos"]):
            with cols[i % 3]:
                st.image(url, use_column_width=True)
