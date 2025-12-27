import streamlit as st
import pandas as pd
from datetime import datetime
from firebase_admin import firestore

# ================= DB =================
db = firestore.client()

# ================= SEGURIDAD =================
if "auth" not in st.session_state:
    st.error("Inicia sesión"); st.stop()

auth = st.session_state["auth"]
if auth["role"] != "jefe":
    st.warning("Sin permisos"); st.stop()

# ================= ESTADO =================
st.session_state.setdefault("mat_edit", None)
st.session_state.setdefault("mat_obra_edit", None)

# ================= FUNCIONES =================
def cargar_materiales():
    docs = db.collection("materiales").order_by("nombre").stream()
    return [{"id": d.id, **d.to_dict()} for d in docs]

def obtener_obras():
    return {d.id: d.to_dict()["nombre"] for d in db.collection("obras").stream()}

def cargar_materiales_obra(obra_id):
    docs = (
        db.collection("obras")
        .document(obra_id)
        .collection("materiales")
        .order_by("fecha", direction=firestore.Query.DESCENDING)
        .stream()
    )
    return [{"id": d.id, **d.to_dict()} for d in docs]

def limpiar():
    st.session_state.mat_edit = None
    st.session_state.mat_obra_edit = None
    st.rerun()

# ================= UI =================
st.title("🧱 Gestión de Materiales por Obra")

# ================= SELECCIÓN OBRA =================
OBRAS = obtener_obras()
obra_sel = st.sidebar.selectbox(
    "Seleccionar obra",
    options=list(OBRAS.keys()),
    format_func=lambda x: OBRAS[x]
)

# ================= DATOS =================
materiales = cargar_materiales()
df = pd.DataFrame(materiales)

col_izq, col_der = st.columns([1.4, 1], gap="medium")

# ================= CATÁLOGO =================
with col_izq:
    st.subheader("📦 Catálogo de materiales")

    q = st.text_input("Buscar material")
    df_v = df.copy()

    if q and not df_v.empty:
        df_v = df_v[df_v["nombre"].str.contains(q, case=False, na=False)]

    if not df_v.empty:
        sel = st.dataframe(
            df_v[["nombre", "unidad", "precio_unitario"]],
            hide_index=True,
            use_container_width=True,
            selection_mode="single-row",
            on_select="rerun"
        )

        if sel and sel["selection"]["rows"]:
            idx = sel["selection"]["rows"][0]
            st.session_state.mat_edit = materiales[df_v.index[idx]]
    else:
        st.info("Sin materiales")

# ================= CRUD MATERIAL =================
with col_der:
    mat = st.session_state.mat_edit
    st.subheader("📝 " + ("Editar material" if mat else "Nuevo material"))

    with st.container(border=True):
        nombre = st.text_input("Nombre", value=mat["nombre"] if mat else "")
        unidad = st.text_input("Unidad", value=mat["unidad"] if mat else "")
        precio = st.number_input(
            "Precio unitario",
            min_value=0.0,
            step=0.01,
            value=float(mat["precio_unitario"]) if mat else 0.0
        )

        st.divider()

        if mat:
            c1, c2 = st.columns(2)
            if c1.button("Actualizar", type="primary", use_container_width=True):
                db.collection("materiales").document(mat["id"]).update({
                    "nombre": nombre,
                    "unidad": unidad,
                    "precio_unitario": precio
                })
                limpiar()

            if c2.button("Eliminar", use_container_width=True):
                db.collection("materiales").document(mat["id"]).delete()
                limpiar()

            st.divider()
            st.subheader("➕ Asignar a esta obra")

            cantidad = st.number_input("Cantidad", min_value=0.0, step=1.0)

            if st.button("Asignar material"):
                if cantidad > 0:
                    db.collection("obras").document(obra_sel)\
                        .collection("materiales").add({
                            "material_id": mat["id"],
                            "nombre": mat["nombre"],
                            "unidad": mat["unidad"],
                            "cantidad": cantidad,
                            "precio_unitario": mat["precio_unitario"],
                            "fecha": datetime.now().isoformat()
                        })
                    st.success("Material asignado")
                    st.rerun()

            if st.button("Cancelar"):
                limpiar()
        else:
            if st.button("Crear material", type="primary", use_container_width=True):
                if nombre and unidad:
                    db.collection("materiales").add({
                        "nombre": nombre,
                        "unidad": unidad,
                        "precio_unitario": precio,
                        "creado": datetime.now()
                    })
                    st.rerun()
                else:
                    st.error("Campos obligatorios")

# ================= MATERIALES DE LA OBRA =================
st.divider()
st.subheader("🧾 Materiales de la obra")

mats_obra = cargar_materiales_obra(obra_sel)

if mats_obra:
    df_obra = pd.DataFrame(mats_obra)

    sel_obra = st.dataframe(
        df_obra[["nombre", "unidad", "cantidad", "precio_unitario", "fecha"]],
        hide_index=True,
        use_container_width=True,
        selection_mode="single-row",
        on_select="rerun"
    )

    if sel_obra and sel_obra["selection"]["rows"]:
        idx = sel_obra["selection"]["rows"][0]
        st.session_state.mat_obra_edit = mats_obra[idx]
else:
    st.info("Esta obra no tiene materiales")

# ================= EDITAR MATERIAL EN OBRA =================
mat_obra = st.session_state.mat_obra_edit

if mat_obra:
    st.subheader("✏️ Editar material asignado")

    with st.container(border=True):
        nueva_cantidad = st.number_input(
            "Cantidad",
            min_value=0.0,
            step=1.0,
            value=float(mat_obra["cantidad"])
        )

        c1, c2 = st.columns(2)

        if c1.button("Actualizar cantidad", type="primary", use_container_width=True):
            db.collection("obras").document(obra_sel)\
                .collection("materiales").document(mat_obra["id"])\
                .update({
                    "cantidad": nueva_cantidad,
                    "fecha": datetime.now().isoformat()
                })
            limpiar()

        if c2.button("Eliminar de la obra", use_container_width=True):
            db.collection("obras").document(obra_sel)\
                .collection("materiales").document(mat_obra["id"])\
                .delete()
            limpiar()

# ================= CSS =================
st.markdown("""
<style>
.stDataFrame { border-radius: 8px; }
</style>
""", unsafe_allow_html=True)
