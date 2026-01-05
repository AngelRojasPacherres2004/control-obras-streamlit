import streamlit as st
import pandas as pd
from datetime import datetime, date
import cloudinary
import cloudinary.uploader
from firebase_admin import firestore
import calendar
from collections import defaultdict
MESES_ES = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre"
}

# ================= CLOUDINARY =================
cloudinary.config(
    cloud_name=st.secrets["cloudinary"]["cloud_name"],
    api_key=st.secrets["cloudinary"]["api_key"],
    api_secret=st.secrets["cloudinary"]["api_secret"],
    secure=True
)

# ================= STREAMLIT =================
st.set_page_config(page_title="Obras", layout="wide")
st.title("👷 CRUD de Obras")
st.info("Aquí se administran las obras y su historial")

db = firestore.client()

# ================= FUNCIONES =================
def obtener_obras():
    return {d.id: d.to_dict()["nombre"] for d in db.collection("obras").stream()}

def cargar_avances(obra_id):
    docs = (
        db.collection("obras")
        .document(obra_id)
        .collection("avances")
        .order_by("fecha", direction=firestore.Query.DESCENDING)
        .stream()
    )
    return [d.to_dict() for d in docs]

# ================= AUTH =================
auth = st.session_state["auth"]

if "crear_obra" not in st.session_state:
    st.session_state["crear_obra"] = False

# ================= SELECCIÓN DE OBRA =================
OBRAS = obtener_obras()

if not OBRAS:
    st.warning("No hay obras creadas")
    st.stop()

if auth["role"] == "jefe":
    obra_id_sel = st.sidebar.selectbox(
        "Seleccionar obra",
        options=list(OBRAS.keys()),
        format_func=lambda x: OBRAS[x],
        on_change=lambda: st.session_state.update({"crear_obra": False})
    )

    st.sidebar.divider()

    if st.sidebar.button("➕ Crear Obra", use_container_width=True):
        st.session_state["crear_obra"] = True

else:
    obra_id_sel = auth["obra"]
    st.sidebar.success(f"Obra asignada: {OBRAS[obra_id_sel]}")





# ================= CREAR OBRA (FORMULARIO) =================
if auth["role"] == "jefe" and st.session_state["crear_obra"]:

    st.title("➕ Crear nueva obra")

    with st.form("form_crear_obra"):
        nombre = st.text_input("Nombre de la obra")
        ubicacion = st.text_input("Ubicación")

        estado = st.selectbox(
            "Estado",
            ["en espera", "en progreso", "pausado", "finalizado"]
        )

        col1, col2 = st.columns(2)
        fecha_inicio = col1.date_input("Fecha inicio")
        fecha_fin = col2.date_input("Fecha fin estimado")

        col1, col2 = st.columns(2)
        guardar = col1.form_submit_button("💾 Crear obra")
        cancelar = col2.form_submit_button("❌ Cancelar")

    if guardar:
        if not nombre or not ubicacion:
            st.error("Nombre y ubicación son obligatorios")
        else:
            obra_id = nombre.lower().strip().replace(" ", "_")

            db.collection("obras").document(obra_id).set({
                "nombre": nombre,
                "ubicacion": ubicacion,
                "estado": estado,

                # ✅ Guardar como TIMESTAMP (Firestore)
                "fecha_inicio": datetime.combine(
                    fecha_inicio, datetime.min.time()
                ),
                "fecha_fin_estimado": datetime.combine(
                    fecha_fin, datetime.min.time()
                ),

                "presupuesto_total": 0,
                "creado_en": datetime.now()
            })

            st.session_state["crear_obra"] = False
            st.success("✅ Obra creada correctamente")
            st.rerun()

    if cancelar:
        st.session_state["crear_obra"] = False
        st.rerun()

    # ⛔ Detiene el resto de la página
    st.stop()


           







# ================= INFO OBRA =================
obra_doc = db.collection("obras").document(obra_id_sel).get().to_dict()

st.subheader(f"🏗️ {obra_doc['nombre']}")
st.write(f"📍 **Ubicación:** {obra_doc['ubicacion']}")
st.write(f"📌 **Estado:** {obra_doc['estado']}")
st.write(f"📅 **Inicio:** {obra_doc['fecha_inicio']}")
st.write(f"📅 **Fin estimado:** {obra_doc['fecha_fin_estimado']}")

st.divider()

# ================= PASANTE: REGISTRAR AVANCE =================
if auth["role"] == "pasante":
    st.header("📝 Registrar avance")

    with st.form("nuevo_avance"):
        responsable = st.text_input("Responsable")
        descripcion = st.text_area("Descripción del avance")
        fotos = st.file_uploader(
            "Subir fotos (mínimo 3)",
            type=["jpg", "png", "jpeg"],
            accept_multiple_files=True
        )
        guardar = st.form_submit_button("GUARDAR AVANCE")

    if guardar:
        if not responsable or not descripcion:
            st.error("Responsable y descripción son obligatorios")
        elif not fotos or len(fotos) < 3:
            st.error("Debes subir mínimo 3 fotos")
        else:
            urls = []
            for f in fotos:
                res = cloudinary.uploader.upload(
                    f,
                    folder=f"obras/{obra_id_sel}"
                )
                urls.append(res["secure_url"])

            db.collection("obras")\
                .document(obra_id_sel)\
                .collection("avances")\
                .add({
                    "fecha": datetime.now().isoformat(),
                    "responsable": responsable,
                    "descripcion": descripcion,
                    "fotos": urls
                })

            st.success("Avance registrado correctamente")
            st.rerun()


# ================= DASHBOARD DE AVANCES =================
st.divider()
st.subheader("📊 Avance económico de la obra")

obra = db.collection("obras").document(obra_id_sel).get().to_dict()
avances = cargar_avances(obra_id_sel)

if not avances:
    st.info("Aún no hay avances registrados")
else:
    # ---------- PROCESAR AVANCES ----------
    registros = []
    for av in avances:
        fecha = datetime.fromisoformat(av["fecha"])
        registros.append({
            "fecha": fecha,
            "semana": fecha.isocalendar()[1],
            "mes": fecha.month,
            "costo": av.get("costo", 0),
            "avance": av
        })

    df = pd.DataFrame(registros)

    col1, col2 = st.columns(2)

    # ---------- SELECT SEMANA ----------
    semanas = sorted(df["semana"].unique())
    semana_sel = col1.selectbox(
        "📆 Seleccionar semana",
        semanas,
        format_func=lambda x: f"Semana {x}"
    )

    # ---------- SELECT MES ----------
    meses = sorted(df["mes"].unique())
    mes_sel = col2.selectbox(
        "📅 Seleccionar mes",
        meses,
        format_func=lambda x: MESES_ES[x]
    )


    # ---------- MODO VISUAL ----------
    modo = st.radio(
        "Vista",
        ["Semana (L–V)", "Meses"],
        horizontal=True
    )

    # ================== GRAFICO SEMANAL ==================
    if modo == "Semana (L–V)":
        dias = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        dias_es = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]

        df_sem = df[df["semana"] == semana_sel]

        costos_por_dia = defaultdict(float)
        for _, r in df_sem.iterrows():
            dia = r["fecha"].strftime("%A")
            if dia in dias:
                costos_por_dia[dia] += r["costo"]

        valores = [costos_por_dia.get(d, 0) for d in dias]

        chart_df = pd.DataFrame({
            "Día": dias_es,
            "Costo": valores
        }).set_index("Día")

        st.bar_chart(chart_df, height=300)

    # ================== GRAFICO MENSUAL ==================
    else:
        costos_mes = defaultdict(float)
        for _, r in df.iterrows():
            costos_mes[r["mes"]] += r["costo"]

        meses_orden = list(range(1, 13))
        valores = [costos_mes.get(m, 0) for m in meses_orden]

        chart_df = pd.DataFrame({
            "Mes": [MESES_ES[m] for m in meses_orden],
            "Costo": valores
        }).set_index("Mes")


        st.bar_chart(chart_df, height=300)

    # ================== PROGRESO TOTAL ==================
    st.divider()
    st.subheader("📈 Progreso total de la obra")

    presupuesto = obra.get("presupuesto_total", 0)
    total_gastado = df["costo"].sum()

    if presupuesto > 0:
        porcentaje = min(int((total_gastado / presupuesto) * 100), 100)
    else:
        porcentaje = 0

    st.progress(porcentaje)
    st.caption(f"💰 Gastado: S/ {total_gastado:,.2f} / S/ {presupuesto:,.2f}")



# ================= HISTORIAL DE AVANCES =================
st.header("📚 Historial de Avances")

avances = cargar_avances(obra_id_sel)

if not avances:
    st.info("Esta obra aún no tiene avances registrados")
else:
    for av in avances:
        fecha = datetime.fromisoformat(av["fecha"])
        with st.expander(f"📅 {fecha:%d/%m/%Y %H:%M} — {av.get('responsable','N/D')}"):
            st.write(
                    av.get("observaciones")
                    or av.get("descripcion")
                    or "Sin descripción"
                )


            fotos = av.get("fotos", [])
            if fotos:
                cols = st.columns(3)
                for i, img in enumerate(fotos):
                    cols[i % 3].image(img, use_container_width=True)
            else:
                st.warning("Sin fotos")
