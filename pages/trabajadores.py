"trabajadores.py"
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
    """
    Recalcula el presupuesto disponible de mano de obra tomando como base
    el `presupuesto_mano_obra` original de la obra y restando el
    `sueldo_acumulado` de todos los trabajadores.

    También actualiza el campo `gasto_mano_obra` para reflejar el total
    devengado hasta el momento.
    """
    # 1. Obtener todos los trabajadores de la subcolección
    trabajadores_docs = db.collection("obras").document(obra_id).collection("trabajadores").stream()
    
    # 2. Calcular el total acumulado de sueldos
    total_acumulado = 0.0
    for d in trabajadores_docs:
        data_t = d.to_dict()
        total_acumulado += float(data_t.get("sueldo_acumulado", 0))
    
    # 3. Obtener el presupuesto inicial de la obra
    obra_ref = db.collection("obras").document(obra_id)
    obra_data = obra_ref.get().to_dict()
    
    p_mo_inicial = float(obra_data.get("presupuesto_mano_obra", 0))
    
    # 4. Calcular saldo restante basado en acumulado
    saldo_disponible = p_mo_inicial - total_acumulado
    
    # 5. Actualizar campos en el documento de obra
    obra_ref.update({
        "presupuesto_mano_obra_actual": round(saldo_disponible, 2),
        "gasto_mano_obra": round(total_acumulado, 2),
        "fecha_actualizacion_mo": datetime.now()
    })
    return saldo_disponible
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
# --- MÉTRICAS ACTUALIZADAS EN EL SIDEBAR ---
obra_snap = db.collection("obras").document(obra_id_sel).get()
if obra_snap.exists:
    obra_d = obra_snap.to_dict()
    
    # Extraer valores con seguros (defaults)
    p_mo_fijo = float(obra_d.get("presupuesto_mano_obra", 0))
    p_mo_restante = float(obra_d.get("presupuesto_mano_obra_actual", p_mo_fijo))
    p_mo_gastado = float(obra_d.get("gasto_mano_obra", 0))
    
    st.sidebar.divider()
    st.sidebar.subheader("📊 Resumen Mano de Obra")
    
    # Métrica principal
    st.sidebar.metric(
        label="Disponible para contratar", 
        value=f"S/ {p_mo_restante:,.2f}",
        delta=f"Gastado: S/ {p_mo_gastado:,.2f}",
        delta_color="inverse"
    )
    
    # Barra de progreso
    if p_mo_fijo > 0:
        # Calcular porcentaje disponible
        porcentaje = max(0.0, min(1.0, p_mo_restante / p_mo_fijo))
        st.sidebar.progress(porcentaje, text=f"Cupo: {porcentaje*100:.1f}%")
        
    if p_mo_restante < 0:
        st.sidebar.error("⚠️ Presupuesto excedido")
# ================= CRUD TRABAJADORES =================
tab1, tab2 = st.tabs(["➕ Registrar Personal", "📋 Lista y Edición"])

with tab1:
    st.subheader("Registrar Nuevo Trabajador")
    
    # 1. Obtener datos maestros de la obra
    obra_ref_data = db.collection("obras").document(obra_id_sel).get().to_dict()
    
    # 2. Lógica de Saldo Dinámico
    # El 'presupuesto_mano_obra' es el inicial (fijo)
    p_inicial_mo = float(obra_ref_data.get("presupuesto_mano_obra", 0))
    # El 'presupuesto_mano_obra_actual' es lo que queda (calculado por la función)
    saldo_mo_actual = float(obra_ref_data.get("presupuesto_mano_obra_actual", p_inicial_mo))
    
    # Mostrar información de presupuesto
    if saldo_mo_actual <= 0:
        st.error(f"⚠️ Presupuesto de Mano de Obra agotado. Disponible: S/ {saldo_mo_actual:,.2f}")
    else:
        st.info(f"💰 Saldo disponible para nuevas contrataciones: S/ {saldo_mo_actual:,.2f}")

    with st.form("form_trabajador", clear_on_submit=True):
        col1, col2 = st.columns(2)
        nombre_t = col1.text_input("Nombre Completo")
        dni_t = col2.text_input("DNI / ID")
        email_t = col1.text_input("Correo Electrónico")
        telefono_t = col2.text_input("Teléfono / WhatsApp")
        rol_t = col1.selectbox("Rol / Especialidad", ROLES_CONSTRUCCION)
        grupo_t = col2.text_input("Grupo / Cuadrilla")
        
        sueldo_diario = st.number_input("Sueldo diario (S/)", min_value=0.0, step=10.0)

        foto_contrato = st.file_uploader("Subir Foto/Contrato", type=["jpg", "png", "jpeg"])
        
        submit = st.form_submit_button("CONTRATAR Y DESCONTAR DEL PRESUPUESTO")
        
        if submit:
            if not nombre_t or not dni_t or not foto_contrato:
                st.error("Faltan datos obligatorios o la foto.")
            else:
                with st.spinner("Procesando contratación..."):
                    res = cloudinary.uploader.upload(
                    foto_contrato,
                    folder=f"obras/{obra_id_sel}/personal"
            )

                # AGREGA "dias_asistidos": 0 AQUÍ ABAJO
                    db.collection("obras").document(obra_id_sel)\
                    .collection("trabajadores").add({
                        "nombre": nombre_t,
                        "dni": dni_t,
                        "email": email_t,
                        "telefono": telefono_t,
                        "rol": rol_t,
                        "grupo": grupo_t,
                        "sueldo_diario": sueldo_diario,
                        "url_foto": res["secure_url"],
                        "fecha_registro": datetime.now(),
                        "dias_asistidos": 0,  # <--- dias
                        "sueldo_acumulado": 0.0  # nuevo campo acumulado
                    })

                    st.success(f"✅ {nombre_t} registrado correctamente con 0 asistencias.")
                    st.rerun()

                    
                    st.success(f"✅ {nombre_t} contratado. Saldo actualizado correctamente.")
                    st.rerun()
with tab2:
    st.subheader("Personal Asignado")
    trabajadores = obtener_trabajadores_obra(obra_id_sel)
    
    if not trabajadores:
        st.info("No hay trabajadores registrados en esta obra.")
    else:
        # --- TABLA RESUMEN ---
        df_t = pd.DataFrame(trabajadores)

        # Compatibilidad con trabajadores antiguos
        if "sueldo_diario" not in df_t.columns:
            if "presupuesto" in df_t.columns:
                df_t["sueldo_diario"] = df_t["presupuesto"]
            else:
                df_t["sueldo_diario"] = 0.0
        if "sueldo_acumulado" not in df_t.columns:
            df_t["sueldo_acumulado"] = 0.0
        if "dias_asistidos" not in df_t.columns:
            df_t["dias_asistidos"] = 0

        st.dataframe(
            df_t[["nombre", "rol", "telefono", "email", "grupo", "sueldo_diario", "dias_asistidos", "sueldo_acumulado"]],
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
                nuevo_sueldo = st.number_input(
    "Sueldo diario (S/)",
    value=float(trabajador_sel.get("sueldo_diario", 0)),
    step=10.0
)

                # mostrar solo lectura para dias y acumulado
                cinfo1, cinfo2 = st.columns(2)
                cinfo1.metric("Días asistidos", trabajador_sel.get("dias_asistidos", 0))
                cinfo2.metric("Sueldo acumulado", f"S/ {trabajador_sel.get('sueldo_acumulado', 0):,.2f}")

                col_b1, col_b2, col_b3 = st.columns(3)
                btn_update = col_b1.form_submit_button("💾 Actualizar Datos")
                btn_delete = col_b2.form_submit_button("🗑️ Eliminar Trabajador")
                btn_pay = col_b3.form_submit_button("💸 Pagar Salario")
                
                if btn_update:
                    db.collection("obras").document(obra_id_sel).collection("trabajadores").document(trabajador_sel["id"]).update({
                        "nombre": nuevo_nombre,
                        "dni": nuevo_dni,
                        "email": nuevo_email,
                        "telefono": nuevo_telefono,
                        "rol": nuevo_rol,
                        "grupo": nuevo_grupo,
                        "sueldo_diario": nuevo_sueldo

                    })
                   
                    st.success("Datos actualizados correctamente")
                    st.rerun()
                if btn_pay:
                    monto = float(trabajador_sel.get("sueldo_acumulado", 0))

                    if monto <= 0:
                        st.info("No hay salario acumulado para pagar.")
                    else:

                        obra_ref = db.collection("obras").document(obra_id_sel)

                        # 🔹 REGISTRAR EL PAGO CON FECHA
                        obra_ref.collection("pagos_mano_obra").add({
                            "trabajador": trabajador_sel.get("nombre"),
                            "trabajador_id": trabajador_sel.get("id"),
                            "monto": monto,
                            "fecha": datetime.now(),
                            "tipo": "pago_salario"
                        })

                        # 🔹 SUMAR AL GASTO TOTAL
                        obra_ref.update({
                            "gasto_mano_obra": firestore.Increment(monto)
                        })

                        # 🔹 RESETEAR ACUMULADO
                        db.collection("obras").document(obra_id_sel)\
                            .collection("trabajadores")\
                            .document(trabajador_sel["id"]).update({
                                "sueldo_acumulado": 0.0
                            })

                        st.success(f"Salario pagado: S/ {monto:,.2f}")
                        st.rerun()
# ================= EXPORTAR =================
if trabajadores:
    st.divider()
    buffer = pd.DataFrame(trabajadores)[["nombre", "dni", "email", "telefono", "rol", "grupo", "sueldo_diario"]]
    st.download_button(
        label="📥 Descargar Planilla de Trabajadores",
        data=buffer.to_csv(index=False).encode('utf-8'),
        file_name=f"trabajadores_{obra_id_sel}.csv",
        mime="text/csv"
    )
