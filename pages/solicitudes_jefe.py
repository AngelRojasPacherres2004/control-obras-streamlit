import streamlit as st
from datetime import datetime
from firebase_admin import firestore
import pytz

# ================= CONFIG =================
st.set_page_config(page_title="Recepción de Solicitudes", layout="wide")
db = firestore.client()
tz = pytz.timezone("America/Lima")

# ================= SEGURIDAD =================
if "auth" not in st.session_state:
    st.error("Inicia sesión")
    st.stop()

if st.session_state["auth"]["role"] != "jefe":
    st.warning("Sin permisos")
    st.stop()

# ================= FUNCIONES =================
def obtener_obras():
    return {d.id: d.to_dict().get("nombre", d.id)
            for d in db.collection("obras").stream()}

def obtener_solicitudes(obra_id):
    docs = (
        db.collection("obras")
        .document(obra_id)
        .collection("solicitudes")
        .stream()
    )

    solicitudes = []
    for d in docs:
        data = d.to_dict()
        data["doc_id"] = d.id
        solicitudes.append(data)

    # ordenar en Python
    solicitudes.sort(
        key=lambda x: x.get("timestamp", datetime.min),
        reverse=True
    )

    return solicitudes


# ================= UI =================
st.title("📬 Solicitudes de Pasantes")

OBRAS = obtener_obras()
obra_id = st.sidebar.selectbox(
    "Seleccionar obra",
    options=list(OBRAS.keys()),
    format_func=lambda x: OBRAS[x]
)

st.sidebar.success(f"🏗️ {OBRAS[obra_id]}")

solicitudes = obtener_solicitudes(obra_id)

if not solicitudes:
    st.info("No hay solicitudes")
    st.stop()

# ================= LISTADO =================
for doc_id, s in solicitudes:
    estado = s.get("estado", "pendiente")

    color = {
        "pendiente": "🟡",
        "aprobada": "🟢",
        "rechazada": "🔴"
    }.get(estado, "⚪")

    tipo_icon = "👷" if s.get("tipo") == "personal" else "🧱"
    fecha = s.get("timestamp")
    fecha_str = fecha.astimezone(tz).strftime("%d/%m/%Y %H:%M") if fecha else "N/D"

    with st.expander(
        f"{color} {tipo_icon} {s.get('tipo','')} | {s.get('solicitante','')} | {fecha_str}"
    ):

        st.write(f"**Estado:** {estado.upper()}")
        st.write(f"**Descripción:** {s['descripcion']}")

        if estado == "pendiente":
            respuesta = st.text_area(
                "Respuesta / Observación",
                key=f"resp_{doc_id}"
            )

            col1, col2 = st.columns(2)

            if col1.button("✅ Aprobar", key=f"ap_{doc_id}"):
                db.collection("obras").document(obra_id) \
                    .collection("solicitudes").document(doc_id).update({
                        "estado": "aprobada",
                        "respuesta_jefe": respuesta,
                        "fecha_respuesta": datetime.now(tz)
                    })
                st.success("Solicitud aprobada")
                st.rerun()

            if col2.button("❌ Rechazar", key=f"re_{doc_id}"):
                db.collection("obras").document(obra_id) \
                    .collection("solicitudes").document(doc_id).update({
                        "estado": "rechazada",
                        "respuesta_jefe": respuesta,
                        "fecha_respuesta": datetime.now(tz)
                    })
                st.error("Solicitud rechazada")
                st.rerun()

        else:
            st.markdown("**Respuesta del jefe:**")
            st.info(s.get("respuesta_jefe", "—"))
