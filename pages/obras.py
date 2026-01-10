import streamlit as st
import pandas as pd
from datetime import datetime, date
import pytz
import cloudinary
import cloudinary.uploader
from firebase_admin import firestore
from collections import defaultdict

# ================= CONFIGURACIÓN DE ZONA HORARIA =================
local_tz = pytz.timezone('America/Lima')

# ================= CONFIGURACIÓN =================
MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
    7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}

# Configuración Cloudinary
cloudinary.config(
    cloud_name=st.secrets["cloudinary"]["cloud_name"],
    api_key=st.secrets["cloudinary"]["api_key"],
    api_secret=st.secrets["cloudinary"]["api_secret"],
    secure=True
)

st.set_page_config(page_title="Gestión de Obras", layout="wide")
st.title("👷 Gestión de Obras y Avances")

db = firestore.client()

# ================= FUNCIONES =================
def obtener_obras():
    return {d.id: d.to_dict().get("nombre", d.id) for d in db.collection("obras").stream()}

def cargar_avances(obra_id):
    docs = (
        db.collection("obras")
        .document(obra_id)
        .collection("avances")
        .order_by("timestamp", direction=firestore.Query.ASCENDING)
        .stream()
    )
    return [d.to_dict() for d in docs]

# ================= SEGURIDAD / AUTH =================
if "auth" not in st.session_state:
    st.error("Por favor, inicia sesión.")
    st.stop()

auth = st.session_state["auth"]

if "crear_obra" not in st.session_state:
    st.session_state["crear_obra"] = False

# ================= SELECCIÓN DE OBRA =================
OBRAS = obtener_obras()

if auth["role"] == "jefe":
    obra_id_sel = st.sidebar.selectbox(
        "Seleccionar obra",
        options=list(OBRAS.keys()) if OBRAS else [],
        format_func=lambda x: OBRAS.get(x, x),
        on_change=lambda: st.session_state.update({"crear_obra": False})
    )
    st.sidebar.divider()
    if st.sidebar.button("➕ Crear Nueva Obra", use_container_width=True):
        st.session_state["crear_obra"] = True
else:
    obra_id_sel = auth.get("obra")
    if not obra_id_sel:
        st.error("No tienes una obra asignada.")
        st.stop()
    st.sidebar.success(f"Obra asignada: {OBRAS.get(obra_id_sel, 'Desconocida')}")

# ================= FORMULARIO CREAR OBRA (ACTUALIZADO) =================
if auth["role"] == "jefe" and st.session_state["crear_obra"]:
    st.title("➕ Crear nueva obra")
    with st.form("form_crear_obra"):
        nombre = st.text_input("Nombre de la obra")
        ubicacion = st.text_input("Ubicación")
        estado = st.selectbox("Estado", ["en espera", "en progreso", "pausado", "finalizado"])
        
        c1, c2 = st.columns(2)
        f_inicio = c1.date_input("Fecha inicio")
        f_fin = c2.date_input("Fecha fin estimado")
        
        st.subheader("💰 Presupuestos Iniciales")
        col_p1, col_p2 = st.columns(2)
        p_caja_chica = col_p1.number_input("Presupuesto Caja Chica (S/)", min_value=0.0, step=100.0)
        p_mano_obra = col_p2.number_input("Presupuesto Mano de Obra (S/)", min_value=0.0, step=100.0)
        
        # El presupuesto de materiales inicia en 0 según tu solicitud
        p_materiales = 0.0
        p_total = p_caja_chica + p_mano_obra + p_materiales
        
        st.info(f"**Presupuesto Total Calculado:** S/ {p_total:,.2f}")
        
        col_g, col_c = st.columns(2)
        if col_g.form_submit_button("💾 Guardar Obra"):
            if not nombre: 
                st.error("El nombre es obligatorio")
            else:
                oid = nombre.lower().strip().replace(" ", "_")
                ahora_obra = datetime.now(local_tz)
                
                db.collection("obras").document(oid).set({
                    "nombre": nombre,
                    "ubicacion": ubicacion,
                    "estado": estado,
                    "fecha_inicio": datetime.combine(f_inicio, datetime.min.time()),
                    "fecha_fin_estimado": datetime.combine(f_fin, datetime.min.time()),
                    "presupuesto_caja_chica": p_caja_chica,
                    "presupuesto_mano_obra": p_mano_obra,
                    "presupuesto_materiales": p_materiales, # Inicia en 0
                    "presupuesto_total": p_total,           # Suma de los 3
                    "gasto_acumulado": 0,
                    "creado_en": ahora_obra
                })
                st.session_state["crear_obra"] = False
                st.success("Obra creada exitosamente")
                st.rerun()
        if col_c.form_submit_button("❌ Cancelar"):
            st.session_state["crear_obra"] = False
            st.rerun()
    st.stop()

# ================= INFORMACIÓN DE LA OBRA =================
if not obra_id_sel:
    st.info("Selecciona o crea una obra para comenzar.")
    st.stop()

doc_ref = db.collection("obras").document(obra_id_sel).get()
if not doc_ref.exists:
    st.error("La obra seleccionada no existe.")
    st.stop()

obra_data = doc_ref.to_dict()
# El presupuesto base para alertas será el total (Caja + Mano de Obra + Materiales)
presupuesto_referencia = float(obra_data.get("presupuesto_total", 0))

st.subheader(f"🏗️ {obra_data.get('nombre')}")
st.caption(f"📍 {obra_data.get('ubicacion')} | 📌 {obra_data.get('estado')}")

# Métricas de Presupuesto
m1, m2, m3, m4 = st.columns(4)
m1.metric("📦 Caja Chica", f"S/ {obra_data.get('presupuesto_caja_chica', 0):,.2f}")
m2.metric("👷 Mano Obra", f"S/ {obra_data.get('presupuesto_mano_obra', 0):,.2f}")
m3.metric("🧱 Materiales", f"S/ {obra_data.get('presupuesto_materiales', 0):,.2f}")
m4.metric("💰 Presupuesto Total", f"S/ {presupuesto_referencia:,.2f}")

# ================= REGISTRAR AVANCE (PASANTE) =================
if auth["role"] == "pasante":
    st.divider()
    st.header("📝 Registrar Avance Diario")
    
    materiales_ref = db.collection("obras").document(obra_id_sel).collection("materiales").stream()
    lista_mats = [m.to_dict() for m in materiales_ref]

    with st.form("nuevo_avance", clear_on_submit=True):
        resp = st.text_input("Responsable", value=auth.get("username", ""))
        desc = st.text_area("Descripción del trabajo")
        
        st.write("🧱 **Materiales usados hoy:**")
        mats_usados = []
        costo_dia = 0.0
        
        for m in lista_mats:
            c1, c2 = st.columns([3, 1])
            cant = c2.number_input(f"{m['nombre']} ({m['unidad']})", min_value=0.0, key=f"form_{m['nombre']}")
            if cant > 0:
                subt = round(cant * m.get("precio_unitario", 0), 2)
                costo_dia += subt
                mats_usados.append({
                    "nombre": m['nombre'], "unidad": m['unidad'],
                    "cantidad": cant, "precio_unitario": m.get("precio_unitario", 0),
                    "subtotal": subt
                })
        
        st.info(f"Costo calculado del día: S/ {costo_dia:.2f}")
        fotos = st.file_uploader("Subir fotos (mínimo 3)", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
        enviar = st.form_submit_button("GUARDAR AVANCE")

    if enviar:
        if not desc or len(fotos) < 3:
            st.error("Faltan campos obligatorios o fotos (mínimo 3)")
        else:
            with st.spinner("Subiendo fotos..."):
                urls = [cloudinary.uploader.upload(f, folder=f"obras/{obra_id_sel}")["secure_url"] for f in fotos]
                ahora_local = datetime.now(local_tz)
                
                db.collection("obras").document(obra_id_sel).collection("avances").add({
                    "fecha": ahora_local.isoformat(),
                    "timestamp": ahora_local,
                    "responsable": resp,
                    "descripcion": desc,
                    "materiales_usados": mats_usados,
                    "costo_total_dia": costo_dia,
                    "fotos": urls
                })
                db.collection("obras").document(obra_id_sel).update({
                    "gasto_acumulado": firestore.Increment(costo_dia)
                })
                st.success("✅ Avance guardado correctamente")
                st.rerun()

# ================= ANÁLISIS ECONÓMICO =================
st.divider()
st.subheader("📊 Resumen de Gastos")

avances_lista = cargar_avances(obra_id_sel)

if not avances_lista:
    st.info("No hay datos registrados aún.")
else:
    acumulado = 0.0
    registros = []
    
    for a in avances_lista:
        costo = float(a.get("costo_total_dia", 0))
        acumulado += costo
        a["_acumulado_momento"] = acumulado
        
        try:
            dt = a.get("timestamp")
            if dt:
                dt = dt.astimezone(local_tz) if dt.tzinfo else pytz.utc.localize(dt).astimezone(local_tz)
            else:
                dt = datetime.fromisoformat(a.get("fecha")).astimezone(local_tz)
            
            a["_dt_local"] = dt
        except: continue

    porcentaje = min(acumulado / presupuesto_referencia, 1.0) if presupuesto_referencia > 0 else 0
    st.write(f"**Gasto Acumulado:** S/ {acumulado:,.2f} de S/ {presupuesto_referencia:,.2f} ({porcentaje*100:.1f}%)")
    st.progress(porcentaje)

# ================= HISTORIAL DE AVANCES =================
st.divider()
st.header("📚 Historial de Avances")

if not avances_lista:
    st.info("No hay registros en el historial.")
else:
    avances_mostrar = avances_lista[::-1]
    for av in avances_mostrar:
        f_dt = av.get("_dt_local")
        f_txt = f_dt.strftime("%d/%m/%Y %H:%M") if f_dt else "Fecha N/D"
        excede = av.get("_acumulado_momento", 0) > presupuesto_referencia
        alerta = "🔴" if excede else "🟢"

        with st.expander(f"{alerta} {f_txt} — {av.get('responsable', 'N/D')}"):
            st.write(f"**Descripción:** {av.get('descripcion', 'Sin descripción')}")
            mats = av.get("materiales_usados")
            if mats:
                st.write("**🧱 Materiales utilizados:**")
                df_m = pd.DataFrame(mats)[["nombre", "cantidad", "unidad", "subtotal"]]
                df_m.columns = ["Material", "Cant.", "Unidad", "Subtotal (S/)"]
                st.table(df_m)
            
            c_col1, c_col2 = st.columns(2)
            c_col1.metric("Costo del día", f"S/ {av.get('costo_total_dia', 0):,.2f}")
            c_col2.metric("Acumulado Obra", f"S/ {av.get('_acumulado_momento', 0):,.2f}")

            fotos = av.get("fotos", [])
            if fotos:
                cols = st.columns(3)
                for i, url in enumerate(fotos):
                    cols[i % 3].image(url, use_container_width=True)
