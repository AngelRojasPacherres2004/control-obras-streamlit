import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import cloudinary
from cookies_manager import cookies
from auth import mostrar_pantalla_inicial, verificar_autenticacion
import json

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

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



if not cookies.ready():
    st.stop()

# ================= RESTAURAR SESIÓN DESDE COOKIE =================
# ================= RESTAURAR SESIÓN DESDE COOKIE =================
if "auth" not in st.session_state and cookies.get("session_id"):
    session_id = cookies.get("session_id")
    session_doc = db.collection("sessions").document(session_id).get()

    if session_doc.exists:
        st.session_state["auth"] = session_doc.to_dict()
        st.session_state["show_login"] = True



# ====== ESTADO ======
if "show_login" not in st.session_state:
    st.session_state.show_login = False

# ====== FLUJO VISUAL ======

# 1️⃣ Pantalla inicial (solo diseño)
if not st.session_state.get("show_login", False) and "auth" not in st.session_state:
    mostrar_pantalla_inicial()
    st.stop()


# 2️⃣ Login (diseño + autenticación)
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
# ================= CERRAR SESIÓN =================
with st.sidebar:
    st.divider()
    if st.button("🚪 Cerrar sesión", use_container_width=True):

        #  eliminar cookie
        if "session_id" in cookies:
            db.collection("sessions").document(cookies["session_id"]).delete()
            del cookies["session_id"]
            cookies.save()




        #  limpiar sesión
        st.session_state.clear()

        # marcar logout
       # st.session_state["logout"] = True
       # st.session_state["show_login"] = False


        # volver al login
        st.rerun()






pg.run()
