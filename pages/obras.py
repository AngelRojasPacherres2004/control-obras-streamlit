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

# ================= FORMULARIO CREAR OBRA =================
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
       
        
        p_materiales = 0.0
        p_mano_obra = 0.0
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
                    "presupuesto_materiales": p_materiales,
                    "presupuesto_total": p_total,
                    "gasto_acumulado": 0,
                    "gastos_adicionales": 0,
                    "creado_en": ahora_obra
                })
                st.session_state["crear_obra"] = False
                st.success("Obra creada exitosamente")
                st.rerun()
        if col_c.form_submit_button("❌ Cancelar"):
            st.session_state["crear_obra"] = False
            st.rerun()
    st.stop()

# ================= INFORMACIÓN DE LA OBRA (MÉTRICAS DOBLES) =================
if not obra_id_sel:
    st.info("Selecciona o crea una obra para comenzar.")
    st.stop()

doc_ref = db.collection("obras").document(obra_id_sel).get()
obra_data = doc_ref.to_dict()

st.subheader(f"🏗️ {obra_data.get('nombre')}")
st.caption(f"📍 {obra_data.get('ubicacion')} | 📌 {obra_data.get('estado')}")

# --- LÓGICA DE CÁLCULOS (CORREGIDA) ---
# 1. Caja Chica
p_caja_ini = float(obra_data.get("presupuesto_caja_chica", 0))
g_caja_uso = float(obra_data.get("gastos_adicionales", 0))
p_caja_act = p_caja_ini - g_caja_uso

# 2. Materiales
p_mats_ini = float(obra_data.get("presupuesto_materiales", 0))
g_mats_uso = float(obra_data.get("gasto_acumulado", 0)) 
p_mats_act = p_mats_ini - g_mats_uso

# 3. Mano de Obra
p_mano_ini = float(obra_data.get("presupuesto_mano_obra", 0))
g_mano_uso = float(obra_data.get("gasto_mano_obra", 0)) # <--- Obtenido de Firebase
p_mano_act = p_mano_ini - g_mano_uso # <--- Esto debería ser 0 si p = g

# 4. Totales
p_total_ini = float(obra_data.get("presupuesto_total", 0))
# El total disponible es la suma de lo que queda en cada rubro
p_total_act = p_caja_act + p_mats_act + p_mano_act

# --- DISEÑO DE MÉTRICAS (INICIAL ARRIBA / ACTUAL ABAJO) ---
m1, m2, m3, m4 = st.columns(4)

with m1:
    st.metric("📦 Caja Chica (Inicial)", f"S/ {p_caja_ini:,.2f}")
    st.metric("Caja Chica (Actual)", f"S/ {p_caja_act:,.2f}", 
              delta=f"- S/ {g_caja_uso:,.2f}", delta_color="inverse")

with m2:
    st.metric("👷 Mano Obra (Inicial)", f"S/ {p_mano_ini:,.2f}")
    st.metric("Mano Obra (Actual)", f"S/ {p_mano_act:,.2f}",
              delta=f"- S/ {g_mano_uso:,.2f}", delta_color="inverse")

with m3:
    st.metric("🧱 Materiales (Inicial)", f"S/ {p_mats_ini:,.2f}")
    st.metric("Materiales (Actual)", f"S/ {p_mats_act:,.2f}", 
              delta=f"- S/ {g_mats_uso:,.2f}", delta_color="inverse")

with m4:
    st.metric("💰 Total Obra (Inicial)", f"S/ {p_total_ini:,.2f}")
    st.metric("Total Disponible", f"S/ {p_total_act:,.2f}", 
              delta=f"{(p_total_act/p_total_ini*100) if p_total_ini > 0 else 0:.1f}%")

# ================= REGISTRAR AVANCE (PASANTE) =================
if auth["role"] == "pasante":
    st.divider()
    st.header("📝 Registrar Avance Diario")
    
    materiales_ref = db.collection("obras").document(obra_id_sel).collection("materiales").stream()
    lista_mats = [m.to_dict() for m in materiales_ref]

    with st.form("nuevo_avance", clear_on_submit=True):
        resp = st.text_input("Responsable", value=auth.get("username", ""))
        desc = st.text_area("Descripción del trabajo")
        
        col_av1, col_av2 = st.columns(2)
        prob_input = col_av1.text_area("⚠️ Problemática (Opcional)")
        sol_input = col_av2.text_area("✅ Solución (Opcional)")
        
        gasto_caja_input = st.number_input("💰 Gasto Extra (Caja Chica S/)", min_value=0.0, step=10.0)
        
        st.write("🧱 **Materiales usados hoy:**")
        mats_usados = []
        costo_dia_mats = 0.0
        
        for m in lista_mats:
            c1, c2 = st.columns([3, 1])
            cant = c2.number_input(f"{m['nombre']} ({m['unidad']})", min_value=0.0, key=f"form_{m['nombre']}")
            if cant > 0:
                subt = round(cant * m.get("precio_unitario", 0), 2)
                costo_dia_mats += subt
                mats_usados.append({
                    "nombre": m['nombre'], "unidad": m['unidad'],
                    "cantidad": cant, "precio_unitario": m.get("precio_unitario", 0),
                    "subtotal": subt
                })
        
        st.info(f"Costo Materiales: S/ {costo_dia_mats:.2f} | Gasto Caja: S/ {gasto_caja_input:.2f}")
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
                    "problematica": prob_input,
                    "solucion": sol_input,
                    "gasto_adicional": gasto_caja_input,
                    "materiales_usados": mats_usados,
                    "costo_total_dia": costo_dia_mats,
                    "fotos": urls
                })
                
                # Actualizar acumulados de la obra
                db.collection("obras").document(obra_id_sel).update({
                    "gasto_acumulado": firestore.Increment(costo_dia_mats),
                    "gastos_adicionales": firestore.Increment(gasto_caja_input)
                })
                st.success("✅ Avance guardado correctamente")
                st.rerun()

# ================= ANÁLISIS ECONÓMICO =================
st.divider()
st.subheader("📊 Resumen de Gastos")

avances_lista = cargar_avances(obra_id_sel)

if avances_lista:
    total_gastado = float(obra_data.get("gasto_acumulado", 0)) + float(obra_data.get("gastos_adicionales", 0))
    porcentaje = min(total_gastado / p_total_ini, 1.0) if p_total_ini > 0 else 0
    st.write(f"**Gasto Real Total (Materiales + Caja):** S/ {total_gastado:,.2f} de S/ {p_total_ini:,.2f} ({porcentaje*100:.1f}%)")
    st.progress(porcentaje)

# ================= HISTORIAL DE AVANCES (CON PROBLEMÁTICA Y CAJA) =================
st.divider()
st.header("📚 Historial de Avances")

if not avances_lista:
    st.info("No hay registros en el historial.")
else:
    avances_mostrar = avances_lista[::-1]
    for av in avances_mostrar:
        try:
            dt = av.get("timestamp")
            f_txt = dt.astimezone(local_tz).strftime("%d/%m/%Y %H:%M") if dt else "Fecha N/D"
        except: f_txt = "Fecha N/D"

        with st.expander(f"📅 {f_txt} — {av.get('responsable', 'N/D')}"):
            st.write(f"**Descripción:** {av.get('descripcion', 'Sin descripción')}")
            
            # --- SECCIÓN DE PROBLEMÁTICA Y SOLUCIÓN ---
            col_h1, col_h2 = st.columns(2)
            prob = av.get("problematica")
            sol = av.get("solucion")
            
            if prob:
                col_h1.warning(f"**⚠️ Problemática:**\n\n{prob}")
            if sol:
                col_h2.success(f"**✅ Solución:**\n\n{sol}")
                
            # --- SECCIÓN DE MATERIALES ---
            mats = av.get("materiales_usados")
            if mats:
                st.write("**🧱 Materiales utilizados:**")
                df_m = pd.DataFrame(mats)[["nombre", "cantidad", "unidad", "subtotal"]]
                df_m.columns = ["Material", "Cant.", "Unidad", "Subtotal (S/)"]
                st.table(df_m)
            
            # --- MÉTRICAS DEL DÍA ---
            c_col1, c_col2 = st.columns(2)
            c_col1.metric("Costo Materiales", f"S/ {av.get('costo_total_dia', 0):,.2f}")
            c_col2.metric("Gasto Caja Chica", f"S/ {av.get('gasto_adicional', 0):,.2f}")
            
            # --- FOTOS ---
            fotos = av.get("fotos", [])
            if fotos:
                cols = st.columns(3)
                for i, url in enumerate(fotos):
                    cols[i % 3].image(url, use_container_width=True)