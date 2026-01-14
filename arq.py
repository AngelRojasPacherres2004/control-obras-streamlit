import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import cloudinary
from cookies_manager import cookies
from auth import mostrar_pantalla_inicial, verificar_autenticacion
import json

obra_id = st.session_state.get("obra_id_global")

if not obra_id:
    st.warning("⚠️ Por favor, selecciona una obra en el menú lateral izquierdo para continuar.")
    st.stop()
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
# ... (todo tu código de INIT, FLUJO VISUAL y NAVEGACIÓN se mantiene igual)

# ================= NAVEGACIÓN =================
auth = st.session_state["auth"]

usuarios_page     = st.Page("pages/usuarios.py", title="Usuarios", icon=":material/group:")
materiales_page   = st.Page("pages/materiales.py", title="Materiales", icon=":material/inventory:")
obras_page        = st.Page("pages/obras.py", title="Obras", icon=":material/construction:")
avances_page      = st.Page("pages/avances_pasante.py", title="Parte Diario", icon=":material/edit_note:")
trabajadores_page = st.Page("pages/trabajadores.py", title="Mano de Obra", icon=":material/engineering:")

if auth["role"] == "jefe":
    pg = st.navigation([
        obras_page, 
        materiales_page, 
        trabajadores_page,
        usuarios_page
    ])
else:
    pg = st.navigation([avances_page])

# ================= BARRA LATERAL GLOBAL =================
with st.sidebar:
    st.markdown("### 🏗️ Gestión")
    
    # 1. Solo mostramos el selector si el usuario es jefe
    if auth["role"] == "jefe":
        # Función para obtener obras (puedes optimizarla luego con cache)
        obras_docs = db.collection("obras").stream()
        OBRAS_DICT = {d.id: d.to_dict().get("nombre", d.id) for d in obras_docs}
        lista_ids = list(OBRAS_DICT.keys())

        if lista_ids:
            # Si no hay nada seleccionado aún, tomamos la primera
            if "obra_id_global" not in st.session_state:
                st.session_state["obra_id_global"] = lista_ids[0]
            
            # Buscamos el índice para que el selectbox no se mueva al cambiar de pestaña
            try:
                idx_actual = lista_ids.index(st.session_state["obra_id_global"])
            except ValueError:
                idx_actual = 0

            # --- EL SELECTOR PERSISTENTE ---
            obra_seleccionada = st.selectbox(
                "Obra activa:",
                options=lista_ids,
                index=idx_actual,
                format_func=lambda x: OBRAS_DICT[x],
                key="selector_obra_global" # Streamlit guarda esto automáticamente
            )
            
            # Actualizamos la variable global
            st.session_state["obra_id_global"] = obra_seleccionada
        else:
            st.warning("Crea una obra primero")
    
    st.divider()
    
    # Botón de cerrar sesión (tu código original)
    if st.button("🚪 Cerrar sesión", use_container_width=True):
        del cookies["auth"]
        cookies.save()
        st.session_state.clear()
        st.session_state["logout"] = True
        st.session_state["show_login"] = False
        st.rerun()

# Lanzar la aplicación
pg.run()



pg.run()
