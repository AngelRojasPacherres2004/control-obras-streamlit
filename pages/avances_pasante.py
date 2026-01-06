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

# ================= DATOS OBRA =================
obra_ref = db.collection("obras").document(obra_id)
obra = obra_ref.get().to_dict()

# ================= FECHAS =================
hoy = date.today()

fecha_inicio = obra.get("fecha_inicio")
fecha_fin = obra.get("fecha_fin_estimado")

if fecha_inicio and hasattr(fecha_inicio, "date"):
    fecha_inicio = fecha_inicio.date()

if fecha_fin and hasattr(fecha_fin, "date"):
    fecha_fin = fecha_fin.date()

fuera_fecha_hoy = hoy < fecha_inicio or hoy > fecha_fin if fecha_inicio and fecha_fin else False

# ================= SIDEBAR =================
with st.sidebar:
    st.header("🏗️ Obra asignada")
    st.write(f"**Nombre:** {obra.get('nombre')}")
    st.write(f"**Estado:** {obra.get('estado')}")
    st.write(f"📅 Inicio: {fecha_inicio}")
    st.write(f"🏁 Fin estimado: {fecha_fin}")

# ================= MATERIALES =================
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

# ================= GASTO GLOBAL =================
gasto_acumulado = float(obra.get("gasto_acumulado", 0))
excede_presupuesto = gasto_acumulado > presupuesto_total if presupuesto_total else False
porcentaje_total = (gasto_acumulado / presupuesto_total) * 100 if presupuesto_total else 0

# ================= AVANCES ORDENADOS (CLAVE) =================
avances_ordenados = list(
    obra_ref.collection("avances")
    .order_by("timestamp", direction=firestore.Query.ASCENDING)
    .stream()
)

# ================= DETECCIÓN GLOBAL REAL =================
gasto_tmp = 0.0
hay_rojo = False

for av in avances_ordenados:
    d = av.to_dict()
    ts = d.get("timestamp")
    gasto_tmp += float(d.get("costo_total_dia", 0))

    fuera_fecha = False
    if ts and fecha_inicio and fecha_fin:
        f = ts.date()
        fuera_fecha = f < fecha_inicio or f > fecha_fin

    if gasto_tmp > presupuesto_total or fuera_fecha:
        hay_rojo = True
        break

# ================= MÉTRICAS =================
st.subheader("📊 Estado Financiero")

st.metric("💰 Presupuesto total", f"S/ {presupuesto_total:,.2f}")
st.metric("🔥 Gasto acumulado", f"S/ {gasto_acumulado:,.2f}")
st.metric("📈 % ejecutado", f"{porcentaje_total:.2f}%")
st.progress(min(porcentaje_total / 100, 1.0))

# ================= SEMÁFORO GLOBAL =================
if hay_rojo:
    st.error("🔴 Existen avances que exceden presupuesto o están fuera de fecha")
else:
    st.success("🟢 Dentro de presupuesto y fechas")

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
        cantidad = col2.number_input("Cant.", 0.0, step=1.0, key=mat["doc_id"])

        if cantidad > 0:
            subtotal = cantidad * mat["precio_unitario"]
            costo_total_dia += subtotal
            materiales_usados[mat["doc_id"]] = subtotal

    st.info(f"💰 Costo del día: S/ {costo_total_dia:.2f}")

    fotos = st.file_uploader(
        "Subir fotos (mínimo 3)",
        accept_multiple_files=True,
        type=["jpg", "png", "jpeg"]
    )

    guardar = st.form_submit_button("Guardar avance")

if guardar:
    urls = []
    for f in fotos:
        res = cloudinary.uploader.upload(f, folder=f"obras/{obra_id}/avances")
        urls.append(res["secure_url"])

    obra_ref.collection("avances").add({
        "timestamp": datetime.now(),
        "usuario": username,
        "responsable": responsable,
        "observaciones": descripcion,
        "costo_total_dia": round(costo_total_dia, 2),
        "porcentaje_avance_financiero": round(
            (costo_total_dia / presupuesto_total) * 100 if presupuesto_total else 0, 2
        ),
        "fotos": urls
    })

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

# ================= HISTORIAL (CORRECTO) =================
st.divider()
st.subheader("📂 Historial de avances")

gasto_corriente = 0.0
ruptura_detectada = False

for av in avances_ordenados[::-1]:  # mostrar recientes primero
    d = av.to_dict()
    ts = d.get("timestamp")
    costo = float(d.get("costo_total_dia", 0))

    gasto_corriente += costo

    fuera_fecha = False
    if ts and fecha_inicio and fecha_fin:
        f = ts.date()
        fuera_fecha = f < fecha_inicio or f > fecha_fin

    if not ruptura_detectada and (gasto_corriente > presupuesto_total or fuera_fecha):
        ruptura_detectada = True

    alerta = "🔴" if ruptura_detectada else "🟢"

    with st.expander(
        f"{alerta} {ts:%d/%m/%Y %H:%M} | S/ {costo:,.2f} | {d.get('responsable')}"
    ):
        st.write(d.get("observaciones"))
        st.metric("Costo del día", f"S/ {costo:,.2f}")

        for img in d.get("fotos", []):
            st.image(img, use_container_width=True)
