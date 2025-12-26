
import streamlit as st
import pandas as pd
from datetime import datetime, date
import cloudinary
import cloudinary.uploader
import firebase_admin
from firebase_admin import credentials, firestore

st.set_page_config(page_title="Materiales", layout="wide")

st.title("👷 CRUD de Materiales")

st.info("Aquí se administrarán los materiales")


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

# ================= ADMIN: GESTIÓN DE MATERIALES =================
if auth["role"] == "jefe":
    st.header(" Gestión de Materiales")

    # ---- CREAR MATERIAL ----
    with st.form("crear_material"):
        nom = st.text_input("Nombre del material")
        uni = st.text_input("Unidad (kg, m3, bolsa, etc)")
        precio = st.number_input(
        "Precio unitario",
        min_value=0.0,
        step=0.1
        )
        crear_mat = st.form_submit_button("CREAR MATERIAL")

    if crear_mat:
        if not nom or not uni:
            st.error("Nombre y unidad obligatorios")
        else:
            db.collection("materiales").add({
                "nombre": nom,
                "unidad": uni,
                "precio_unitario": precio,
                "creado": datetime.now()
            })
            st.success("Material creado")
            st.rerun()

    # ---- LISTA MATERIALES GENERALES ----
    st.subheader(" Materiales registrados")
    mats = obtener_materiales()

    if "precio_unitario" not in pd.DataFrame(mats).columns:
        pd.DataFrame(mats)["precio_unitario"] = 0.0
    else:
        pd.DataFrame(mats)["precio_unitario"] = pd.DataFrame(mats)["precio_unitario"].fillna(0.0)

    if mats:
        st.dataframe(
            pd.DataFrame(mats)[["nombre", "unidad", "precio_unitario"]],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No hay materiales creados")

    # ---- ACTUALIZAR MATERIALES ----
    st.subheader("✏️ Editar / 🗑️ Eliminar material")

    if not mats:
        st.info("No hay materiales para editar")
    else:
        mat_sel = st.selectbox(
            "Selecciona un material",
            options=mats,
            format_func=lambda x: f"{x['nombre']} ({x['unidad']})"
        )

    with st.form("editar_material"):
        nom_e = st.text_input("Nombre", value=mat_sel["nombre"])
        uni_e = st.text_input("Unidad", value=mat_sel["unidad"])
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
            "nombre": nom_e,
            "unidad": uni_e,
            "precio_unitario": precio_e
        })
        st.success("Material actualizado")
        st.rerun()
    
    if borrar:
        st.warning("Material eliminado")
        db.collection("materiales").document(mat_sel["id"]).delete()
        st.rerun()

        
