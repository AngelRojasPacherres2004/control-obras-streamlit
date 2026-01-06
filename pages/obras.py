import streamlit as st
import pandas as pd
from datetime import datetime, date
import cloudinary
import cloudinary.uploader
from firebase_admin import firestore
import calendar
from collections import defaultdict

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

st.set_page_config(page_title="Obras", layout="wide")
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
        .order_by("timestamp", direction=firestore.Query.DESCENDING)
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

if not OBRAS and auth["role"] != "jefe":
    st.warning("No hay obras creadas.")
    st.stop()

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
        presupuesto_inicial = st.number_input("Presupuesto Total (S/)", min_value=0.0)
        
        col_g, col_c = st.columns(2)
        guardar = col_g.form_submit_button("💾 Guardar Obra")
        cancelar = col_c.form_submit_button("❌ Cancelar")

    if guardar:
        if not nombre:
            st.error("El nombre es obligatorio")
        else:
            oid = nombre.lower().strip().replace(" ", "_")
            db.collection("obras").document(oid).set({
                "nombre": nombre,
                "ubicacion": ubicacion,
                "estado": estado,
                "fecha_inicio": datetime.combine(f_inicio, datetime.min.time()),
                "fecha_fin_estimado": datetime.combine(f_fin, datetime.min.time()),
                "presupuesto_total": presupuesto_inicial,
                "gasto_acumulado": 0,
                "creado_en": datetime.now()
            })
            st.session_state["crear_obra"] = False
            st.success("Obra creada")
            st.rerun()
    if cancelar:
        st.session_state["crear_obra"] = False
        st.rerun()
    st.stop()

# ================= INFORMACIÓN DE LA OBRA =================
doc_ref = db.collection("obras").document(obra_id_sel).get()
if not doc_ref.exists:
    st.error("La obra seleccionada no existe.")
    st.stop()

obra_data = doc_ref.to_dict()
st.subheader(f"🏗️ {obra_data.get('nombre')}")
st.caption(f"📍 {obra_data.get('ubicacion')} | 📌 {obra_data.get('estado')}")

# ================= REGISTRAR AVANCE (PASANTE) =================
if auth["role"] == "pasante":
    st.divider()
    st.header("📝 Registrar Avance Diario")
    
    # Obtener materiales para el formulario
    materiales_ref = db.collection("obras").document(obra_id_sel).collection("materiales").stream()
    lista_mats = [m.to_dict() for m in materiales_ref]

    with st.form("nuevo_avance", clear_on_submit=True):
        resp = st.text_input("Responsable", value=auth.get("username", ""))
        desc = st.text_area("Descripción del trabajo")
        
        st.write("🧱 **Materiales usados:**")
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
                
                db.collection("obras").document(obra_id_sel).collection("avances").add({
                    "fecha": datetime.now().isoformat(),
                    "timestamp": datetime.now(),
                    "responsable": resp,
                    "descripcion": desc,
                    "materiales_usados": mats_usados,
                    "costo_total_dia": costo_dia,
                    "fotos": urls
                })
                # Actualizar acumulado
                db.collection("obras").document(obra_id_sel).update({
                    "gasto_acumulado": firestore.Increment(costo_dia)
                })
                st.success("✅ Avance guardado correctamente")
                st.rerun()

# ================= DASHBOARD ECONÓMICO =================
st.divider()
st.subheader("📊 Análisis de Costos")

avances_raw = cargar_avances(obra_id_sel)

if not avances_raw:
    st.info("No hay datos suficientes para mostrar gráficos.")
else:
    # PROCESAMIENTO SEGURO DE DATOS
    registros = []
    for a in avances_raw:
        # Evitar KeyError si "fecha" no existe
        fecha_str = a.get("fecha")
        try:
            dt = datetime.fromisoformat(fecha_str) if fecha_str else a.get("timestamp")
            if not dt: continue
            
            registros.append({
                "fecha": dt,
                "semana": dt.isocalendar()[1],
                "mes": dt.month,
                "costo": float(a.get("costo_total_dia", 0)),
                "dia_nombre": dt.strftime("%A")
            })
        except:
            continue

    if registros:
        df = pd.DataFrame(registros)
        
        c1, c2 = st.columns(2)
        sem_sel = c1.selectbox("📆 Ver Semana", sorted(df["semana"].unique(), reverse=True))
        modo = st.radio("Filtro de Tiempo", ["Semana Completa", "Mensual"], horizontal=True)

        if modo == "Semana Completa":
            # Incluye de Lunes a Domingo
            dias_semana = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            dias_es = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
            
            df_sem = df[df["semana"] == sem_sel]
            costos_dia = df_sem.groupby("dia_nombre")["costo"].sum().reindex(dias_semana, fill_value=0)
            
            chart_df = pd.DataFrame({"Día": dias_es, "Gasto (S/)": costos_dia.values}).set_index("Día")
            st.bar_chart(chart_df)
        else:
            costos_mes = df.groupby("mes")["costo"].sum().reindex(range(1, 13), fill_value=0)
            chart_mes = pd.DataFrame({
                "Mes": [MESES_ES[m] for m in range(1, 13)],
                "Gasto (S/)": costos_mes.values
            }).set_index("Mes")
            st.bar_chart(chart_mes)

        # Progreso Económico
        presu = float(obra_data.get("presupuesto_total", 0))
        gastado = df["costo"].sum()
        porcentaje = min(gastado / presu, 1.0) if presu > 0 else 0
        
        st.write(f"**Progreso del Presupuesto:** {porcentaje*100:.1f}%")
        st.progress(porcentaje)
        st.caption(f"S/ {gastado:,.2f} gastados de S/ {presu:,.2f} presupuestados")

# ================= HISTORIAL DE AVANCES =================
st.divider()
st.header("📚 Historial de Avances")

if not avances_raw:
    st.info("No hay registros en el historial.")
else:
    for av in avances_raw:
        # Validación de fecha para el expander
        f_raw = av.get("fecha")
        try:
            f_dt = datetime.fromisoformat(f_raw) if f_raw else av.get("timestamp")
            f_txt = f_dt.strftime("%d/%m/%Y %H:%M")
        except:
            f_txt = "Fecha no disponible"

        with st.expander(f"📅 {f_txt} — {av.get('responsable', 'Sin responsable')}"):
            st.write(f"**Descripción:** {av.get('descripcion', av.get('observaciones', 'S/D'))}")
            
            # Tabla de materiales usados
            m_usados = av.get("materiales_usados", [])
            if m_usados:
                st.write("**🧱 Materiales:**")
                df_m = pd.DataFrame(m_usados)[["nombre", "cantidad", "unidad", "subtotal"]]
                st.table(df_m)
            
            # Fotos
            fotos_lista = av.get("fotos", [])
            if fotos_lista:
                cols = st.columns(3)
                for i, url in enumerate(fotos_lista):
                    cols[i % 3].image(url, use_container_width=True)
            else:
                st.caption("No hay fotos en este registro.")