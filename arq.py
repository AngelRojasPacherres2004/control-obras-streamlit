import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import cloudinary

# ================= FIREBASE & CLOUDINARY =================
if not firebase_admin._apps:
    firebase_admin.initialize_app(credentials.Certificate(dict(st.secrets["firebase"])))

db = firestore.client()

cloudinary.config(
    cloud_name=st.secrets["cloudinary"]["cloud_name"],
    api_key=st.secrets["cloudinary"]["api_key"],
    api_secret=st.secrets["cloudinary"]["api_secret"],
    secure=True
)

# ================= CONFIGURACIÓN DE PÁGINAS =================
# Define las páginas apuntando a sus archivos en la carpeta /pages
usuarios_page = st.Page("pages/usuarios.py", title="Usuarios", icon=":material/group:")
materiales_page = st.Page("pages/materiales.py", title="Materiales", icon=":material/inventory:")
obras_page = st.Page("pages/obras.py", title="Gestión de Obras", icon=":material/construction:", default=True)

# ================= LOGIN =================
def check_password():
    if "auth" not in st.session_state:
        st.title("🏗️ CONTROL DE OBRAS 2025")
        username = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        if st.button("INGRESAR"):
            user_doc = db.collection("users").document(username).get()
            if user_doc.exists and user_doc.to_dict().get("password") == password:
                st.session_state["auth"] = user_doc.to_dict()
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
        return False
    return True

if not check_password():
    st.stop()

# ================= NAVEGACIÓN =================
auth = st.session_state["auth"]

# Si es jefe ve todo, si es pasante quizás solo quieras mostrarle "Obras"
if auth["role"] == "jefe":
    pg = st.navigation([obras_page, materiales_page, usuarios_page])
else:
    pg = st.navigation([obras_page])

pg.run() # <--- AQUÍ TERMINA ESTE ARCHIVO. No pongas lógica de UI debajo.