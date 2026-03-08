#obras.py
import streamlit as st
import pandas as pd
from datetime import datetime, date
import pytz  # Librería para manejo de zonas horarias
import cloudinary
import cloudinary.uploader
from firebase_admin import firestore
from collections import defaultdict
from io import BytesIO

# ================= CONFIGURACIÓN DE ZONA HORARIA =================
# Cambia 'America/Lima' por tu ciudad si es necesario
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

# --- NUEVA LÓGICA: RESET AL CAMBIAR DE PESTAÑA ---
# Si la última página registrada no es esta, cerramos el formulario de creación
if st.session_state.get("last_page") != "obras":
    st.session_state["crear_obra"] = False
    st.session_state["last_page"] = "obras"

# ================= SELECCIÓN DE OBRA =================
OBRAS = obtener_obras()

if not OBRAS and auth["role"] != "jefe":
    st.warning("No hay obras creadas.")
    st.stop()

if auth["role"] == "jefe":
    # Buscamos en qué posición de la lista está la obra que seleccionamos antes
    indice_actual = 0
    if "obra_id_global" in st.session_state and st.session_state["obra_id_global"] in lista_ids:
        indice_actual = lista_ids.index(st.session_state["obra_id_global"])

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
        if col_g.form_submit_button("💾 Guardar Obra"):
            if not nombre: st.error("El nombre es obligatorio")
            else:
                oid = nombre.lower().strip().replace(" ", "_")
                # Guardamos las fechas de creación con zona horaria
                ahora_obra = datetime.now(local_tz)
                db.collection("obras").document(oid).set({
                    "nombre": nombre, "ubicacion": ubicacion, "estado": estado,
                    "fecha_inicio": datetime.combine(f_inicio, datetime.min.time()),
                    "fecha_fin_estimado": datetime.combine(f_fin, datetime.min.time()),
                    "presupuesto_total": presupuesto_inicial,
                    "gasto_acumulado": 0, "creado_en": ahora_obra
                })
                st.session_state["crear_obra"] = False
                st.rerun()
        if col_c.form_submit_button("❌ Cancelar"):
            st.session_state["crear_obra"] = False
            st.rerun()
    st.stop()

# ================= INFORMACIÓN DE LA OBRA =================
doc_ref = db.collection("obras").document(obra_id_sel).get()
if not doc_ref.exists:
    st.error("La obra seleccionada no existe.")
    st.stop()

obra_data = doc_ref.to_dict()
presupuesto_obra = float(obra_data.get("presupuesto_total", 0))

st.subheader(f"🏗️ {obra_data.get('nombre')}")
st.caption(f"📍 {obra_data.get('ubicacion')} | 📌 {obra_data.get('estado')}")

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
        for mat in av.get("materiales_usados", []):
            nombre_mat = mat.get("nombre")
            # Buscamos el precio en el diccionario de materiales de la obra
            precio = precios_materiales.get(nombre_mat, 0)
            costo_dia += float(mat.get("cantidad", 0)) * precio

        registros.append({
            "fecha": fecha,
            "semana": fecha.isocalendar()[1],
            "mes": fecha.month,
            "costo": costo_dia,
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

        dias_en = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        dias_es = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]

        df_sem = df[
            (df["semana"] == semana_sel) &
            (df["mes"] == mes_sel)
        ]

        gastos_por_dia = {dia: 0.0 for dia in dias_en}

avances_lista = cargar_avances(obra_id_sel)

            if dia_en in gastos_por_dia:

                # 🔥 USAR TOTALES REALES GUARDADOS
                subtotal_materiales = float(r["avance"].get("subtotal_materiales", 0))
                subtotal_mano_obra = float(r["avance"].get("subtotal_mano_obra", 0))
                gasto_caja = float(r["avance"].get("gasto_caja_chica", 0) or 0)

                gasto_total = subtotal_materiales + subtotal_mano_obra + gasto_caja

                gastos_por_dia[dia_en] += gasto_total

        chart_df = pd.DataFrame({
            "Día": dias_es,
            "Gasto Total (S/)": [gastos_por_dia[d] for d in dias_en]
        })

        chart_df["Día"] = pd.Categorical(
            chart_df["Día"],
            categories=["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"],
            ordered=True
        )

        chart_df = chart_df.sort_values("Día").set_index("Día")

        st.bar_chart(chart_df, height=320)

    # ================== GRAFICO MENSUAL ==================
    else:

        df_mes = df[df["mes"] == mes_sel]

        gasto_total_mes = 0.0

        for _, r in df_mes.iterrows():

            subtotal_materiales = float(r["avance"].get("subtotal_materiales", 0))
            subtotal_mano_obra = float(r["avance"].get("subtotal_mano_obra", 0))
            gasto_caja = float(r["avance"].get("gasto_caja_chica", 0) or 0)

            gasto_total_mes += subtotal_materiales + subtotal_mano_obra + gasto_caja

        chart_df = pd.DataFrame({
            "Mes": [MESES_ES[mes_sel]],
            "Gasto Total (S/)": [gasto_total_mes]
        }).set_index("Mes")

        st.bar_chart(chart_df, height=320)
# ================= HISTORIAL DE AVANCES =================
st.divider()
st.header("📚 Historial de Avances")

if not avances_lista:
    st.info("No hay registros en el historial.")
else:
    avances_mostrar = avances_lista[::-1]
    
    for av in avances_mostrar:
        # Usamos la fecha corregida que procesamos en el bloque anterior
        f_dt = av.get("_dt_local")
        f_txt = f_dt.strftime("%d/%m/%Y %H:%M") if f_dt else "Fecha N/D"

        seccion = av.get("seccion_nombre", "Sin sección")
        with st.expander(f"📅 {f_txt} — {av.get('responsable', 'N/D')} | 🧱 {seccion}"):

            st.write(f"**Descripción:** {av.get('descripcion', 'Sin descripción')}")

            # ================= RENDIMIENTO =================
            rend_real = av.get("rendimiento_real", 0)
            porc = av.get("porcentaje_rendimiento", 0)

            st.markdown("### 📊 Rendimiento del día")
            st.caption(
                f"🔎 Rendimiento real: **{rend_real:.2f}** "
                f"({porc*100:.1f}% del plan)"
            )
            st.progress(min(porc, 1.0))

            # ================= RESUMEN ECONÓMICO =================
            st.markdown("### 💰 Resumen económico")

            df_resumen = pd.DataFrame([{
                "Mano de obra (S/)": av.get("subtotal_mano_obra", 0),
                "Materiales (S/)": av.get("subtotal_materiales", 0),
                "Total avance (S/)": av.get("total_avance", 0)
            }])

            st.table(df_resumen)

            # ================= MANO DE OBRA =================
            mo = av.get("mano_obra_detalle")
            if mo:
                st.markdown("### 👷 Mano de Obra")
                df_mo = pd.DataFrame(mo)
                st.table(df_mo)

            # ================= MATERIALES =================
            mats = av.get("materiales_detalle")
            if mats:
                st.markdown("### 🧱 Materiales")
                df_mat = pd.DataFrame(mats)
                st.table(df_mat)

            # ================= FOTOS =================
            fotos = av.get("fotos", [])
            if fotos:
                st.markdown("### 📸 Fotos del avance")
                cols = st.columns(min(3, len(fotos)))
                for i, url in enumerate(fotos):
                    cols[i % 3].image(url, use_container_width=True)

            # ================= PROBLEMÁTICA / SOLUCIÓN =================
            col_h1, col_h2 = st.columns(2)
            prob = av.get("problematica")
            sol = av.get("solucion")

            if prob:
                col_h1.warning(f"**⚠️ Problemática:**\n\n{prob}")
            if sol:
                col_h2.success(f"**✅ Solución:**\n\n{sol}")

            # --- FOTO DE GASTO ADICIONAL (BOLETA / EVIDENCIA) ---
            foto_gasto = av.get("foto_gasto_adicional")

            if foto_gasto:
                st.markdown("#### 📸 Evidencia / Boleta")
                st.image(foto_gasto, use_container_width=True)

def limpiar_fechas_para_excel(df: pd.DataFrame) -> pd.DataFrame:
    """
    Elimina timezone de columnas datetime para que Excel no falle
    """
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.tz_localize(None)
    return df
def formatear_materiales_texto(materiales):
    """
    Convierte materiales_usados a texto legible para Excel
    """
    if not materiales:
        return ""

    lineas = []
    for m in materiales:
        nombre = m.get("nombre", "")
        cant = m.get("cantidad", 0)
        unidad = m.get("unidad", "")
        subtotal = m.get("subtotal", 0)
        lineas.append(f"- {nombre}: {cant} {unidad} (S/ {subtotal:.2f})")

    return "\n".join(lineas)

def exportar_obra_excel(obra_id: str):
    obra_ref = db.collection("obras").document(obra_id)
    obra = obra_ref.get().to_dict()

    # ================= DATOS GENERALES =================
    df_resumen = pd.DataFrame([{
        "Nombre de la Obra": obra.get("nombre"),
        "Ubicación": obra.get("ubicacion"),
        "Estado": obra.get("estado"),
        "Presupuesto Caja Chica (S/)": obra.get("presupuesto_caja_chica", 0),
        "Presupuesto Materiales (S/)": obra.get("presupuesto_materiales", 0),
        "Presupuesto Mano de Obra (S/)": obra.get("presupuesto_mano_obra", 0),
        "Presupuesto Total (S/)": obra.get("presupuesto_total", 0),
        "Gasto Materiales (S/)": obra.get("gasto_materiales", 0),
        "Gasto Caja Chica (S/)": obra.get("gasto_caja_chica", 0),
        "Gasto Mano de Obra (S/)": obra.get("gasto_mano_obra", 0),
    }])

    # ================= MATERIALES =================
    mats_docs = obra_ref.collection("materiales").stream()
    materiales = [m.to_dict() for m in mats_docs]
    df_materiales = pd.DataFrame(materiales) if materiales else pd.DataFrame()

    # ================= MANO DE OBRA =================
    trab_docs = obra_ref.collection("trabajadores").stream()
    trabajadores = [t.to_dict() for t in trab_docs]
    df_trabajadores = pd.DataFrame(trabajadores) if trabajadores else pd.DataFrame()

    # ================= AVANCES =================
    avances_docs = obra_ref.collection("avances").stream()
    avances = [a.to_dict() for a in avances_docs]
    df_avances = pd.DataFrame(avances) if avances else pd.DataFrame()

    # 🔥 LIMPIEZA DE FECHAS (JUSTO ANTES DE EXCEL)
    df_resumen = limpiar_fechas_para_excel(df_resumen)
    if not df_materiales.empty:
        df_materiales = limpiar_fechas_para_excel(df_materiales)
    if not df_trabajadores.empty:
        df_trabajadores = limpiar_fechas_para_excel(df_trabajadores)
    if not df_avances.empty:
        df_avances = limpiar_fechas_para_excel(df_avances)

    # ================= CREAR EXCEL =================
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        workbook = writer.book

        # --- FORMATOS ---
        header_format = workbook.add_format({
            "bold": True,
            "bg_color": "#1F4E78",
            "color": "white",
            "border": 1,
            "align": "center"
        })

        # -------- RESUMEN --------
        df_resumen.to_excel(writer, sheet_name="Resumen General", index=False)
        ws = writer.sheets["Resumen General"]
        ws.set_column("A:J", 30)
        for col_num, _ in enumerate(df_resumen.columns):
            ws.write(0, col_num, df_resumen.columns[col_num], header_format)

        # -------- MATERIALES --------
        if not df_materiales.empty:
            df_materiales.to_excel(writer, sheet_name="Materiales", index=False)
            ws = writer.sheets["Materiales"]
            ws.set_column("A:Z", 22)
            for col_num, col in enumerate(df_materiales.columns):
                ws.write(0, col_num, col, header_format)

        # -------- MANO DE OBRA --------
        if not df_trabajadores.empty:
            df_trabajadores.to_excel(writer, sheet_name="Mano de Obra", index=False)
            ws = writer.sheets["Mano de Obra"]
            ws.set_column("A:Z", 22)
            for col_num, col in enumerate(df_trabajadores.columns):
                ws.write(0, col_num, col, header_format)

        # -------- AVANCES --------
        if not df_avances.empty:
            df_avances.to_excel(writer, sheet_name="Avances", index=False)
            ws = writer.sheets["Avances"]
            ws.set_column("A:Z", 25)
            for col_num, col in enumerate(df_avances.columns):
                ws.write(0, col_num, col, header_format)

    output.seek(0)
    return output


if auth["role"] == "jefe":
    st.divider()
    st.subheader("📤 Exportar Información de la Obra")

    excel = exportar_obra_excel(obra_id_sel)

    st.download_button(
        label="📊 Descargar Excel de la Obra",
        data=excel,
        file_name=f"obra_{obra_id_sel}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
