import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import cloudinary
import extra_streamlit_components as stx
import time

# Configuración de página
st.set_page_config(page_title="Control de Obras", layout="centered")

# ================= GESTOR DE COOKIES =================
def get_cookie_manager():
    return stx.CookieManager()

cookie_manager = get_cookie_manager()

# ================= CONEXIÓN FIREBASE & CLOUDINARY =================
def get_db():
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(dict(st.secrets["firebase"])))
    return firestore.client()

db = get_db()

cloudinary.config(
    cloud_name=st.secrets["cloudinary"]["cloud_name"],
    api_key=st.secrets["cloudinary"]["api_key"],
    api_secret=st.secrets["cloudinary"]["api_secret"],
    secure=True
)

# ================= RESTAURAR SESIÓN =================
if "auth" not in st.session_state:
    time.sleep(0.5) # Espera para que el navegador entregue cookies
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
        u = st.text_input("Usuario", key="login_user")
        p = st.text_input("Contraseña", type="password", key="login_pwd")
        if st.button("INGRESAR", type="primary", use_container_width=True):
            doc = db.collection("users").document(u).get()
            if doc.exists and p == doc.to_dict().get("password"):
                data = doc.to_dict()
                st.session_state["auth"] = {"username": u, "role": data.get("role"), "obra": data.get("obra")}
                # Guardar cookies
                expires = 7 * 24 * 3600
                cookie_manager.set("user", u, max_age=expires, key="s_u")
                cookie_manager.set("role", data.get("role"), max_age=expires, key="s_r")
                st.success("Redirigiendo...")
                time.sleep(0.5)
                st.rerun()
            else:
                st.error("Credenciales inválidas")

# ================= CONTROL DE ACCESO (CRÍTICO) =================
if "auth" not in st.session_state:
    login()
    st.stop() # DETIENE la ejecución aquí si no hay login

auth = st.session_state["auth"]

# ================= SIDEBAR & CERRAR SESIÓN (CORREGIDO) =================
with st.sidebar:
    st.write(f"👤 Usuario: **{auth['username']}**")
    
    # Usamos un callback para que el borrado ocurra ANTES de que la página se redibuje
    if st.button("Cerrar sesión", type="primary", use_container_width=True):
        # 1. Borramos las cookies físicamente
        try:
            cookie_manager.delete("user", key="force_logout_u")
            cookie_manager.delete("role", key="force_logout_r")
            cookie_manager.delete("obra", key="force_logout_o")
        except:
            pass
        
        # 2. LIMPIEZA INMEDIATA: Esto es lo que permite el cierre en 1 solo clic
        # Eliminamos la llave 'auth' y limpiamos el estado
        for key in list(st.session_state.keys()):
            del st.session_state[key]
            
        # 3. Pequeña pausa para sincronizar con el navegador
        st.info("Cerrando sesión...")
        time.sleep(0.6)
        
        # 4. Forzamos el reinicio total
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