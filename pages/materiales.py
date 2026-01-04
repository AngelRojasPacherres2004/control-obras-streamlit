import streamlit as st
import pandas as pd
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore

# ================= CONEXIÓN SEGURA =================
def get_db():
    if not firebase_admin._apps:
        cred = credentials.Certificate(dict(st.secrets["firebase"]))
        firebase_admin.initialize_app(cred)
    return firestore.client()

db = get_db()

# ================= DB =================
db = firestore.client()

# ================= SEGURIDAD =================
if "auth" not in st.session_state:
    st.error("Inicia sesión"); st.stop()

if st.session_state["auth"]["role"] != "jefe":
    st.warning("Sin permisos"); st.stop()

# ================= ESTADO =================
st.session_state.setdefault("mat_global", None)
st.session_state.setdefault("mat_obra", None)

# ================= FUNCIONES =================
def cargar_materiales():
    return [{"id": d.id, **d.to_dict()}
            for d in db.collection("materiales").order_by("nombre").stream()]

def obtener_obras():
    return {d.id: d.to_dict()["nombre"]
            for d in db.collection("obras").stream()}

def cargar_materiales_obra(obra_id):
    return [{"id": d.id, **d.to_dict()}
            for d in db.collection("obras")
            .document(obra_id)
            .collection("materiales")
            .order_by("fecha", direction=firestore.Query.DESCENDING)
            .stream()]

def reset():
    st.session_state.mat_global = None
    st.session_state.mat_obra = None
    st.rerun()

# ================= UI =================
st.title("🧱 Materiales")

# -------- SELECCIÓN DE OBRA --------
OBRAS = obtener_obras()
obra_id = st.sidebar.selectbox(
    "Seleccionar obra",
    options=list(OBRAS.keys()),
    format_func=lambda x: OBRAS[x]
)

# ================== SECCIÓN A ==================
st.header("📦 Materiales globales")

materiales = cargar_materiales()
df_mat = pd.DataFrame(materiales)

col1, col2 = st.columns([1.5, 1])

# ----- LISTA -----
with col1:
    busq = st.text_input("Buscar material")
    df_v = df_mat if not busq else df_mat[df_mat["nombre"].str.contains(busq, case=False)]

    if not df_v.empty:
        sel = st.dataframe(
            df_v[["nombre", "unidad", "precio_unitario"]],
            hide_index=True,
            use_container_width=True,
            selection_mode="single-row",
            on_select="rerun"
        )
        if sel and sel["selection"]["rows"]:
            st.session_state.mat_global = materiales[df_v.index[sel["selection"]["rows"][0]]]
    else:
        st.info("No hay materiales")

# ----- FORM CRUD -----
with col2:
    mat = st.session_state.mat_global
    st.subheader("✏️ Editar" if mat else "➕ Nuevo")

    nombre = st.text_input("Nombre", value=mat["nombre"] if mat else "")
    unidad = st.text_input("Unidad", value=mat["unidad"] if mat else "")
    precio = st.number_input("Precio", 0.0, step=0.01,
                             value=float(mat["precio_unitario"]) if mat else 0.0)

    if mat:
        if st.button("Actualizar", type="primary", use_container_width=True):
            db.collection("materiales").document(mat["id"]).update({
                "nombre": nombre, "unidad": unidad, "precio_unitario": precio
            })
            reset()

        if st.button("Eliminar", use_container_width=True):
            db.collection("materiales").document(mat["id"]).delete()
            reset()
    else:
        if st.button("Crear material", type="primary", use_container_width=True):
            if nombre and unidad:
                db.collection("materiales").add({
                    "nombre": nombre,
                    "unidad": unidad,
                    "precio_unitario": precio,
                    "creado": datetime.now()
                })
                reset()
            else:
                st.error("Campos obligatorios")

# ================== SECCIÓN B ==================
st.divider()
st.header("➕ Asignar material a la obra")

if materiales:
    mat_sel = st.selectbox(
        "Material",
        options=materiales,
        format_func=lambda x: f"{x['nombre']} ({x['unidad']})"
    )
    cantidad = st.number_input("Cantidad", min_value=1.0, step=1.0)

    if st.button("Asignar a obra", type="primary"):
        db.collection("obras").document(obra_id).collection("materiales").add({
            "material_id": mat_sel["id"],
            "nombre": mat_sel["nombre"],
            "unidad": mat_sel["unidad"],
            "cantidad": cantidad,
            "precio_unitario": mat_sel["precio_unitario"],
            "subtotal": round(cantidad * mat_sel["precio_unitario"], 2),
            "fecha": datetime.now()
        })
        st.success("Material asignado")
        st.rerun()

# ================== SECCIÓN C ==================
st.divider()
st.header("🧾 Materiales de la obra")

mats_obra = cargar_materiales_obra(obra_id)

if mats_obra:
    df_obra = pd.DataFrame(mats_obra)
    sel = st.dataframe(
        df_obra[["nombre", "unidad", "cantidad", "precio_unitario", "subtotal"]],
        hide_index=True,
        use_container_width=True,
        selection_mode="single-row",
        on_select="rerun"
    )
    if sel and sel["selection"]["rows"]:
        st.session_state.mat_obra = mats_obra[sel["selection"]["rows"][0]]
else:
    st.info("No hay materiales asignados")

# ----- EDITAR MATERIAL OBRA -----
mat_o = st.session_state.mat_obra
if mat_o:
    st.subheader("✏️ Editar material en obra")
    nueva = st.number_input("Cantidad", min_value=1.0,
                            value=float(mat_o["cantidad"]))

    if st.button("Actualizar cantidad", type="primary"):
        db.collection("obras").document(obra_id)\
            .collection("materiales").document(mat_o["id"]).update({
                "cantidad": nueva,
                "subtotal": round(nueva * mat_o["precio_unitario"], 2),
                "fecha": datetime.now()
            })
        reset()

    if st.button("Eliminar de la obra"):
        db.collection("obras").document(obra_id)\
            .collection("materiales").document(mat_o["id"]).delete()
        reset()
