import streamlit as st
import pandas as pd
from datetime import datetime, date
import pytz  # <--- SE AGREGA ESTA LIBRERÍA (Instalar con: pip install pytz)
import cloudinary.uploader
from firebase_admin import firestore

# 1. CONFIGURAR TU ZONA HORARIA (Cambia 'America/Lima' por tu ciudad si es necesario)
# Ejemplos: 'America/Lima', 'America/Bogota', 'America/Mexico_City'
pais_tz = pytz.timezone('America/Lima')

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

# ================= DATOS OBRA =================
obra_ref = db.collection("obras").document(obra_id)
obra_doc = obra_ref.get()

if not obra_doc.exists:
    st.error("La obra asignada no existe")
    st.stop()

obra = obra_doc.to_dict()

# ================= FECHAS (Para validación de estado) =================
# 2. USAR LA FECHA DE TU PAÍS AQUÍ TAMBIÉN
hoy = datetime.now(pais_tz).date() 
fecha_inicio = obra.get("fecha_inicio")
fecha_fin = obra.get("fecha_fin_estimado")

if fecha_inicio and hasattr(fecha_inicio, "date"):
    fecha_inicio = fecha_inicio.date()
if fecha_fin and hasattr(fecha_fin, "date"):
    fecha_fin = fecha_fin.date()

fuera_fecha_hoy = False
if fecha_inicio and fecha_fin:
    fuera_fecha_hoy = hoy < fecha_inicio or hoy > fecha_fin

# ================= SIDEBAR =================
with st.sidebar:
    st.header("🏗️ Obra asignada")
    st.write(f"**Nombre:** {obra.get('nombre')}")
    st.write(f"**Estado:** {obra.get('estado')}")
    st.write(f"📅 Inicio: {fecha_inicio}")
    st.write(f"🏁 Fin estimado: {fecha_fin}")

# ================= MATERIALES =================
materiales = []
presupuesto_total = 0.0

for m in obra_ref.collection("materiales").stream():
    d = m.to_dict()
    d["doc_id"] = m.id
    materiales.append(d)
    presupuesto_total += float(d.get("subtotal", 0))

if not materiales:
    st.warning("La obra no tiene materiales asignados")
    st.stop()

# ================= GASTO =================
gasto_acumulado = float(obra.get("gasto_acumulado", 0))
excede_presupuesto = gasto_acumulado > presupuesto_total if presupuesto_total else False
porcentaje_total = (gasto_acumulado / presupuesto_total) * 100 if presupuesto_total else 0

# ================= MÉTRICAS =================
st.subheader("📊 Estado Financiero")
st.metric("💰 Presupuesto total", f"S/ {presupuesto_total:,.2f}")
st.metric("🔥 Gasto acumulado", f"S/ {gasto_acumulado:,.2f}")
st.metric("📈 % ejecutado", f"{porcentaje_total:.2f}%")
st.progress(min(porcentaje_total / 100, 1.0))

if excede_presupuesto:
    st.error("🔴 Estado Actual: Presupuesto excedido")
elif fuera_fecha_hoy:
    st.warning("🟠 Estado Actual: Fuera de rango de fechas")
else:
    st.success("🟢 Estado Actual: En regla")

st.divider()

# ================= FORMULARIO =================
st.title("📝 Registrar avance diario")

with st.form("form_avance", clear_on_submit=True):
    responsable = st.text_input("Responsable", value=username)
    descripcion = st.text_area("Descripción del trabajo", height=100)

    st.subheader("🧱 Materiales usados hoy")
    materiales_para_historial = [] 
    costo_total_dia = 0.0

    for mat in materiales:
        col1, col2 = st.columns([3, 1])
        col1.write(f"**{mat['nombre']}** ({mat['unidad']})")
        cantidad = col2.number_input("Cant.", min_value=0.0, step=1.0, key=f"mat_{mat['doc_id']}")

        if cantidad > 0:
            subtotal = cantidad * mat["precio_unitario"]
            costo_total_dia += subtotal
            
            item = {
                "nombre": mat["nombre"],
                "unidad": mat["unidad"],
                "cantidad": cantidad,
                "precio_unitario": mat["precio_unitario"],
                "subtotal": round(subtotal, 2)
            }
            materiales_para_historial.append(item)

    st.info(f"💰 Costo del día: S/ {costo_total_dia:.2f}")
    fotos = st.file_uploader("Fotos (mínimo 3)", accept_multiple_files=True, type=["jpg", "png", "jpeg"])
    guardar = st.form_submit_button("Guardar avance")

# ================= GUARDAR =================
if guardar:
    if not responsable.strip() or not descripcion.strip():
        st.error("Responsable y descripción son obligatorios")
    elif not materiales_para_historial:
        st.error("Debes usar al menos un material")
    elif not fotos or len(fotos) < 3:
        st.error("Debes subir mínimo 3 fotos")
    else:
        urls = []
        for f in fotos:
            res = cloudinary.uploader.upload(f, folder=f"obras/{obra_id}/avances")
            urls.append(res["secure_url"])

        # 3. GUARDAR CON LA HORA EXACTA DE TU PAÍS
        ahora_mi_pais = datetime.now(pais_tz)

        obra_ref.collection("avances").add({
            "timestamp": ahora_mi_pais, # <--- HORA DE TU PAÍS
            "usuario": username,
            "responsable": responsable,
            "observaciones": descripcion,
            "costo_total_dia": round(costo_total_dia, 2),
            "detalle_materiales": materiales_para_historial,
            "porcentaje_avance_financiero": round((costo_total_dia / presupuesto_total) * 100 if presupuesto_total else 0, 2),
            "fotos": urls
        })

        # Actualizar total
        total_docs = obra_ref.collection("avances").stream()
        nuevo_total = sum(float(a.to_dict().get("costo_total_dia", 0)) for a in total_docs)

        obra_ref.update({
            "gasto_acumulado": round(nuevo_total, 2),
            "ultima_actualizacion": firestore.SERVER_TIMESTAMP
        })

        st.success("✅ Avance registrado correctamente")
        st.rerun()

# ================= HISTORIAL DETALLADO =================
st.divider()
st.subheader("📂 Historial de avances")

avances_todos = obra_ref.collection("avances").order_by("timestamp", direction=firestore.Query.ASCENDING).stream()

lista_avances = []
acumulado_paso_a_paso = 0.0

for av in avances_todos:
    d = av.to_dict()
    
    # --- AJUSTE DE HORA AL LEER ---
    ts = d.get("timestamp")
    # Si la fecha viene de Firebase, la convertimos a la zona horaria de tu país para mostrarla bien
    if ts and hasattr(ts, "astimezone"):
        ts = ts.astimezone(pais_tz)
        d["timestamp"] = ts # Actualizamos el diccionario con la hora corregida

    costo_dia = float(d.get("costo_total_dia", 0))
    acumulado_paso_a_paso += costo_dia
    d["excede_en_su_momento"] = acumulado_paso_a_paso > presupuesto_total
    d["acumulado_al_momento"] = acumulado_paso_a_paso
    lista_avances.append(d)

lista_avances.reverse()

if not lista_avances:
    st.info("Aún no hay avances registrados.")
else:
    for d in lista_avances:
        ts = d.get("timestamp")
        # Ya no usamos .date() solo, mantenemos el objeto ts que ya está en tu zona horaria
        fecha_av = ts.date() if ts else None
        
        fuera_fecha = False
        if fecha_av and fecha_inicio and fecha_fin:
            fuera_fecha = fecha_av < fecha_inicio or fecha_av > fecha_fin

        alerta = "🔴" if (fuera_fecha or d["excede_en_su_momento"]) else "🟢"
        prog = d.get("porcentaje_avance_financiero", 0)

        with st.expander(f"{alerta} {ts:%d/%m/%Y %H:%M} | 📈 {prog}% | {d.get('responsable')}"):
            st.write(f"**Descripción:** {d.get('observaciones')}")
            
            st.write("**🧱 Materiales utilizados en este reporte:**")
            detalles = d.get("detalle_materiales", [])
            if detalles:
                df_mats = pd.DataFrame(detalles)
                df_mats = df_mats[['nombre', 'cantidad', 'unidad', 'subtotal']]
                df_mats.columns = ['Material', 'Cant.', 'Unidad', 'Subtotal (S/)']
                st.table(df_mats)
            else:
                st.caption("No se encontró detalle de materiales.")

            col_met1, col_met2 = st.columns(2)
            col_met1.metric("Costo del día", f"S/ {d.get('costo_total_dia', 0):,.2f}")
            col_met2.metric("Acumulado obra", f"S/ {d['acumulado_al_momento']:,.2f}")
            
            st.write("**🖼️ Evidencia fotográfica:**")
            fotos_list = d.get("fotos", [])
            if fotos_list:
                cols_fotos = st.columns(3)
                for i, url in enumerate(fotos_list):
                    cols_fotos[i % 3].image(url, use_container_width=True)