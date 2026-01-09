import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import cloudinary
from auth import login_screen

st.set_page_config(page_title="Control de Obras", layout="centered")

# ===== INIT =====
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

# ===== LOGIN =====
if "auth" not in st.session_state:
    authenticator = login_screen(db)
    if "auth" not in st.session_state:
        st.stop()
else:
    authenticator = None

auth = st.session_state["auth"]

# ===== NAVEGACIÓN =====
usuarios_page   = st.Page("pages/usuarios.py", title="Usuarios", icon="👥")
materiales_page = st.Page("pages/materiales.py", title="Materiales", icon="📦")
obras_page      = st.Page("pages/obras.py", title="Obras", icon="🏗️")
avances_page    = st.Page("pages/avances_pasante.py", title="Parte Diario", icon="📝")

if auth["role"] == "jefe":
    pg = st.navigation([obras_page, materiales_page, usuarios_page])
else:
    pg = st.navigation([avances_page])

# ===== LOGOUT =====
with st.sidebar:
    st.divider()
    st.write(f"👤 {auth['username']}")

    if authenticator:
        authenticator.logout("🚪 Cerrar sesión", "sidebar")
        if "auth" not in st.session_state:
            st.rerun()

pg.run()
