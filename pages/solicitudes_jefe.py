#solicitudes_jefe.py
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
    return {
        d.id: d.to_dict().get("nombre", d.id)
        for d in db.collection("obras").stream()
    }

def obtener_solicitudes(obra_id):
    solicitudes = []
    docs = db.collection("obras").document(obra_id).collection("solicitudes").stream()

    for d in docs:
        data = d.to_dict()
        data["doc_id"] = d.id
        solicitudes.append(data)

    # ordenar por timestamp
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
    format_func=lambda x: OBRAS[x],
    key="obra_jefe"
)

st.sidebar.success(f"🏗️ {OBRAS[obra_id]}")

solicitudes = obtener_solicitudes(obra_id)

if not solicitudes:
    st.info("No hay solicitudes")
    st.stop()

# ================= LISTADO =================
for s in solicitudes:
    estado = s.get("estado", "pendiente")
    doc_id = s["doc_id"]

    color = {
        "pendiente": "🟡",
        "aprobada": "🟢",
        "rechazada": "🔴"
    }.get(estado, "⚪")

    tipo = s.get("tipo", "—")
    solicitante = s.get("solicitante", "—")

    ts = s.get("timestamp")
    if ts and hasattr(ts, "astimezone"):
        ts = ts.astimezone(tz)
        fecha = ts.strftime("%d/%m/%Y %H:%M")
    else:
        fecha = "Fecha N/D"

    with st.expander(f"{color} {tipo.upper()} | {solicitante} | {fecha}"):

        st.markdown(f"**Estado:** `{estado.upper()}`")
        st.write(f"**Descripción:** {s.get('descripcion', '—')}")

        if tipo == "personal":
            st.info(
                f"Cantidad: {s.get('cantidad')} trabajadores\n\n"
                f"Grupo: {s.get('grupo')}"
            )

        if tipo == "materiales":
            mats = s.get("materiales", [])
            if mats:
                st.table(mats)

        elif tipo == "caja_chica":
            st.metric(
                "Monto solicitado",
                f"S/ {s.get('costo', 0):,.2f}"
            )

            st.warning(
                f"**Problemática:**\n\n{s.get('problematica', '—')}"
            )

            st.success(
                f"**Solución propuesta:**\n\n{s.get('solucion', '—')}"
            )



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
            st.info(f"Respuesta del jefe: {s.get('respuesta_jefe', '—')}")
