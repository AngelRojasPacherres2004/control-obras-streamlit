"""avances_pasante.py"""
import streamlit as st
import pandas as pd
from datetime import datetime
from firebase_admin import firestore
import cloudinary.uploader
import pytz

# ================= CONFIG =================
st.set_page_config(page_title="Avances por Sección", layout="wide")
db = firestore.client()
tz = pytz.timezone("America/Lima")

# ================= SEGURIDAD =================
if "auth" not in st.session_state:
    st.error("Sesión no válida")
    st.stop()

auth = st.session_state["auth"]

if auth.get("role") != "pasante":
    st.warning("Acceso solo para pasantes")
    st.stop()

obra_id = auth.get("obra")
usuario = auth.get("username", "pasante")

if not obra_id:
    st.error("No tienes obra asignada")
    st.stop()

obra_ref = db.collection("obras").document(obra_id)
obra = obra_ref.get().to_dict()

# ================= SIDEBAR =================
with st.sidebar:
    st.header("🏗️ Obra asignada")
    st.write(f"**Nombre:** {obra.get('nombre')}")
    st.write(f"**Estado:** {obra.get('estado')}")
    st.write(f"📅 Inicio: {obra.get('fecha_inicio').date()}")
    st.write(f"🏁 Fin estimado: {obra.get('fecha_fin_estimado').date()}")

# ================= ESTADO =================
st.session_state.setdefault("partida_abierta", None)
st.session_state.setdefault("mo_refrescar", False)
st.session_state.setdefault("doble_refresh", 0)

# =========================================================
# ================= LISTA DE SECCIONES =====================
# =========================================================
if st.session_state.partida_abierta is None:

    # 📦 RESUMEN DE MATERIALES (CON STOCK_INICIAL Y STOCK_ACTUAL)

    st.subheader("📦 Resumen de materiales")

    materiales_obra = obra_ref.collection("materiales").stream()
    filas_resumen = []

    for m in materiales_obra:
        d = m.to_dict()

        stock_inicial = float(d.get("stock_inicial", 0))
        stock_actual = float(d.get("stock_actual", 0))
        gastado = stock_inicial - stock_actual  # ✅ AHORA sí es real

        filas_resumen.append({
            "Material": d.get("nombre"),
            "Unidad": d.get("unidad", "und"),
            "Stock Inicial": round(stock_inicial, 2),
            "Gastado": round(gastado, 2),
            "Stock Actual": round(stock_actual, 2)
        })


    df_resumen = pd.DataFrame(filas_resumen)

    st.dataframe(
        df_resumen,
        use_container_width=True,
        hide_index=True
    )


    # =========================================================
    # 📋 SECCIONES DE LA OBRA
    # =========================================================
    st.title("📋 Secciones de la Obra")

    partidas = list(
        obra_ref.collection("partidas")
        .order_by("codigo")
        .stream()
    )

    if not partidas:
        st.info("No hay secciones creadas")
        st.stop()

    # -------- SECCIONES (BOTONES) --------
    for p in partidas:
        d = p.to_dict()
        col1, col2 = st.columns([5, 1])
        with col1:
            st.markdown(f"### 🧱 {d.get('codigo')} - {d.get('nombre')}")
            st.caption(f"{len(d.get('materiales', []))} materiales • {len(d.get('mano_obra', []))} personal")

        if col2.button("📂 Abrir", key=p.id, use_container_width=True):
            st.session_state.partida_abierta = {"id": p.id, **d}
            st.rerun()

    # =====================================================
    # 📚 HISTORIAL DE AVANCES (AL FINAL)
    # =====================================================
    st.divider()
    st.title("📚 Historial de Avances")

    for p in partidas:
        avances = obra_ref.collection("partidas").document(p.id) \
            .collection("avances") \
            .order_by("fecha", direction=firestore.Query.DESCENDING) \
            .stream()

        avances = [a.to_dict() for a in avances]

        if avances:
            d = p.to_dict()
            st.subheader(f"🧱 {d.get('codigo')} - {d.get('nombre')}")

            for av in avances:
                fecha = av.get("fecha")
                fecha_txt = fecha.astimezone(tz).strftime("%d/%m/%Y %H:%M") if fecha else "N/D"

                with st.expander(f"📅 {fecha_txt} — {av.get('usuario')}"):
                    st.write(av.get("descripcion", ""))

                    # 📋 Detalle del avance
                    if av.get("detalle"):
                        st.table(pd.DataFrame(av["detalle"]))

                    st.markdown("### 💰 Resumen del avance")

                    df_resumen = pd.DataFrame([{
                        "Mano de obra (S/)": av.get("subtotal_mano_obra", 0),
                        "Materiales (S/)": av.get("subtotal_materiales", 0),
                        "Total avance (S/)": av.get("total_avance", 0)
                    }])

                    st.table(df_resumen)

                    rend_real = av.get("rendimiento_real", 0)
                    porc = av.get("porcentaje_rendimiento", 0)

                    st.markdown("### 📊 Rendimiento del día")

                    st.caption(
                        f"🔎 Rendimiento real: **{rend_real:.2f} {d.get('unidad_rendimiento','')}** "
                        f"({porc*100:.1f}% del plan)"
                    )

                    st.progress(min(porc, 1.0))


                    # 👷 MANO DE OBRA
                    if av.get("mano_obra_detalle"):
                        st.markdown("### 👷 Mano de Obra")
                        st.table(pd.DataFrame(av["mano_obra_detalle"]))

                    # 🧱 MATERIALES
                    if av.get("materiales_detalle"):
                        st.markdown("### 🧱 Materiales")
                        st.table(pd.DataFrame(av["materiales_detalle"]))



                    # 📸 Mostrar fotos del avance
                    fotos = av.get("fotos", [])
                    if fotos:
                        st.markdown("📸 **Fotos del avance**")
                        cols = st.columns(min(3, len(fotos)))  # máximo 3 por fila

                        for i, url in enumerate(fotos):
                            with cols[i % 3]:
                                st.image(url, use_container_width=True)
# =========================================================
# ================= VISTA DE AVANCE ========================
# =========================================================
else:
    partida = st.session_state.partida_abierta
    
    # 🆕 TÍTULO CON RENDIMIENTO Y UNIDAD
    st.title(f"🧱 {partida['codigo']} - {partida['nombre']}")
    
    col_info1, col_info2 = st.columns(2)
    col_info1.metric(
        "📊 Valor de Rendimiento", 
        f"{partida.get('valor_rendimiento', 0):,.2f}"
    )
    col_info2.metric(
        "📏 Unidad", 
        partida.get('unidad_rendimiento', 'N/D')
    )



  

        
    st.divider()

    
    # =====================================================
    st.subheader("📦 Materiales asignados a esta sección")

    
    
    partida_ref = obra_ref.collection("partidas").document(partida["id"])
    partida_actual = partida_ref.get().to_dict()

    filas_seccion = []

    for mat in partida_actual.get("materiales", []):
        nombre = mat.get("nombre")
        unidad = mat.get("unidad", "und")

        stock_inicial_asignado = float(mat.get("cantidad_asignada", 0))
        gastado = float(mat.get("gastado", 0))
        stock_actual_asignado = stock_inicial_asignado - gastado

        filas_seccion.append({
        "Material": nombre,
        "Unidad": unidad,
        "Stock inicial asignado": round(stock_inicial_asignado, 2),
        "Gastado": round(gastado, 2),
        "Stock actual asignado": round(stock_actual_asignado, 2),
        "_max": round(stock_actual_asignado, 2)  # 👈 límite por fila
        })


    if filas_seccion:
        st.dataframe(
            pd.DataFrame(filas_seccion),
            use_container_width=True,
            hide_index=True
        )
    else:
            st.info("Esta sección no tiene materiales asignados")
    # =====================================================
    # 🔹 PRECIOS DE MATERIALES DESDE FIREBASE (OBRA)
    # =====================================================
    materiales_obra = obra_ref.collection("materiales").stream()
    precios_materiales = {
        m.to_dict().get("nombre"): float(m.to_dict().get("precio_unitario", 0))
        for m in materiales_obra
        }
    # =====================================================
    # 🔹 MANO DE OBRA (CON ASISTENCIA INTEGRADA)
    # =====================================================
    # =====================================================
    # 🔹 MANO DE OBRA (TIEMPO REAL – PATRÓN CORRECTO)
    # =====================================================

    st.subheader("👷 Mano de Obra")

    editor_key = f"mo_df_{partida['id']}"
    editor_ui_key = f"mo_editor_ui_{partida['id']}"

    valor_rendimiento_seccion = float(partida.get("valor_rendimiento", 1))
    hh_por_m3 = float(partida.get("hh_por_m3", 2.16))  # o fijo si aún no lo guardas

    # 1️⃣ Inicializar UNA sola vez
    if editor_key not in st.session_state:
        filas_mo = []
        for t in partida.get("mano_obra", []):
            filas_mo.append({
                "Asistencia": False,
                "ID": t.get("trabajador_id"),
                "Tipo": "Mano de obra",
                "Descripción": t["nombre"],
                "Rendimiento": 0.0,
                "Precio": 0.0,
                "Cantidad": 0.0,
                "Parcial": 0.0
            })
        st.session_state[editor_key] = pd.DataFrame(filas_mo)

    df_mo = st.session_state[editor_key]
    df_mo_before = df_mo.copy(deep=True)
    # 2️⃣ Asegurar columnas
    for col in ["Rendimiento", "Precio", "Cantidad", "Parcial", "Asistencia"]:
        if col not in df_mo.columns:
            df_mo[col] = 0.0 if col != "Asistencia" else False

    # 3️⃣ Calcular SIEMPRE antes del editor
    for idx, row in df_mo.iterrows():
        rendimiento = float(row["Rendimiento"])
        precio = float(row["Precio"])

        jornal = rendimiento * 8
        cantidad = jornal / valor_rendimiento_seccion if valor_rendimiento_seccion > 0 else 0
        parcial = cantidad * precio

        df_mo.at[idx, "Cantidad"] = round(cantidad, 4)
        df_mo.at[idx, "Parcial"] = round(parcial, 2)

    # 4️⃣ Editor
    df_mo_edit = st.data_editor(
        df_mo,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Asistencia": st.column_config.CheckboxColumn("¿Asistió?"),
            "ID": None,
            "Tipo": st.column_config.TextColumn(disabled=True),
            "Descripción": st.column_config.TextColumn(disabled=True),
            "Rendimiento": st.column_config.NumberColumn("Rendimiento", min_value=0, step=0.1),
            "Precio": st.column_config.NumberColumn("Precio", min_value=0, format="S/ %.2f"),
            "Cantidad": st.column_config.NumberColumn("Cantidad", disabled=True),
            "Parcial": st.column_config.NumberColumn("Parcial", format="S/ %.2f", disabled=True),
        },
        key=editor_ui_key
    )


    
    # =============================
    # 📊 RENDIMIENTO REAL (LÓGICO)
    # =============================

    # =============================
    # 📊 RENDIMIENTO REAL (CORRECTO APU)
    # =============================

    # Cuadrilla humana (suma del rendimiento humano)
    cuadrilla_real = df_mo_edit["Rendimiento"].sum()

    # HH por día
    hh_dia = cuadrilla_real * 8

    # Rendimiento real (m³/día)
    rendimiento_real = round(hh_dia / hh_por_m3, 2) if hh_por_m3 > 0 else 0

    valor_rendimiento_plan = float(partida.get("valor_rendimiento", 0))

    porcentaje_rendimiento = (
        rendimiento_real / valor_rendimiento_plan
        if valor_rendimiento_plan > 0
        else 0
    )

    # =============================
    # 📊 BARRA DE AVANCE DE RENDIMIENTO
    # =============================

    st.markdown("### 📊 Avance de Rendimiento")

    st.caption(
        f"🔎 Rendimiento real: **{rendimiento_real:.2f} {partida.get('unidad_rendimiento','')}** "
        f"({porcentaje_rendimiento*100:.1f}% del plan)"
    )

    st.progress(min(porcentaje_rendimiento, 1.0))

    st.divider()

   


    # 5️⃣ Guardar
    st.session_state[editor_key] = df_mo_edit

    # =============================
    # 🧮 TOTAL MANO DE OBRA (TIEMPO REAL)
    # =============================
    total_mo = df_mo_edit["Parcial"].sum()

    st.markdown("### 💰 Total Mano de Obra")
    st.metric(
        label="Suma Parcial Mano de Obra",
        value=f"S/ {total_mo:,.2f}"
    )


    # 🔁 Detectar cambios y forzar doble refresh
    if not df_mo_edit.equals(df_mo):
        st.session_state.doble_refresh = 2


    # 🔹 MATERIALES (CON VALIDACIÓN DE STOCK ASIGNADO)
    #=====================================================
   
    # =====================================================
    # 🔹 MATERIALES (MISMO PATRÓN QUE MANO DE OBRA)
    # =====================================================

    st.subheader("🧱 Materiales")

    editor_key_mat = f"mat_df_{partida['id']}"
    editor_ui_key_mat = f"mat_editor_ui_{partida['id']}"

    # 1️⃣ Inicializar UNA sola vez
    if editor_key_mat not in st.session_state:
        filas_mat = []

        for m in partida_actual.get("materiales", []):
            nombre = m.get("nombre")
            precio = precios_materiales.get(nombre, 0.0)

            stock_asignado = float(m.get("cantidad_asignada", 0))
            gastado = float(m.get("gastado", 0))
            disponible = stock_asignado - gastado

            filas_mat.append({
                "Tipo": "Material",
                "Descripción": nombre,
                "Disponible": round(disponible, 2),
                "Cantidad": 0.0,      # 👈 SOLO UNA
                "Precio": round(precio, 2),
                "Parcial": 0.0
            })

        st.session_state[editor_key_mat] = pd.DataFrame(filas_mat)

    df_mat = st.session_state[editor_key_mat]

    # 2️⃣ Asegurar columnas
    for col in ["Cantidad", "Precio", "Parcial"]:
        if col not in df_mat.columns:
            df_mat[col] = 0.0

    # 3️⃣ EDITOR (primero)
    df_mat_edit = st.data_editor(
        df_mat,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Tipo": st.column_config.TextColumn(disabled=True),
            "Descripción": st.column_config.TextColumn(disabled=True),
            "Disponible": st.column_config.NumberColumn("Stock disponible", disabled=True),
            "Cantidad": st.column_config.NumberColumn("Usar", min_value=0),
            "Precio": st.column_config.NumberColumn("Precio", format="S/ %.2f"),
            "Parcial": st.column_config.NumberColumn("Parcial", format="S/ %.2f", disabled=True),
        },
        key=editor_ui_key_mat
    )

    # 4️⃣ RECALCULAR DESPUÉS DEL EDITOR (🔥 AQUÍ ESTABA EL ERROR)
    for idx, row in df_mat_edit.iterrows():
        cantidad = float(row["Cantidad"])
        precio = float(row["Precio"])
        df_mat_edit.at[idx, "Parcial"] = round(cantidad * precio, 2)

    # 5️⃣ Guardar estado
    st.session_state[editor_key_mat] = df_mat_edit

    # =============================
    # 🧮 TOTAL MATERIALES (TIEMPO REAL)
    # =============================
    total_mat = df_mat_edit["Parcial"].sum()

    st.markdown("### 💰 Total Materiales")
    st.metric(
        label="Suma Parcial Materiales",
        value=f"S/ {total_mat:,.2f}"
)

hay = False


for av in avances_docs:
    hay = True
    d = av.to_dict()

    fecha_raw = d.get("fecha")

    if isinstance(fecha_raw, str):
        f = datetime.fromisoformat(fecha_raw)

    elif hasattr(fecha_raw, "to_datetime"):
        # Firestore Timestamp
        f = fecha_raw.to_datetime()

    else:
        # 🔁 MISMO COMPORTAMIENTO DE ANTES
        f = datetime.now()

    prog = d.get("porcentaje_avance_financiero", 0)

    with st.expander(
        f"📅 {f:%d/%m/%Y %H:%M} | 📈 {prog}% | {d.get('responsable')}"
    ):
        st.write(d.get("observaciones"))
        st.metric("Costo del día", f"S/ {d.get('costo_total_dia', 0):,.2f}")
        st.progress(min(prog / 100, 1.0))

        st.markdown("### 🧱 Materiales usados")
        for m in d.get("materiales_usados", []):
            st.write(
                f"- **{m['nombre']}** ({m['unidad']}): "
                f"{m['cantidad']} × S/ {m['precio_unitario']} "
                f"= **S/ {m['subtotal']}**"
            )
            st.stop()


    # 🔄 EJECUTOR DE DOBLE REFRESH
    if st.session_state.doble_refresh > 0:
        st.session_state.doble_refresh -= 1
        st.rerun()

        for img in d.get("fotos", []):
            st.image(img, use_container_width=True)
            
if not hay:
    st.info("Aún no hay avances registrados.")
