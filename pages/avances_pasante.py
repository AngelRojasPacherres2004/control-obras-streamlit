import streamlit as st
from datetime import datetime
import cloudinary.uploader
from firebase_admin import firestore

# ================= CONFIG =================
st.set_page_config(page_title="Parte Diario", layout="centered")

db = firestore.client()

# ================= SEGURIDAD =================
if "auth" not in st.session_state:
    st.error("Sesión no válida")
    st.stop()

auth = st.session_state["auth"]

if auth["role"] != "pasante":
    st.warning("Acceso solo para pasantes")
    st.stop()

obra_id = auth.get("obra")

if not obra_id:
    st.error("No tienes una obra asignada")
    st.stop()

# ================= DATOS DE LA OBRA =================
obra_ref = db.collection("obras").document(obra_id).get()

if not obra_ref.exists:
    st.error("La obra asignada no existe")
    st.stop()

obra = obra_ref.to_dict()

# ================= SIDEBAR =================
with st.sidebar:
    st.header("🏗️ Obra asignada")
    st.markdown(f"**Nombre:** {obra.get('nombre','-')}")
    st.markdown(f"**Ubicación:** {obra.get('ubicacion','-')}")
    st.markdown(f"**Estado:** {obra.get('estado','-')}")
    st.markdown(f"**Inicio:** {obra.get('fecha_inicio','-')}")
    st.markdown(f"**Fin estimado:** {obra.get('fecha_fin_estimada','-')}")

# ================= UI =================
st.title("📝 Parte Diario de Avance")
st.caption("Registra el avance diario de tu obra")

with st.form("form_avance", clear_on_submit=True):
    responsable = st.text_input("Responsable")
    descripcion = st.text_area("Descripción del avance", height=120)

    fotos = st.file_uploader(
        "Subir fotos (mínimo 3)",
        accept_multiple_files=True,
        type=["jpg", "png", "jpeg"]
    )

    guardar = st.form_submit_button("Guardar avance")

# ================= LÓGICA =================
if guardar:
    if not responsable or not descripcion:
        st.error("Responsable y descripción son obligatorios")
    elif not fotos or len(fotos) < 3:
        st.error("Debes subir al menos 3 fotos")
    else:
        urls = []

        with st.spinner("Subiendo fotos..."):
            for f in fotos:
                res = cloudinary.uploader.upload(
                    f,
                    folder=f"obras/{obra_id}"
                )
                urls.append(res["secure_url"])

        db.collection("obras") \
            .document(obra_id) \
            .collection("avances") \
            .add({
                "fecha": datetime.now().isoformat(),
                "responsable": responsable,
                "observaciones": descripcion,
                "fotos": urls
            })

        st.success("Avance registrado correctamente")
