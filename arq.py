import streamlit as st
import pandas as pd
from datetime import datetime, date
import cloudinary
import cloudinary.uploader
import firebase_admin
from firebase_admin import credentials, firestore

# ================= FIREBASE =================
if not firebase_admin._apps:
    firebase_admin.initialize_app(
        credentials.Certificate(dict(st.secrets["firebase"]))
    )

db = firestore.client()

# ================= CLOUDINARY =================
cloudinary.config(
    cloud_name=st.secrets["cloudinary"]["cloud_name"],
    api_key=st.secrets["cloudinary"]["api_key"],
    api_secret=st.secrets["cloudinary"]["api_secret"],
    secure=True
)

# ================= STREAMLIT =================
st.set_page_config(page_title="Arq. Supervisor 2025", layout="wide")

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
        "unidad": d.to_dict()["unidad"]
    } for d in docs]

def cargar_materiales_obra(obra_id):
    docs = db.collection("obras").document(obra_id)\
        .collection("materiales")\
        .order_by("fecha", direction=firestore.Query.DESCENDING)\
        .stream()
    return [d.to_dict() for d in docs]

# ================= LOGIN CON FIREBASE =================
def check_password():
    if "auth" not in st.session_state:
        st.title("CONTROL DE OBRAS 2025")
        username = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")

        if st.button("INGRESAR"):
            user_doc = db.collection("users").document(username).get()

            if not user_doc.exists:
                st.error("Usuario no existe")
                return False

            data = user_doc.to_dict()

            if password != data.get("password"):
                st.error("Contraseña incorrecta")
                return False

            # 🔐 Login correcto
            st.session_state["auth"] = {
                "username": data["username"],
                "role": data["role"],
                "obra": data.get("obra")
            }
            st.rerun()

        return False
    return True

if not check_password():
    st.stop()

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


# ================= ADMIN: CREAR OBRA =================
if auth["role"] == "jefe":
    with st.sidebar.expander("➕ Crear Obra"):
        with st.form("crear_obra"):
            nombre = st.text_input("Nombre")
            ubicacion = st.text_input("Ubicación")
            estado = st.selectbox(
                "Estado",
                ["en espera", "activo", "pausado", "finalizado"]
            )
            f_ini = st.date_input("Fecha inicio", value=date.today())
            f_fin = st.date_input("Fecha fin estimada")
            crear = st.form_submit_button("CREAR")

        if crear:
            obra_id = nombre.lower().replace(" ", "_")
            db.collection("obras").document(obra_id).set({
                "nombre": nombre,
                "ubicacion": ubicacion,
                "estado": estado,
                "fecha_inicio": f_ini.isoformat(),
                "fecha_fin_estimada": f_fin.isoformat(),
                "fecha_fin_real": None,
                "creada": datetime.now()
            })
            st.success("Obra creada correctamente")
            st.rerun()


# ================= TITULO =================
st.title(f"🏗️ {OBRAS[obra_id_sel]}")

# ================= ADMIN: GESTIÓN DE MATERIALES =================
if st.session_state["auth"] == "jefe":
    st.header("🧱 Gestión de Materiales")

    # ---- CREAR MATERIAL ----
    with st.form("crear_material"):
        nom = st.text_input("Nombre del material")
        uni = st.text_input("Unidad (kg, m3, bolsa, etc)")
        crear_mat = st.form_submit_button("CREAR MATERIAL")

    if crear_mat:
        if not nom or not uni:
            st.error("Nombre y unidad obligatorios")
        else:
            db.collection("materiales").add({
                "nombre": nom,
                "unidad": uni,
                "creado": datetime.now()
            })
            st.success("Material creado")
            st.rerun()

    # ---- LISTA MATERIALES GENERALES ----
    st.subheader("📋 Materiales registrados")
    mats = obtener_materiales()

    if mats:
        st.dataframe(
            pd.DataFrame(mats)[["nombre", "unidad"]],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No hay materiales creados")

    # ---- ASIGNAR MATERIAL A OBRA ----
    st.subheader("📦 Asignar material a esta obra")

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
                    "fecha": datetime.now().isoformat()
                })
            st.success("Material asignado a la obra")
            st.rerun()

    # ---- LISTA MATERIALES DE LA OBRA ----
    st.subheader("📦 Materiales en esta obra")
    mats_obra = cargar_materiales_obra(obra_id_sel)

    if mats_obra:
        st.dataframe(
            pd.DataFrame(mats_obra)[["nombre", "unidad", "cantidad", "fecha"]],
            use_container_width=True
        )
    else:
        st.info("Esta obra aún no tiene materiales asignados")


# ================= PASANTE: PARTE DIARIO =================
if auth["role"] == "pasante":
    st.header("📝 Parte Diario")

    with st.form("parte_diario"):
        responsable = st.text_input("Responsable")
        observaciones = st.text_area("Observaciones")
        fotos = st.file_uploader(
            "Subir fotos (mínimo 3)",
            accept_multiple_files=True
        )
        enviar = st.form_submit_button("GUARDAR AVANCE")

    if enviar:
        if not responsable or not observaciones:
            st.error("Responsable y observaciones son obligatorios")
        elif len(fotos) < 3:
            st.error("Debes subir mínimo 3 fotos")
        else:
            urls = []
            for f in fotos:
                res = cloudinary.uploader.upload(
                    f,
                    folder=f"obras/{obra_id_sel}"
                )
                urls.append(res["secure_url"])

            db.collection("obras")\
              .document(obra_id_sel)\
              .collection("avances")\
              .add({
                  "fecha": datetime.now().isoformat(),
                  "responsable": responsable,
                  "observaciones": observaciones,
                  "fotos": urls
              })

            st.success("Avance guardado correctamente")
            st.rerun()

# ================= HISTORIAL =================
st.header("📊 Historial de Avances")

for av in cargar_avances(obra_id_sel):
    f = datetime.fromisoformat(av["fecha"])
    with st.expander(f"📅 {f:%d/%m/%Y %H:%M} - {av.get('responsable','N/D')}"):
        st.write(av.get("observaciones", "Sin observaciones"))
        for img in av.get("fotos", []):
            st.image(img, use_container_width=True)
