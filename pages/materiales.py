import streamlit as st
import pandas as pd
from datetime import datetime
from firebase_admin import firestore

st.set_page_config(page_title="Materiales", layout="wide")

st.title("👷 CRUD de Materiales")
st.info("Aquí se administran los materiales generales del sistema")

db = firestore.client()

auth = st.session_state["auth"]

# ================= FUNCIONES =================
def obtener_materiales():
    docs = db.collection("materiales").stream()
    data = []
    for d in docs:
        doc = d.to_dict()
        data.append({
            "id": d.id,
            "nombre": doc.get("nombre"),
            "unidad": doc.get("unidad"),
            "precio_unitario": doc.get("precio_unitario", 0.0)
        })
    return data

# ================= ADMIN =================
if auth["role"] != "jefe":
    st.warning("No tienes permisos para administrar materiales")
    st.stop()

st.header("🧱 Gestión de Materiales")

# ---------- CREAR MATERIAL ----------
with st.form("crear_material"):
    nombre = st.text_input("Nombre del material")
    unidad = st.text_input("Unidad (kg, m3, bolsa, etc)")
    precio = st.number_input(
        "Precio unitario",
        min_value=0.0,
        step=0.1
    )
    crear = st.form_submit_button("CREAR MATERIAL")

if crear:
    if not nombre or not unidad:
        st.error("Nombre y unidad son obligatorios")
    else:
        db.collection("materiales").add({
            "nombre": nombre,
            "unidad": unidad,
            "precio_unitario": precio,
            "creado": datetime.now()
        })
        st.success("Material creado correctamente")
        st.rerun()

# ---------- LISTA DE MATERIALES ----------
st.subheader("📋 Materiales registrados")
materiales = obtener_materiales()

if materiales:
    df = pd.DataFrame(materiales)
    st.dataframe(
        df[["nombre", "unidad", "precio_unitario"]],
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("No hay materiales registrados")

# ---------- EDITAR / ELIMINAR ----------
st.subheader("✏️ Editar / 🗑️ Eliminar material")

if not materiales:
    st.info("No hay materiales para editar")
else:
    mat_sel = st.selectbox(
        "Selecciona un material",
        options=materiales,
        format_func=lambda x: f"{x['nombre']} ({x['unidad']})"
    )

    with st.form("editar_material"):
        nombre_e = st.text_input("Nombre", value=mat_sel["nombre"])
        unidad_e = st.text_input("Unidad", value=mat_sel["unidad"])
        precio_e = st.number_input(
            "Precio unitario",
            min_value=0.0,
            step=0.1,
            value=float(mat_sel["precio_unitario"])
        )

        col1, col2 = st.columns(2)
        guardar = col1.form_submit_button("💾 Guardar cambios")
        borrar = col2.form_submit_button("🗑️ Eliminar material")

    if guardar:
        db.collection("materiales").document(mat_sel["id"]).update({
            "nombre": nombre_e,
            "unidad": unidad_e,
            "precio_unitario": precio_e
        })
        st.success("Material actualizado")
        st.rerun()

    if borrar:
        db.collection("materiales").document(mat_sel["id"]).delete()
        st.warning("Material eliminado")
        st.rerun()
