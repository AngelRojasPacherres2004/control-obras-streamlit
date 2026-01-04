import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import cloudinary
from streamlit_cookies_controller import CookieController
import time

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

# ================= RESTAURAR SESIÓN (VERSION ROBUSTA) =================
if "auth" not in st.session_state:
   
    cookies = controller.getAll()
    
    #Si no hay nada, esperamos un segundo y volvemos a intentar
    if not cookies:
        with st.empty():
            st.info("Sincronizando sesión...")
            time.sleep(1.5) # Tiempo suficiente para que el navegador responda
        
        # Intentamos obtenerlas de nuevo tras la espera
        cookies = controller.getAll()

    # Si después del intento sigue vacío, mostramos el login
    if cookies:
        user = cookies.get("user")
        role = cookies.get("role")

        if user and role:
            st.session_state["auth"] = {
                "username": user,
                "role": role
            }
            st.rerun()
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
                return

            data = doc.to_dict()

            if pwd != data.get("password"):
                st.error("Contraseña incorrecta")
                return

            st.session_state["auth"] = {
                "username": user,
                "role": data.get("role")
            }

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
        controller.remove("user")
        controller.remove("role")
        st.session_state.pop("auth", None)
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
