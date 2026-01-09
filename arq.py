import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import cloudinary
from cookies_manager import cookies
from auth import mostrar_pantalla_inicial, verificar_autenticacion
import uuid

# ================= CONFIG BÁSICA =================
st.set_page_config(page_title="Control de Obras", layout="centered")

# ================= FIREBASE INIT =================
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

# ================= COOKIES READY =================
if not cookies.ready():
    st.stop()

# ================= BROWSER ID ÚNICO =================
if "browser_id" not in cookies:
    cookies["browser_id"] = str(uuid.uuid4())
    cookies.save()

browser_id = cookies["browser_id"]

# ================= RESTAURAR SESIÓN DESDE COOKIE =================
if "auth" not in st.session_state and cookies.get("session_id"):

    session_id = cookies.get("session_id")
    session_doc = db.collection("sessions").document(session_id).get()

    if session_doc.exists:
        data = session_doc.to_dict()

        # validar que la sesión sea del mismo navegador
        if data.get("browser_id") == browser_id:
            st.session_state["auth"] = {
                "username": data["username"],
                "role": data["role"],
                "obra": data.get("obra"),
                "session_id": session_id
            }
        else:
            # sesión NO válida → borrar cookie
            del cookies["session_id"]
            cookies.save()
    else:
        # sesión ya no existe → borrar cookie
        del cookies["session_id"]
        cookies.save()

# ================= ESTADO VISUAL =================
if "show_login" not in st.session_state:
    st.session_state.show_login = False

# ================= FLUJO DE LOGIN =================

# 1️⃣ Pantalla inicial
if "auth" not in st.session_state and not st.session_state.show_login:
    mostrar_pantalla_inicial()
    st.stop()

# 2️⃣ Login
if "auth" not in st.session_state:
    verificar_autenticacion(db)
    st.stop()

# ================= USUARIO AUTENTICADO =================
auth = st.session_state["auth"]

# ================= NAVEGACIÓN =================
usuarios_page   = st.Page("pages/usuarios.py", title="Usuarios", icon=":material/group:")
materiales_page = st.Page("pages/materiales.py", title="Materiales", icon=":material/inventory:")
obras_page      = st.Page("pages/obras.py", title="Obras", icon=":material/construction:")
avances_page    = st.Page("pages/avances_pasante.py", title="Parte Diario", icon=":material/edit_note:")

if auth["role"] == "jefe":
    pg = st.navigation([obras_page, materiales_page, usuarios_page])
else:
    pg = st.navigation([avances_page])

# ================= CERRAR SESIÓN =================
with st.sidebar:
    st.divider()
    if st.button("🚪 Cerrar sesión", use_container_width=True):

        # eliminar sesión en Firestore
        if cookies.get("session_id"):
            db.collection("sessions").document(cookies["session_id"]).delete()
            del cookies["session_id"]

        cookies.save()

        # limpiar sesión local
        st.session_state.clear()
        st.rerun()

# ================= EJECUTAR APP =================
pg.run()
