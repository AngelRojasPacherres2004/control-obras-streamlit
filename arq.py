import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import cloudinary
import extra_streamlit_components as stx
import time

# Configuración de página
st.set_page_config(page_title="Control de Obras", layout="centered")

# ================= GESTOR DE COOKIES =================
# Usamos un delay inicial para que el navegador sincronice
@st.cache_resource
def get_cookie_manager():
    return stx.CookieManager()

cookie_manager = get_cookie_manager()

# ================= INIT FIREBASE & CLOUDINARY =================
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

# ================= RESTAURAR SESIÓN =================
if "auth" not in st.session_state:
    # Tiempo para que el componente JS cargue las cookies
    time.sleep(0.6) 
    user_c = cookie_manager.get("user")
    role_c = cookie_manager.get("role")

    if user_c and role_c:
        st.session_state["auth"] = {"username": user_c, "role": role_c}
        st.rerun()

# ================= LOGIN =================
def login():
    st.markdown("## 🏗️ Control de Obras")
    st.caption("Ingrese sus credenciales")

    with st.container(border=True):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")

        if st.button("INGRESAR", type="primary", use_container_width=True):
            doc = db.collection("users").document(u).get()
            if doc.exists and p == doc.to_dict().get("password"):
                role = doc.to_dict().get("role")
                
                # Guardar en sesión
                st.session_state["auth"] = {"username": u, "role": role}
                
                # Guardar en cookies (Vencimiento en 1 día por seguridad)
                in_one_day = 24 * 3600
                cookie_manager.set("user", u, max_age=in_one_day, key="save_u")
                cookie_manager.set("role", role, max_age=in_one_day, key="save_r")
                
                st.success("Cargando...")
                time.sleep(0.5)
                st.rerun()
            else:
                st.error("Credenciales inválidas")

# ================= CONTROL DE ACCESO =================
if "auth" not in st.session_state:
    login()
    st.stop()

auth = st.session_state["auth"]

# ================= SIDEBAR & NAV =================
with st.sidebar:
    st.write(f"👤 **{auth['username']}**")
    if st.button("Cerrar sesión"):
        cookie_manager.delete("user", key="del_u")
        cookie_manager.delete("role", key="del_r")
        del st.session_state["auth"]
        st.rerun()

# Definición de páginas
usuarios_page   = st.Page("pages/usuarios.py", title="Usuarios", icon="group")
materiales_page = st.Page("pages/materiales.py", title="Materiales", icon="inventory")
obras_page      = st.Page("pages/obras.py", title="Obras", icon="construction")
avances_page    = st.Page("pages/avances_pasante.py", title="Parte Diario", icon="edit_note")

if auth["role"] == "jefe":
    pg = st.navigation([obras_page, materiales_page, usuarios_page])
else:
    pg = st.navigation([avances_page])

pg.run()
