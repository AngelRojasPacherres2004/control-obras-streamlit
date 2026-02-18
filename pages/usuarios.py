"usuarios.py"
import streamlit as st
import pandas as pd
from datetime import datetime
from firebase_admin import firestore

# ================= CONFIGURACIÓN PÁGINA =================
st.set_page_config(page_title="Usuarios", layout="wide")

st.title("👷 CRUD de Usuarios")
st.info("Administración central de accesos y roles")

db = firestore.client()

# ================= SEGURIDAD BÁSICA =================
if "auth" not in st.session_state:
    st.error("Por favor, inicia sesión.")
    st.stop()

auth = st.session_state["auth"]

# ================= FUNCIONES =================
def obtener_obras():
    # Retorna diccionario para mapear IDs a nombres
    return {d.id: d.to_dict().get("nombre", d.id) for d in db.collection("obras").stream()}

def obtener_usuarios():
    docs = db.collection("users").stream()
    return [{
        "id": d.id,
        "obra": d.to_dict().get("obra", "all"),
        "password": d.to_dict().get("password", ""),
        "username": d.to_dict().get("username", ""),
        "role": d.to_dict().get("role", "pasante")
    } for d in docs]

# ================= CARGA DE DATOS =================
OBRAS = obtener_obras()
OBRAS_OPCIONES = ["all"] + list(OBRAS.keys())
usuarios = obtener_usuarios()

# ================= GESTIÓN DE USUARIOS (SOLO JEFE) =================
if auth["role"] == "jefe":
    
    # ---- CREAR USUARIO ----
    st.header("👤 Gestión de Usuarios")
    with st.expander("➕ Crear nuevo usuario", expanded=False):
        with st.form("crear_usuario", clear_on_submit=True):
            col1, col2 = st.columns(2)
            username = col1.text_input("Nombre de Usuario")
            password = col2.text_input("Contraseña", type="password")
            
            role = col1.selectbox("Rol del sistema", ["jefe", "pasante"])
            obra_asignada = col2.selectbox(
                "Obra asignada",
                options=OBRAS_OPCIONES,
                format_func=lambda x: OBRAS.get(x, x) if x != "all" else "Todas (Acceso Jefe)",
                help="Los pasantes solo verán la obra asignada aquí."
            )
            
            crear_user = st.form_submit_button("REGISTRAR USUARIO", use_container_width=True)

        if crear_user:
            if not username or not password:
                st.error("Nombre y contraseña son obligatorios")
            else:
                db.collection("users").document(username).set({
                    "obra": obra_asignada,
                    "password": password,
                    "username": username,
                    "role": role
                })
                st.success(f"Usuario '{username}' creado exitosamente")
                st.rerun()

    # ---- TABLA DE USUARIOS ----
    st.subheader("📋 Usuarios en el sistema")
    if usuarios:
        df_usuarios = pd.DataFrame(usuarios)
        # Formatear la columna obra para que sea legible
        df_usuarios["obra_nombre"] = df_usuarios["obra"].apply(lambda x: OBRAS.get(x, "Acceso Total") if x != "all" else "Acceso Total")
        
        st.dataframe(
            df_usuarios[["username", "password", "role", "obra_nombre"]],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No hay usuarios registrados.")

    # ---- EDITAR / ELIMINAR ----
    if usuarios:
        st.divider()
        st.subheader("✏️ Modificar Usuario")
        
        user_sel = st.selectbox(
            "Selecciona un usuario para editar",
            options=usuarios,
            format_func=lambda x: f"{x['username']} [{x['role']}]"
        )

        if user_sel:
            with st.form("editar_usuario"):
                col_e1, col_e2 = st.columns(2)
                
                username_e = col_e1.text_input("Usuario", value=user_sel["username"], disabled=True)
                password_e = col_e2.text_input("Nueva Contraseña", value=user_sel["password"])
                
                role_e = col_e1.selectbox(
                    "Cambiar Rol", 
                    ["jefe", "pasante"], 
                    index=["jefe", "pasante"].index(user_sel["role"])
                )
                
                # Manejo del índice de la obra para evitar errores si la obra ya no existe
                idx_obra = 0
                if user_sel["obra"] in OBRAS_OPCIONES:
                    idx_obra = OBRAS_OPCIONES.index(user_sel["obra"])

                obra_e = col_e2.selectbox(
                    "Cambiar Obra Asignada",
                    options=OBRAS_OPCIONES,
                    index=idx_obra,
                    format_func=lambda x: OBRAS.get(x, x) if x != "all" else "Todas (Acceso Jefe)"
                )
                
                c1, c2 = st.columns(2)
                guardar = c1.form_submit_button("💾 GUARDAR CAMBIOS", use_container_width=True)
                borrar = c2.form_submit_button("🗑️ ELIMINAR USUARIO", use_container_width=True)

            if guardar:
                db.collection("users").document(user_sel["id"]).update({
                    "password": password_e,
                    "role": role_e,
                    "obra": obra_e
                })
                st.success("Cambios aplicados")
                st.rerun()
            
            if borrar:
                db.collection("users").document(user_sel["id"]).delete()
                st.warning(f"Usuario {user_sel['username']} eliminado")
                st.rerun()
else:
    st.warning("Acceso restringido: Solo el personal de nivel 'Jefe' puede administrar usuarios.")