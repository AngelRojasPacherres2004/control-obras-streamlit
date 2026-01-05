import streamlit as st
import pandas as pd
from datetime import datetime, date
import cloudinary.uploader
from firebase_admin import firestore

# ================= CONFIG =================
st.set_page_config(page_title="Parte Diario", layout="centered")
db = firestore.client()

# ================= SEGURIDAD =================
if "auth" not in st.session_state:
    st.error("Sesión no válida")
    st.stop()

auth = st.session_state["auth"]

if auth.get("role") != "pasante":
    st.warning("Acceso solo para pasantes")
    st.stop()

obra_id = auth.get("obra")
username = auth.get("username", "desconocido")

if not obra_id:
    st.error("No tienes una obra asignada")
    st.stop()

# ================= DATOS DE LA OBRA =================
obra_doc = db.collection("obras").document(obra_id).get()
if not obra_doc.exists:
    st.error("La obra asignada no existe")
    st.stop()

obra = obra_doc.to_dict()

# ================= SIDEBAR (DETALLES DE OBRA) =================
with st.sidebar:
    st.header("🏗️ Información de la Obra")
    st.write(f"**Nombre:** {obra.get('nombre', 'Sin nombre')}")
    st.write(f"**Estado:** {obra.get('estado', 'Pendiente')}")
    st.divider()
    
    f_inicio = obra.get("fecha_inicio")
    f_fin = obra.get("fecha_fin_estimada")
    
    st.write(f"📅 **Inicio:** {f_inicio.strftime('%d/%m/%Y') if hasattr(f_inicio, 'date') else f_inicio}")
    st.write(f"🏁 **Fin Estimado:** {f_fin.strftime('%d/%m/%Y') if hasattr(f_fin, 'date') else f_fin}")

# ================= MATERIALES ASIGNADOS =================
mats_admin_docs = db.collection("obras").document(obra_id).collection("materiales").stream()

materiales_disponibles = []
presupuesto_total = 0.0

for m in mats_admin_docs:
    d = m.to_dict()
    d["doc_id"] = m.id
    materiales_disponibles.append(d)
    presupuesto_total += float(d.get("subtotal", 0))

if not materiales_disponibles:
    st.warning("La obra no tiene materiales asignados")
    st.stop()

# ================= GASTO ACUMULADO =================
usados_docs = db.collection("obras").document(obra_id).collection("materiales_usados").stream()
gasto_actual = sum(float(u.to_dict().get("subtotal", 0)) for u in usados_docs)

# ================= MÉTRICAS Y SEMÁFORO =================
st.subheader("📊 Estado Financiero")
porcentaje_ejecutado = (gasto_actual / presupuesto_total) * 100 if presupuesto_total else 0

# Lógica de Semáforo
if porcentaje_ejecutado < 80:
    color_semaforo = "green"
    mensaje_semaforo = "🟢 Dentro del presupuesto"
elif 80 <= porcentaje_ejecutado <= 100:
    color_semaforo = "orange"
    mensaje_semaforo = "🟡 Alerta: Presupuesto próximo al límite"
else:
    color_semaforo = "red"
    mensaje_semaforo = "🔴 Crítico: Presupuesto excedido"

st.markdown(f"### {mensaje_semaforo}")

col1, col2, col3 = st.columns(3)
col1.metric("💰 Presupuesto", f"S/ {presupuesto_total:,.0f}")
col2.metric("🔥 Gasto Total", f"S/ {gasto_actual:,.0f}", delta=f"{porcentaje_ejecutado:.1f}%", delta_color="inverse" if porcentaje_ejecutado > 100 else "normal")
col3.metric("📈 Saldo Disp.", f"S/ {max(0, presupuesto_total - gasto_actual):,.0f}")

st.progress(min(porcentaje_ejecutado / 100, 1.0))

st.divider()

# ================= UI FORMULARIO =================
st.title("📝 Nuevo Registro de Avance")

with st.form("form_avance", clear_on_submit=True):
    responsable = st.text_input("Responsable", value=username)
    descripcion = st.text_area("Descripción detallada del trabajo realizado", height=100)
    
    st.subheader("🧱 Materiales Utilizados Hoy")
    inputs_materiales = {}
    
    for mat in materiales_disponibles:
        col_m, col_c = st.columns([3, 1])
        col_m.write(f"**{mat['nombre']}** ({mat['unidad']})")
        cant = col_c.number_input("Cant.", min_value=0.0, step=0.5, key=f"input_{mat['doc_id']}")
        if cant > 0:
            inputs_materiales[mat['doc_id']] = {
                "nombre": mat['nombre'],
                "unidad": mat['unidad'],
                "cantidad": cant,
                "precio_unitario": float(mat.get("precio_unitario", 0))
            }

    st.divider()
    fotos = st.file_uploader("Evidencia fotográfica (mínimo 3)", accept_multiple_files=True, type=["jpg", "png", "jpeg"])
    
    guardar = st.form_submit_button("🚀 GUARDAR REPORTE DIARIO", use_container_width=True)

# ================= GUARDAR LÓGICA =================
if guardar:
    if not responsable.strip() or not descripcion.strip():
        st.error("Responsable y descripción son obligatorios")
    elif not inputs_materiales:
        st.error("Debe registrar al menos 1 material usado")
    elif not fotos or len(fotos) < 3:
        st.error("Debes subir al menos 3 fotos")
    else:
        with st.spinner("Subiendo fotos y guardando registros..."):
            urls = []
            for f in fotos:
                res = cloudinary.uploader.upload(f, folder=f"obras/{obra_id}/avances")
                urls.append(res["secure_url"])

            costo_total_dia = 0
            batch = db.batch()
            
            for m_id, m_data in inputs_materiales.items():
                subtotal_m = round(m_data["cantidad"] * m_data["precio_unitario"], 2)
                costo_total_dia += subtotal_m
                
                ref_usados = db.collection("obras").document(obra_id).collection("materiales_usados").document()
                batch.set(ref_usados, {
                    "fecha": datetime.now(),
                    "material_doc_id": m_id,
                    "nombre": m_data["nombre"],
                    "unidad": m_data["unidad"],
                    "cantidad": m_data["cantidad"],
                    "precio_unitario": m_data["precio_unitario"],
                    "subtotal": subtotal_m,
                    "usuario": username
                })

            # Cálculo de impacto en el progreso para este avance específico
            progreso_este_avance = (costo_total_dia / presupuesto_total) * 100 if presupuesto_total else 0

            ref_avance = db.collection("obras").document(obra_id).collection("avances").document()
            batch.set(ref_avance, {
                "fecha": datetime.now().isoformat(),
                "timestamp": datetime.now(),
                "usuario": username,
                "responsable": responsable,
                "observaciones": descripcion,
                "costo_total_dia": costo_total_dia,
                "porcentaje_avance_financiero": round(progreso_este_avance, 2),
                "fotos": urls
            })
            
            batch.commit()
            st.success(f"✅ Reporte guardado. Este avance representa el {progreso_este_avance:.2f}% del presupuesto.")
            st.rerun()

# ================= HISTORIAL CON PROGRESO =================
st.subheader("📂 Historial de Avances (Últimos 10)")
avances_docs = db.collection("obras").document(obra_id).collection("avances").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(10).stream()

for av in avances_docs:
    d = av.to_dict()
    f = datetime.fromisoformat(d["fecha"])
    prog_avance = d.get('porcentaje_avance_financiero', 0)
    
    # Encabezado del expander con porcentaje de progreso incluido
    with st.expander(f"📅 {f:%d/%m/%Y %H:%M} | 📈 Progreso: {prog_avance}% | Responsable: {d.get('responsable')}"):
        st.write(f"**Descripción:** {d.get('observaciones')}")
        
        # Indicador visual de progreso dentro del historial
        st.write(f"**Impacto presupuestario del día:** S/ {d.get('costo_total_dia', 0):,.2f}")
        st.progress(min(prog_avance / 100, 1.0))
        
        if d.get("fotos"):
            cols = st.columns(3)
            for idx, img in enumerate(d["fotos"]):
                cols[idx % 3].image(img, use_container_width=True)