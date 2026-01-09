import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import cloudinary
from cookies_manager import cookies
from auth import mostrar_pantalla_inicial, verificar_autenticacion
import uuid

# ================= CONFIG =================
st.set_page_config(page_title="Control de Obras", layout="centered")

# ================= INIT FIREBASE =================
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

# ================= COOKIES =================
if not cookies.ready():
    st.stop()

# ================= BROWSER ID (AISLA SESIONES) =================
if "browser_id" not in cookies:
    cookies["browser_id"] = str(uuid.uuid4())
    cookies.save()

browser_id = cookies["browser_id"]

# ================= RESTAURAR SESIÓN DESDE COOKIE =================
if "auth" not in st.session_state and cookies.get("session_id"):

    session_id = cookies["session_id"]
    session_doc = db.collection("sessions").document(session_id).get()

    if session_doc.exists:
        data = session_doc.to_dict()

        # Validar que la sesión pertenece a ESTE navegador
        if data.get("browser_id") == browser_id:
            st.session_state["auth"] = {
                "username": data["username"],
                "role": data["role"],
                "obra": data.get("obra"),
                "session_id": session_id
            }
        else:
            # Cookie inválida para este navegador
            del cookies["session_id"]
            cookies.save()
    else:
        # Sesión ya no existe
        del cookies["session_id"]
        cookies.save()

# ================= ESTADO VISUAL =================
if "show_login" not in st.session_state:
    st.session_state.show_login = False

# ================= FLUJO =================

# 1️⃣ Pantalla inicial
if "auth" not in st.session_state and not st.session_state.show_login:
    mostrar_pantalla_inicial()
    st.stop()

# 2️⃣ Login
if "auth" not in st.session_state:
    verificar_autenticacion(db)
    st.stop()

# ================= NAVEGACIÓN =================
auth = st.session_state["auth"]

usuarios_page   = st.Page("pages/usuarios.py", title="Usuarios", icon="👥")
materiales_page = st.Page("pages/materiales.py", title="Materiales", icon="📦")
obras_page      = st.Page("pages/obras.py", title="Obras", icon="🏗️")
avances_page    = st.Page("pages/avances_pasante.py", title="Parte Diario", icon="📝")

if auth["role"] == "jefe":
    pg = st.navigation([obras_page, materiales_page, usuarios_page])
else:
    pg = st.navigation([avances_page])

# ================= LOGOUT =================
with st.sidebar:
    st.divider()
    if st.button("🚪 Cerrar sesión", use_container_width=True):

        if cookies.get("session_id"):
            db.collection("sessions").document(cookies["session_id"]).delete()
            del cookies["session_id"]
            cookies.save()   # ✅ SOLO AQUÍ

        st.session_state.clear()
        st.rerun()

# ================= RUN =================
pg.run()
