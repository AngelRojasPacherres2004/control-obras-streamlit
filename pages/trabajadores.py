import streamlit as st
import pandas as pd
from datetime import datetime
from firebase_admin import firestore
import cloudinary
import cloudinary.uploader

# Configuración Cloudinary (usa los mismos secrets que en obras.py)
cloudinary.config(
    cloud_name=st.secrets["cloudinary"]["cloud_name"],
    api_key=st.secrets["cloudinary"]["api_key"],
    api_secret=st.secrets["cloudinary"]["api_secret"],
    secure=True
)
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
    """Suma el presupuesto de todos los trabajadores y actualiza presupuesto y gasto de mano de obra."""
    trabajadores_docs = db.collection("obras").document(obra_id).collection("trabajadores").stream()
    total_mano_obra = sum(float(d.to_dict().get("presupuesto", 0)) for d in trabajadores_docs)
    
    obra_ref = db.collection("obras").document(obra_id)
    obra_data = obra_ref.get().to_dict()
    
    p_caja = float(obra_data.get("presupuesto_caja_chica", 0))
    p_mats = float(obra_data.get("presupuesto_materiales", 0))
    
    nuevo_total = p_caja + p_mats + total_mano_obra
    
    # SE AÑADE 'gasto_mano_obra' CON EL MISMO VALOR
    obra_ref.update({
        "presupuesto_mano_obra": round(total_mano_obra, 2),
        "gasto_mano_obra": round(total_mano_obra, 2), # <--- Nuevo campo añadido
        "presupuesto_total": round(nuevo_total, 2)
    })
    return total_mano_obra
def recalcular_mano_obra(obra_id):
    """
    Calcula cuánto se ha gastado en personal y actualiza el saldo disponible 
    específicamente en el rubro de Mano de Obra.
    """
    # 1. Sumar lo que ganan todos los trabajadores actuales
    trabajadores_docs = db.collection("obras").document(obra_id).collection("trabajadores").stream()
    total_asignado_personal = sum(float(d.to_dict().get("presupuesto", 0)) for d in trabajadores_docs)
    
    obra_ref = db.collection("obras").document(obra_id)
    obra_data = obra_ref.get().to_dict()
    
    # IMPORTANTE: Usamos 'presupuesto_mano_obra_inicial' como la base (el techo)
    # Si no existe en tu DB, usará el valor actual por única vez
    p_mo_inicial = float(obra_data.get("presupuesto_mano_obra_inicial", obra_data.get("presupuesto_mano_obra", 0)))
    
    # El nuevo saldo disponible para mostrar a la izquierda
    saldo_disponible_mo = p_mo_inicial - total_asignado_personal
    
    obra_ref.update({
        "presupuesto_mano_obra_inicial": round(p_mo_inicial, 2), # Aseguramos que se guarde la base
        "presupuesto_mano_obra": round(saldo_disponible_mo, 2),   # Este es el que baja en el sidebar
        "gasto_mano_obra": round(total_asignado_personal, 2)     # Lo que ya se consumió
    })
    return saldo_disponible_mo
def tiene_presupuesto_disponible(obra_id, monto_a_sumar):
    """Verifica si el nuevo trabajador cabe en el presupuesto total de la obra."""
    obra_ref = db.collection("obras").document(obra_id).get().to_dict()
    # Aquí definimos el límite basado en el presupuesto total inicial de la obra
    p_total_inicial = float(obra_ref.get("presupuesto_total", 0))
    
    # Calculamos cuánto se ha comprometido ya (Materiales + Caja + Mano Obra actual)
    p_caja = float(obra_ref.get("presupuesto_caja_chica", 0))
    p_mats = float(obra_ref.get("presupuesto_materiales", 0))
    mano_obra_actual = float(obra_ref.get("presupuesto_mano_obra", 0))
    
    gastado_total = p_caja + p_mats + mano_obra_actual
    
    return (gastado_total + monto_a_sumar) <= p_total_inicial
def obtener_obras():
    return {d.id: d.to_dict().get("nombre", d.id) for d in db.collection("obras").stream()}

def obtener_trabajadores_obra(obra_id):
    docs = db.collection("obras").document(obra_id).collection("trabajadores").stream()
    return [{"id": d.id, **d.to_dict()} for d in docs]

# ================= UI =================
st.title("👷 Gestión de Trabajadores y Mano de Obra")
# ================= SELECCIÓN DE OBRA SINCRONIZADA =================
OBRAS = obtener_obras()
lista_ids = list(OBRAS.keys())

# 1. Recuperar la selección global (cerebro compartido)
if "obra_id_global" not in st.session_state and lista_ids:
    st.session_state["obra_id_global"] = lista_ids[0]

# 2. Calcular el índice para que el selector no se mueva solo
indice_actual = 0
if st.session_state.get("obra_id_global") in lista_ids:
    indice_actual = lista_ids.index(st.session_state["obra_id_global"])

# 3. Dibujar el selector en el sidebar (igual que en Obras y Materiales)
obra_id_sel = st.sidebar.selectbox(
    "Seleccionar Obra para personal",
    options=lista_ids,
    format_func=lambda x: OBRAS.get(x, x),
    index=indice_actual,
    key="selector_trabajadores_global"
)

# 4. Sincronizar la elección
st.session_state["obra_id_global"] = obra_id_sel

# 5. Validación de seguridad
if not obra_id_sel:
    st.info("💡 Por favor, selecciona una obra en la pestaña **Obras** para gestionar su personal.")
    st.stop()

nombre_obra = OBRAS.get(obra_id_sel, "Desconocida")
st.sidebar.success(f"📍 Obra actual: **{nombre_obra}**")

# --- Métricas en Sidebar ---
obra_ref = db.collection("obras").document(obra_id_sel).get()
if obra_ref.exists:
    obra_actual = obra_ref.to_dict()
    st.sidebar.divider()
    st.sidebar.metric("Presupuesto Mano Obra", f"S/ {obra_actual.get('presupuesto_mano_obra', 0):,.2f}")
else:
    st.error("La obra seleccionada ya no existe.")
    st.stop()
# ================= CRUD TRABAJADORES =================
tab1, tab2 = st.tabs(["➕ Registrar Personal", "📋 Lista y Edición"])

with tab1:
    st.subheader("Registrar Nuevo Trabajador")
    
    # Obtenemos los datos actuales de la obra
    obra_ref_data = db.collection("obras").document(obra_id_sel).get().to_dict()
    
    # El saldo disponible es lo que queda en la "bolsa" de Mano de Obra
    saldo_mo_actual = float(obra_ref_data.get("presupuesto_mano_obra", 0))
    
    if saldo_mo_actual <= 0:
        st.error(f"⚠️ Saldo de Mano de Obra agotado. Disponible: S/ {saldo_mo_actual:,.2f}")
    else:
        st.info(f"💰 Saldo disponible para contratar: S/ {saldo_mo_actual:,.2f}")

    with st.form("form_trabajador", clear_on_submit=True):
        col1, col2 = st.columns(2)
        nombre_t = col1.text_input("Nombre Completo")
        dni_t = col2.text_input("DNI / ID")
        email_t = col1.text_input("Correo Electrónico")
        telefono_t = col2.text_input("Teléfono / WhatsApp")
        rol_t = col1.selectbox("Rol / Especialidad", ROLES_CONSTRUCCION)
        grupo_t = col2.text_input("Grupo / Cuadrilla")
        
        presupuesto_t = st.number_input("Sueldo asignado (S/)", min_value=0.0, step=50.0)
        foto_contrato = st.file_uploader("Subir Foto/Contrato", type=["jpg", "png", "jpeg"])
        
        submit = st.form_submit_button("CONTRATAR Y DESCONTAR DEL PRESUPUESTO")
        
        if submit:
            if not nombre_t or not dni_t or not foto_contrato:
                st.error("Faltan datos obligatorios o la foto.")
            elif presupuesto_t > saldo_mo_actual:
                st.error(f"No puedes asignar S/ {presupuesto_t}. El saldo es de solo S/ {saldo_mo_actual}")
            else:
                with st.spinner("Procesando contratación..."):
                    # 1. Subir Foto
                    res = cloudinary.uploader.upload(foto_contrato, folder=f"obras/{obra_id_sel}/personal")
                    
                    # 2. Registrar Trabajador
                    db.collection("obras").document(obra_id_sel).collection("trabajadores").add({
                        "nombre": nombre_t,
                        "dni": dni_t,
                        "email": email_t,
                        "telefono": telefono_t,
                        "rol": rol_t,
                        "grupo": grupo_t,
                        "presupuesto": presupuesto_t,
                        "url_foto": res["secure_url"],
                        "fecha_registro": datetime.now()
                    })
                    
                    # 3. Actualizar la bolsa de dinero de la obra
                    recalcular_mano_obra(obra_id_sel)
                    
                    st.success(f"✅ {nombre_t} contratado. El presupuesto de mano de obra se ha actualizado.")
                    st.rerun()
with tab2:
    st.subheader("Personal Asignado")
    trabajadores = obtener_trabajadores_obra(obra_id_sel)
    
    if not trabajadores:
        st.info("No hay trabajadores registrados en esta obra.")
    else:
        # --- TABLA RESUMEN ---
        df_t = pd.DataFrame(trabajadores)
        st.dataframe(
            df_t[["nombre", "rol", "telefono", "email", "grupo", "presupuesto"]],
            use_container_width=True,
            hide_index=True
        )
        
        st.divider()
        st.subheader("✏️ Detalle y Modificación")
        
        # --- SELECTOR DE TRABAJADOR ---
        trabajador_sel = st.selectbox(
            "Seleccionar trabajador para ver detalle o modificar",
            options=trabajadores,
            format_func=lambda x: f"{x['nombre']} - {x['rol']}"
        )
        
        # --- VISUALIZACIÓN DE FOTO Y FORMULARIO ---
        # Creamos dos columnas: una pequeña para la foto y una grande para los datos
        col_foto, col_datos = st.columns([1, 2])
        
        with col_foto:
            st.markdown("##### 📸 Foto / Contrato")
            url_f = trabajador_sel.get("url_foto")
            if url_f:
                st.image(url_f, use_container_width=True, caption=f"Evidencia de {trabajador_sel['nombre']}")
            else:
                st.warning("Sin foto registrada.")

        with col_datos:
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
                    # Opcional: Podrías añadir un código aquí para borrar la imagen de Cloudinary también
                    db.collection("obras").document(obra_id_sel).collection("trabajadores").document(trabajador_sel["id"]).delete()
                    recalcular_mano_obra(obra_id_sel)
                    st.warning("Trabajador eliminado")
                    st.rerun()
# ================= EXPORTAR =================
if trabajadores:
    st.divider()
    buffer = pd.DataFrame(trabajadores)[["nombre", "dni", "email", "telefono", "rol", "grupo", "presupuesto"]]
    st.download_button(
        label="📥 Descargar Planilla de Trabajadores",
        data=buffer.to_csv(index=False).encode('utf-8'),
        file_name=f"trabajadores_{obra_id_sel}.csv",
        mime="text/csv"
    )