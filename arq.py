import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import cloudinary
from streamlit_cookies_controller import CookieController

st.set_page_config(page_title="Control de Obras", layout="centered")

# ================= COOKIES =================
controller = CookieController()

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

# ================= RESTAURAR SESIÓN (AL RECARGAR) =================
if "auth" not in st.session_state:
    user = controller.get("user")
    role = controller.get("role")

    if user and role:
        st.session_state["auth"] = {
            "username": user,
            "role": role
        }

# ================= LOGIN =================
def login():
    st.markdown("## 🏗️ Control de Obras")
    st.caption("Ingrese sus credenciales")

    with st.container(border=True):
        user = st.text_input("Usuario")
        pwd = st.text_input("Contraseña", type="password")

        if st.button("INGRESAR", type="primary", use_container_width=True):
            doc = db.collection("users").document(user).get()

            if not doc.exists:
                st.error("Usuario no existe")
                st.stop()

            data = doc.to_dict()

            if pwd != data.get("password"):
                st.error("Contraseña incorrecta")
                st.stop()

            # Guardar sesión
            st.session_state["auth"] = {
                "username": user,
                "role": data.get("role")
            }

            # Guardar cookies (persistente)
            controller.set("user", user)
            controller.set("role", data.get("role"))

            st.rerun()

# ================= CONTROL DE ACCESO =================
if "auth" not in st.session_state:
    login()
    st.stop()

auth = st.session_state["auth"]

# ================= SIDEBAR =================
with st.sidebar:
    st.write(f"👤 Usuario: **{auth['username']}**")

    if st.button("Cerrar sesión"):
        # Eliminar cookies
        controller.remove("user")
        controller.remove("role")

        # Eliminar solo auth
        del st.session_state["auth"]

        st.rerun()

# ================= NAVEGACIÓN =================
usuarios_page   = st.Page("pages/usuarios.py", title="Usuarios", icon=":material/group:")
materiales_page = st.Page("pages/materiales.py", title="Materiales", icon=":material/inventory:")
obras_page      = st.Page("pages/obras.py", title="Obras", icon=":material/construction:")
avances_page    = st.Page("pages/avances_pasante.py", title="Parte Diario", icon=":material/edit_note:")

if auth["role"] == "jefe":
    pg = st.navigation([obras_page, materiales_page, usuarios_page])
else:
    pg = st.navigation([avances_page])

pg.run()