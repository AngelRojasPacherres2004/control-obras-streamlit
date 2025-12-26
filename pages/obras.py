import streamlit as st
import pandas as pd
from datetime import datetime, date
import cloudinary
import cloudinary.uploader
import firebase_admin
from firebase_admin import credentials, firestore




st.set_page_config(page_title="Obras", layout="wide")

st.title("👷 CRUD de Obras")

st.info("Aquí se administrarán las obras")

db = firestore.client()

# ================= FUNCIONES =================
def obtener_obras():
    return {d.id: d.to_dict()["nombre"] for d in db.collection("obras").stream()}

def cargar_avances(obra_id):
    docs = (
        db.collection("obras")
        .document(obra_id)
        .collection("avances")
        .order_by("fecha", direction=firestore.Query.DESCENDING)
        .stream()
    )
    return [d.to_dict() for d in docs]
    
def obtener_materiales():
    docs = db.collection("materiales").stream()
    return [{
        "id": d.id,
        "nombre": d.to_dict()["nombre"],
        "unidad": d.to_dict()["unidad"],
        "precio_unitario": d.to_dict()["precio_unitario"]
    } for d in docs]

def cargar_materiales_obra(obra_id):
    docs = db.collection("obras").document(obra_id)\
        .collection("materiales")\
        .order_by("fecha", direction=firestore.Query.DESCENDING)\
        .stream()
    return [d.to_dict() for d in docs]

# ================= SELECCIÓN DE OBRA =================
auth = st.session_state["auth"]
OBRAS = obtener_obras()

if auth["role"] == "jefe":
    obra_id_sel = st.sidebar.selectbox(
        "Seleccionar obra",
        options=list(OBRAS.keys()),
        format_func=lambda x: OBRAS[x]
    )
else:
    obra_id_sel = auth["obra"]
    st.sidebar.success(f"Obra asignada: {OBRAS[obra_id_sel]}")

# ================= ADMIN: GESTIONAR OBRAS =================
if auth["role"] == "jefe":
    st.header(" Gestión de Obras")
    mats = obtener_materiales()

    # ---- ASIGNAR MATERIAL A OBRA ----
    st.subheader(" Asignar material a esta obra")

    if mats:
        with st.form("asignar_material"):
            mat = st.selectbox(
                "Material",
                options=mats,
                format_func=lambda x: f"{x['nombre']} ({x['unidad']})"
            )
            cant = st.number_input("Cantidad", min_value=0.0, step=1.0)
            asignar = st.form_submit_button("ASIGNAR")

        if asignar and cant > 0:
            db.collection("obras").document(obra_id_sel)\
                .collection("materiales").add({
                    "material_id": mat["id"],
                    "nombre": mat["nombre"],
                    "unidad": mat["unidad"],
                    "cantidad": cant,
                    "precio_unitario": mat["precio_unitario"],
                    "fecha": datetime.now().isoformat()
                })
            st.success("Material asignado a la obra")
            st.rerun()

    # ---- LISTA MATERIALES DE LA OBRA ----
    st.subheader("Materiales en esta obra")
    mats_obra = cargar_materiales_obra(obra_id_sel)

    if mats_obra:
        st.dataframe(
            pd.DataFrame(mats_obra)[["nombre", "unidad", "cantidad", "precio_unitario", "fecha"]],
            use_container_width=True
        )
    else:
        st.info("Esta obra aún no tiene materiales asignados")