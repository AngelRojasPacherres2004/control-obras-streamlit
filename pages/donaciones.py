# donaciones.py
import streamlit as st
import pandas as pd
from datetime import datetime, date
import pytz
from firebase_admin import firestore

# ================= CONFIGURACIÓN DE ZONA HORARIA =================
local_tz = pytz.timezone('America/Lima')

# ================= DB =================
db = firestore.client()

# ================= SEGURIDAD =================
if "auth" not in st.session_state:
    st.error("Por favor, inicia sesión.")
    st.stop()

auth = st.session_state["auth"]
if auth["role"] != "jefe":
    st.warning("No tienes permisos para gestionar donaciones.")
    st.stop()

# ================= FUNCIONES =================
def obtener_obras():
    return {d.id: d.to_dict().get("nombre", d.id) for d in db.collection("obras").stream()}

def obtener_donaciones_monetarias(obra_id):
    docs = db.collection("obras").document(obra_id).collection("donaciones_monetarias").order_by("fecha", direction=firestore.Query.DESCENDING).stream()
    return [{"id": d.id, **d.to_dict()} for d in docs]

def obtener_donaciones_materiales(obra_id):
    docs = db.collection("obras").document(obra_id).collection("donaciones_materiales").order_by("fecha", direction=firestore.Query.DESCENDING).stream()
    return [{"id": d.id, **d.to_dict()} for d in docs]

def recalcular_donaciones_monetarias(obra_id):
    """Suma todas las donaciones monetarias y actualiza el total en la obra"""
    donaciones = obtener_donaciones_monetarias(obra_id)
    total_donaciones = sum(float(d.get("monto", 0)) for d in donaciones)
    
    db.collection("obras").document(obra_id).update({
        "total_donaciones_monetarias": round(total_donaciones, 2),
        "fecha_actualizacion_donaciones": datetime.now(local_tz)
    })
    return total_donaciones

# ================= UI =================
st.title("💝 Gestión de Donaciones")

# ================= SELECCIÓN DE OBRA SINCRONIZADA =================
OBRAS = obtener_obras()
lista_ids = list(OBRAS.keys())

if "obra_id_global" not in st.session_state and lista_ids:
    st.session_state["obra_id_global"] = lista_ids[0]

indice_actual = 0
if st.session_state.get("obra_id_global") in lista_ids:
    indice_actual = lista_ids.index(st.session_state["obra_id_global"])

obra_id_sel = st.sidebar.selectbox(
    "Seleccionar Obra",
    options=lista_ids,
    format_func=lambda x: OBRAS.get(x, x),
    index=indice_actual,
    key="selector_donaciones_global"
)

st.session_state["obra_id_global"] = obra_id_sel

if not obra_id_sel:
    st.info("💡 Por favor, selecciona una obra para gestionar sus donaciones.")
    st.stop()

nombre_obra = OBRAS.get(obra_id_sel, "Desconocida")
st.sidebar.success(f"📍 Obra actual: **{nombre_obra}**")

# --- MÉTRICAS EN SIDEBAR ---
obra_snap = db.collection("obras").document(obra_id_sel).get()
if obra_snap.exists:
    obra_d = obra_snap.to_dict()
    total_don_mon = float(obra_d.get("total_donaciones_monetarias", 0))
    
    st.sidebar.divider()
    st.sidebar.subheader("📊 Resumen de Donaciones")
    st.sidebar.metric(
        label="Total Donaciones Monetarias",
        value=f"S/ {total_don_mon:,.2f}"
    )

# ================= PESTAÑAS PRINCIPALES =================
tab1, tab2, tab3, tab4 = st.tabs([
    "💵 Registrar Donación Monetaria",
    "🧱 Registrar Donación de Materiales",
    "📋 Historial Monetarias",
    "📦 Historial Materiales"
])

# ================= TAB 1: DONACIÓN MONETARIA =================
with tab1:
    st.subheader("💵 Nueva Donación Monetaria")
    
    with st.form("form_donacion_monetaria", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        donante = col1.text_input("Nombre del Donante")
        pais = col2.text_input("País de origen", value="Perú")
        
        fecha_don = col1.date_input("Fecha de donación", value=date.today())
        monto = col2.number_input("Monto (S/)", min_value=0.0, step=10.0)
        
        destino = st.selectbox(
            "Destino de la donación",
            ["Caja Chica", "Materiales", "Mano de Obra", "General"]
        )
        
        notas = st.text_area("Notas adicionales (opcional)")
        
        submit = st.form_submit_button("💾 Registrar Donación Monetaria")
        
        if submit:
            if not donante or monto <= 0:
                st.error("Por favor completa todos los campos obligatorios.")
            else:
                with st.spinner("Registrando donación..."):
                    # Convertir fecha a datetime
                    fecha_dt = datetime.combine(fecha_don, datetime.min.time())
                    fecha_dt = local_tz.localize(fecha_dt)
                    
                    # Guardar en subcolección
                    db.collection("obras").document(obra_id_sel).collection("donaciones_monetarias").add({
                        "donante": donante,
                        "pais": pais,
                        "fecha": fecha_dt,
                        "monto": monto,
                        "destino": destino,
                        "notas": notas,
                        "registrado_en": datetime.now(local_tz)
                    })
                    
                    # Recalcular total
                    recalcular_donaciones_monetarias(obra_id_sel)
                    
                    st.success(f"✅ Donación de S/ {monto:,.2f} de {donante} registrada correctamente.")
                    st.rerun()

# ================= TAB 2: DONACIÓN DE MATERIALES =================
with tab2:
    st.subheader("🧱 Nueva Donación de Materiales")
    
    # 1. Creamos un disparador de reinicio en el session_state si no existe
    if "reset_donacion" not in st.session_state:
        st.session_state.reset_donacion = 0

    st.info("💡 Los materiales donados se registrarán en el inventario de la obra con identificador 'DONACIÓN'")
    
    # 2. CAMPOS DE ENTRADA
    # Usamos una clave dinámica: al cambiar st.session_state.reset_donacion, los widgets se limpian
    c_key = st.session_state.reset_donacion

    col_reg1, col_reg2 = st.columns(2)
    donante_mat = col_reg1.text_input("Nombre del Donante", key=f"donante_{c_key}")
    fecha_mat = col_reg2.date_input("Fecha de donación", value=date.today(), key=f"fecha_{c_key}")

    nombre_mat = st.text_input("Nombre del material", key=f"nombre_{c_key}")

    col_m1, col_m2, col_m3 = st.columns(3)
    cantidad = col_m1.number_input("Cantidad", min_value=0.0, step=1.0, key=f"cant_{c_key}")
    unidad = col_m2.selectbox("Unidad", ["kg", "unidad", "m", "m²", "m³", "bolsa", "lata", "galón", "caja"], key=f"uni_{c_key}")
    precio_unit = col_m3.number_input("Precio unitario estimado (S/)", min_value=0.0, step=0.10, key=f"precio_{c_key}")

    # 3. CÁLCULO EN VIVO
    subtotal_estimado = cantidad * precio_unit
    if subtotal_estimado > 0:
        st.success(f"💰 **Valor Total de la Donación: S/ {subtotal_estimado:,.2f}**")
    
    # 4. BOTÓN DE REGISTRO
    if st.button("💾 Registrar Donación de Material", type="primary", use_container_width=True):
        if not donante_mat or not nombre_mat or cantidad <= 0:
            st.error("⚠️ Por favor completa los campos obligatorios.")
        else:
            with st.spinner("Registrando..."):
                fecha_dt = datetime.combine(fecha_mat, datetime.min.time())
                fecha_dt = local_tz.localize(fecha_dt)
                
                # Registro en Firebase (Historial)
                db.collection("obras").document(obra_id_sel).collection("donaciones_materiales").add({
                    "donante": donante_mat,
                    "fecha": fecha_dt,
                    "nombre": nombre_mat,
                    "cantidad": cantidad,
                    "unidad": unidad,
                    "precio_unitario": precio_unit,
                    "subtotal": subtotal_estimado,
                    "registrado_en": datetime.now(local_tz)
                })
                
                # Registro en Firebase (Inventario)
                db.collection("obras").document(obra_id_sel).collection("materiales").add({
                    "nombre": nombre_mat,
                    "cantidad": cantidad,
                    "unidad": unidad,
                    "precio_unitario": precio_unit,
                    "subtotal": 0.0, 
                    "tipo": "DONACIÓN",
                    "donante": donante_mat,
                    "fecha": fecha_dt,
                    "registrado_en": datetime.now(local_tz)
                })
                
                # --- AQUÍ LIMPIAMOS SIN ERROR ---
                # Incrementamos el contador: esto cambia las llaves (keys) de los widgets
                # y Streamlit los trata como widgets nuevos y vacíos.
                st.session_state.reset_donacion += 1
                st.success("✅ ¡Registrado con éxito!")
                st.rerun()
# ================= TAB 3: HISTORIAL MONETARIAS =================
with tab3:
    st.subheader("📋 Historial de Donaciones Monetarias")
    
    donaciones_mon = obtener_donaciones_monetarias(obra_id_sel)
    
    if not donaciones_mon:
        st.info("No hay donaciones monetarias registradas.")
    else:
        # Tabla resumen
        df_don = pd.DataFrame(donaciones_mon)
        
        # Formatear fecha para visualización
        if 'fecha' in df_don.columns:
            df_don['fecha_formato'] = df_don['fecha'].apply(
                lambda x: x.astimezone(local_tz).strftime('%d/%m/%Y') if hasattr(x, 'astimezone') else 'N/D'
            )
        
        st.dataframe(
            df_don[['fecha_formato', 'donante', 'pais', 'monto', 'destino', 'notas']],
            use_container_width=True,
            hide_index=True,
            column_config={
                'fecha_formato': 'Fecha',
                'donante': 'Donante',
                'pais': 'País',
                'monto': st.column_config.NumberColumn('Monto (S/)', format="S/ %.2f"),
                'destino': 'Destino',
                'notas': 'Notas'
            }
        )
        
        # Total
        total = sum(d['monto'] for d in donaciones_mon)
        st.success(f"**Total acumulado:** S/ {total:,.2f}")
        
        # Exportar
        st.divider()
        csv = df_don[['fecha_formato', 'donante', 'pais', 'monto', 'destino', 'notas']].to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar CSV",
            data=csv,
            file_name=f"donaciones_monetarias_{obra_id_sel}.csv",
            mime="text/csv"
        )

# ================= TAB 4: HISTORIAL MATERIALES =================
with tab4:
    st.subheader("📦 Historial de Donaciones de Materiales")
    
    donaciones_mat = obtener_donaciones_materiales(obra_id_sel)
    
    if not donaciones_mat:
        st.info("No hay donaciones de materiales registradas.")
    else:
        # Tabla resumen
        df_mat = pd.DataFrame(donaciones_mat)
        
        # Formatear fecha
        if 'fecha' in df_mat.columns:
            df_mat['fecha_formato'] = df_mat['fecha'].apply(
                lambda x: x.astimezone(local_tz).strftime('%d/%m/%Y') if hasattr(x, 'astimezone') else 'N/D'
            )
        
        st.dataframe(
            df_mat[['fecha_formato', 'donante', 'nombre', 'cantidad', 'unidad', 'precio_unitario', 'subtotal', 'notas']],
            use_container_width=True,
            hide_index=True,
            column_config={
                'fecha_formato': 'Fecha',
                'donante': 'Donante',
                'nombre': 'Material',
                'cantidad': 'Cantidad',
                'unidad': 'Unidad',
                'precio_unitario': st.column_config.NumberColumn('P. Unit. (S/)', format="S/ %.2f"),
                'subtotal': st.column_config.NumberColumn('Subtotal (S/)', format="S/ %.2f"),
                'notas': 'Notas'
            }
        )
        
        # Total
        total_mat = sum(d['subtotal'] for d in donaciones_mat)
        st.success(f"**Valor total de materiales donados:** S/ {total_mat:,.2f}")
        
        # Exportar
        st.divider()
        csv_mat = df_mat[['fecha_formato', 'donante', 'nombre', 'cantidad', 'unidad', 'precio_unitario', 'subtotal', 'notas']].to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar CSV",
            data=csv_mat,
            file_name=f"donaciones_materiales_{obra_id_sel}.csv",
            mime="text/csv"
        )