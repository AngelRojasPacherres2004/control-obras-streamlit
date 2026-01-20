import streamlit as st
import pandas as pd
from datetime import datetime
from firebase_admin import firestore
import pytz

# ================= ZONA HORARIA =================
pais_tz = pytz.timezone("America/Lima")

# ================= CONFIG =================
st.set_page_config(page_title="Solicitudes", layout="centered")
db = firestore.client()

# ================= SEGURIDAD =================
if "auth" not in st.session_state:
    st.error("Sesión no válida")
    st.stop()

auth = st.session_state["auth"]

if auth.get("role") != "pasante":
    st.warning("Acceso solo para pasantes")
    st.stop()

obra_id = auth.get("obra")
username = auth.get("username", "desconocido")

if not obra_id:
    st.error("No tienes una obra asignada")
    st.stop()

# ================= DATOS OBRA =================
obra_ref = db.collection("obras").document(obra_id)
obra_doc = obra_ref.get()

if not obra_doc.exists:
    st.error("La obra asignada no existe")
    st.stop()

obra = obra_doc.to_dict()

# ================= TÍTULO =================
st.title("📋 Solicitudes de Recursos")
st.caption(f"🏗️ Obra: {obra.get('nombre')}")

tab1, tab2 = st.tabs(["➕ Nueva Solicitud", "📂 Mis Solicitudes"])

# ==========================================================
# TAB 1 – NUEVA SOLICITUD
# ==========================================================



with tab1:
    tipo_solicitud = st.radio(
        "Tipo de solicitud",
        ["👷 Personal", "🧱 Materiales", "💵 Caja Chica"],
        horizontal=True
    )

    # ---------- PERSONAL ----------
    if tipo_solicitud == "👷 Personal":
        with st.form("form_personal", clear_on_submit=True):
            cantidad = st.number_input("Cantidad de trabajadores", 1, step=1)
            grupo = st.text_input("Grupo o cuadrilla")
            descripcion = st.text_area("Justificación", height=100)

            enviar = st.form_submit_button("📤 Enviar solicitud")

            if enviar:
                if not grupo or not descripcion:
                    st.error("Todos los campos son obligatorios")
                else:
                    ahora = datetime.now(pais_tz)
                    obra_ref.collection("solicitudes").add({
                        "tipo": "personal",
                        "estado": "pendiente",
                        "timestamp": ahora,
                        "fecha": ahora.isoformat(),
                        "solicitante": username,
                        "cantidad": cantidad,
                        "grupo": grupo,
                        "descripcion": descripcion
                    })
                    st.success("✅ Solicitud enviada")
                    st.rerun()

    # ---------- MATERIALES ----------
    elif tipo_solicitud == "🧱 Materiales":
        materiales = []
        for m in obra_ref.collection("materiales").stream():
            d = m.to_dict()
            d["id"] = m.id
            materiales.append(d)

        if not materiales:
            st.warning("No hay materiales asignados")
        else:
            with st.form("form_materiales", clear_on_submit=True):
                seleccionados = {}

                for mat in materiales:
                    c1, c2 = st.columns([3, 1])
                    c1.write(f"**{mat['nombre']}** ({mat['unidad']})")
                    cant = c2.number_input(
                        "Cant",
                        min_value=0.0,
                        step=1.0,
                        key=f"mat_{mat['id']}",
                        label_visibility="collapsed"
                    )
                    if cant > 0:
                        seleccionados[mat["id"]] = {
                            "nombre": mat["nombre"],
                            "unidad": mat["unidad"],
                            "cantidad": cant
                        }

                descripcion = st.text_area("Justificación", height=100)
                enviar = st.form_submit_button("📤 Enviar solicitud")

                if enviar:
                    if not seleccionados:
                        st.error("Selecciona al menos un material")
                    elif not descripcion:
                        st.error("La descripción es obligatoria")
                    else:
                        ahora = datetime.now(pais_tz)
                        obra_ref.collection("solicitudes").add({
                            "tipo": "materiales",
                            "estado": "pendiente",
                            "timestamp": ahora,
                            "fecha": ahora.isoformat(),
                            "solicitante": username,
                            "materiales": list(seleccionados.values()),
                            "descripcion": descripcion
                        })
                        st.success("✅ Solicitud enviada")
                        st.rerun()

    # ---------- CAJA CHICA ----------
    elif tipo_solicitud == "💵 Caja Chica":
        with st.form("form_caja_chica", clear_on_submit=True):
            costo = st.number_input("Monto solicitado (S/)", min_value=0.0, step=1.0)
            problematica = st.text_area("Problemática", height=100)
            solucion = st.text_area("Solución", height=100)

            enviar = st.form_submit_button("📤 Enviar solicitud")

            if enviar:
                if costo <= 0:
                    st.error("El monto debe ser mayor a 0")
                elif not problematica or not solucion:
                    st.error("Todos los campos son obligatorios")
                else:
                    ahora = datetime.now(pais_tz)
                    obra_ref.collection("solicitudes").add({
                        "tipo": "caja_chica",
                        "estado": "pendiente",
                        "timestamp": ahora,
                        "fecha": ahora.isoformat(),
                        "solicitante": username,
                        "costo": costo,
                        "problematica": problematica,
                        "solucion": solucion
                    })
                    st.success("✅ Solicitud de caja chica enviada")
                    st.rerun()

# ==========================================================
# TAB 2 – MIS SOLICITUDES
# ==========================================================
with tab2:
    st.subheader("📂 Historial de solicitudes")

    solicitudes = []
    docs = obra_ref.collection("solicitudes") \
        .where("solicitante", "==", username) \
        .stream()

    for d in docs:
        s = d.to_dict()
        s["id"] = d.id
        solicitudes.append(s)

    solicitudes.sort(key=lambda x: x.get("timestamp", datetime.min), reverse=True)

    if not solicitudes:
        st.info("Aún no has enviado solicitudes")
        st.stop()

    col1, col2 = st.columns(2)

    filtro_tipo = col1.selectbox(
        "Tipo",
        ["Todas", "Personal", "Materiales", "Caja Chica"]
    )

    filtro_estado = col2.selectbox(
        "Estado",
        ["Todos", "Pendiente", "Aprobada", "Rechazada"]
    )

    mapa = {
        "Personal": "personal",
        "Materiales": "materiales",
        "Caja Chica": "caja_chica"
    }

    if filtro_tipo != "Todas":
        solicitudes = [
            s for s in solicitudes
            if s.get("tipo") == mapa[filtro_tipo]
        ]

    if filtro_estado != "Todos":
        solicitudes = [
            s for s in solicitudes
            if s.get("estado") == filtro_estado.lower()
        ]

    st.divider()

    for s in solicitudes:
        ts = s.get("timestamp")
        fecha = ts.astimezone(pais_tz).strftime("%d/%m/%Y %H:%M") if ts else "N/D"

        icono = {
            "personal": "👷",
            "materiales": "🧱",
            "caja_chica": "💵"
        }.get(s["tipo"], "📄")

        with st.expander(f"{icono} {s['tipo'].replace('_',' ').title()} · {fecha}"):
            st.markdown(f"**Estado:** `{s['estado'].upper()}`")

            if s["tipo"] == "personal":
                st.info(f"Cantidad: {s['cantidad']} | Grupo: {s['grupo']}")
                st.write(s.get("descripcion", ""))

            elif s["tipo"] == "materiales":
                st.table(pd.DataFrame(s.get("materiales", [])))
                st.write(s.get("descripcion", ""))

            elif s["tipo"] == "caja_chica":
                st.metric("Monto solicitado", f"S/ {s.get('costo', 0):,.2f}")
                st.warning(f"**Problemática:** {s.get('problematica', '')}")
                st.success(f"**Solución:** {s.get('solucion', '')}")

            if s["estado"] == "rechazada":
                st.error(f"Motivo: {s.get('respuesta_jefe', 'Sin observaciones')}")
