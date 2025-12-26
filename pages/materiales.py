import streamlit as st
import pandas as pd
from datetime import datetime
from firebase_admin import firestore

# Configuración de página (solo si se accede directamente, 
# aunque en multipage suele heredarse del main)
st.set_page_config(page_title="Gestión de Materiales", layout="wide")

# Inicializar Firestore
db = firestore.client()

# Verificar autenticación
if "auth" not in st.session_state:
    st.error("No has iniciado sesión")
    st.stop()

auth = st.session_state["auth"]

# Bloqueo de seguridad: Solo el Jefe administra el catálogo maestro
if auth["role"] != "jefe":
    st.warning("⚠️ No tienes permisos para administrar el catálogo global de materiales.")
    st.info("Contacta con el administrador para solicitar nuevos materiales.")
    st.stop()

# ================= FUNCIONES DE DATOS =================
def obtener_materiales():
    """Obtiene la lista de materiales desde Firestore."""
    docs = db.collection("materiales").stream()
    data = []
    for d in docs:
        doc = d.to_dict()
        data.append({
            "id": d.id,
            "nombre": doc.get("nombre", "Sin nombre"),
            "unidad": doc.get("unidad", "N/D"),
            "precio_unitario": float(doc.get("precio_unitario", 0.0))
        })
    return data

# ================= INTERFAZ PRINCIPAL =================
st.title("🧱 Catálogo Maestro de Materiales")
st.markdown("Administra los insumos base que estarán disponibles para todas las obras.")

# Organizamos por pestañas para una interfaz más limpia
tab_lista, tab_crear, tab_editar = st.tabs([
    "📋 Inventario Global", 
    "➕ Registrar Nuevo", 
    "⚙️ Modificar / Eliminar"
])

materiales = obtener_materiales()

# ---------- PESTAÑA 1: LISTADO ----------
with tab_lista:
    st.subheader("Lista de Materiales Existentes")
    if materiales:
        df = pd.DataFrame(materiales)
        # Configuración de columnas para mejorar la visualización
        st.dataframe(
            df[["nombre", "unidad", "precio_unitario"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "nombre": "Descripción del Material",
                "unidad": "Unidad de Medida",
                "precio_unitario": st.column_config.NumberColumn(
                    "Precio Unitario",
                    format="$ %.2f"
                )
            }
        )
        st.caption(f"Total de materiales en catálogo: {len(materiales)}")
    else:
        st.info("Aún no hay materiales registrados en el sistema.")

# ---------- PESTAÑA 2: CREAR ----------
with tab_crear:
    st.subheader("Añadir nuevo material al catálogo")
    with st.form("form_crear", clear_on_submit=True):
        col1, col2 = st.columns(2)
        n_nombre = col1.text_input("Nombre del Material", placeholder="Ej: Cemento Sol")
        n_unidad = col2.text_input("Unidad", placeholder="Ej: Bolsa 42.5kg")
        n_precio = st.number_input("Precio Unitario Estimado", min_value=0.0, step=0.01)
        
        btn_crear = st.form_submit_button("✅ Guardar Material")
        
    if btn_crear:
        if n_nombre and n_unidad:
            db.collection("materiales").add({
                "nombre": n_nombre.strip(),
                "unidad": n_unidad.strip(),
                "precio_unitario": n_precio,
                "creado": datetime.now()
            })
            st.success(f"Material '{n_nombre}' añadido correctamente.")
            st.rerun()
        else:
            st.error("Por favor, completa los campos de nombre y unidad.")

# ---------- PESTAÑA 3: EDITAR / ELIMINAR ----------
with tab_editar:
    st.subheader("Gestión de materiales existentes")
    if not materiales:
        st.info("No hay materiales para gestionar.")
    else:
        # Buscador/Selector de material
        mat_nombres = {m["id"]: f"{m['nombre']} ({m['unidad']})" for m in materiales}
        id_a_gestionar = st.selectbox(
            "Selecciona el material a modificar",
            options=list(mat_nombres.keys()),
            format_func=lambda x: mat_nombres[x]
        )
        
        # Recuperar datos del material seleccionado
        mat_data = next(m for m in materiales if m["id"] == id_a_gestionar)
        
        with st.form("form_edicion"):
            st.markdown(f"**Editando ID:** `{id_a_gestionar}`")
            e_nombre = st.text_input("Editar Nombre", value=mat_data["nombre"])
            e_unidad = st.text_input("Editar Unidad", value=mat_data["unidad"])
            e_precio = st.number_input("Editar Precio", value=mat_data["precio_unitario"], min_value=0.0, step=0.01)
            
            c1, c2, c3 = st.columns([1, 1, 2])
            btn_actualizar = c1.form_submit_button("💾 Actualizar")
            btn_borrar = c2.form_submit_button("🗑️ Eliminar")
            
        if btn_actualizar:
            db.collection("materiales").document(id_a_gestionar).update({
                "nombre": e_nombre,
                "unidad": e_unidad,
                "precio_unitario": e_precio
            })
            st.success("Cambios guardados.")
            st.rerun()
            
        if btn_borrar:
            # Confirmación simple antes de borrar
            db.collection("materiales").document(id_a_gestionar).delete()
            st.warning(f"Material '{e_nombre}' eliminado del sistema.")
            st.rerun()