import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import cloudinary
from cookies_manager import cookies
from auth import mostrar_pantalla_inicial, verificar_autenticacion
import json

# ================= INIT (Siempre al principio) =================
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

# Configuración de página
st.set_page_config(page_title="Control de Obras", layout="centered")

# Esperar a que las cookies estén listas
if not cookies.ready():
    st.stop()

# ================= ESTADO INICIAL =================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "show_login" not in st.session_state:
    st.session_state.show_login = False

# ================= FLUJO DE AUTENTICACIÓN =================

# 1️⃣ Pantalla inicial (Portada)
if not st.session_state.get("show_login", False) and "auth" not in st.session_state:
    mostrar_pantalla_inicial()
    st.stop()

# 2️⃣ Login (Formulario)
if "auth" not in st.session_state:
    verificar_autenticacion(db)
    st.stop()

# ================= SI LLEGA AQUÍ, EL USUARIO ESTÁ LOGUEADO =================
auth = st.session_state["auth"]

# Definición de páginas
usuarios_page     = st.Page("pages/usuarios.py", title="Usuarios", icon=":material/group:")
materiales_page   = st.Page("pages/materiales.py", title="Materiales", icon=":material/inventory:")
obras_page        = st.Page("pages/obras.py", title="Obras", icon=":material/construction:")
avances_page      = st.Page("pages/avances_pasante.py", title="Parte Diario", icon=":material/edit_note:")
trabajadores_page = st.Page("pages/trabajadores.py", title="Mano de Obra", icon=":material/engineering:")

# Configurar navegación según rol
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
    
    # El selector de obra solo aparece para el jefe después de loguear
    if auth["role"] == "jefe":
        # Cargar lista de obras desde Firebase
        obras_docs = db.collection("obras").stream()
        OBRAS_DICT = {d.id: d.to_dict().get("nombre", d.id) for d in obras_docs}
        lista_ids = list(OBRAS_DICT.keys())

        if lista_ids:
            # Inicializar la obra global si no existe
            if "obra_id_global" not in st.session_state:
                st.session_state["obra_id_global"] = lista_ids[0]
            
            # Calcular índice para que el componente no se resetee al navegar
            try:
                idx_actual = lista_ids.index(st.session_state["obra_id_global"])
            except ValueError:
                idx_actual = 0

            # --- SELECTOR MAESTRO ---
            obra_seleccionada = st.selectbox(
                "Seleccionar Obra Activa:",
                options=lista_ids,
                index=idx_actual,
                format_func=lambda x: OBRAS_DICT[x],
                key="selector_maestro_obras"
            )
            
            # Guardar selección en el estado global
            st.session_state["obra_id_global"] = obra_seleccionada
        else:
            st.warning("No se encontraron obras en la base de datos.")
    
    st.divider()
    
    # Botón de cerrar sesión
    if st.button("🚪 Cerrar sesión", use_container_width=True):
        if "auth" in cookies:
            del cookies["auth"]
            cookies.save()
        st.session_state.clear()
        st.session_state["show_login"] = False
        st.rerun()

# ================= EJECUCIÓN =================
# Esto renderiza la página seleccionada
pg.run()