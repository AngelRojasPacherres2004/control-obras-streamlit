import streamlit as st
import pandas as pd
from datetime import datetime, date
import cloudinary
import cloudinary.uploader
import firebase_admin
from firebase_admin import credentials, firestore

# ================= 1. CONFIGURACIÓN DE NUBE =================
if not firebase_admin._apps:
    firebase_admin.initialize_app(
        credentials.Certificate(dict(st.secrets["firebase"]))
    )
db = firestore.client()

# Configuración de Cloudinary (ACTIVA)
cloudinary.config(
    cloud_name=st.secrets["cloudinary"]["cloud_name"],
    api_key=st.secrets["cloudinary"]["api_key"],
    api_secret=st.secrets["cloudinary"]["api_secret"],
    secure=True
)

st.set_page_config(page_title="Arq. Supervisor 2025", layout="wide")

# ================= 2. FUNCIONES DE DATOS =================
def obtener_obras():
    docs = db.collection("obras").stream()
    return {d.id: d.to_dict().get("nombre", d.id) for d in docs}

def cargar_avances(obra_id):
    docs = db.collection("obras").document(obra_id).collection("avances")\
             .order_by("fecha", direction=firestore.Query.DESCENDING).stream()
    return [d.to_dict() for d in docs]

def obtener_materiales():
    docs = db.collection("materiales").stream()
    return [{"id": d.id, **d.to_dict()} for d in docs]

def cargar_materiales_obra(obra_id):
    docs = db.collection("obras").document(obra_id).collection("materiales")\
             .order_by("fecha", direction=firestore.Query.DESCENDING).stream()
    return [d.to_dict() for d in docs]

# ================= 3. SISTEMA DE LOGIN =================
def login():
    if "auth" not in st.session_state:
        st.title("🏗️ CONTROL DE OBRAS 2025")
        col1, _ = st.columns([1, 1])
        with col1:
            user = st.text_input("Usuario")
            pw = st.text_input("Contraseña", type="password")
            if st.button("INGRESAR", use_container_width=True):
                u_doc = db.collection("users").document(user).get()
                if u_doc.exists and u_doc.to_dict().get("password") == pw:
                    st.session_state["auth"] = u_doc.to_dict()
                    st.rerun()
                else:
                    st.error("Credenciales incorrectas")
        return False
    return True

if not login():
    st.stop()

auth = st.session_state["auth"]

# ================= 4. NAVEGACIÓN Y SELECCIÓN =================
st.sidebar.title(f"Bienvenido, {auth['username']}")
menu = st.sidebar.radio("MENÚ", ["Obras", "Materiales", "Configuración"])

OBRAS = obtener_obras()
if auth["role"] == "jefe":
    obra_id_sel = st.sidebar.selectbox("Obra Actual", options=list(OBRAS.keys()), format_func=lambda x: OBRAS[x])
else:
    obra_id_sel = auth["obra"]
    st.sidebar.success(f"Obra: {OBRAS[obra_id_sel]}")

st.markdown(f"# 🏗️ {OBRAS[obra_id_sel]}")
st.divider()

# ================= 5. LÓGICA DE PÁGINAS =================

if menu == "Obras":
    tab1, tab2 = st.tabs(["📋 Parte Diario", "History Historial"])

    with tab1:
        if auth["role"] in ["jefe", "pasante"]:
            with st.form("parte_diario"):
                st.subheader("Registrar Avance")
                resp = st.text_input("Responsable", value=auth["username"])
                obs = st.text_area("Observaciones")
                fotos = st.file_uploader("Fotos (Mín. 3)", accept_multiple_files=True, type=['jpg','png','jpeg'])
                if st.form_submit_button("GUARDAR REPORTE"):
                    if len(fotos) < 3: st.error("Subir mínimo 3 fotos")
                    else:
                        with st.spinner("Subiendo fotos..."):
                            urls = [cloudinary.uploader.upload(f, folder=f"obras/{obra_id_sel}")["secure_url"] for f in fotos]
                            db.collection("obras").document(obra_id_sel).collection("avances").add({
                                "fecha": datetime.now().isoformat(),
                                "responsable": resp,
                                "observaciones": obs,
                                "fotos": urls
                            })
                            st.success("Reporte Guardado"); st.rerun()

    with tab2:
        avances = cargar_avances(obra_id_sel)
        for av in avances:
            fecha_f = datetime.fromisoformat(av["fecha"]).strftime("%d/%m/%Y %H:%M")
            with st.expander(f"📅 {fecha_f} - {av['responsable']}"):
                st.write(av["observaciones"])
                cols = st.columns(3)
                for i, img in enumerate(av.get("fotos", [])):
                    cols[i%3].image(img, use_container_width=True)

elif menu == "Materiales":
    if auth["role"] == "jefe":
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("📦 Catálogo Maestro")
            with st.form("nuevo_mat"):
                n = st.text_input("Nombre Material")
                u = st.text_input("Unidad")
                p = st.number_input("Precio Unitario", min_value=0.0)
                if st.form_submit_button("Añadir al Catálogo"):
                    db.collection("materiales").add({"nombre": n, "unidad": u, "precio_unitario": p})
                    st.rerun()
        
        with col2:
            st.subheader("➕ Asignar a Obra")
            mats = obtener_materiales()
            if mats:
                with st.form("asig_mat"):
                    m_sel = st.selectbox("Material", mats, format_func=lambda x: f"{x['nombre']} ({x['unidad']})")
                    c = st.number_input("Cantidad", min_value=1.0)
                    if st.form_submit_button("Asignar a esta Obra"):
                        db.collection("obras").document(obra_id_sel).collection("materiales").add({
                            **m_sel, "cantidad": c, "fecha": datetime.now().isoformat()
                        })
                        st.success("Asignado"); st.rerun()

    st.subheader("📊 Inventario en esta Obra")
    mats_obra = cargar_materiales_obra(obra_id_sel)
    if mats_obra:
        df = pd.DataFrame(mats_obra)
        st.dataframe(df[["nombre", "cantidad", "unidad", "precio_unitario", "fecha"]], use_container_width=True)

elif menu == "Configuración" and auth["role"] == "jefe":
    st.subheader("🛠️ Administración de Obras")
    with st.expander("➕ Crear Nueva Obra"):
        with st.form("nueva_obra"):
            nom = st.text_input("Nombre de Obra")
            ubi = st.text_input("Ubicación")
            est = st.selectbox("Estado", ["activo", "en espera", "pausado"])
            f_i = st.date_input("Inicio")
            f_e = st.date_input("Fin Estimado")
            if st.form_submit_button("CREAR OBRA"):
                db.collection("obras").document(nom.lower().replace(" ","_")).set({
                    "nombre": nom, "ubicacion": ubi, "estado": est,
                    "fecha_inicio": f_i.isoformat(), "fecha_fin_estimada": f_e.isoformat(),
                    "fecha_fin_real": None, "creada": datetime.now()
                })
                st.success("Obra creada"); st.rerun()

if st.sidebar.button("Cerrar Sesión"):
    del st.session_state["auth"]
    st.rerun()