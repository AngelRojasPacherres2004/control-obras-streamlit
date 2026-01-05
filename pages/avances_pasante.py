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

if auth.get("role") != "pasante":
    st.warning("Acceso solo para pasantes")
    st.stop()

obra_id = auth.get("obra")
username = auth.get("username", "desconocido")

if not obra_id:
    st.error("No tienes una obra asignada")
    st.stop()

# ================= DATOS DE LA OBRA =================
obra_ref = db.collection("obras").document(obra_id)
obra_doc = obra_ref.get()

if not obra_doc.exists:
    st.error("La obra asignada no existe")
    st.stop()

obra = obra_doc.to_dict()

fecha_inicio = obra.get("fecha_inicio")
fecha_fin = obra.get("fecha_fin_estimado")
presupuesto_total = float(obra.get("presupuesto_total", 0))
gasto_acumulado = float(obra.get("gasto_acumulado", 0))

# ================= SIDEBAR =================
with st.sidebar:
    st.header("🏗️ Obra asignada")
    st.write(f"**Nombre:** {obra.get('nombre')}")
    st.write(f"**Estado:** {obra.get('estado')}")
    st.write(f"📅 Inicio: {fecha_inicio.date()}")
    st.write(f"🏁 Fin estimado: {fecha_fin.date()}")

# ================= MATERIALES =================
materiales = []
for m in obra_ref.collection("materiales").stream():
    d = m.to_dict()
    d["doc_id"] = m.id
    materiales.append(d)

if not materiales:
    st.warning("La obra no tiene materiales asignados")
    st.stop()

# ================= MÉTRICAS =================
st.subheader("📊 Estado Financiero")

porcentaje = (gasto_acumulado / presupuesto_total) * 100 if presupuesto_total else 0

st.metric("💰 Presupuesto total", f"S/ {presupuesto_total:,.2f}")
st.metric("🔥 Gasto acumulado", f"S/ {gasto_acumulado:,.2f}")
st.metric("📈 % ejecutado", f"{porcentaje:.2f}%")
st.progress(min(porcentaje / 100, 1.0))

st.divider()

# ================= FORMULARIO =================
st.title("📝 Registrar avance diario")

with st.form("form_avance", clear_on_submit=True):
    responsable = st.text_input("Responsable", value=username)
    descripcion = st.text_area("Descripción", height=100)

    materiales_usados = {}
    costo_total_dia = 0.0

    st.subheader("🧱 Materiales usados")

    for mat in materiales:
        c1, c2 = st.columns([3, 1])
        c1.write(f"**{mat['nombre']}** ({mat['unidad']})")

        cantidad = c2.number_input(
            "Cant.",
            min_value=0.0,
            step=1.0,
            key=mat["doc_id"]
        )

        if cantidad > 0:
            subtotal = cantidad * mat["precio_unitario"]
            costo_total_dia += subtotal

            materiales_usados[mat["doc_id"]] = {
                "nombre": mat["nombre"],
                "unidad": mat["unidad"],
                "cantidad": cantidad,
                "precio_unitario": mat["precio_unitario"],
                "subtotal": round(subtotal, 2)
            }

    st.info(f"💰 Costo del día: S/ {costo_total_dia:.2f}")

    fotos = st.file_uploader(
        "Subir fotos (mínimo 3)",
        accept_multiple_files=True,
        type=["jpg", "png", "jpeg"]
    )

    guardar = st.form_submit_button("Guardar avance")

# ================= GUARDAR =================
if guardar:
    hoy = datetime.now()

    fuera_presupuesto = (gasto_acumulado + costo_total_dia) > presupuesto_total
    fuera_fecha = hoy < fecha_inicio or hoy > fecha_fin

    if not responsable.strip() or not descripcion.strip():
        st.error("Campos obligatorios")
    elif not materiales_usados:
        st.error("Debes usar materiales")
    elif not fotos or len(fotos) < 3:
        st.error("Mínimo 3 fotos")
    else:
        urls = []
        for f in fotos:
            r = cloudinary.uploader.upload(f, folder=f"obras/{obra_id}/avances")
            urls.append(r["secure_url"])

        batch = db.batch()

        # ---- avance ----
        ref_avance = obra_ref.collection("avances").document()
        batch.set(ref_avance, {
            "fecha": hoy.isoformat(),
            "timestamp": hoy,
            "responsable": responsable,
            "usuario": username,
            "observaciones": descripcion,
            "costo_total_dia": round(costo_total_dia, 2),
            "materiales_usados": list(materiales_usados.values()),
            "fotos": urls,
            "fuera_presupuesto": fuera_presupuesto,
            "fuera_fecha": fuera_fecha
        })

        # ---- gasto acumulado ATÓMICO ----
        batch.update(obra_ref, {
            "gasto_acumulado": firestore.Increment(costo_total_dia),
            "ultima_actualizacion": firestore.SERVER_TIMESTAMP
        })

        batch.commit()

        st.success("Avance registrado correctamente")
        st.rerun()

# ================= HISTORIAL =================
st.divider()
st.subheader("📂 Historial de avances")

for av in obra_ref.collection("avances")\
        .order_by("timestamp", direction=firestore.Query.DESCENDING)\
        .limit(10).stream():

    d = av.to_dict()
    f = datetime.fromisoformat(d["fecha"])

    semaforo = "🟢"
    if d.get("fuera_presupuesto") or d.get("fuera_fecha"):
        semaforo = "🔴"

    with st.expander(f"{semaforo} {f:%d/%m/%Y %H:%M} — {d['responsable']}"):
        st.metric("Costo del día", f"S/ {d['costo_total_dia']:,.2f}")
        st.write(d.get("observaciones"))

        if d.get("fuera_presupuesto"):
            st.error("⚠ Excede el presupuesto")

        if d.get("fuera_fecha"):
            st.error("⚠ Fuera de la fecha de la obra")

        for img in d.get("fotos", []):
            st.image(img, use_container_width=True)
