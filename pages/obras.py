import streamlit as st
import pandas as pd
from datetime import datetime, date
import cloudinary
import cloudinary.uploader
from firebase_admin import firestore

# ================= CLOUDINARY =================
cloudinary.config(
    cloud_name=st.secrets["cloudinary"]["cloud_name"],
    api_key=st.secrets["cloudinary"]["api_key"],
    api_secret=st.secrets["cloudinary"]["api_secret"],
    secure=True
)

# ================= STREAMLIT =================
st.set_page_config(page_title="Obras", layout="wide")
st.title("👷 CRUD de Obras")
st.info("Aquí se administran las obras y su historial")

db = firestore.client()

# ================= FUNCIONES =================
def obtener_obras():
    return {d.id: d.to_dict()["nombre"] for d in db.collection("obras").stream()}

def cargar_avances(obra_id):
    docs = (
        db.collection("obras")
        .document(obra_id)
        .collection("avances")
        .order_by("fecha", direction=firestore.Query.DESCENDING)
        .stream()
    )
    return [d.to_dict() for d in docs]

# ================= AUTH =================
auth = st.session_state["auth"]

if "crear_obra" not in st.session_state:
    st.session_state["crear_obra"] = False

# ================= SELECCIÓN DE OBRA =================
OBRAS = obtener_obras()

if not OBRAS:
    st.warning("No hay obras creadas")
    st.stop()

if auth["role"] == "jefe":
    obra_id_sel = st.sidebar.selectbox(
        "Seleccionar obra",
        options=list(OBRAS.keys()),
        format_func=lambda x: OBRAS[x],
        on_change=lambda: st.session_state.update({"crear_obra": False})
    )

    st.sidebar.divider()

    if st.sidebar.button("➕ Crear Obra", use_container_width=True):
        st.session_state["crear_obra"] = True

else:
    obra_id_sel = auth["obra"]
    st.sidebar.success(f"Obra asignada: {OBRAS[obra_id_sel]}")





# ================= CREAR OBRA (FORMULARIO) =================
if auth["role"] == "jefe" and st.session_state["crear_obra"]:

    st.title("➕ Crear nueva obra")

    with st.form("form_crear_obra"):
        nombre = st.text_input("Nombre de la obra")
        ubicacion = st.text_input("Ubicación")

        estado = st.selectbox(
            "Estado",
            ["en espera", "en progreso", "pausado", "finalizado"]
        )

        col1, col2 = st.columns(2)
        fecha_inicio = col1.date_input("Fecha inicio")
        fecha_fin = col2.date_input("Fecha fin estimada")

        col1, col2 = st.columns(2)
        guardar = col1.form_submit_button("💾 Crear obra")
        cancelar = col2.form_submit_button("❌ Cancelar")

    if guardar:
        if not nombre or not ubicacion:
            st.error("Nombre y ubicación son obligatorios")
        else:
            obra_id = nombre.lower().strip().replace(" ", "_")

            db.collection("obras").document(obra_id).set({
                "nombre": nombre,
                "ubicacion": ubicacion,
                "estado": estado,
                "fecha_inicio": fecha_inicio.isoformat(),
                "fecha_fin_estimada": fecha_fin.isoformat(),
                "creado_en": datetime.now().isoformat()
            })

            st.session_state["crear_obra"] = False
            st.success("Obra creada correctamente")
            st.rerun()

    if cancelar:
        st.session_state["crear_obra"] = False
        st.rerun()

    # ⛔ CORTA TODO LO DEMÁS
    st.stop()

           







# ================= INFO OBRA =================
obra_doc = db.collection("obras").document(obra_id_sel).get().to_dict()

st.subheader(f"🏗️ {obra_doc['nombre']}")
st.write(f"📍 **Ubicación:** {obra_doc['ubicacion']}")
st.write(f"📌 **Estado:** {obra_doc['estado']}")
st.write(f"📅 **Inicio:** {obra_doc['fecha_inicio']}")
st.write(f"📅 **Fin estimado:** {obra_doc['fecha_fin_estimada']}")

st.divider()

# ================= PASANTE: REGISTRAR AVANCE =================
if auth["role"] == "pasante":
    st.header("📝 Registrar avance")

    with st.form("nuevo_avance"):
        responsable = st.text_input("Responsable")
        descripcion = st.text_area("Descripción del avance")
        fotos = st.file_uploader(
            "Subir fotos (mínimo 3)",
            type=["jpg", "png", "jpeg"],
            accept_multiple_files=True
        )
        guardar = st.form_submit_button("GUARDAR AVANCE")

    if guardar:
        if not responsable or not descripcion:
            st.error("Responsable y descripción son obligatorios")
        elif not fotos or len(fotos) < 3:
            st.error("Debes subir mínimo 3 fotos")
        else:
            urls = []
            for f in fotos:
                res = cloudinary.uploader.upload(
                    f,
                    folder=f"obras/{obra_id_sel}"
                )
                urls.append(res["secure_url"])

            db.collection("obras")\
                .document(obra_id_sel)\
                .collection("avances")\
                .add({
                    "fecha": datetime.now().isoformat(),
                    "responsable": responsable,
                    "descripcion": descripcion,
                    "fotos": urls
                })

            st.success("Avance registrado correctamente")
            st.rerun()

# ================= HISTORIAL DE AVANCES =================
st.header("📚 Historial de Avances")

avances = cargar_avances(obra_id_sel)

if not avances:
    st.info("Esta obra aún no tiene avances registrados")
else:
    for av in avances:
        fecha = datetime.fromisoformat(av["fecha"])
        with st.expander(f"📅 {fecha:%d/%m/%Y %H:%M} — {av.get('responsable','N/D')}"):
            st.write(av.get("descripcion", "Sin descripción"))

            fotos = av.get("fotos", [])
            if fotos:
                cols = st.columns(3)
                for i, img in enumerate(fotos):
                    cols[i % 3].image(img, use_container_width=True)
            else:
                st.warning("Sin fotos")