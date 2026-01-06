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
obra_ref = db.collection("obras").document(obra_id)
obra_doc = obra_ref.get()

if not obra_doc.exists:
    st.error("La obra asignada no existe")
    st.stop()

obra = obra_doc.to_dict()

# ================= FECHAS NORMALIZADAS =================
hoy = date.today()

fecha_inicio = obra.get("fecha_inicio")
fecha_fin = obra.get("fecha_fin_estimado")

if fecha_inicio and hasattr(fecha_inicio, "date"):
    fecha_inicio = fecha_inicio.date()

if fecha_fin and hasattr(fecha_fin, "date"):
    fecha_fin = fecha_fin.date()

fuera_fecha = False
if fecha_inicio and fecha_fin:
    fuera_fecha = hoy < fecha_inicio or hoy > fecha_fin

# ================= SIDEBAR =================
with st.sidebar:
    st.header("🏗️ Obra asignada")
    st.write(f"**Nombre:** {obra.get('nombre')}")
    st.write(f"**Estado:** {obra.get('estado')}")
    st.write(f"📅 Inicio: {fecha_inicio}")
    st.write(f"🏁 Fin estimado: {fecha_fin}")

# ================= MATERIALES ASIGNADOS =================
materiales = []
presupuesto_total = 0.0

for m in obra_ref.collection("materiales").stream():
    d = m.to_dict()
    d["doc_id"] = m.id
    materiales.append(d)
    presupuesto_total += float(d.get("subtotal", 0))

if not materiales:
    st.warning("La obra no tiene materiales asignados")
    st.stop()

# ================= GASTO ACUMULADO =================
gasto_acumulado = float(obra.get("gasto_acumulado", 0))
porcentaje_total = (gasto_acumulado / presupuesto_total) * 100 if presupuesto_total else 0
excede_presupuesto = gasto_acumulado > presupuesto_total if presupuesto_total else False

# ================= MÉTRICAS =================
st.subheader("📊 Estado Financiero")

st.metric("💰 Presupuesto total", f"S/ {presupuesto_total:,.2f}")
st.metric("🔥 Gasto acumulado", f"S/ {gasto_acumulado:,.2f}")
st.metric("📈 % ejecutado", f"{porcentaje_total:.2f}%")
st.progress(min(porcentaje_total / 100, 1.0))

# ================= SEMÁFORO GLOBAL =================
if excede_presupuesto and fuera_fecha:
    st.error("🔴 Presupuesto excedido y avance fuera de fecha")
elif excede_presupuesto:
    st.warning("🟠 Presupuesto excedido")
elif fuera_fecha:
    st.warning("🟠 Avance fuera del rango de fechas")
else:
    st.success("🟢 Avance dentro de presupuesto y fechas")

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

            for m_id, m in materiales_usados.items():
                ref = obra_ref.collection("materiales_usados").document()
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

            ref_avance = obra_ref.collection("avances").document()
            batch.set(ref_avance, {
                "fecha": datetime.now().isoformat(),
                "timestamp": datetime.now(),
                "usuario": username,
                "responsable": responsable,
                "observaciones": descripcion,
                "costo_total_dia": round(costo_total_dia, 2),
                "porcentaje_avance_financiero": round(porcentaje_avance, 2),
                "fuera_fecha": fuera_fecha,
                "fotos": urls
            })

            batch.commit()

            total = sum(
                float(a.to_dict().get("costo_total_dia", 0))
                for a in obra_ref.collection("avances").stream()
            )

            obra_ref.update({
                "gasto_acumulado": round(total, 2),
                "ultima_actualizacion": firestore.SERVER_TIMESTAMP
            })

            st.success("✅ Avance registrado correctamente")
            st.rerun()

# ================= HISTORIAL =================
st.divider()
st.subheader("📂 Historial de avances")

avances_docs = (
    obra_ref.collection("avances")
    .order_by("timestamp", direction=firestore.Query.DESCENDING)
    .limit(10)
    .stream()
)

hay = False

for av in avances_docs:
    hay = True
    d = av.to_dict()

    # ✅ TIMESTAMP YA ES datetime
    f = d.get("timestamp")

    prog = d.get("porcentaje_avance_financiero", 0)
    alerta = "🔴" if d.get("fuera_fecha") else "🟢"

    with st.expander(
        f"{alerta} {f:%d/%m/%Y %H:%M} | 📈 {prog}% | {d.get('responsable')}"
    ):
        st.write(d.get("observaciones"))
        st.metric("Costo del día", f"S/ {d.get('costo_total_dia', 0):,.2f}")
        st.progress(min(prog / 100, 1.0))

        for img in d.get("fotos", []):
            st.image(img, use_container_width=True)

if not hay:
    st.info("Aún no hay avances registrados.")
