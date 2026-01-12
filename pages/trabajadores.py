import streamlit as st
import pandas as pd
from datetime import datetime
from firebase_admin import firestore

# ================= DB =================
db = firestore.client()

# ================= SEGURIDAD =================
if "auth" not in st.session_state:
    st.error("Por favor, inicia sesión.")
    st.stop()

auth = st.session_state["auth"]
if auth["role"] != "jefe":
    st.warning("No tienes permisos para gestionar trabajadores.")
    st.stop()

# ================= CONFIGURACIÓN Y ROLES =================
ROLES_CONSTRUCCION = [
    "Residente de Obra", "Capataz", "Maestro de Obra", 
    "Albañil", "Peón", "Ayudante", "Fierrero", 
    "Encofrador", "Electricista", "Gasfitero", 
    "Pintor", "Operador de Maquinaria", "Topógrafo", 
    "Seguridad (SST)", "Almacenero"
]

# ================= FUNCIONES DE CÁLCULO =================
def recalcular_mano_obra(obra_id):
    """Suma el presupuesto de todos los trabajadores y actualiza la obra."""
    trabajadores_docs = db.collection("obras").document(obra_id).collection("trabajadores").stream()
    total_mano_obra = sum(float(d.to_dict().get("presupuesto", 0)) for d in trabajadores_docs)
    
    obra_ref = db.collection("obras").document(obra_id)
    obra_data = obra_ref.get().to_dict()
    
    p_caja = float(obra_data.get("presupuesto_caja_chica", 0))
    p_mats = float(obra_data.get("presupuesto_materiales", 0))
    
    nuevo_total = p_caja + p_mats + total_mano_obra
    
    obra_ref.update({
        "presupuesto_mano_obra": round(total_mano_obra, 2),
        "presupuesto_total": round(nuevo_total, 2)
    })
    return total_mano_obra

def obtener_obras():
    return {d.id: d.to_dict().get("nombre", d.id) for d in db.collection("obras").stream()}

def obtener_trabajadores_obra(obra_id):
    docs = db.collection("obras").document(obra_id).collection("trabajadores").stream()
    return [{"id": d.id, **d.to_dict()} for d in docs]

# ================= UI =================
st.title("👷 Gestión de Trabajadores y Mano de Obra")

OBRAS = obtener_obras()
obra_id_sel = st.sidebar.selectbox(
    "Seleccionar Obra para personal",
    options=list(OBRAS.keys()),
    format_func=lambda x: OBRAS[x]
)

# --- Métricas en Sidebar ---
obra_actual = db.collection("obras").document(obra_id_sel).get().to_dict()
st.sidebar.divider()
st.sidebar.metric("Presupuesto Mano Obra", f"S/ {obra_actual.get('presupuesto_mano_obra', 0):,.2f}")

# ================= CRUD TRABAJADORES =================
tab1, tab2 = st.tabs(["➕ Registrar Personal", "📋 Lista y Edición"])

with tab1:
    st.subheader("Registrar Nuevo Trabajador")
    with st.form("form_trabajador", clear_on_submit=True):
        col1, col2 = st.columns(2)
        nombre_t = col1.text_input("Nombre Completo")
        dni_t = col2.text_input("DNI / ID")
        
        email_t = col1.text_input("Correo Electrónico")
        telefono_t = col2.text_input("Teléfono / WhatsApp")
        
        rol_t = col1.selectbox("Rol / Especialidad", ROLES_CONSTRUCCION)
        grupo_t = col2.text_input("Grupo / Cuadrilla", placeholder="Ej: Cuadrilla A")
        
        presupuesto_t = st.number_input("Presupuesto Asignado (S/)", min_value=0.0, step=50.0)
        
        submit = st.form_submit_button("GUARDAR TRABAJADOR")
        
        if submit:
            if not nombre_t or not dni_t:
                st.error("Nombre y DNI son obligatorios")
            else:
                db.collection("obras").document(obra_id_sel).collection("trabajadores").add({
                    "nombre": nombre_t,
                    "dni": dni_t,
                    "email": email_t,
                    "telefono": telefono_t,
                    "rol": rol_t,
                    "grupo": grupo_t,
                    "presupuesto": presupuesto_t,
                    "fecha_registro": datetime.now()
                })
                recalcular_mano_obra(obra_id_sel)
                st.success(f"✅ {nombre_t} registrado correctamente.")
                st.rerun()

with tab2:
    st.subheader("Personal Asignado")
    trabajadores = obtener_trabajadores_obra(obra_id_sel)
    
    if not trabajadores:
        st.info("No hay trabajadores registrados en esta obra.")
    else:
        df_t = pd.DataFrame(trabajadores)
        # Mostrar tabla con nuevos datos
        st.dataframe(
            df_t[["nombre", "rol", "telefono", "email", "grupo", "presupuesto"]],
            use_container_width=True,
            hide_index=True
        )
        
        st.divider()
        st.subheader("✏️ Editar o Eliminar")
        trabajador_sel = st.selectbox(
            "Seleccionar trabajador para modificar",
            options=trabajadores,
            format_func=lambda x: f"{x['nombre']} - {x['rol']}"
        )
        
        with st.form("editar_trabajador"):
            c1, c2 = st.columns(2)
            nuevo_nombre = c1.text_input("Nombre", value=trabajador_sel.get("nombre", ""))
            nuevo_dni = c2.text_input("DNI", value=trabajador_sel.get("dni", ""))
            
            nuevo_email = c1.text_input("Correo", value=trabajador_sel.get("email", ""))
            nuevo_telefono = c2.text_input("Teléfono", value=trabajador_sel.get("telefono", ""))
            
            nuevo_rol = c1.selectbox("Rol", ROLES_CONSTRUCCION, index=ROLES_CONSTRUCCION.index(trabajador_sel["rol"]))
            nuevo_grupo = c2.text_input("Grupo", value=trabajador_sel.get("grupo", ""))
            
            nuevo_presupuesto = st.number_input("Presupuesto (S/)", value=float(trabajador_sel.get("presupuesto", 0)))
            
            col_b1, col_b2 = st.columns(2)
            btn_update = col_b1.form_submit_button("💾 Actualizar Datos")
            btn_delete = col_b2.form_submit_button("🗑️ Eliminar Trabajador")
            
            if btn_update:
                db.collection("obras").document(obra_id_sel).collection("trabajadores").document(trabajador_sel["id"]).update({
                    "nombre": nuevo_nombre,
                    "dni": nuevo_dni,
                    "email": nuevo_email,
                    "telefono": nuevo_telefono,
                    "rol": nuevo_rol,
                    "grupo": nuevo_grupo,
                    "presupuesto": nuevo_presupuesto
                })
                recalcular_mano_obra(obra_id_sel)
                st.success("Datos actualizados correctamente")
                st.rerun()
                
            if btn_delete:
                db.collection("obras").document(obra_id_sel).collection("trabajadores").document(trabajador_sel["id"]).delete()
                recalcular_mano_obra(obra_id_sel)
                st.warning("Trabajador eliminado")
                st.rerun()

# ================= EXPORTAR =================
if trabajadores:
    st.divider()
    # Exportar incluyendo los nuevos campos
    buffer = pd.DataFrame(trabajadores)[["nombre", "dni", "email", "telefono", "rol", "grupo", "presupuesto"]]
    st.download_button(
        label="📥 Descargar Planilla de Trabajadores",
        data=buffer.to_csv(index=False).encode('utf-8'),
        file_name=f"trabajadores_{obra_id_sel}.csv",
        mime="text/csv"
    )
