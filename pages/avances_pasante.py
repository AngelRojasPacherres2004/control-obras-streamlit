# avances_pasante.py
import streamlit as st
import pandas as pd
from datetime import datetime
import cloudinary.uploader
from firebase_admin import firestore
import pytz

# ================= CONFIG =================
st.set_page_config(page_title="Parte Diario", layout="centered")
db = firestore.client()
tz = pytz.timezone("America/Lima")

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

# ================= OBRA =================
obra_ref = db.collection("obras").document(obra_id)
obra_doc = obra_ref.get()

if not obra_doc.exists:
    st.error("La obra asignada no existe")
    st.stop()

obra = obra_doc.to_dict()




# ================= FIX AVANCES ANTIGUOS (SIN FECHA) =================
avances_ref = obra_ref.collection("avances").stream()

batch_fix = db.batch()
fix_count = 0

for av in avances_ref:
    data = av.to_dict()

    if "fecha" not in data and "timestamp" in data:
        ts = data["timestamp"].astimezone(tz)
        batch_fix.update(av.reference, {
            "fecha": ts.isoformat()
        })
        fix_count += 1

if fix_count > 0:
    batch_fix.commit()



# ================= SIDEBAR =================
with st.sidebar:
    st.header("🏗️ Obra asignada")
    st.write(f"**Nombre:** {obra.get('nombre')}")
    st.write(f"**Estado:** {obra.get('estado')}")
    st.write(f"📅 Inicio: {obra.get('fecha_inicio').date()}")
    st.write(f"🏁 Fin estimado: {obra.get('fecha_fin_estimado').date()}")

# ================= MATERIALES ASIGNADOS =================
materiales = []

for m in obra_ref.collection("materiales").stream():
    d = m.to_dict()
    d["doc_id"] = m.id
    materiales.append(d)

if not materiales:
    st.warning("La obra no tiene materiales asignados")
    st.stop()
# ================= CALCULAR MATERIAL GASTADO DESDE AVANCES =================
gastado_por_material = {}

avances_docs = obra_ref.collection("avances").stream()

for av in avances_docs:
    mats = av.to_dict().get("materiales_usados", [])
    for m in mats:
        mid = m.get("material_id")
        cant = float(m.get("cantidad", 0))
        gastado_por_material[mid] = gastado_por_material.get(mid, 0) + cant


st.subheader("📦 Resumen de materiales")

resumen = []

for mat in materiales:
    disponible = float(mat.get("cantidad", 0))
    gastado = gastado_por_material.get(mat["doc_id"], 0)

    resumen.append({
        "Material": mat.get("nombre"),
        "Unidad": mat.get("unidad"),
        "Gastado": gastado,
        "Disponible": disponible
    })

df_resumen = pd.DataFrame(resumen)

st.dataframe(
    df_resumen,
    use_container_width=True,
    hide_index=True
)


# ================= FORMULARIO =================
st.title("📝 Registrar avance diario")

with st.form("form_avance", clear_on_submit=True):
    responsable = st.text_input("Responsable", value=username)
    descripcion = st.text_area("Descripción del trabajo", height=100)

    st.subheader("🧱 Materiales usados hoy")

    materiales_usados = {}

    for mat in materiales:
        stock = float(mat.get("cantidad", 0))

        col1, col2 = st.columns([3, 1])
        col1.write(f"**{mat['nombre']}** ({mat['unidad']}) — Disponible: {stock}")

        cantidad = col2.number_input(
            "Cant.",
            min_value=0.0,
            max_value=stock,   # 🔒 LÍMITE MÁXIMO
            step=1.0,
            key=f"mat_{mat['doc_id']}"
        )

        if cantidad > 0:
            materiales_usados[mat["doc_id"]] = {
                "material_id": mat["doc_id"],
                "nombre": mat["nombre"],
                "unidad": mat["unidad"],
                "cantidad": cantidad
            }

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
            try:
                # Subir fotos
                urls = []
                for f in fotos:
                    f.seek(0)
                    res = cloudinary.uploader.upload(
                        f,
                        folder=f"obras/{obra_id}/avances"
                    )
                    urls.append(res["secure_url"])

                batch = db.batch()

                ref_avance = obra_ref.collection("avances").document()
                ahora = datetime.now(tz)

                batch.set(ref_avance, {
                    "fecha": ahora.isoformat(),   # 🔥 CLAVE PARA obras.py
                    "timestamp": ahora,           # se mantiene para orden y zonas horarias
                    "responsable": responsable,
                    "usuario": username,
                    "descripcion": descripcion,
                    "materiales_usados": list(materiales_usados.values()),
                    "fotos": urls
                })

                # Descontar stock
                for mat_id, uso in materiales_usados.items():
                    mat_ref = obra_ref.collection("materiales").document(mat_id)
                    mat_doc = mat_ref.get()

                    stock_actual = float(mat_doc.to_dict().get("cantidad", 0))

                    batch.update(mat_ref, {
                        "cantidad": stock_actual - uso["cantidad"]
                    })

                batch.commit()

                st.success("✅ Avance guardado correctamente")
                st.rerun()

            except Exception as e:
                st.error(f"❌ Error: {str(e)}")

# ================= HISTORIAL =================
st.divider()
st.subheader("📂 Historial de avances")

avances = (
    obra_ref.collection("avances")
    .order_by("timestamp", direction=firestore.Query.DESCENDING)
    .stream()
)

hay = False

for av in avances:
    hay = True
    d = av.to_dict()
    ts = d.get("timestamp").astimezone(tz)

    with st.expander(f"📅 {ts:%d/%m/%Y %H:%M} | {d.get('responsable')}"):
        st.write(f"**Descripción:** {d.get('descripcion')}")

        mats = d.get("materiales_usados", [])
        if mats:
            df = pd.DataFrame(mats)
            st.table(df[["nombre", "cantidad", "unidad"]])

        fotos = d.get("fotos", [])
        if fotos:
            cols = st.columns(3)
            for i, url in enumerate(fotos):
                cols[i % 3].image(url, use_container_width=True)

if not hay:
    st.info("Aún no hay avances registrados.")
