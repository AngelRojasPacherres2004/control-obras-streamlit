import streamlit as st
from datetime import datetime, date
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
obra_doc = db.collection("obras").document(obra_id).get()
if not obra_doc.exists:
    st.error("La obra asignada no existe")
    st.stop()

obra = obra_doc.to_dict()

# ================= SIDEBAR =================
with st.sidebar:
    st.header("🏗️ Obra asignada")
    st.write(f"**Nombre:** {obra.get('nombre')}")
    st.write(f"**Estado:** {obra.get('estado')}")
    st.write(f"📅 Inicio: {obra.get('fecha_inicio').date()}")
    st.write(f"🏁 Fin estimado: {obra.get('fecha_fin_estimada').date()}")

# ================= MATERIALES ASIGNADOS =================
materiales_docs = (
    db.collection("obras")
    .document(obra_id)
    .collection("materiales")
    .stream()
)

materiales = []
presupuesto_total = 0.0

for m in materiales_docs:
    d = m.to_dict()
    d["doc_id"] = m.id
    materiales.append(d)
    presupuesto_total += float(d.get("subtotal", 0))

if not materiales:
    st.warning("La obra no tiene materiales asignados")
    st.stop()

# ================= GASTO ACUMULADO =================
usados_docs = (
    db.collection("obras")
    .document(obra_id)
    .collection("materiales_usados")
    .stream()
)

gasto_actual = sum(float(u.to_dict().get("subtotal", 0)) for u in usados_docs)

# ================= MÉTRICAS =================
st.subheader("📊 Estado Financiero")

porcentaje_total = (gasto_actual / presupuesto_total) * 100 if presupuesto_total else 0

st.metric("💰 Presupuesto total", f"S/ {presupuesto_total:,.2f}")
st.metric("🔥 Gasto acumulado", f"S/ {gasto_actual:,.2f}")
st.metric("📈 % ejecutado", f"{porcentaje_total:.2f}%")
st.progress(min(porcentaje_total / 100, 1.0))

st.divider()

# ================= FORMULARIO =================
st.title("📝 Registrar avance diario")

with st.form("form_avance", clear_on_submit=True):
    responsable = st.text_input("Responsable", value=username)
    descripcion = st.text_area("Descripción del trabajo", height=100)

    st.subheader("🧱 Materiales usados hoy")

    materiales_usados = {}
    costo_total_dia = 0.0

    for mat in materiales:
        col1, col2 = st.columns([3, 1])
        col1.write(f"**{mat['nombre']}** ({mat['unidad']})")

        cantidad = col2.number_input(
            "Cant.",
            min_value=0.0,
            step=1.0,
            key=f"mat_{mat['doc_id']}"
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
    if not responsable.strip() or not descripcion.strip():
        st.error("Responsable y descripción son obligatorios")
    elif not materiales_usados:
        st.error("Debes usar al menos un material")
    elif not fotos or len(fotos) < 3:
        st.error("Debes subir mínimo 3 fotos")
    else:
        with st.spinner("Guardando avance..."):
            urls = []
            for f in fotos:
                res = cloudinary.uploader.upload(
                    f,
                    folder=f"obras/{obra_id}/avances"
                )
                urls.append(res["secure_url"])

            batch = db.batch()

            # ---- guardar materiales usados ----
            for m_id, m in materiales_usados.items():
                ref = (
                    db.collection("obras")
                    .document(obra_id)
                    .collection("materiales_usados")
                    .document()
                )
                batch.set(ref, {
                    "fecha": datetime.now(),
                    "material_doc_id": m_id,
                    **m,
                    "usuario": username
                })

            porcentaje_avance = (
                (costo_total_dia / presupuesto_total) * 100
                if presupuesto_total else 0
            )

            # ---- guardar avance (SNAPSHOT) ----
            ref_avance = (
                db.collection("obras")
                .document(obra_id)
                .collection("avances")
                .document()
            )

            batch.set(ref_avance, {
                "fecha": datetime.now().isoformat(),
                "timestamp": datetime.now(),
                "usuario": username,
                "responsable": responsable,
                "observaciones": descripcion,
                "costo_total_dia": round(costo_total_dia, 2),
                "porcentaje_avance_financiero": round(porcentaje_avance, 2),
                "materiales_usados": list(materiales_usados.values()),
                "fotos": urls
            })

            batch.commit()

            st.success(
                f"Avance registrado. Impacto del día: {porcentaje_avance:.2f}%"
            )
            st.rerun()

# ================= HISTORIAL =================
st.divider()
st.subheader("📂 Historial de avances")

avances_docs = (
    db.collection("obras")
    .document(obra_id)
    .collection("avances")
    .order_by("timestamp", direction=firestore.Query.DESCENDING)
    .limit(10)
    .stream()
)

hay = False

for av in avances_docs:
    hay = True
    d = av.to_dict()
    f = datetime.fromisoformat(d["fecha"])
    prog = d.get("porcentaje_avance_financiero", 0)

    with st.expander(
        f"📅 {f:%d/%m/%Y %H:%M} | 📈 {prog}% | {d.get('responsable')}"
    ):
        st.write(d.get("observaciones"))
        st.metric("Costo del día", f"S/ {d.get('costo_total_dia', 0):,.2f}")
        st.progress(min(prog / 100, 1.0))

        st.markdown("### 🧱 Materiales usados")
        for m in d.get("materiales_usados", []):
            st.write(
                f"- **{m['nombre']}** ({m['unidad']}): "
                f"{m['cantidad']} × S/ {m['precio_unitario']} "
                f"= **S/ {m['subtotal']}**"
            )

        for img in d.get("fotos", []):
            st.image(img, use_container_width=True)

if not hay:
    st.info("Aún no hay avances registrados.")
