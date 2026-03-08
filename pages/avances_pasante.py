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
    # 🔥 LIMPIAR ESTADOS DE EDITORES AL REGRESAR
    keys_to_clear = [k for k in st.session_state.keys() if k.startswith(("mo_df_", "mat_df_", "mo_editor_ui_", "mat_editor_ui_"))]
    for k in keys_to_clear:
        del st.session_state[k]
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

    # -------- SECCIONES (BOTONES Y PROGRESO ACUMULADO) --------
    for p in partidas:
        d = p.to_dict()
        
        # 1. Obtener métricas de rendimiento (Usando valor_rendimiento como meta)
        # Usamos .get() con 0.0 por defecto para evitar errores de tipo
        meta_rendimiento = float(d.get("valor_rendimiento", 0))  
        acumulado = float(d.get("rendimiento_acumulado", 0))
        unidad = d.get('unidad_rendimiento', 'und')
        
        # 2. Calcular porcentaje total de la sección
        porcentaje_total = (acumulado / meta_rendimiento) if meta_rendimiento > 0 else 0
        
        # 3. Diseño de la tarjeta de la sección
        with st.container(border=True):
            col_txt, col_met, col_btn = st.columns([4, 3, 1.2])
            
            with col_txt:
                st.markdown(f"### 🧱 {d.get('codigo')} - {d.get('nombre')}")
                # Mostramos el Valor de Rendimiento como la meta oficial
                st.markdown(f"**Meta total:** `{meta_rendimiento:,.2f} {unidad}`")
            
            with col_met:
                # Mostrar métrica de avance con formato numérico claro
                st.write(f"**Avance:** {acumulado:,.2f} {unidad}")
                
                # Barra de progreso: min(progreso, 1.0) para evitar que la barra se rompa si exceden la meta
                progreso_visual = min(porcentaje_total, 1.0)
                st.progress(progreso_visual)
                
                # Porcentaje con color según estado
                porcentaje_texto = f"{porcentaje_total*100:.1f}%"
                if porcentaje_total >= 1.0:
                    st.caption(f"✅ **Completado: {porcentaje_texto}**")
                else:
                    st.caption(f"📈 **Progreso: {porcentaje_texto}**")

            with col_btn:
                st.write("###") # Espaciador para alinear el botón
                if st.button("📂 Abrir", key=f"btn_secc_{p.id}", use_container_width=True, type="secondary"):
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
            trabajador_id = t.get("trabajador_id")

            # 🔎 Buscar datos reales del trabajador en Firebase
            rol_trabajador = "Sin rol"
            sueldo_diario = 0.0
            sueldo_acumulado = 0.0

            if trabajador_id:
                doc_trab = obra_ref.collection("trabajadores").document(trabajador_id).get()
                if doc_trab.exists:
                    trab_dict = doc_trab.to_dict()
                    rol_trabajador = trab_dict.get("rol", "Sin rol")
                    sueldo_diario = float(trab_dict.get("sueldo_diario", 0.0))
                    sueldo_acumulado = float(trab_dict.get("sueldo_acumulado", 0.0))

            filas_mo.append({
                "Asistencia": False,
                "ID": trabajador_id,
                "Tipo": rol_trabajador,  # 🔥 AQUÍ AHORA VA EL ROL REAL
                "Descripción": t.get("nombre", ""),
                "Rendimiento": 0.0,
                "Precio": sueldo_diario,  # 🔥 AQUÍ AHORA VA EL SUELDO DIARIO
                "Cantidad": 0.0,
                "Parcial": 0.0,
                "Sueldo Acumulado": sueldo_acumulado  # 🔥 ACUMULADO DEL TRABAJADOR
            })

        st.session_state[editor_key] = pd.DataFrame(filas_mo)

            

    df_mo = st.session_state[editor_key]
    df_mo_before = df_mo.copy(deep=True)
    # 2️⃣ Asegurar columnas
    for col in ["Rendimiento", "Precio", "Cantidad", "Parcial", "Asistencia", "Sueldo Acumulado"]:
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
            "Sueldo Acumulado": st.column_config.NumberColumn("Sueldo Acumulado", format="S/ %.2f", disabled=True),
        },
        key=editor_ui_key
    )

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

    # ================= BARRA DE RENDIMIENTO DE LA SECCIÓN =================
    st.markdown("### 📈 Avance de Rendimiento de esta Sección")

    st.caption(
        f"🔎 Rendimiento real del día: **{rendimiento_real:.2f} {partida.get('unidad_rendimiento','')}** "
        f"({porcentaje_rendimiento*100:.1f}% del plan diario)"
    )

    st.progress(min(porcentaje_rendimiento, 1.0))

    # Mostrar también el acumulado de la sección
    acumulado_seccion = float(partida.get('rendimiento_acumulado', 0))
    meta_seccion = float(partida.get('valor_rendimiento', 0))

    if meta_seccion > 0:
        porcentaje_acumulado = acumulado_seccion / meta_seccion
    
        st.caption(
            f"📊 Acumulado de la sección: **{acumulado_seccion:.2f} / {meta_seccion:.2f} {partida.get('unidad_rendimiento','')}** "
            f"({porcentaje_acumulado*100:.1f}% completado)"
        )
    
        st.progress(min(porcentaje_acumulado, 1.0))
    
        col_s1, col_s2, col_s3 = st.columns(3)
        col_s1.metric("🎯 Meta Sección", f"{meta_seccion:,.2f} {partida.get('unidad_rendimiento','')}")
        col_s2.metric("📊 Acumulado", f"{acumulado_seccion:,.2f}", delta=f"{acumulado_seccion - meta_seccion:+,.2f}")
        col_s3.metric("📉 Faltante", f"{max(0, meta_seccion - acumulado_seccion):,.2f}")

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

    # 🔁 Detectar cambios y forzar doble refresh (IGUAL QUE MANO DE OBRA)
    if not df_mat_edit.equals(df_mat):
        st.session_state.doble_refresh = 2

    # 6️⃣ Validación de stock
    for _, row in df_mat_edit.iterrows():
        if row["Cantidad"] > row["Disponible"]:
            st.error(
                f"❌ {row['Descripción']}: "
                f"solo hay {row['Disponible']} disponibles"
            )
            st.stop()

    # 🔄 EJECUTOR DE DOBLE REFRESH
    if st.session_state.doble_refresh > 0:
        st.session_state.doble_refresh -= 1
        st.rerun()

    # 🔹 DESCRIPCIÓN Y FOTOS    
    # =====================================================
    descripcion = st.text_area("📝 Descripción del trabajo realizado")

    fotos = st.file_uploader(
        "📸 Subir fotos del avance (mínimo 3)",
        accept_multiple_files=True,
        type=["jpg", "png", "jpeg"]
    )

    col1, col2 = st.columns(2)

# =====================================================
# 💾 GUARDAR AVANCE Y ACTUALIZAR STOCK Y RENDIMIENTO
# =====================================================
    if col1.button("💾 Guardar Avance", type="primary"):
        if not descripcion.strip():
            st.error("Falta descripción")
        elif not fotos or len(fotos) < 3:
            st.error("Mínimo 3 fotos")
        else:
            with st.spinner("Guardando avance y actualizando métricas..."):
                try:
                    # 1. Subir fotos
                    urls = []
                    for f in fotos:
                        res = cloudinary.uploader.upload(f, folder=f"obras/{obra_id}/avances")
                        urls.append(res["secure_url"])

                    # 2. Procesar Datos de Materiales y Mano de Obra
                    df_mat_usado = df_mat_edit[df_mat_edit["Cantidad"] > 0].copy()
                    df_mo_asistio = df_mo_edit[df_mo_edit["Asistencia"] == True].copy()
                    
                    gasto_materiales_total = 0.0
                    materiales_para_historial = []

                    # Referencia a la partida actual
                    partida_ref = obra_ref.collection("partidas").document(partida["id"])
                    partida_data = partida_ref.get().to_dict()
                    materiales_partida = partida_data.get("materiales", [])

                    # --- PROCESO DE MATERIALES ---
                    for _, row in df_mat_usado.iterrows():
                        nombre_mat = row["Descripción"]
                        cant_gastada = float(row["Cantidad"])
                        precio_unid = float(row["Precio"])
                        subtotal_mat = cant_gastada * precio_unid
                        
                        gasto_materiales_total += subtotal_mat

                        materiales_para_historial.append({
                            "nombre": nombre_mat,
                            "cantidad": cant_gastada,
                            "unidad": row.get("Unidad", "und"),
                            "subtotal": subtotal_mat
                        })

                        # Descontar stock GENERAL
                        mats_query = obra_ref.collection("materiales").where("nombre", "==", nombre_mat).limit(1).stream()
                        for doc in mats_query:
                            obra_ref.collection("materiales").document(doc.id).update({
                                "stock_actual": firestore.Increment(-cant_gastada)
                            })

                        # Actualizar gastado en el array de la partida
                        for m in materiales_partida:
                            if m.get("nombre") == nombre_mat:
                                m["gastado"] = float(m.get("gastado", 0)) + cant_gastada

                    # --- PROCESO DE ASISTENCIA ---
                    if not df_mo_asistio.empty:
                        batch_asist = db.batch()
                        for _, fila in df_mo_asistio.iterrows():
                            t_id = fila["ID"]
                            if t_id:
                                t_ref = obra_ref.collection("trabajadores").document(t_id)
                                # Actualizar ambos: días asistidos y sueldo acumulado
                                sueldo_parcial = float(fila["Parcial"])
                                batch_asist.update(t_ref, {
                                    "dias_asistidos": firestore.Increment(1),
                                    "sueldo_acumulado": firestore.Increment(sueldo_parcial)  # 🔥 ACUMULAR SUELDO
                                })
                        batch_asist.commit()

                    # 3. PREPARAR DOCUMENTO DE AVANCE
                    # antes de convertir, incrementar el acumulado en el dataframe para reflejar el pago
                    if "Sueldo Acumulado" in df_mo_asistio.columns:
                        df_mo_asistio["Sueldo Acumulado"] = (
                            df_mo_asistio["Sueldo Acumulado"].astype(float)
                            + df_mo_asistio["Parcial"].astype(float)
                        )
                    tabla_mano_obra = df_mo_asistio[[
                        "Tipo",
                        "Descripción",
                        "Rendimiento",
                        "Cantidad",
                        "Precio",
                        "Parcial",
                        "Sueldo Acumulado"
                    ]].to_dict(orient="records")

                    tabla_materiales = df_mat_usado[[
                        "Descripción", "Cantidad", "Precio", "Parcial"
                    ]].to_dict(orient="records")

                    avance = {
                        "fecha": datetime.now(tz),
                        "usuario": usuario,
                        "descripcion": descripcion,
                        "subtotal_mano_obra": round(total_mo, 2),
                        "subtotal_materiales": round(total_mat, 2),
                        "total_avance": round(total_mo + total_mat, 2),
                        "rendimiento_real": rendimiento_real,
                        "porcentaje_rendimiento": porcentaje_rendimiento,
                        "mano_obra_detalle": tabla_mano_obra,
                        "materiales_detalle": tabla_materiales,
                        "fotos": urls
                    }

                    # 4. 🔥 ACTUALIZAR SECCIÓN (PARTIDA) EN FIREBASE
                    # Guardamos el avance en su subcolección
                    partida_ref.collection("avances").add(avance)

                    # Actualizamos la partida con el nuevo acumulado y materiales
                    partida_ref.update({
                        "materiales": materiales_partida,
                        "rendimiento_acumulado": firestore.Increment(rendimiento_real),
                        "ultimo_rendimiento": rendimiento_real,
                        "fecha_ultimo_avance": datetime.now(tz)
                    })

                    # 5. ACTUALIZAR TOTALES DE LA OBRA
                    # Nota: no actualizamos gasto_materiales desde esta pantalla, solo se mantiene
                    # el subtotal en el avance. El cálculo global se realiza en otro módulo.
                    obra_ref.update({
                        "gasto_mano_obra": firestore.Increment(total_mo)
                    })

                    st.success(f"✅ Avance guardado. Se sumaron {rendimiento_real} {partida.get('unidad_rendimiento')} al total.")
                    st.session_state.partida_abierta = None
                    st.rerun()

                except Exception as e:
                    st.error(f"Error crítico: {e}")
    if col2.button("⬅️ Volver"):
        st.session_state.partida_abierta = None
        st.rerun()
