import streamlit as st
import pandas as pd
from datetime import datetime
from firebase_admin import firestore

# ================= DB =================
db = firestore.client()

# ================= SEGURIDAD =================
if "auth" not in st.session_state:
    st.error("Inicia sesión")
    st.stop()

if st.session_state["auth"]["role"] != "jefe":
    st.warning("Sin permisos")
    st.stop()

# ================= ESTADO =================
st.session_state.setdefault("mat_global", None)
st.session_state.setdefault("mat_obra", None)

# ================= FUNCIONES =================
def cargar_materiales():
    return [{"id": d.id, **d.to_dict()}
            for d in db.collection("materiales").order_by("nombre").stream()]

def obtener_obras():
    return {d.id: d.to_dict().get("nombre", d.id)
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
st.title("🧱 Materiales y Presupuesto")

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
    precio = st.number_input(
        "Precio unitario",
        0.0,
        step=0.01,
        value=float(mat["precio_unitario"]) if mat else 0.0
    )

    if mat:
        if st.button("Actualizar", type="primary", use_container_width=True):
            db.collection("materiales").document(mat["id"]).update({
                "nombre": nombre,
                "unidad": unidad,
                "precio_unitario": precio
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
    nueva = st.number_input(
        "Cantidad",
        min_value=1.0,
        value=float(mat_o["cantidad"])
    )

    if st.button("Actualizar cantidad", type="primary"):
        db.collection("obras").document(obra_id) \
            .collection("materiales").document(mat_o["id"]).update({
                "cantidad": nueva,
                "subtotal": round(nueva * mat_o["precio_unitario"], 2),
                "fecha": datetime.now()
            })
        reset()

    if st.button("Eliminar de la obra"):
        db.collection("obras").document(obra_id) \
            .collection("materiales").document(mat_o["id"]).delete()
        reset()

# ================== SECCIÓN D ==================
st.divider()
st.header("📥 Importar materiales desde Excel")

archivo = st.file_uploader("Subir Excel", type=["xlsx", "xls"])

if archivo:
    df_excel = pd.read_excel(archivo)

    columnas = {"nombre", "unidad", "cantidad", "precio_unitario"}
    if not columnas.issubset(df_excel.columns):
        st.error("El Excel debe tener: nombre, unidad, cantidad, precio_unitario")
    else:
        df_excel["subtotal"] = df_excel["cantidad"] * df_excel["precio_unitario"]
        st.dataframe(df_excel, use_container_width=True)

        if st.button("Importar materiales a la obra", type="primary"):
            for _, r in df_excel.iterrows():
                db.collection("obras").document(obra_id).collection("materiales").add({
                    "nombre": r["nombre"],
                    "unidad": r["unidad"],
                    "cantidad": float(r["cantidad"]),
                    "precio_unitario": float(r["precio_unitario"]),
                    "subtotal": round(float(r["subtotal"]), 2),
                    "fecha": datetime.now()
                })
            st.success("Materiales importados correctamente")
            st.rerun()

# ================== SECCIÓN E ==================
st.divider()
st.header("💰 Presupuesto total de la obra")

total_obra = sum(float(m.get("subtotal", 0)) for m in mats_obra)
st.metric("Presupuesto calculado", f"S/ {total_obra:,.2f}")

if st.button("Asignar presupuesto total a la obra", type="primary"):
    db.collection("obras").document(obra_id).update({
        "presupuesto_total": round(total_obra, 2),
        "presupuesto_actualizado": datetime.now()
    })
    st.success("Presupuesto total asignado")
    # ================== SECCIÓN X ==================
st.divider()
st.header("📤 Exportar materiales de la obra a Excel")

if mats_obra:
    df_export = pd.DataFrame(mats_obra)

    # Nos quedamos solo con las columnas que quieres
    df_export = df_export[["nombre", "unidad", "precio_unitario"]]

    # Crear el archivo Excel en memoria
    from io import BytesIO
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df_export.to_excel(writer, index=False, sheet_name="Materiales")
    buffer.seek(0)

    st.download_button(
        label="📥 Descargar Excel",
        data=buffer,
        file_name=f"materiales_{obra_id}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.info("No hay materiales para exportar")
