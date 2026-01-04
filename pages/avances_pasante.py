import streamlit as st
import pandas as pd
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
fecha_inicio = obra["fecha_inicio"].date()
fecha_fin = obra["fecha_fin_estimada"].date()


# ================= MATERIALES ASIGNADOS (ADMIN) =================
mats_admin = list(
    db.collection("obras")
    .document(obra_id)
    .collection("materiales")
    .stream()
)

if not mats_admin:
    st.warning("La obra no tiene materiales asignados")
    st.stop()

materiales = []
presupuesto_total = 0

for m in mats_admin:
    d = m.to_dict()
    d["id"] = m.id
    materiales.append(d)
    presupuesto_total += d["subtotal"]

# ================= GASTO ACUMULADO =================
usados = list(
    db.collection("obras")
    .document(obra_id)
    .collection("materiales_usados")
    .stream()
)

gasto_actual = sum(u.to_dict().get("subtotal", 0) for u in usados)

# ================= SEMÁFORO =================
hoy = date.today()
en_plazo = fecha_inicio <= hoy <= fecha_fin
excede_presupuesto = gasto_actual > presupuesto_total

if en_plazo and not excede_presupuesto:
    st.success("🟢 En plazo y dentro del presupuesto")
elif not en_plazo and excede_presupuesto:
    st.error("🔴 Fuera de plazo y presupuesto excedido")
else:
    st.warning("🟡 Atención: revisar fechas o presupuesto")

porcentaje = round((gasto_actual / presupuesto_total) * 100, 2) if presupuesto_total else 0

st.metric("💰 Presupuesto total", f"S/ {presupuesto_total:,.2f}")
st.metric("🔥 Gasto acumulado", f"S/ {gasto_actual:,.2f}")
st.metric("📊 % ejecutado", f"{porcentaje} %")

st.divider()

# ================= UI =================
st.title("📝 Parte Diario – Materiales y Avance")

with st.form("form_avance", clear_on_submit=True):

    responsable = st.text_input("Responsable")

    mat_sel = st.selectbox(
        "Material usado",
        options=materiales,
        format_func=lambda x: f"{x['nombre']} ({x['unidad']})"
    )

    cantidad = st.number_input("Cantidad usada", min_value=0.0, step=1.0)

    descripcion = st.text_area("Descripción del avance", height=120)

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
    elif cantidad <= 0:
        st.error("La cantidad debe ser mayor a 0")
    elif not fotos or len(fotos) < 3:
        st.error("Debes subir al menos 3 fotos")
    else:
        subtotal = round(cantidad * mat_sel["precio_unitario"], 2)

        urls = []
        with st.spinner("Subiendo fotos..."):
            for f in fotos:
                res = cloudinary.uploader.upload(
                    f,
                    folder=f"obras/{obra_id}/avances"
                )
                urls.append(res["secure_url"])

        # guardar material usado
        db.collection("obras") \
            .document(obra_id) \
            .collection("materiales_usados") \
            .add({
                "fecha": datetime.now(),
                "material_id": mat_sel["material_id"],
                "nombre": mat_sel["nombre"],
                "unidad": mat_sel["unidad"],
                "cantidad": cantidad,
                "precio_unitario": mat_sel["precio_unitario"],
                "subtotal": subtotal,
                "usuario": username
            })

        # guardar avance
        db.collection("obras") \
            .document(obra_id) \
            .collection("avances") \
            .add({
                "fecha": datetime.now().isoformat(),
                "timestamp": datetime.now(),
                "usuario": username,
                "responsable": responsable,
                "observaciones": descripcion,
                "material": mat_sel["nombre"],
                "cantidad": cantidad,
                "costo": subtotal,
                "fotos": urls
            })

        st.success("Avance registrado correctamente")
        st.rerun()

# ================= HISTORIAL =================
st.divider()
st.subheader("📂 Historial de avances")

avances = (
    db.collection("obras")
    .document(obra_id)
    .collection("avances")
    .order_by("timestamp", direction=firestore.Query.DESCENDING)
    .stream()
)

hay = False
for av in avances:
    hay = True
    d = av.to_dict()
    f = datetime.fromisoformat(d["fecha"])

    with st.expander(f"📅 {f:%d/%m/%Y %H:%M} — {d.get('responsable','N/D')}"):
        st.write(d.get("observaciones", ""))
        st.caption(f"Material: {d.get('material')} | Cantidad: {d.get('cantidad')} | Costo: S/ {d.get('costo')}")
        st.caption(f"Registrado por: {d.get('usuario')}")
        for img in d.get("fotos", []):
            st.image(img, use_container_width=True)

if not hay:
    st.info("Aún no hay avances registrados.")
