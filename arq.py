# arq.py
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import cloudinary
from cookies_manager import cookies
from auth import mostrar_pantalla_inicial, verificar_autenticacion
import uuid

# ================= INIT =================
if not firebase_admin._apps:
    firebase_admin.initialize_app(
        credentials.Certificate(dict(st.secrets["firebase"]))
    )

db = firestore.client()

cloudinary.config(
    cloud_name=st.secrets["cloudinary"]["cloud_name"],
    api_key=st.secrets["cloudinary"]["api_key"],
    api_secret=st.secrets["cloudinary"]["api_secret"],
    secure=True
)

st.set_page_config(page_title="Control de Obras", layout="centered")

# ================= COOKIES =================
if not cookies.ready():
    st.stop()

# cada navegador tiene su propio browser_id
if "browser_id" not in cookies:
    cookies["browser_id"] = str(uuid.uuid4())
    cookies.save()

browser_id = cookies["browser_id"]

# ================= RESTAURAR SESIÓN =================
if "auth" not in st.session_state and browser_id:
    # Buscar sesión de este navegador
    query = db.collection("sessions").where("browser_id", "==", browser_id).limit(1).stream()
    for session in query:
        data = session.to_dict()
        st.session_state["auth"] = {
            "username": data["username"],
            "role": data["role"],
            "obra": data.get("obra"),
            "session_id": session.id
        }
        break  # restauramos solo la primera sesión encontrada

# ================= ESTADO =================
if "show_login" not in st.session_state:
    st.session_state.show_login = False

# ================= FLUJO VISUAL =================
if not st.session_state.get("show_login", False) and "auth" not in st.session_state:
    mostrar_pantalla_inicial()
    st.stop()

if "auth" not in st.session_state:
    verificar_autenticacion(db)
    st.stop()

# ================= NAVEGACIÓN =================
auth = st.session_state["auth"]

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
        # eliminar sesión de Firestore
        if "session_id" in st.session_state["auth"]:
            db.collection("sessions").document(st.session_state["auth"]["session_id"]).delete()

        # eliminar cookie
        if cookies.get("browser_id"):
            del cookies["browser_id"]
            cookies.save()

        # limpiar session_state
        st.session_state.clear()
        st.session_state["show_login"] = False

        # volver al login
        st.rerun()

# ================= EJECUTAR PÁGINA =================
pg.run()
