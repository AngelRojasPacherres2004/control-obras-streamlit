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
    st.write(f"**Ubicación:** {obra.get('ubicacion', 'Sin ubicación')}")
    st.write(f"**Estado:** {obra.get('estado', 'Pendiente')}")
    st.divider()
    
    # Manejo de fechas para el sidebar
    f_inicio = obra.get("fecha_inicio")
    f_fin = obra.get("fecha_fin_estimada") # Ajustado al nombre común
    
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

# ================= MÉTRICAS =================
col1, col2, col3 = st.columns(3)
col1.metric("💰 Presupuesto", f"S/ {presupuesto_total:,.0f}")
col2.metric("🔥 Gasto", f"S/ {gasto_actual:,.0f}")
porcentaje = round((gasto_actual / presupuesto_total) * 100, 1) if presupuesto_total else 0
col3.metric("📊 Ejecutado", f"{porcentaje}%")

st.divider()

# ================= UI FORMULARIO =================
st.title("📝 Parte Diario")

with st.form("form_avance", clear_on_submit=True):
    responsable = st.text_input("Responsable", value=username)
    descripcion = st.text_area("Descripción del avance", height=100)
    
    st.subheader("🧱 Registro de Materiales Usados")
    st.caption("Ingrese la cantidad para cada material utilizado hoy")
    
    # Diccionario para capturar inputs dinámicos
    inputs_materiales = {}
    
    # Crear una fila por cada material
    for mat in materiales_disponibles:
        col_m, col_c = st.columns([3, 1])
        col_m.write(f"**{mat['nombre']}** ({mat['unidad']})")
        # Usamos una key única para cada input basada en el ID del documento
        cant = col_c.number_input("Cant.", min_value=0.0, step=0.5, key=f"input_{mat['doc_id']}")
        if cant > 0:
            inputs_materiales[mat['doc_id']] = {
                "nombre": mat['nombre'],
                "unidad": mat['unidad'],
                "cantidad": cant,
                "precio_unitario": float(mat.get("precio_unitario", 0))
            }

    st.divider()
    fotos = st.file_uploader("Subir fotos (mínimo 3)", accept_multiple_files=True, type=["jpg", "png", "jpeg"])
    
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
            # 1. Subir fotos
            urls = []
            for f in fotos:
                res = cloudinary.uploader.upload(f, folder=f"obras/{obra_id}/avances")
                urls.append(res["secure_url"])

            costo_total_dia = 0
            
            # 2. Guardar cada material usado y calcular costo total
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

            # 3. Guardar el avance general
            ref_avance = db.collection("obras").document(obra_id).collection("avances").document()
            batch.set(ref_avance, {
                "fecha": datetime.now().isoformat(),
                "timestamp": datetime.now(),
                "usuario": username,
                "responsable": responsable,
                "observaciones": descripcion,
                "costo_total_dia": costo_total_dia,
                "fotos": urls
            })
            
            batch.commit()
            st.success("✅ Parte diario guardado correctamente")
            st.rerun()

# ================= HISTORIAL =================
st.subheader("📂 Historial Reciente")
avances_docs = db.collection("obras").document(obra_id).collection("avances").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(10).stream()

for av in avances_docs:
    d = av.to_dict()
    f = datetime.fromisoformat(d["fecha"])
    with st.expander(f"📅 {f:%d/%m/%Y %H:%M} — {d.get('responsable')}"):
        st.write(d.get("observaciones"))
        st.info(f"💰 Costo reportado: S/ {d.get('costo_total_dia', 0):,.2f}")
        
        # Mostrar imágenes en columnas
        if d.get("fotos"):
            cols = st.columns(3)
            for idx, img in enumerate(d["fotos"]):
                cols[idx % 3].image(img, use_container_width=True)