import streamlit as st
import pandas as pd
from datetime import datetime
from firebase_admin import firestore
import cloudinary.uploader
import pytz

# ================= CONFIG =================
st.set_page_config(page_title="Avances por Sección", layout="wide")
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
usuario = auth.get("username", "pasante")

if not obra_id:
    st.error("No tienes obra asignada")
    st.stop()

obra_ref = db.collection("obras").document(obra_id)
obra = obra_ref.get().to_dict()

# ================= SIDEBAR =================
with st.sidebar:
    st.header("🏗️ Obra asignada")
    st.write(f"**Nombre:** {obra.get('nombre')}")
    st.write(f"**Estado:** {obra.get('estado')}")
    st.write(f"📅 Inicio: {obra.get('fecha_inicio').date()}")
    st.write(f"🏁 Fin estimado: {obra.get('fecha_fin_estimado').date()}")

# ================= ESTADO =================
st.session_state.setdefault("partida_abierta", None)

# =========================================================
# ================= LISTA DE SECCIONES =====================
# =========================================================
if st.session_state.partida_abierta is None:
    # =========================================================
    # 📦 RESUMEN DE MATERIALES (GASTADO VS DISPONIBLE)
    # =========================================================
    st.subheader("📦 Resumen de materiales")

    # ---- 1. Stock desde inventario de la obra ----
    materiales_obra = list(obra_ref.collection("materiales").stream())

    stock_materiales = {}
    unidad_materiales = {}

    for m in materiales_obra:
        d = m.to_dict()
        nombre = d.get("nombre")
        stock_materiales[nombre] = float(d.get("stock", 0))
        unidad_materiales[nombre] = d.get("unidad", "und")

    # ---- 2. Calcular lo gastado desde avances ----
    gastado_materiales = {}

    partidas = obra_ref.collection("partidas").stream()
    for p in partidas:
        avances = obra_ref.collection("partidas").document(p.id) \
            .collection("avances").stream()

        for av in avances:
            detalle = av.to_dict().get("detalle", [])
            for item in detalle:
                if item.get("Tipo") == "Material":
                    nombre = item.get("Descripción")
                    cantidad = float(item.get("Cantidad", 0))
                    gastado_materiales[nombre] = gastado_materiales.get(nombre, 0) + cantidad

    # ---- 3. Construir tabla resumen ----
    filas_resumen = []

    for nombre, stock in stock_materiales.items():
        gastado = gastado_materiales.get(nombre, 0)
        disponible = stock - gastado

        filas_resumen.append({
            "Material": nombre,
            "Unidad": unidad_materiales.get(nombre, "und"),
            "Gastado": round(gastado, 2),
            "Disponible": round(disponible, 2)
        })

    df_resumen = pd.DataFrame(filas_resumen)

    st.dataframe(
        df_resumen,
        use_container_width=True,
        hide_index=True
    )

    st.title("📋 Secciones de la Obra")

    partidas = list(
        obra_ref.collection("partidas")
        .order_by("codigo")
        .stream()
    )

    if not partidas:
        st.info("No hay secciones creadas")
        st.stop()

    # -------- SECCIONES --------
    for p in partidas:
        d = p.to_dict()

        col1, col2 = st.columns([5, 1])
        col1.markdown(f"""
### 🧱 {d.get('codigo')} - {d.get('nombre')}
{len(d.get('materiales', []))} materiales • {len(d.get('mano_obra', []))} trabajadores
""")

        if col2.button("📂 Abrir", key=p.id):
            st.session_state.partida_abierta = {"id": p.id, **d}
            st.rerun()

    # =====================================================
    # 📚 HISTORIAL DE AVANCES (AL FINAL)
    # =====================================================
    st.divider()
    st.title("📚 Historial de Avances")

    for p in partidas:
        avances = obra_ref.collection("partidas").document(p.id) \
            .collection("avances") \
            .order_by("fecha", direction=firestore.Query.DESCENDING) \
            .stream()

        avances = [a.to_dict() for a in avances]

        if avances:
            d = p.to_dict()
            st.subheader(f"🧱 {d.get('codigo')} - {d.get('nombre')}")

            for av in avances:
                fecha = av.get("fecha")
                fecha_txt = fecha.astimezone(tz).strftime("%d/%m/%Y %H:%M") if fecha else "N/D"

                with st.expander(f"📅 {fecha_txt} — {av.get('usuario')}"):
                    st.write(av.get("descripcion", ""))
                    if av.get("detalle"):
                        st.table(pd.DataFrame(av["detalle"]))

# =========================================================
# ================= VISTA DE AVANCE ========================
# =========================================================
else:
    partida = st.session_state.partida_abierta
    st.title(f"🧱 {partida['codigo']} - {partida['nombre']}")

    # =====================================================
    # 🔹 PRECIOS DE MATERIALES DESDE FIREBASE (OBRA)
    # =====================================================
    materiales_obra = obra_ref.collection("materiales").stream()
    precios_materiales = {
        m.to_dict().get("nombre"): float(m.to_dict().get("precio_unitario", 0))
        for m in materiales_obra
    }

    # =====================================================
    # 🔹 MANO DE OBRA
    # =====================================================
    st.subheader("👷 Mano de Obra")

    filas_mo = []
    for t in partida.get("mano_obra", []):
        filas_mo.append({
            "Tipo": "Mano de obra",
            "Descripción": t["nombre"],
            "Rendimiento": 0.0,
            "Precio": 0.0,
            "Cantidad": 0.0,
            "Parcial": 0.0
        })

    df_mo = pd.DataFrame(filas_mo)

    df_mo_edit = st.data_editor(
        df_mo,
        use_container_width=True,
        column_config={
            "Cantidad": st.column_config.NumberColumn(disabled=True)
        }
    )

    # =====================================================
    # 🔹 MATERIALES (SIN RENDIMIENTO)
    # =====================================================
    st.subheader("🧱 Materiales")

    filas_mat = []
    for m in partida.get("materiales", []):
        precio = precios_materiales.get(m["nombre"], 0.0)
        filas_mat.append({
            "Tipo": "Material",
            "Descripción": m["nombre"],
            "Cantidad": 0.0,
            "Precio": precio,
            "Parcial": 0.0
        })

    df_mat = pd.DataFrame(filas_mat)

    df_mat_edit = st.data_editor(
        df_mat,
        use_container_width=True,
        column_config={
            "Precio": st.column_config.NumberColumn(disabled=True)
        }
    )

    # =====================================================
    # 🔹 DESCRIPCIÓN Y FOTOS
    # =====================================================
    descripcion = st.text_area("📝 Descripción del trabajo realizado")

    fotos = st.file_uploader(
        "📸 Subir fotos del avance (mínimo 3)",
        accept_multiple_files=True,
        type=["jpg", "png", "jpeg"]
    )

    col1, col2 = st.columns(2)

    # =====================================================
    # 💾 GUARDAR
    # =====================================================
    if col1.button("💾 Guardar Avance", type="primary"):
        if not descripcion.strip():
            st.error("Falta descripción")
        elif not fotos or len(fotos) < 3:
            st.error("Mínimo 3 fotos")
        else:
            urls = []
            for f in fotos:
                res = cloudinary.uploader.upload(
                    f,
                    folder=f"obras/{obra_id}/avances"
                )
                urls.append(res["secure_url"])

            detalle = pd.concat([df_mo_edit, df_mat_edit]).to_dict("records")

            avance = {
                "fecha": datetime.now(tz),
                "usuario": usuario,
                "descripcion": descripcion,
                "detalle": detalle,
                "fotos": urls
            }

            obra_ref.collection("partidas") \
                .document(partida["id"]) \
                .collection("avances") \
                .add(avance)

            st.success("✅ Avance guardado correctamente")
            st.session_state.partida_abierta = None
            st.rerun()

    if col2.button("⬅️ Volver"):
        st.session_state.partida_abierta = None
        st.rerun()
