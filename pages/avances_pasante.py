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

# ================= PROGRESO DE LA OBRA =================
def calcular_progreso(db, obra_id):
    avances = (
        db.collection("obras")
        .document(obra_id)
        .collection("avances")
        .stream()
    )

    total = 0
    for av in avances:
        total += int(av.to_dict().get("avance_porcentaje", 0))

    return min(total, 100)

total_avance = calcular_progreso(db, obra_id)

st.subheader("📊 Progreso total de la obra")
st.progress(total_avance / 100)
st.caption(f"{total_avance}% completado")

# Bloquear si ya terminó
if total_avance >= 100:
    st.success("✅ La obra ya alcanzó el 100% de avance")
    st.info("No es posible registrar más avances")
    st.stop()

# ================= MATERIALES DE LA OBRA =================
materiales_obra = (
    db.collection("obras")
    .document(obra_id)
    .collection("materiales")
    .stream()
)

lista_materiales = [
    {"id": m.id, **m.to_dict()}
    for m in materiales_obra
]

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
st.caption("Registra el avance diario de tu obra asignada")

with st.form("form_avance", clear_on_submit=True):
    responsable = st.text_input("Responsable")
    descripcion = st.text_area("Descripción del avance", height=120)

    porcentaje = st.number_input(
        "📈 Porcentaje de avance del día",
        min_value=1,
        max_value=100,
        step=1
    )

    st.subheader("🧱 Materiales usados hoy")

    materiales_usados = []
    costo_total_dia = 0.0

    for mat in lista_materiales:
        cantidad = st.number_input(
            f"{mat['nombre']} ({mat['unidad']})",
            min_value=0.0,
            step=1.0,
            key=f"mat_{mat['id']}"
        )

        if cantidad > 0:
            subtotal = cantidad * mat["precio_unitario"]
            costo_total_dia += subtotal

            materiales_usados.append({
                "material_id": mat["id"],
                "nombre": mat["nombre"],
                "cantidad": cantidad,
                "precio_unitario": mat["precio_unitario"],
                "subtotal": round(subtotal, 2)
            })

    st.info(f"💰 Costo estimado del día: S/ {costo_total_dia:.2f}")

    fotos = st.file_uploader(
        "Subir fotos (mínimo 3)",
        accept_multiple_files=True,
        type=["jpg", "png", "jpeg"]
    )

    guardar = st.form_submit_button("Guardar avance")

# ================= GUARDAR AVANCE =================
if guardar:
    if not responsable.strip() or not descripcion.strip():
        st.error("Responsable y descripción son obligatorios")
        st.stop()

    if not fotos or len(fotos) < 3:
        st.error("Debes subir al menos 3 fotos")
        st.stop()

    if total_avance + porcentaje > 100:
        st.error("❌ El porcentaje ingresado supera el 100% total de la obra")
        st.stop()

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
            "timestamp": datetime.now(),
            "usuario": username,
            "responsable": responsable,
            "observaciones": descripcion,
            "avance_porcentaje": porcentaje,
            "materiales_usados": materiales_usados,
            "costo_dia": round(costo_total_dia, 2),
            "fotos": urls
        })

    st.success("✅ Avance registrado correctamente")
    st.rerun()

# ================= HISTORIAL =================
st.divider()
st.subheader("📂 Historial de avances")

avances = (
    db.collection("obras")
    .document(obra_id)
    .collection("avances")
    .order_by("fecha", direction=firestore.Query.DESCENDING)
    .stream()
)

hay_avances = False

for av in avances:
    hay_avances = True
    data = av.to_dict()
    f = datetime.fromisoformat(data["fecha"])

    with st.expander(f"📅 {f:%d/%m/%Y %H:%M} — {data.get('responsable','N/D')}"):
        st.write(data.get("observaciones", "Sin observaciones"))
        st.caption(f"Registrado por: {data.get('usuario','-')}")
        st.write(f"📈 Avance: {data.get('avance_porcentaje', 0)}%")

        for img in data.get("fotos", []):
            st.image(img, use_container_width=True)

if not hay_avances:
    st.info("Aún no hay avances registrados para esta obra.")
