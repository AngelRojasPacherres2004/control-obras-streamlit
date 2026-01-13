"""avances_pasante.py"""
import streamlit as st
import pandas as pd
from datetime import datetime
import cloudinary.uploader
from firebase_admin import firestore
import pytz

# Zona horaria
pais_tz = pytz.timezone("America/Lima")
# ================= CONFIG =================
st.set_page_config(page_title="Parte Diario", layout="centered")
db = firestore.client()

# ================= SEGURIDAD =================
if "auth" not in st.session_state:
    st.error("Sesión no válida")
    st.stop()

auth = st.session_state["auth"]
# ================= USUARIO Y OBRA =================
if auth.get("role") != "pasante":
    st.warning("Acceso solo para pasantes")
    st.stop()

obra_id = auth.get("obra")
username = auth.get("username", "desconocido")

if not obra_id:
    st.error("No tienes una obra asignada")
    st.stop()


# ================= SESSION STATE (INICIALIZACIÓN) =================
if "gasto_extra_monto" not in st.session_state:
    st.session_state.gasto_extra_monto = 0.0

if "gasto_extra_problematica" not in st.session_state:
    st.session_state.gasto_extra_problematica = ""

if "gasto_extra_solucion" not in st.session_state:
    st.session_state.gasto_extra_solucion = ""

if "mostrar_gasto_extra" not in st.session_state:
    st.session_state.mostrar_gasto_extra = False

if "gasto_extra_foto" not in st.session_state:
    st.session_state.gasto_extra_foto = None


# ================= DATOS DE LA OBRA =================
obra_ref = db.collection("obras").document(obra_id)
obra_doc = obra_ref.get()

if not obra_doc.exists:
    st.error("La obra asignada no existe")
    st.stop()

obra = obra_doc.to_dict()


# ================= FECHAS DE LA OBRA =================
fecha_inicio = obra.get("fecha_inicio")
fecha_fin = obra.get("fecha_fin_estimado")

if fecha_inicio and hasattr(fecha_inicio, "date"):
    fecha_inicio = fecha_inicio.date()

if fecha_fin and hasattr(fecha_fin, "date"):
    fecha_fin = fecha_fin.date()

# ================= SIDEBAR =================
with st.sidebar:
    st.header("🏗️ Obra asignada")
    st.write(f"**Nombre:** {obra.get('nombre')}")
    st.write(f"**Estado:** {obra.get('estado')}")
    st.write(f"📅 Inicio: {obra.get('fecha_inicio').date()}")
    st.write(f"🏁 Fin estimado: {obra.get('fecha_fin_estimado').date()}")

# ================= MATERIALES ASIGNADOS =================
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

# ================= MÉTRICAS (VERSUS: INICIAL VS DISPONIBLE) =================
st.subheader("📊 Estado Financiero: Presupuesto vs. Disponible")

# 1. Extracción de valores desde el documento de la obra
pres_total_obra = float(obra.get("presupuesto_total", 0))-float(obra.get("gasto_mano_obra", 0))
pres_caja_inicial = float(obra.get("presupuesto_caja_chica", 0)) 
pres_mats_inicial = float(obra.get("presupuesto_materiales", 0))
pres_mo_inicial = float(obra.get("presupuesto_mano_obra", 0))

gasto_mats_acum = float(obra.get("gasto_acumulado", 0))
gasto_caja_acum = float(obra.get("gastos_adicionales", 0))
gasto_mo_acum = float(obra.get("gasto_mano_obra", 0))

# 2. Cálculos de Disponibles (Lo que queda)
disponible_mats = pres_mats_inicial - gasto_mats_acum
disponible_caja = pres_caja_inicial - gasto_caja_acum
disponible_total = pres_total_obra - (gasto_mats_acum + gasto_caja_acum )

# 3. Porcentaje de ejecución total
porcentaje_ejecutado = ((pres_total_obra - disponible_total) / pres_total_obra * 100) if pres_total_obra > 0 else 0

# --- FILA 1: VERSUS MATERIALES ---
st.markdown("#### 🧱 Materiales")
col1, col2 = st.columns(2)
col1.metric("Presupuesto Inicial", f"S/ {pres_mats_inicial:,.2f}")
col2.metric("Disponible Actual", f"S/ {disponible_mats:,.2f}", 
            delta=f"-S/ {gasto_mats_acum:,.2f}", delta_color="inverse")

# --- FILA 2: VERSUS CAJA CHICA ---
st.markdown("#### 📦 Caja Chica")
col3, col4 = st.columns(2)
col3.metric("Presupuesto Inicial", f"S/ {pres_caja_inicial:,.2f}")
col4.metric("Disponible Actual", f"S/ {disponible_caja:,.2f}", 
            delta=f"-S/ {gasto_caja_acum:,.2f}", delta_color="inverse")

st.divider()

# --- FILA 3: TOTAL GENERAL ---
st.markdown("#### 💰 Resumen de Obra")
col5, col6 = st.columns(2)
col5.metric("PRESUPUESTO TOTAL", f"S/ {pres_total_obra:,.2f}")
col6.metric("TOTAL DISPONIBLE", f"S/ {disponible_total:,.2f}", 
            delta=f"{porcentaje_ejecutado:.1f}% consumido")

st.progress(min(porcentaje_ejecutado / 100, 1.0))
st.divider()
# ================= GASTOS ADICIONALES =================
st.markdown("---")
st.subheader("➕ Gastos adicionales (Caja chica)")

if "mostrar_gasto_extra" not in st.session_state:
    st.session_state.mostrar_gasto_extra = False

if st.button("➕ Registrar gasto adicional"):
    st.session_state.mostrar_gasto_extra = not st.session_state.mostrar_gasto_extra

if st.session_state.mostrar_gasto_extra:
    st.session_state.gasto_extra_problematica = st.text_area(
        "🛑 Problemática",
        value=st.session_state.gasto_extra_problematica
    )

    st.session_state.gasto_extra_solucion = st.text_area(
        "✅ Solución",
        value=st.session_state.gasto_extra_solucion
    )

    st.session_state.gasto_extra_monto = st.number_input(
        "💸 Gasto a descontar de caja chica (S/)",
        min_value=0.0,
        step=1.0,
        value=st.session_state.gasto_extra_monto
    )

    foto_gasto = st.file_uploader(
    "📸 Foto del gasto (boleta / evidencia)",
    type=["jpg", "png", "jpeg"],
    accept_multiple_files=False
    )

    st.session_state.gasto_extra_foto = foto_gasto


    st.info("ℹ️ Este gasto se guardará **junto con el avance diario**")

if st.session_state.gasto_extra_monto > 0:
    st.warning(
        f"🟡 Gastos adicionales pendientes: "
        f"S/ {st.session_state.gasto_extra_monto:,.2f}"
    )


# ================= FORMULARIO =================
st.title("📝 Registrar avance diario")

with st.form("form_avance", clear_on_submit=True):
    responsable = st.text_input("Responsable", value=username)
    descripcion = st.text_area("Descripción del trabajo", height=100)

    st.subheader("🧱 Materiales usados hoy")

    materiales_usados = {}
    costo_total_dia = 0.0

    for mat in materiales:
        col1, col2 = st.columns([3, 1])
        col1.write(f"**{mat['nombre']}** ({mat['unidad']})")

        cantidad = col2.number_input(
            "Cant.",
            min_value=0.0,
            step=1.0,
            key=f"mat_{mat['doc_id']}"
        )

        if cantidad > 0:
            subtotal = cantidad * mat["precio_unitario"]
            costo_total_dia += subtotal

            materiales_usados[mat["doc_id"]] = {
                "nombre": mat["nombre"],
                "unidad": mat["unidad"],
                "cantidad": cantidad,
                "precio_unitario": mat["precio_unitario"],
                "subtotal": round(subtotal, 2)
            }

    st.info(f"💰 Costo del día: S/ {costo_total_dia:.2f}")

    fotos = st.file_uploader(
        "Subir fotos (mínimo 3)",
        accept_multiple_files=True,
        type=["jpg", "png", "jpeg"]
    )

    guardar = st.form_submit_button("Guardar avance")

# ================= GUARDAR CON LÓGICA DE TRASVASE =================
if guardar:
    if not responsable.strip() or not descripcion.strip():
        st.error("Responsable y descripción son obligatorios")
    elif not materiales_usados:
        st.error("Debes usar al menos un material")
    elif not fotos or len(fotos) < 3:
        st.error("Debes subir mínimo 3 fotos")
    else:
        # --- LÓGICA DE PRESUPUESTO INTELIGENTE ---
        # 1. ¿Cuánto queda de materiales ANTES de este gasto?
        disponible_mats_antes = pres_mats_inicial - gasto_mats_acum
        
        # 2. ¿Cuánto queda de caja chica ANTES de este gasto?
        disponible_caja_antes = pres_caja_inicial - gasto_caja_acum
        
        gasto_mats_hoy = costo_total_dia
        gasto_caja_hoy = st.session_state.gasto_extra_monto
        
        exceso_materiales = 0.0
        pago_desde_materiales = gasto_mats_hoy
        
        # Si el gasto de hoy supera lo que queda en materiales...
        if gasto_mats_hoy > disponible_mats_antes:
            # Solo podemos sacar de la "bolsa" de materiales lo que quede (si queda algo)
            pago_desde_materiales = max(0, disponible_mats_antes)
            # El resto se convierte en una deuda para la caja chica
            exceso_materiales = gasto_mats_hoy - pago_desde_materiales
            
        total_a_descontar_caja = gasto_caja_hoy + exceso_materiales
        
        # --- VALIDACIÓN FINAL ---
        if total_a_descontar_caja > disponible_caja_antes:
            st.error(f"""
            🚫 **FONDO INSUFICIENTE**: 
            - El gasto de materiales excede el presupuesto en S/ {exceso_materiales:,.2f}.
            - Se intentó cobrar S/ {total_a_descontar_caja:,.2f} de Caja Chica.
            - Solo queda S/ {disponible_caja_antes:,.2f} disponible.
            """)
        else:
            with st.spinner("Guardando avance..."):
                # ---------- SUBIR FOTOS ----------
                urls = []
                for f in fotos:
                    res = cloudinary.uploader.upload(f, folder=f"obras/{obra_id}/avances")
                    urls.append(res["secure_url"])

                url_foto_gasto = ""
                if st.session_state.gasto_extra_foto:
                    res = cloudinary.uploader.upload(st.session_state.gasto_extra_foto, folder=f"obras/{obra_id}/caja_chica")
                    url_foto_gasto = res["secure_url"]

                batch = db.batch()

                # ---------- REGISTRO DE AVANCE ----------
                ref_avance = obra_ref.collection("avances").document()
                batch.set(ref_avance, {
                    "fecha": datetime.now().isoformat(),
                    "timestamp": datetime.now(),
                    "usuario": username,
                    "responsable": responsable,
                    "observaciones": descripcion,
                    "costo_total_dia": round(gasto_mats_hoy, 2),
                    "gasto_adicional": round(gasto_caja_hoy, 2),
                    "exceso_mats_a_caja": round(exceso_materiales, 2), # Auditamos el trasvase
                    "problematica": st.session_state.gasto_extra_problematica if total_a_descontar_caja > 0 else "",
                    "solucion": st.session_state.gasto_extra_solucion if total_a_descontar_caja > 0 else "",
                    "foto_gasto_adicional": url_foto_gasto,
                    "porcentaje_avance_financiero": round((gasto_mats_hoy/pres_mats_inicial*100), 2) if pres_mats_inicial > 0 else 0,
                    "materiales_usados": list(materiales_usados.values()),
                    "fotos": urls
                })

                # ---------- ACTUALIZAR ACUMULADOS EN OBRA ----------
                # El gasto_acumulado de materiales solo sube hasta el tope, el resto va a caja
                nuevo_gasto_mats = gasto_mats_acum + pago_desde_materiales
                nuevo_gasto_caja = gasto_caja_acum + total_a_descontar_caja
                
                update_data = {
                    "gasto_acumulado": round(nuevo_gasto_mats, 2),
                    "gastos_adicionales": round(nuevo_gasto_caja, 2),
                    "ultima_actualizacion": firestore.SERVER_TIMESTAMP
                }

                obra_ref.update(update_data)
                batch.commit()

                # ---------- LIMPIAR Y REINICIAR ----------
                st.session_state.gasto_extra_monto = 0.0
                st.session_state.mostrar_gasto_extra = False
                st.success("✅ Avance guardado. El exceso de materiales se descontó de Caja Chica.")
                st.rerun()

# ================= HISTORIAL DE AVANCES CORREGIDO =================
st.divider()
st.subheader("📂 Historial de avances")

avances_todos = (
    obra_ref.collection("avances")
    .order_by("timestamp", direction=firestore.Query.ASCENDING)
    .stream()
)

lista_avances = []
acumulado_paso_a_paso = 0.0

for av in avances_todos:
    d = av.to_dict()

    ts = d.get("timestamp")
    if ts and hasattr(ts, "astimezone"):
        ts = ts.astimezone(pais_tz)
        d["timestamp"] = ts

    costo_dia = float(d.get("costo_total_dia", 0))
    gasto_extra = float(d.get("gasto_adicional", 0))

    # Sumamos al acumulado histórico
    acumulado_paso_a_paso += costo_dia + gasto_extra
    d["acumulado_al_momento"] = round(acumulado_paso_a_paso, 2)

    # --- LÓGICA DE ALERTAS (EL SEMÁFORO) ---
    # 🔴 Rojo: Si el acumulado total superó el presupuesto total de la obra
    excede_total = acumulado_paso_a_paso > pres_total_obra
    
    # 🟠 Naranja: Si el gasto acumulado de materiales superó el presupuesto de materiales
    # (Calculamos cuánto se ha gastado de materiales hasta este avance)
    gasto_mats_hasta_hoy = sum(float(a.to_dict().get("costo_total_dia", 0)) for a in obra_ref.collection("avances").where("timestamp", "<=", d.get("timestamp")).stream())
    excede_materiales = gasto_mats_hasta_hoy > pres_mats_inicial

    if excede_total:
        d["emoji_estado"] = "🔴"
        d["msj_alerta"] = "¡PRESUPUESTO TOTAL EXCEDIDO!"
    elif excede_materiales:
        d["emoji_estado"] = "🟠"
        d["msj_alerta"] = "AVISO: Se superó el presupuesto de MATERIALES"
    else:
        d["emoji_estado"] = "🟢"
        d["msj_alerta"] = "Dentro del presupuesto"

    lista_avances.append(d)

if not lista_avances:
    st.info("Aún no hay avances registrados.")
else:
    # Mostramos de más reciente a más antiguo
    for d in reversed(lista_avances):
        ts = d.get("timestamp")
        alerta = d["emoji_estado"]
        prog = d.get("porcentaje_avance_financiero", 0)

        with st.expander(f"{alerta} {ts:%d/%m/%Y %H:%M} | 📈 {prog}% | {d.get('responsable')}"):
            if alerta != "🟢":
                st.warning(f"**{d['msj_alerta']}**")
            
            st.write(f"**Descripción:** {d.get('observaciones')}")

            # ... (Resto de tu código de tablas y fotos igual que antes)
            st.write("**🧱 Materiales usados:**")
            mats = d.get("materiales_usados", [])
            if mats:
                df_m = pd.DataFrame(mats)[["nombre", "cantidad", "unidad", "subtotal"]]
                df_m.columns = ["Material", "Cant.", "Unidad", "Subtotal (S/)"]
                st.table(df_m)

            c1, c2 = st.columns(2)
            c1.metric("Costo del día", f"S/ {d.get('costo_total_dia', 0):,.2f}")
            c2.metric("Acumulado obra", f"S/ {d['acumulado_al_momento']:,.2f}")
            
            # (Mantén tus fotos y problemática aquí...)
            fotos_list = d.get("fotos", [])
            if fotos_list:
                st.write("**🖼️ Evidencia fotográfica:**")
                cols = st.columns(3)
                for i, url in enumerate(fotos_list):
                    cols[i % 3].image(url, use_container_width=True)