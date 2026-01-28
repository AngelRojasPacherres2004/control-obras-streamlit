# avances_pasante.py
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
    st.title(f"🧱 {partida['codigo']} - {partida['nombre']}")
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
    st.subheader("👷 Mano de Obra")

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

    df_mo = pd.DataFrame(filas_mo)

    df_mo_edit = st.data_editor(
        df_mo,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Asistencia": st.column_config.CheckboxColumn("¿Asistió?"),
            "ID": None,  # Ocultar
            "Tipo": st.column_config.TextColumn("Tipo", disabled=True),  # 🔒 NO editable
            "Descripción": st.column_config.TextColumn("Nombre", disabled=True),  # 🔒 NO editable
            "Rendimiento": st.column_config.NumberColumn("Rendimiento", min_value=0, step=0.1),  # ✅ Editable
            "Precio": st.column_config.NumberColumn("Precio", min_value=0, format="S/ %.2f"),  # ✅ Editable
            "Cantidad": st.column_config.NumberColumn("Cantidad", min_value=0, step=0.5),  # ✅ Editable
            "Parcial": st.column_config.NumberColumn("Parcial", min_value=0, format="S/ %.2f"),  # ✅ Editable
        },
        key=f"mo_editor_{partida['id']}"
    )
    # 🔹 MATERIALES (CON VALIDACIÓN DE STOCK ASIGNADO)
    #=====================================================
    st.subheader("🧱 Materiales")

    # Obtener la partida actualizada
    partida_ref = obra_ref.collection("partidas").document(partida["id"])
    partida_actual = partida_ref.get().to_dict()

    filas_mat = []
    for m in partida_actual.get("materiales", []):
        nombre = m.get("nombre")
        precio = precios_materiales.get(nombre, 0.0)
    
        # Calcular stock disponible de la partida
        stock_asignado = float(m.get("cantidad_asignada", 0))
        gastado = float(m.get("gastado", 0))
        disponible = stock_asignado - gastado
    
        filas_mat.append({
            "Tipo": "Material",
            "Descripción": nombre,
            "Disponible": disponible,  # ✅ Columna informativa
            "Cantidad": 0.0,
            "Precio": precio,
            "Parcial": 0.0
        })

    df_mat = pd.DataFrame(filas_mat)

    df_mat_edit = st.data_editor(
        df_mat,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Tipo": st.column_config.TextColumn(disabled=True),
            "Descripción": st.column_config.TextColumn(disabled=True),
            "Disponible": st.column_config.NumberColumn(
                "Stock Disponible",
                disabled=True,
                help="Cantidad asignada menos lo ya gastado en esta sección"
            ),
            "Cantidad": st.column_config.NumberColumn("Usar", min_value=0),
            "Precio": st.column_config.NumberColumn(disabled=True),
            "Parcial": st.column_config.NumberColumn(disabled=True)
        },
        key=f"editor_mat_{partida['id']}"
    )
    # ✅ VALIDACIÓN DE STOCK
    if not df_mat_edit.empty:
        for _, row in df_mat_edit.iterrows():
            cantidad = float(row["Cantidad"])
            disponible = float(row["Disponible"])
        
            if cantidad > disponible:
                st.error(f"❌ {row['Descripción']}: Solo hay {disponible} disponibles, intentaste usar {cantidad}")
                st.stop()  
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
# 💾 GUARDAR AVANCE Y ACTUALIZAR STOCK REAL
# =====================================================
    if col1.button("💾 Guardar Avance", type="primary"):
        if not descripcion.strip():
            st.error("Falta descripción")
        elif not fotos or len(fotos) < 3:
            st.error("Mínimo 3 fotos")
        else:
            with st.spinner("Guardando avance y actualizando inventario..."):
                try:
                    # 1. Subir fotos
                    urls = []
                    for f in fotos:
                        res = cloudinary.uploader.upload(f, folder=f"obras/{obra_id}/avances")
                        urls.append(res["secure_url"])

                    # 2. Filtrar solo lo usado
                    df_mat_usado = df_mat_edit[df_mat_edit["Cantidad"] > 0].copy()
                    df_mo_asistio = df_mo_edit[df_mo_edit["Asistencia"] == True].copy()
                
                    # Eliminar columnas auxiliares antes de guardar
                    if "Disponible" in df_mat_usado.columns:
                        df_mat_usado = df_mat_usado.drop(columns=["Disponible"])
                    if "ID" in df_mo_asistio.columns:
                        df_mo_asistio = df_mo_asistio.drop(columns=["ID"])
                
                    detalle = pd.concat([df_mo_asistio, df_mat_usado], ignore_index=True).to_dict("records")

                    # 3. ACTUALIZAR STOCK EN FIREBASE
                    partida_ref = obra_ref.collection("partidas").document(partida["id"])
                    partida_data = partida_ref.get().to_dict()
                    materiales_partida = partida_data.get("materiales", [])

                    # --- PROCESO DE MATERIALES ---
                    for _, row in df_mat_edit[df_mat_edit["Cantidad"] > 0].iterrows():
                        nombre_mat = row["Descripción"]
                        cant_gastada = float(row["Cantidad"])

                        # Descontar stock GENERAL de la obra
                        mats_query = obra_ref.collection("materiales").where("nombre", "==", nombre_mat).limit(1).stream()
                        for doc in mats_query:
                            obra_ref.collection("materiales").document(doc.id).update({
                                "stock_actual": firestore.Increment(-cant_gastada)
                            })

                        # Sumar gastado en la SECCIÓN
                        for m in materiales_partida:
                            if m.get("nombre") == nombre_mat:
                                m["gastado"] = float(m.get("gastado", 0)) + cant_gastada

                    # Guardar materiales actualizados en la sección
                    partida_ref.update({"materiales": materiales_partida})

                    # --- PROCESO DE ASISTENCIA ---
                    asistentes = df_mo_edit[df_mo_edit["Asistencia"] == True]
                    if not asistentes.empty:
                        batch_asist = db.batch()
                        for _, fila in asistentes.iterrows():
                            t_id = fila["ID"]
                            if t_id:  # Verificar que existe el ID
                                t_ref = obra_ref.collection("trabajadores").document(t_id)
                                batch_asist.update(t_ref, {"dias_asistidos": firestore.Increment(1)})
                        batch_asist.commit()

                    # 4. Guardar el documento de avance
                    avance = {
                        "fecha": datetime.now(tz),
                        "usuario": usuario,
                        "descripcion": descripcion,
                        "detalle": detalle,
                        "fotos": urls
                    }

                    obra_ref.collection("partidas").document(partida["id"]).collection("avances").add(avance)

                    st.success("✅ Avance guardado, asistencia registrada y stock actualizado.")
                    st.session_state.partida_abierta = None
                    st.rerun()
            
                except Exception as e:
                    st.error(f"Error al guardar: {e}")
                    import traceback
                    st.code(traceback.format_exc())

    if col2.button("⬅️ Volver"):
        st.session_state.partida_abierta = None
        st.rerun()
