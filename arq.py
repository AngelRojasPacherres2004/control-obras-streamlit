import streamlit as st
import pandas as pd
from datetime import datetime, date
import cloudinary
import cloudinary.uploader
import firebase_admin
from firebase_admin import credentials, firestore

# ================= FIREBASE =================
if not firebase_admin._apps:
    firebase_admin.initialize_app(
        credentials.Certificate(dict(st.secrets["firebase"]))
    )

db = firestore.client()

# ================= CLOUDINARY =================
cloudinary.config(
    cloud_name=st.secrets["cloudinary"]["cloud_name"],
    api_key=st.secrets["cloudinary"]["api_key"],
    api_secret=st.secrets["cloudinary"]["api_secret"],
    secure=True
)

# ================= STREAMLIT =================
st.set_page_config(page_title="Arq. Supervisor 2025", layout="wide")

# ================= FUNCIONES =================
def obtener_obras():
    return {d.id: d.to_dict().get("nombre", d.id) for d in db.collection("obras").stream()}

def cargar_avances(obra_id):
    return [
        d.to_dict()
        for d in db.collection("obras")
        .document(obra_id)
        .collection("avances")
        .order_by("fecha", direction=firestore.Query.DESCENDING)
        .stream()
    ]

# ================= LOGIN FIREBASE =================
def check_login():
    if "auth" not in st.session_state:
        st.title("CONTROL DE OBRAS 2025")

        usuario = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")

        if st.button("INGRESAR"):
            doc = db.collection("users").document(usuario).get()

            if not doc.exists:
                st.error("Usuario no existe")
                return False

            data = doc.to_dict()

            if password != data.get("password"):
                st.error("Contraseña incorrecta")
                return False

            if "rol" not in data:
                st.error("Usuario mal configurado (sin rol)")
                return False

            st.session_state["auth"] = data["rol"]
            st.session_state["user"] = usuario
            st.session_state["obra"] = data.get("obra")
            st.rerun()

        return False
    return True

if not check_login():
    st.stop()

# ================= OBRAS =================
OBRAS = obtener_obras()

if not OBRAS:
    st.error("No hay obras registradas en Firebase")
    st.stop()

# ================= SELECCIÓN DE OBRA =================
if st.session_state["auth"] == "jefe":
    obra_id_sel = st.sidebar.selectbox(
        "Seleccionar obra",
        options=list(OBRAS.keys()),
        format_func=lambda x: OBRAS.get(x, x)
    )
else:
    obra_id_sel = st.session_state.get("obra")

    if obra_id_sel not in OBRAS:
        st.error("Obra asignada inválida o no existe")
        st.stop()

    st.sidebar.success(f"Obra asignada: {OBRAS[obra_id_sel]}")

# ================= TITULO =================
st.title(f"🏗️ {OBRAS[obra_id_sel]}")

# ================= PASANTE =================
if st.session_state["auth"] == "pasante":
    st.header("📝 Parte Diario")

    with st.form("parte_diario"):
        responsable = st.text_input("Responsable")
        observaciones = st.text_area("Observaciones")
        fotos = st.file_uploader(
            "Subir fotos (mínimo 3)",
            accept_multiple_files=True,
            type=["jpg", "png", "jpeg"]
        )
        enviar = st.form_submit_button("GUARDAR AVANCE")

    if enviar:
        if not responsable or not observaciones:
            st.error("Campos obligatorios")
        elif len(fotos) < 3:
            st.error("Sube mínimo 3 fotos")
        else:
            urls = []
            for f in fotos:
                r = cloudinary.uploader.upload(
                    f,
                    folder=f"obras/{obra_id_sel}"
                )
                urls.append(r["secure_url"])

            db.collection("obras") \
              .document(obra_id_sel) \
              .collection("avances") \
              .add({
                  "fecha": datetime.now().isoformat(),
                  "responsable": responsable,
                  "observaciones": observaciones,
                  "fotos": urls
              })

            st.success("Avance guardado")
            st.rerun()

# ================= HISTORIAL =================
st.header("📊 Historial de Avances")

for av in cargar_avances(obra_id_sel):
    f = datetime.fromisoformat(av["fecha"])
    with st.expander(f"{f:%d/%m/%Y %H:%M} - {av.get('responsable','')}"):
        st.write(av.get("observaciones", ""))
        for img in av.get("fotos", []):
            st.image(img, use_container_width=True)
