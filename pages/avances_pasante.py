
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


# ================= MÉTRICAS ACTUALIZADAS =================
st.subheader("📊 Estado Financiero de la Obra")

# Extraemos valores de la base de datos
presupuesto_obra_total = float(obra.get("presupuesto_total", 0))
gasto_materiales = float(obra.get("gasto_acumulado", 0))
gasto_caja_chica = float(obra.get("gastos_adicionales", 0))
gasto_mano_obra = float(obra.get("gasto_mano_obra", 0)) # Campo sincronizado con trabajadores

# Cálculo de disponibilidad real restando los 3 rubros
presupuesto_disponible = presupuesto_obra_total - gasto_materiales - gasto_caja_chica - gasto_mano_obra
porcentaje_ejecutado = ((presupuesto_obra_total - presupuesto_disponible) / presupuesto_obra_total * 100) if presupuesto_obra_total > 0 else 0

col_m1, col_m2 = st.columns(2)
col_m1.metric("💰 Presupuesto Total", f"S/ {presupuesto_obra_total:,.2f}")
col_m2.metric("✅ Disponible Real", f"S/ {presupuesto_disponible:,.2f}", 
              delta=f"- S/ {gasto_mano_obra + gasto_materiales + gasto_caja_chica:,.2f}", delta_color="inverse")

# Desglose pequeño para el pasante
c1, c2, c3 = st.columns(3)
c1.caption(f"🧱 Mats: S/ {gasto_materiales:,.2f}")
c2.caption(f"👷 M.O: S/ {gasto_mano_obra:,.2f}")
c3.caption(f"📦 Caja: S/ {gasto_caja_chica:,.2f}")

st.progress(min(porcentaje_ejecutado / 100, 1.0))
st.write(f"**Progreso del gasto:** {porcentaje_ejecutado:.1f}%")
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
# ================= GUARDAR =================
if guardar:
    if not responsable.strip() or not descripcion.strip():
        st.error("Responsable y descripción son obligatorios")

    elif not materiales_usados:
        st.error("Debes usar al menos un material")

    elif not fotos or len(fotos) < 3:
        st.error("Debes subir mínimo 3 fotos")

    else:
        with st.spinner("Guardando avance..."):
            # ---------- SUBIR FOTOS ----------
            urls = []
            for f in fotos:
                res = cloudinary.uploader.upload(
                    f,
                    folder=f"obras/{obra_id}/avances"
                )
                urls.append(res["secure_url"])

            batch = db.batch()
            
            # ---------- SUBIR FOTO CAJA CHICA ----------
            url_foto_gasto = ""
            if st.session_state.gasto_extra_foto:
                res_gasto = cloudinary.uploader.upload(
                    st.session_state.gasto_extra_foto,
                    folder=f"obras/{obra_id}/caja_chica"
                )
                url_foto_gasto = res_gasto["secure_url"]

            # ---------- MATERIALES USADOS ----------
            for m_id, m in materiales_usados.items():
                ref = obra_ref.collection("materiales_usados").document()
                batch.set(ref, {
                    "fecha": datetime.now(),
                    "material_doc_id": m_id,
                    **m,
                    "usuario": username
                })

            # ---------- PORCENTAJE DE AVANCE ----------
            porcentaje_avance = (
                (costo_total_dia / presupuesto_total) * 100
                if presupuesto_total else 0
            )

            # ---------- REGISTRO DE AVANCE ----------
            ref_avance = obra_ref.collection("avances").document()
            gasto_extra_aplicado = float(st.session_state.gasto_extra_monto)

            batch.set(ref_avance, {
                "fecha": datetime.now().isoformat(),
                "timestamp": datetime.now(),
                "usuario": username,
                "responsable": responsable,
                "observaciones": descripcion,
                "costo_total_dia": round(costo_total_dia, 2),
                "gasto_adicional": round(gasto_extra_aplicado, 2),
                "problematica": st.session_state.gasto_extra_problematica if gasto_extra_aplicado > 0 else "",
                "solucion": st.session_state.gasto_extra_solucion if gasto_extra_aplicado > 0 else "",
                "foto_gasto_adicional": url_foto_gasto,
                "porcentaje_avance_financiero": round(porcentaje_avance, 2),
                "materiales_usados": list(materiales_usados.values()),
                "fotos": urls
            })

            # ---------- COMMIT BATCH ----------
            batch.commit()

            # ---------- ACTUALIZAR TOTALES EN OBRA ----------
            # Usamos firestore.Increment para una actualización precisa y directa
            update_data = {
                "gasto_acumulado": firestore.Increment(round(costo_total_dia, 2)),
                "ultima_actualizacion": firestore.SERVER_TIMESTAMP
            }

            if gasto_extra_aplicado > 0:
                update_data["gastos_adicionales"] = firestore.Increment(round(gasto_extra_aplicado, 2))
                update_data["ultima_problematica"] = st.session_state.gasto_extra_problematica
                update_data["ultima_solucion"] = st.session_state.gasto_extra_solucion

            obra_ref.update(update_data)

            # ---------- LIMPIAR SESSION STATE ----------
            st.session_state.gasto_extra_monto = 0.0
            st.session_state.gasto_extra_problematica = ""
            st.session_state.gasto_extra_solucion = ""
            st.session_state.mostrar_gasto_extra = False
            st.session_state.gasto_extra_foto = None
            
            st.success("✅ Avance guardado correctamente")
            st.rerun()


# ================= HISTORIAL =================
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

    acumulado_paso_a_paso += costo_dia + gasto_extra

    d["acumulado_al_momento"] = round(acumulado_paso_a_paso, 2)
    d["excede_en_su_momento"] = acumulado_paso_a_paso > presupuesto_obra

    lista_avances.append(d)

if not lista_avances:
    st.info("Aún no hay avances registrados.")
else:
    for d in lista_avances:
        ts = d.get("timestamp")

        alerta = "🔴" if d["excede_en_su_momento"] else "🟢"
        prog = d.get("porcentaje_avance_financiero", 0)

        with st.expander(
            f"{alerta} {ts:%d/%m/%Y %H:%M} | 📈 {prog}% | {d.get('responsable')}"
        ):
            st.write(f"**Descripción:** {d.get('observaciones')}")

            st.write("**🧱 Materiales usados:**")
            mats = d.get("materiales_usados", [])
            if mats:
                df_m = pd.DataFrame(mats)[
                    ["nombre", "cantidad", "unidad", "subtotal"]
                ]
                df_m.columns = ["Material", "Cant.", "Unidad", "Subtotal (S/)"]
                st.table(df_m)
            else:
                st.caption("Sin materiales.")

            c1, c2 = st.columns(2)
            c1.metric("Costo del día", f"S/ {d.get('costo_total_dia', 0):,.2f}")
            c2.metric(
                "Acumulado obra",
                f"S/ {d['acumulado_al_momento']:,.2f}"
            )

            if d.get("gasto_adicional", 0) > 0:
                st.warning(
                    f"🟡 Gasto adicional: S/ {d['gasto_adicional']:,.2f}"
                )

            # ================= PROBLEMÁTICA / SOLUCIÓN =================
            problematica = d.get("problematica", "").strip()
            solucion = d.get("solucion", "").strip()
            
            if problematica or solucion:
                with st.expander("🛑 Ver problemática y solución"):
                    foto_gasto = d.get("foto_gasto_adicional", "")

                    if foto_gasto:
                        st.markdown("### 📸 Evidencia de caja chica")
                        st.image(foto_gasto, use_container_width=True)

                    if problematica:
                        st.markdown("### 🛑 Problemática")
                        st.write(problematica)
                    else:
                        st.caption("Sin problemática registrada.")
            
                    if solucion:
                        st.markdown("### ✅ Solución")
                        st.write(solucion)
                    else:
                        st.caption("Sin solución registrada.")


            fotos_list = d.get("fotos", [])
            if fotos_list:
                st.write("**🖼️ Evidencia fotográfica:**")
                cols = st.columns(3)
                for i, url in enumerate(fotos_list):
                    cols[i % 3].image(url, use_container_width=True)
