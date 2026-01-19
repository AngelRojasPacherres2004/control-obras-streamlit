"obras.py"
import streamlit as st
import pandas as pd
from datetime import datetime, date
import pytz
import cloudinary
import cloudinary.uploader
from firebase_admin import firestore
from collections import defaultdict
from io import BytesIO


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

# --- NUEVA LÓGICA: RESET AL CAMBIAR DE PESTAÑA ---
# Si la última página registrada no es esta, cerramos el formulario de creación
if st.session_state.get("last_page") != "obras":
    st.session_state["crear_obra"] = False
    st.session_state["last_page"] = "obras"

# ================= SELECCIÓN DE OBRA =================
OBRAS = obtener_obras()
lista_ids = list(OBRAS.keys())

if auth["role"] == "jefe":
    # Buscamos en qué posición de la lista está la obra que seleccionamos antes
    indice_actual = 0
    if "obra_id_global" in st.session_state and st.session_state["obra_id_global"] in lista_ids:
        indice_actual = lista_ids.index(st.session_state["obra_id_global"])

    obra_id_sel = st.sidebar.selectbox(
        "Seleccionar obra",
        options=lista_ids,
        format_func=lambda x: OBRAS.get(x, x),
        index=indice_actual,
        key="selector_global",
        # Esto asegura que si cambias de obra en el menú, se cierre el formulario "Crear"
        on_change=lambda: st.session_state.update({"crear_obra": False})
    )
    
    # Guardamos para las otras pantallas
    st.session_state["obra_id_global"] = obra_id_sel
    st.sidebar.divider()
    if st.sidebar.button("➕ Crear Nueva Obra", use_container_width=True):
        st.session_state["crear_obra"] = True
        st.rerun()  
else:
    # Para pasantes, usamos la obra asignada en su perfil
    obra_id_sel = auth.get("obra")
    # También lo guardamos globalmente por si el pasante entra a otras páginas
    st.session_state["obra_id_global"] = obra_id_sel
    
    if not obra_id_sel:
        st.error("No tienes una obra asignada.")
        st.stop()
    st.sidebar.success(f"Obra asignada: {OBRAS.get(obra_id_sel, 'Desconocida')}")
# ================= FORMULARIO CREAR OBRA =================
if auth["role"] == "jefe" and st.session_state.get("crear_obra", False):
    st.title("➕ Crear nueva obra")

    # Inicializar estados de pasos si no existen
    if "paso_creacion" not in st.session_state:
        st.session_state.paso_creacion = 1
    if "temp_datos_obra" not in st.session_state:
        st.session_state.temp_datos_obra = {}

    # --- PASO 1: DATOS GENERALES Y PRESUPUESTOS BASE ---
    if st.session_state.paso_creacion == 1:
        with st.form("form_datos_generales"):
            nombre = st.text_input("Nombre de la obra")
            ubicacion = st.text_input("Ubicación")
            estado = st.selectbox("Estado", ["en espera", "en progreso", "pausado", "finalizado"])
            
            c1, c2 = st.columns(2)
            f_inicio = c1.date_input("Fecha inicio", value=date.today())
            f_fin = c2.date_input("Fecha fin estimado", value=date.today())

            st.subheader("💰 Presupuestos Base")
            col_p1, col_p2 = st.columns(2)
            p_caja = col_p1.number_input("Presupuesto Caja Chica (S/)", min_value=0.0, step=100.0)
            p_mano = col_p2.number_input("Presupuesto Mano de Obra (S/)", min_value=0.0, step=100.0)
            
            p_mats_total = st.number_input("Presupuesto TOTAL Materiales (S/)", min_value=0.0, step=100.0, 
                                           help="Este monto se distribuirá por semanas en el siguiente paso")

            if st.form_submit_button("Siguiente: Configurar Semanas ➡️"):
                if not nombre or p_mats_total <= 0:
                    st.error("Por favor completa el nombre y el presupuesto de materiales.")
                elif f_fin <= f_inicio:
                    st.error("La fecha fin debe ser mayor a la de inicio.")
                else:
                    st.session_state.temp_datos_obra = {
                        "nombre": nombre, "ubicacion": ubicacion, "estado": estado,
                        "f_inicio": f_inicio, "f_fin": f_fin,
                        "p_caja": p_caja, "p_mano": p_mano, "p_mats_total": p_mats_total
                    }
                    st.session_state.paso_creacion = 2
                    st.rerun()

    # --- PASO 2: DISTRIBUCIÓN SEMANAL ---
    elif st.session_state.paso_creacion == 2:
        datos = st.session_state.temp_datos_obra
        st.info(f"📍 **Obra:** {datos['nombre']} | **Presupuesto Materiales a distribuir:** S/ {datos['p_mats_total']:,.2f}")
        
        # Calcular semanas según fechas
        duracion_dias = (datos['f_fin'] - datos['f_inicio']).days + 1
        num_semanas = max(1, (duracion_dias + 6) // 7)

        with st.form("form_semanas_materiales"):
            st.subheader("🧱 Distribución Semanal de Materiales")
            lista_semanas = []
            fecha_cursor = datos['f_inicio']
            suma_ingresada = 0.0

            for i in range(num_semanas):
                sem_ini = fecha_cursor
                sem_fin = min(fecha_cursor + pd.Timedelta(days=6), datos['f_fin'])
                
                # Sugerir monto equitativo para facilitar el llenado
                sugerido = round(datos['p_mats_total'] / num_semanas, 2)
                
                monto = st.number_input(
                    f"Semana {i+1} ({sem_ini.strftime('%d/%m')} - {sem_fin.strftime('%d/%m')})",
                    min_value=0.0, step=10.0, value=sugerido, key=f"sem_input_{i}"
                )
                suma_ingresada += monto
                
                lista_semanas.append({
                    "semana": i + 1,
                    "fecha_inicio": datetime.combine(sem_ini, datetime.min.time()),
                    "fecha_fin": datetime.combine(sem_fin, datetime.min.time()),
                    "presupuesto_materiales": monto
                })
                fecha_cursor = sem_fin + pd.Timedelta(days=1)

            diferencia = round(datos['p_mats_total'] - suma_ingresada, 2)
            if diferencia == 0:
                st.success("✅ El total coincide perfectamente.")
            elif diferencia > 0:
                st.warning(f"Faltan asignar: S/ {diferencia:,.2f}")
            else:
                st.error(f"Te has pasado por: S/ {abs(diferencia):,.2f}")

            c_col1, c_col2 = st.columns(2)
            if c_col1.form_submit_button("💾 Finalizar y Guardar Obra"):
                if abs(diferencia) > 0.01: # Tolerancia por decimales
                    st.error(f"La suma de las semanas debe ser exactamente S/ {datos['p_mats_total']:,.2f}")
                else:
                    oid = datos['nombre'].lower().strip().replace(" ", "_")
                    ahora = datetime.now(local_tz)
                    
                    
                    db.collection("obras").document(oid).set({
                    "nombre": datos['nombre'],
                    "ubicacion": datos['ubicacion'],
                    "estado": datos['estado'],
                    "fecha_inicio": datetime.combine(datos['f_inicio'], datetime.min.time()),
                    "fecha_fin_estimado": datetime.combine(datos['f_fin'], datetime.min.time()),
                    "presupuesto_caja_chica": datos['p_caja'],
                    "presupuesto_mano_obra": datos['p_mano'],
                    "presupuesto_materiales": datos['p_mats_total'],
                    "presupuesto_materiales_semanal": lista_semanas,
                    "presupuesto_total": datos['p_caja'] + datos['p_mano'] + datos['p_mats_total'],
                    "gasto_materiales": 0,      
                    "gasto_caja_chica": 0,     
                    "gasto_mano_obra": 0,       
                    "creado_en": ahora
                    })
                    
                    st.session_state.paso_creacion = 1
                    st.session_state.crear_obra = False
                    st.success("Obra creada exitosamente")
                    st.rerun()

            if c_col2.form_submit_button("⬅️ Volver / Editar Totales"):
                st.session_state.paso_creacion = 1
                st.rerun()

    if st.button("❌ Cancelar todo"):
        st.session_state.paso_creacion = 1
        st.session_state.crear_obra = False
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
g_caja_uso = float(obra_data.get("gasto_caja_chica", 0))
p_caja_act = p_caja_ini - g_caja_uso

# 2. Materiales
p_mats_ini = float(obra_data.get("presupuesto_materiales", 0))
g_mats_uso = float(obra_data.get("gasto_materiales", 0)) 
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
                    "gasto_caja_chica": gasto_caja_input,
                    "materiales_usados": mats_usados,
                    "costo_total_dia": costo_dia_mats,
                    "fotos": urls
                })
                
                # Actualizar acumulados de la obra
                db.collection("obras").document(obra_id_sel).update({
                    "gasto_materiales": firestore.Increment(costo_dia_mats),
                    "gastos_caja_chica": firestore.Increment(gasto_caja_input)
                })
                st.success("✅ Avance guardado correctamente")
                st.rerun()

# ================= ANÁLISIS ECONÓMICO =================
st.divider()
st.subheader("📊 Resumen de Gastos")

avances_lista = cargar_avances(obra_id_sel)

if avances_lista:
    total_gastado = float(obra_data.get("gasto_materiales", 0)) + float(obra_data.get("gastos_caja_chica", 0))+ float(obra_data.get("gasto_mano_obra", 0))
    porcentaje = min(total_gastado / p_total_ini, 1.0) if p_total_ini > 0 else 0
    st.write(f"**Gasto Real Total (Materiales + Caja+ Mano de obra):** S/ {total_gastado:,.2f} de S/ {p_total_ini:,.2f} ({porcentaje*100:.1f}%)")
    st.progress(porcentaje)


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
            "costo": av.get("costo_total_dia", 0),
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
    
        df_sem = df[df["semana"] == semana_sel]
    
        gastos_por_dia = {d: 0.0 for d in dias_en}
    
        for _, r in df_sem.iterrows():
            dia = r["fecha"].strftime("%A")
    
            if dia in dias_en:
                avance = r["avance"]
    
                gasto_materiales = avance.get("costo_total_dia", 0) or 0
                gasto_caja = avance.get("gasto_caja_chica", 0) or 0
    
                gastos_por_dia[dia] += gasto_materiales + gasto_caja
    
        chart_df = pd.DataFrame({
            "Día": dias_es,
            "Gasto Total (S/)": [gastos_por_dia[d] for d in dias_en]
        }).set_index("Día")
    
        st.bar_chart(chart_df, height=320)

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
            c_col2.metric("Gasto Caja Chica", f"S/ {av.get('gasto_caja_chica', 0):,.2f}")
            
            # --- FOTOS ---
            fotos = av.get("fotos", [])
            if fotos:
                cols = st.columns(3)
                for i, url in enumerate(fotos):
                    cols[i % 3].image(url, use_container_width=True)
            
              # --- SECCIÓN DE PROBLEMÁTICA Y SOLUCIÓN ---
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
        "Gasto Caja Chica (S/)": obra.get("gastos_caja_chica", 0),
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
