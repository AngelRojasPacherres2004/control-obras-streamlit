import streamlit as st
from datetime import datetime
import cloudinary.uploader
import firebase_admin
from firebase_admin import credentials, firestore

# ================= SEGURIDAD Y CONEXIÓN =================
if "auth" not in st.session_state:
    st.error("Sesión no válida")
    st.stop()

auth = st.session_state["auth"]

if auth["role"] != "pasante":
    st.warning("Acceso restringido a pasantes")
    st.stop()

db = firestore.client()
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

# ================= FUNCIONES DE PROGRESO =================
def calcular_progreso(obra_id):
    avances = db.collection("obras").document(obra_id).collection("avances").stream()
    total = sum(int(av.to_dict().get("avance_porcentaje", 0)) for av in avances)
    return min(total, 100)

total_avance = calcular_progreso(obra_id)

# ================= SIDEBAR INFORMATIVO =================
with st.sidebar:
    st.header("🏗️ Información de Obra")
    st.markdown(f"**Nombre:** {obra.get('nombre','-')}")
    st.markdown(f"**Ubicación:** {obra.get('ubicacion','-')}")
    st.markdown(f"**Estado:** {obra.get('estado','-')}")
    st.divider()
    st.markdown(f"**Inicio:** {obra.get('fecha_inicio','-')}")
    st.markdown(f"**Fin:** {obra.get('fecha_fin_estimada','-')}")

# ================= UI PRINCIPAL =================
st.title("📝 Parte Diario de Avance")

# Barra de progreso visual
st.subheader(f"📊 Progreso Total: {total_avance}%")
st.progress(total_avance / 100)

if total_avance >= 100:
    st.success("✅ Obra completada al 100%. No se admiten más registros.")
    st.stop()

# ================= MATERIALES DISPONIBLES =================
# Traemos la lista de materiales designados a esta obra
materiales_obra_docs = db.collection("obras").document(obra_id).collection("materiales").stream()
lista_materiales = [{"id": m.id, **m.to_dict()} for m in materiales_obra_docs]

# ================= FORMULARIO DE AVANCE =================
with st.form("form_avance", clear_on_submit=True):
    st.subheader("Datos del Reporte")
    responsable = st.text_input("Responsable del turno", value=username)
    descripcion = st.text_area("Descripción detallada del avance", height=100)
    
    porcentaje_dia = st.number_input(
        "📈 Porcentaje de avance de hoy",
        min_value=0, max_value=100 - total_avance, step=1,
        help="Indica cuánto avanzó la obra hoy (0-100)"
    )

    st.divider()
    st.subheader("🧱 Materiales usados hoy")
    st.caption("Ingresa las cantidades de los materiales utilizados en esta jornada")

    materiales_reportados = []
    costo_total_dia = 0.0

    # Generar inputs dinámicos para cada material designado
    if not lista_materiales:
        st.warning("No hay materiales designados para esta obra.")
    else:
        cols_mat = st.columns(2)
        for i, mat in enumerate(lista_materiales):
            # Alternar entre columnas para ahorrar espacio
            with cols_mat[i % 2]:
                cant = st.number_input(
                    f"{mat['nombre']} ({mat['unidad']})",
                    min_value=0.0, step=0.1, key=f"input_{mat['id']}"
                )
                if cant > 0:
                    sub = cant * float(mat.get("precio_unitario", 0))
                    costo_total_dia += sub
                    materiales_reportados.append({
                        "material_id": mat["id"],
                        "nombre": mat["nombre"],
                        "cantidad": cant,
                        "unidad": mat["unidad"],
                        "subtotal": round(sub, 2)
                    })

    st.info(f"💰 Costo total de materiales hoy: S/ {costo_total_dia:,.2f}")

    st.divider()
    fotos = st.file_uploader("Evidencia fotográfica (mínimo 3)", accept_multiple_files=True, type=["jpg", "png", "jpeg"])

    guardar = st.form_submit_button("🚀 GUARDAR REPORTE DIARIO", use_container_width=True)

# ================= LÓGICA DE GUARDADO =================
if guardar:
    if not responsable.strip() or not descripcion.strip():
        st.error("Por favor, completa el responsable y la descripción.")
    elif not fotos or len(fotos) < 3:
        st.error("Se requiere un mínimo de 3 fotografías.")
    elif porcentaje_dia <= 0 and len(materiales_reportados) == 0:
        st.error("Debes registrar al menos un porcentaje de avance o uso de materiales.")
    else:
        with st.spinner("Procesando reporte..."):
            # 1. Subir fotos a Cloudinary
            urls = []
            for f in fotos:
                res = cloudinary.uploader.upload(f, folder=f"obras/{obra_id}/avances")
                urls.append(res["secure_url"])

            # 2. Preparar el documento de avance
            datos_avance = {
                "fecha": datetime.now().isoformat(),
                "timestamp": datetime.now(),
                "usuario": username,
                "responsable": responsable,
                "observaciones": descripcion,
                "avance_porcentaje": porcentaje_dia,
                "materiales_usados": materiales_reportados,
                "costo_materiales_dia": round(costo_total_dia, 2),
                "fotos": urls
            }

            # 3. Guardar en Firebase
            db.collection("obras").document(obra_id).collection("avances").add(datos_avance)
            
            # 4. También guardar en materiales_usados (opcional, para históricos globales)
            for m in materiales_reportados:
                db.collection("obras").document(obra_id).collection("materiales_usados").add({
                    **m, "fecha": datetime.now(), "usuario": username
                })

            st.success("✅ Avance y materiales registrados con éxito.")
            st.rerun()

# ================= HISTORIAL DE AVANCES =================
st.divider()
st.subheader("📂 Historial de Avances")

avances_docs = db.collection("obras").document(obra_id).collection("avances").order_by("fecha", direction=firestore.Query.DESCENDING).limit(10).stream()

for av in avances_docs:
    data = av.to_dict()
    f = datetime.fromisoformat(data["fecha"])
    with st.expander(f"📅 {f:%d/%m/%Y %H:%M} — {data.get('responsable')} (+{data.get('avance_porcentaje')}% )"):
        st.write(f"**Descripción:** {data.get('observaciones')}")
        
        if data.get("materiales_usados"):
            st.markdown("**Materiales reportados:**")
            for m in data["materiales_usados"]:
                st.caption(f"• {m['nombre']}: {m['cantidad']} {m['unidad']} (S/ {m['subtotal']})")
        
        # Galería de fotos
        if data.get("fotos"):
            cols_img = st.columns(3)
            for idx, img_url in enumerate(data["fotos"]):
                cols_img[idx % 3].image(img_url, use_container_width=True)