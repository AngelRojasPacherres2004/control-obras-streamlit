import streamlit as st
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
import cloudinary
import cloudinary.uploader

# ----------------------------
# CONFIG STREAMLIT
# ----------------------------
st.set_page_config(page_title="Control de Obras", layout="wide")

# ----------------------------
# FIREBASE INIT (SOLO UNA VEZ)
# ----------------------------
if not firebase_admin._apps:
    cred = credentials.Certificate(dict(st.secrets["firebase"]))
    firebase_admin.initialize_app(cred)

db = firestore.client()

# ----------------------------
# CLOUDINARY CONFIG
# ----------------------------
cloudinary.config(
    cloud_name=st.secrets["cloudinary"]["cloud_name"],
    api_key=st.secrets["cloudinary"]["api_key"],
    api_secret=st.secrets["cloudinary"]["api_secret"]
)

CARPETA_OBRAS = st.secrets["cloudinary_folders"]["obras"]

# ----------------------------
# UI
# ----------------------------
st.title("🏗️ Registro de Obras")

with st.form("form_obra"):
    titulo = st.text_input("Título de la obra")
    descripcion = st.text_area("Descripción")
    imagen = st.file_uploader("Subir imagen", type=["jpg", "jpeg", "png"])
    guardar = st.form_submit_button("Guardar obra")

# ----------------------------
# LOGICA
# ----------------------------
if guardar:
    if not titulo or not imagen:
        st.error("❌ Título e imagen son obligatorios")
    else:
        with st.spinner("Subiendo imagen a Cloudinary..."):
            upload = cloudinary.uploader.upload(
                imagen,
                folder=CARPETA_OBRAS
            )

        image_url = upload["secure_url"]

        obra_data = {
            "title": titulo,
            "description": descripcion,
            "imageUrl": image_url,
            "createdAt": datetime.utcnow(),
            "status": "published"
        }

        db.collection("obras").add(obra_data)

        st.success("✅ Obra guardada correctamente")

# ----------------------------
# LISTADO
# ----------------------------
st.divider()
st.subheader("📸 Obras registradas")

obras = db.collection("obras").order_by("createdAt", direction=firestore.Query.DESCENDING).stream()

cols = st.columns(3)

i = 0
for obra in obras:
    data = obra.to_dict()
    with cols[i % 3]:
        st.image(data["imageUrl"], use_container_width=True)
        st.markdown(f"**{data['title']}**")
        st.caption(data.get("description", ""))
    i += 1
