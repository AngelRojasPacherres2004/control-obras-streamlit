#materiales.py
import streamlit as st
import pandas as pd
from datetime import datetime
from firebase_admin import firestore
from io import BytesIO
import cloudinary
import cloudinary.uploader

# ================= DB =================
db = firestore.client()

# Configuración Cloudinary
cloudinary.config(
    cloud_name=st.secrets["cloudinary"]["cloud_name"],
    api_key=st.secrets["cloudinary"]["api_key"],
    api_secret=st.secrets["cloudinary"]["api_secret"],
    secure=True
)

# ================= SEGURIDAD =================
if "auth" not in st.session_state:
    st.error("Inicia sesión")
    st.stop()

if st.session_state["auth"]["role"] != "jefe":
    st.warning("Sin permisos")
    st.stop()

# ================= ESTADO =================
st.session_state.setdefault("mat_global", None)
st.session_state.setdefault("mat_obra", None)
st.session_state.setdefault("vista_materiales_globales", False)

# ================= FUNCIONES DE ACTUALIZACIÓN =================
def recalcular_presupuesto_obra(obra_id):
    obra_ref = db.collection("obras").document(obra_id)
    obra_data = obra_ref.get().to_dict()
    
    # 1. Calcular gasto total de materiales COMPRADOS (excluir donaciones)
    mats_docs = obra_ref.collection("materiales").stream()
    mats_lista = [d.to_dict() for d in mats_docs]
    
    # Solo contar materiales comprados (no donados)
    total_gastado = sum(
        float(m.get("subtotal", 0)) 
        for m in mats_lista 
        if m.get("tipo") != "DONACIÓN"
    )
    
    # 2. Recalcular saldos semanales
    presupuesto_semanal_original = obra_data.get("presupuesto_materiales_semanal", [])
    
    # Clonamos la lista para no afectar la original mientras calculamos
    # y reiniciamos el 'gasto' de cada semana para volverlo a sumar
    for sem in presupuesto_semanal_original:
        sem["gasto_real"] = 0.0
        sem["saldo_semanal"] = sem.get("presupuesto_materiales", 0.0)

    # Distribuir cada gasto de la subcolección en su semana correspondiente
    for m in mats_lista:
        # Solo contar materiales comprados
        if m.get("tipo") == "DONACIÓN":
            continue
            
        fecha_mat = m.get("fecha")
        if hasattr(fecha_mat, "to_datetime"): 
            fecha_mat = fecha_mat.to_datetime()
        
        num_sem = obtener_semana_actual_obra(obra_data, fecha_mat)
        
        # Buscar la semana en la lista y restarle
        for sem in presupuesto_semanal_original:
            if sem.get("semana") == num_sem:
                sem["gasto_real"] = round(sem.get("gasto_real", 0) + float(m.get("subtotal", 0)), 2)
                sem["saldo_semanal"] = round(sem["presupuesto_materiales"] - sem["gasto_real"], 2)
                break

    # 3. Cálculo de saldo general
    p_original = float(obra_data.get("presupuesto_materiales", 0))
    saldo_actual = p_original - total_gastado
    
    # 4. Actualizar Firebase con los nuevos saldos semanales
    obra_ref.update({
        "presupuesto_materiales_actual": round(saldo_actual, 2),
        "gasto_materiales": round(total_gastado, 2),
        "presupuesto_materiales_semanal": presupuesto_semanal_original,
        "presupuesto_actualizado": datetime.now()
    })
    return saldo_actual

def cargar_materiales():
    return [{"id": d.id, **d.to_dict()}
            for d in db.collection("materiales").order_by("nombre").stream()]

def obtener_obras():
    return {d.id: d.to_dict().get("nombre", d.id)
            for d in db.collection("obras").stream()}

def cargar_materiales_obra(obra_id):
    return [{"id": d.id, **d.to_dict()}
            for d in db.collection("obras")
            .document(obra_id)
            .collection("materiales")
            .order_by("fecha", direction=firestore.Query.DESCENDING)
            .stream()]

def reset():
    st.session_state.mat_global = None
    st.session_state.mat_obra = None
    st.rerun()

def obtener_semana_actual_obra(obra_data, fecha_consulta=None):
    """Retorna el número de semana (1, 2, 3...) según la fecha de inicio de la obra."""
    if not fecha_consulta:
        fecha_consulta = datetime.now()
    
    f_inicio_obra = obra_data.get("fecha_inicio")
    if not f_inicio_obra:
        return 1
    
    # Convertir a datetime si viene de Firestore (Timestamp)
    if hasattr(f_inicio_obra, "to_datetime"):
        f_inicio_obra = f_inicio_obra.to_datetime()
        
    # Asegurar que ambos sean sin zona horaria para comparar o manejar zonas
    f_inicio_obra = f_inicio_obra.replace(tzinfo=None)
    fecha_consulta = fecha_consulta.replace(tzinfo=None)
    
    dias_transcurridos = (fecha_consulta - f_inicio_obra).days
    if dias_transcurridos < 0: return 1 # Aún no empieza
    
    return (dias_transcurridos // 7) + 1

# ================= UI =================
st.title("🧱 Materiales y Presupuesto")

if not st.session_state["vista_materiales_globales"]:
    if st.button("📦 Materiales globales"):
        st.session_state["vista_materiales_globales"] = True
        st.rerun()

# ================= SELECCIÓN DE OBRA SINCRONIZADA =================
OBRAS = obtener_obras()
lista_ids = list(OBRAS.keys())

# 1. Recuperar la selección global de la sesión
if "obra_id_global" not in st.session_state and lista_ids:
    st.session_state["obra_id_global"] = lista_ids[0]

# 2. Calcular el índice para que el selector aparezca en la obra correcta
indice_actual = 0
if st.session_state["obra_id_global"] in lista_ids:
    indice_actual = lista_ids.index(st.session_state["obra_id_global"])

# 3. Dibujar el selector en el sidebar
obra_id = st.sidebar.selectbox(
    "Seleccionar obra",
    options=lista_ids,
    format_func=lambda x: OBRAS.get(x, x),
    index=indice_actual,
    key="selector_materiales_nav"
)

# 4. Actualizar el estado global por si el usuario cambia de obra aquí mismo
st.session_state["obra_id_global"] = obra_id

# 5. Mostrar confirmación visual de la obra activa
st.sidebar.success(f"🏗️ Obra activa: **{OBRAS.get(obra_id)}**")

# --- MÉTRICAS ACTUALIZADAS EN EL SIDEBAR ---
obra_ref_sidebar = db.collection("obras").document(obra_id).get()
if obra_ref_sidebar.exists:
    obra_data_sidebar = obra_ref_sidebar.to_dict()
    
    # presupuesto_materiales es el TOTAL (fijo)
    p_mats_total = float(obra_data_sidebar.get("presupuesto_materiales", 0))
    # presupuesto_materiales_actual es lo que QUEDA
    p_mats_quedan = float(obra_data_sidebar.get("presupuesto_materiales_actual", p_mats_total))
    p_mats_gastado = float(obra_data_sidebar.get("gasto_materiales", 0))
    
    # Calcular total donado
    total_donaciones = float(obra_data_sidebar.get("total_donaciones_monetarias", 0))
    
    st.sidebar.divider()
    st.sidebar.subheader("📊 Resumen Materiales")
    
    st.sidebar.metric(
        label="Presupuesto Actual", 
        value=f"S/ {p_mats_quedan:,.2f}",
        delta=f"De un total de S/ {p_mats_total:,.2f}",
        delta_color="off"
    )
    
    if total_donaciones > 0:
        st.sidebar.metric(
            label="💝 Donaciones Recibidas",
            value=f"S/ {total_donaciones:,.2f}"
        )
    
    if p_mats_total > 0:
        progreso = max(0.0, min(1.0, p_mats_quedan / p_mats_total))
        st.sidebar.progress(progreso, text=f"Disponible: {progreso*100:.1f}%")
   
st.sidebar.divider()

if not obra_id:
    st.warning("⚠️ No hay obras registradas. Crea una primero en la sección de Obras.")
    st.stop()

# 🔹 Cargar materiales globales UNA SOLA VEZ
materiales = cargar_materiales()

# ================== SECCIÓN A ==================
if st.session_state["vista_materiales_globales"]:

    st.header("📦 Materiales globales")

    df_mat = pd.DataFrame(materiales)

    col1, col2 = st.columns([1.5, 1])

    if st.button("⬅️ Volver"):
        st.session_state["vista_materiales_globales"] = False
        st.rerun()

    # ----- LISTA -----
    with col1:
        busq = st.text_input("Buscar material")
        df_v = df_mat if not busq else df_mat[
            df_mat["nombre"].str.contains(busq, case=False)
        ]

        if not df_v.empty:
            sel = st.dataframe(
                df_v[["nombre", "unidad", "precio_unitario"]],
                hide_index=True,
                use_container_width=True,
                selection_mode="single-row",
                on_select="rerun"
            )
            if sel and sel["selection"]["rows"]:
                st.session_state.mat_global = materiales[
                    df_v.index[sel["selection"]["rows"][0]]
                ]
        else:
            st.info("No hay materiales")

    # ----- FORM CRUD -----
    with col2:
        mat = st.session_state.mat_global
        st.subheader("✏️ Editar" if mat else "➕ Nuevo")

        nombre = st.text_input("Nombre", value=mat["nombre"] if mat else "")
        unidad = st.text_input("Unidad", value=mat["unidad"] if mat else "")
        precio = st.number_input(
            "Precio unitario",
            0.0,
            step=0.01,
            value=float(mat["precio_unitario"]) if mat else 0.0
        )

        if mat:
            if st.button("Actualizar", type="primary", use_container_width=True):
                db.collection("materiales").document(mat["id"]).update({
                    "nombre": nombre,
                    "unidad": unidad,
                    "precio_unitario": precio
                })
                reset()

            if st.button("Eliminar", use_container_width=True):
                db.collection("materiales").document(mat["id"]).delete()
                reset()
        else:
            if st.button("Crear material", type="primary", use_container_width=True):
                if nombre and unidad:
                    db.collection("materiales").add({
                        "nombre": nombre,
                        "unidad": unidad,
                        "precio_unitario": precio,
                        "creado": datetime.now()
                    })
                    reset()
                else:
                    st.error("Campos obligatorios")

    # ⛔ IMPORTANTE: corta aquí
    st.stop()

# ================== SECCIÓN B (CORREGIDA) ==================
st.divider()
st.header("➕ Asignar material a la obra")

# Obtener datos de la obra con validación de existencia de campos
obra_doc = db.collection("obras").document(obra_id).get()
if obra_doc.exists:
    obra_info = obra_doc.to_dict()
    # Si el campo 'actual' no existe, usamos el presupuesto total como inicial
    p_total = float(obra_info.get("presupuesto_materiales", 0))
    p_actual = float(obra_info.get("presupuesto_materiales_actual", p_total))
    
    st.info(f"💰 Saldo disponible: S/ {p_actual:,.2f}")

    if materiales:
        # Usamos un formulario para evitar ejecuciones parciales
        with st.form("form_asignar_material"):
            mat_sel = st.selectbox(
                "Seleccionar Material",
                options=materiales,
                format_func=lambda x: f"{x['nombre']} ({x['unidad']}) - S/ {x['precio_unitario']}"
            )
            cantidad = st.number_input("Cantidad", min_value=0.1, step=1.0, value=1.0)
            
            btn_asignar = st.form_submit_button("Asignar a obra", type="primary")

            if btn_asignar:
                costo_total = round(cantidad * mat_sel["precio_unitario"], 2)
                
                # Volvemos a consultar el saldo más reciente antes de guardar
                obra_ref = db.collection("obras").document(obra_id)
                saldo_fresco = float(obra_ref.get().to_dict().get("presupuesto_materiales_actual", p_total))
                
                if costo_total > saldo_fresco:
                    st.error(f"❌ Presupuesto insuficiente. Costo: S/ {costo_total:,.2f} | Disponible: S/ {saldo_fresco:,.2f}")
                else:
                    # 1. Agregar a la subcolección
                    obra_ref.collection("materiales").add({
                        "material_id": mat_sel["id"],
                        "nombre": mat_sel["nombre"],
                        "unidad": mat_sel["unidad"],
                        "cantidad": cantidad,
                        "precio_unitario": mat_sel["precio_unitario"],
                        "subtotal": costo_total,
                        "tipo": "COMPRADO",  # Marcado como comprado
                        "fecha": datetime.now()
                    })
                    
                    # 2. Actualizar saldos en el documento padre (Obra)
                    recalcular_presupuesto_obra(obra_id)
                    
                    st.success(f"✅ {mat_sel['nombre']} asignado correctamente.")
                    st.rerun()
else:
    st.error("No se encontró la información de la obra.")
# ================== SECCIÓN C: INVENTARIO TOTAL (TODOS LOS MATERIALES) ==================
st.divider()
st.header("🧾 Inventario Total de la Obra")
st.caption("Aquí aparecen Compras, Importaciones y Donaciones por igual.")

# 1. Cargamos TODOS los materiales sin filtros previos
mats_obra = cargar_materiales_obra(obra_id)

# 2. Obtenemos el consumo de los avances (para ver el gasto real en campo)
consumo_por_material = {}
avances_docs = db.collection("obras").document(obra_id).collection("avances").stream()
for av in avances_docs:
    usos = av.to_dict().get("materiales_usados", [])
    for u in usos:
        mid = u.get("material_id")
        cant = float(u.get("cantidad", 0))
        consumo_por_material[mid] = consumo_por_material.get(mid, 0) + cant

if mats_obra:
    resumen_visual = []
    for m in mats_obra:
        mid = m["id"]
        tipo = m.get("tipo", "COMPRADO")
        stock_actual = float(m.get("cantidad", 0))
        gastado_campo = consumo_por_material.get(mid, 0)
        
        # Etiqueta visual para el origen
        if tipo == "DONACIÓN":
            origen_tag = "💝 DONACIÓN"
        elif m.get("es_importado"): # Por si usas una marca de importación
            origen_tag = "📥 IMPORTADO"
        else:
            origen_tag = "🛒 COMPRADO"

        resumen_visual.append({
            "Material": m.get("nombre"),
            "Unidad": m.get("unidad"),
            "Origen": origen_tag,
            "Total Inicial": stock_actual + gastado_campo,
            "Consumo (Campo)": gastado_campo,
            "Disponible Hoy": stock_actual,
            "Precio Unit.": m.get("precio_unitario", 0),
            "Subtotal": m.get("subtotal", 0)
        })

    df_resumen = pd.DataFrame(resumen_visual)

    # Renderizado de la tabla completa
    st.dataframe(
        df_resumen,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Precio Unit.": st.column_config.NumberColumn("Precio (S/)", format="S/ %.2f"),
            "Subtotal": st.column_config.NumberColumn("Inversión (S/)", format="S/ %.2f"),
            "Disponible Hoy": st.column_config.NumberColumn("En Almacén", format="%.2f"),
            "Consumo (Campo)": st.column_config.NumberColumn("Usado", format="%.2f"),
        }
    )

    # --- Gestión Individual ---
    with st.expander("⚙️ Modificar o Eliminar cualquier material"):
        mat_seleccionado = st.selectbox(
            "Seleccione el material (incluye donados)",
            options=mats_obra,
            format_func=lambda x: f"[{x.get('tipo', 'COMPRADO')}] {x['nombre']} - {x['cantidad']} {x['unidad']}"
        )
        
        if mat_seleccionado:
            col_ed1, col_ed2 = st.columns(2)
            
            # Ajuste de cantidad
            valor_db = float(mat_seleccionado.get('cantidad', 0))
            nueva_cant = col_ed1.number_input(
                "Nueva Cantidad Disponible", 
                min_value=0.0, 
                value=max(0.0, valor_db),
                key=f"edit_all_{mat_seleccionado['id']}"
            )
            
            if col_ed1.button("💾 Actualizar Material", use_container_width=True, type="primary"):
                # Actualizar cantidad y subtotal (si es donación, el precio unitario es 0, así que subtotal será 0)
                precio_u = float(mat_seleccionado.get('precio_unitario', 0))
                db.collection("obras").document(obra_id).collection("materiales").document(mat_seleccionado["id"]).update({
                    "cantidad": nueva_cant,
                    "subtotal": round(nueva_cant * precio_u, 2)
                })
                
                recalcular_presupuesto_obra(obra_id)
                st.success(f"✅ {mat_seleccionado['nombre']} actualizado.")
                st.rerun()

            if col_ed2.button("🗑️ Eliminar de la Obra", use_container_width=True):
                db.collection("obras").document(obra_id).collection("materiales").document(mat_seleccionado["id"]).delete()
                recalcular_presupuesto_obra(obra_id)
                st.rerun()
else:
    st.info("🔎 No hay ningún tipo de material registrado.")
# ================== SECCIÓN D ==================
st.divider()
st.header("📥 Importar materiales desde Excel")

archivo = st.file_uploader("Subir Excel", type=["xlsx", "xls"])

if archivo:
    df_excel = pd.read_excel(archivo)
    columnas = {"nombre", "unidad", "cantidad", "precio_unitario"}
    if not columnas.issubset(df_excel.columns):
        st.error("El Excel debe tener: nombre, unidad, cantidad, precio_unitario")
    else:
        df_excel["subtotal"] = df_excel["cantidad"] * df_excel["precio_unitario"]
        st.dataframe(df_excel, use_container_width=True)

        if st.button("Importar materiales a la obra", type="primary"):
            total_importacion = df_excel["subtotal"].sum()
            obra_actual = db.collection("obras").document(obra_id).get().to_dict()
            saldo_disponible = float(obra_actual.get("presupuesto_materiales_actual", 0))
            
            if total_importacion > saldo_disponible:
                st.error(f"❌ El total a importar (S/ {total_importacion:,.2f}) excede el presupuesto disponible (S/ {saldo_disponible:,.2f})")
            else:
                for _, r in df_excel.iterrows():
                    db.collection("obras").document(obra_id).collection("materiales").add({
                        "nombre": r["nombre"],
                        "unidad": r["unidad"],
                        "cantidad": float(r["cantidad"]),
                        "precio_unitario": float(r["precio_unitario"]),
                        "subtotal": round(float(r["cantidad"] * r["precio_unitario"]), 2),
                        "tipo": "COMPRADO",
                        "fecha": datetime.now()
                    })
                nuevo_saldo = recalcular_presupuesto_obra(obra_id)
                st.success(f"✅ {len(df_excel)} materiales importados. Nuevo saldo: S/ {nuevo_saldo:,.2f}")
                st.rerun()

# ================== SECCIÓN E (MEJORADA CON SEMANAS) ==================
st.divider()
st.header("💰 Estado del Presupuesto de Materiales")

obra_final = db.collection("obras").document(obra_id).get().to_dict()
p_semanal_lista = obra_final.get("presupuesto_materiales_semanal", [])
num_sem_actual = obtener_semana_actual_obra(obra_final)

# Buscar datos de la semana actual
datos_sem_actual = next((s for s in p_semanal_lista if s["semana"] == num_sem_actual), None)

if datos_sem_actual:
    st.subheader(f"📅 Semana Actual: {num_sem_actual}")
    col_s1, col_s2, col_s3 = st.columns(3)
    
    p_sem_ini = datos_sem_actual.get("presupuesto_materiales", 0)
    g_sem_real = datos_sem_actual.get("gasto_real", 0)
    s_sem_disp = datos_sem_actual.get("saldo_semanal", p_sem_ini)
    
    col_s1.metric("Asignado Semana", f"S/ {p_sem_ini:,.2f}")
    col_s2.metric("Gastado Semana", f"S/ {g_sem_real:,.2f}", delta=f"Actual", delta_color="inverse")
    col_s3.metric("Disponible Semana", f"S/ {s_sem_disp:,.2f}")
    
    if p_sem_ini > 0:
        st.progress(min(1.0, g_sem_real / p_sem_ini), text=f"Consumo semanal: {(g_sem_real/p_sem_ini)*100:.1f}%")
else:
    st.warning("⚠️ No se encontró presupuesto configurado para esta semana.")

# ================== SECCIÓN F - GESTIÓN DE RECIBOS ==================
st.divider()
st.header("🧾 Gestión de Recibos de Materiales")

tab1, tab2 = st.tabs(["📤 Subir Recibo", "📋 Ver Recibos"])

# ---------- TAB 1: SUBIR RECIBO ----------
with tab1:
    st.subheader("Subir recibo de compra de materiales")
    
    with st.form("form_subir_recibo", clear_on_submit=True):
        col_r1, col_r2 = st.columns(2)
        
        proveedor = col_r1.text_input("Proveedor")
        monto_recibo = col_r2.number_input("Monto Total (S/)", min_value=0.0, step=10.0)
        
        fecha_recibo = st.date_input("Fecha del recibo", value=datetime.now().date())
        descripcion_recibo = st.text_area("Descripción / Concepto")
        
        # Campo para subir fotos
        fotos_recibo = st.file_uploader(
            "📸 Subir fotos del recibo/boleta",
            type=["jpg", "png", "jpeg"],
            accept_multiple_files=True,
            help="Puedes subir múltiples fotos del recibo"
        )
        
        submit_recibo = st.form_submit_button("💾 Guardar Recibo", type="primary")
    
    if submit_recibo:
        if not proveedor or monto_recibo <= 0 or not fotos_recibo:
            st.error("⚠️ Completa todos los campos y sube al menos una foto del recibo")
        else:
            with st.spinner("Subiendo recibo a la nube..."):
                try:
                    # Subir fotos a Cloudinary
                    urls_recibo = []
                    for foto in fotos_recibo:
                        resultado = cloudinary.uploader.upload(
                            foto,
                            folder=f"obras/{obra_id}/recibos"
                        )
                        urls_recibo.append(resultado["secure_url"])
                    
                    # Guardar en Firebase
                    db.collection("obras").document(obra_id).collection("recibos").add({
                        "proveedor": proveedor,
                        "monto": monto_recibo,
                        "fecha": datetime.combine(fecha_recibo, datetime.min.time()),
                        "descripcion": descripcion_recibo,
                        "fotos": urls_recibo,
                        "subido_por": st.session_state["auth"].get("username", "Desconocido"),
                        "timestamp": datetime.now()
                    })
                    
                    st.success(f"✅ Recibo guardado exitosamente con {len(urls_recibo)} foto(s)")
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Error al subir el recibo: {str(e)}")

# ---------- TAB 2: VER RECIBOS ----------
with tab2:
    # Cargar recibos de la obra
    recibos_docs = db.collection("obras").document(obra_id).collection("recibos") \
        .order_by("timestamp", direction=firestore.Query.DESCENDING).stream()
    
    recibos_lista = [{"id": d.id, **d.to_dict()} for d in recibos_docs]
    
    if not recibos_lista:
        st.info("📭 No hay recibos registrados para esta obra")
    else:
        # Mostrar resumen
        total_recibos = sum(r.get("monto", 0) for r in recibos_lista)
        col_t1, col_t2 = st.columns(2)
        col_t1.metric("Total de Recibos", len(recibos_lista))
        col_t2.metric("Monto Total Registrado", f"S/ {total_recibos:,.2f}")
        
        st.divider()
        
        # Mostrar cada recibo
        for recibo in recibos_lista:
            with st.expander(
                f"🧾 {recibo.get('proveedor', 'Sin proveedor')} - S/ {recibo.get('monto', 0):,.2f}",
                expanded=False
            ):
                col_det1, col_det2 = st.columns(2)
                
                # Información del recibo
                fecha_r = recibo.get("fecha")
                if fecha_r:
                    fecha_texto = fecha_r.strftime("%d/%m/%Y") if hasattr(fecha_r, 'strftime') else str(fecha_r)
                else:
                    fecha_texto = "Sin fecha"
                
                col_det1.write(f"**Fecha:** {fecha_texto}")
                col_det2.write(f"**Monto:** S/ {recibo.get('monto', 0):,.2f}")
                
                st.write(f"**Descripción:** {recibo.get('descripcion', 'Sin descripción')}")
                st.caption(f"Subido por: {recibo.get('subido_por', 'Desconocido')}")
                
                # Mostrar fotos
                fotos = recibo.get("fotos", [])
                if fotos:
                    st.write("**📸 Fotos del recibo:**")
                    cols_fotos = st.columns(min(len(fotos), 3))
                    for i, url in enumerate(fotos):
                        cols_fotos[i % 3].image(url, use_container_width=True)
                
                # Botón para eliminar recibo
                if st.button(f"🗑️ Eliminar recibo", key=f"del_recibo_{recibo['id']}"):
                    db.collection("obras").document(obra_id).collection("recibos").document(recibo["id"]).delete()
                    st.success("✅ Recibo eliminado")
                    st.rerun()



# ================== SECCIÓN X ==================
st.divider()
st.header("📤 Exportar materiales y recibos a Excel")

# Preparar datos de materiales
if mats_obra:
    df_export_mats = pd.DataFrame(mats_obra)
    df_export_mats = df_export_mats[["nombre", "unidad", "precio_unitario", "cantidad", "subtotal"]]
else:
    df_export_mats = pd.DataFrame()

# Preparar datos de recibos
recibos_export = db.collection("obras").document(obra_id).collection("recibos").stream()
recibos_data = []
for r in recibos_export:
    r_dict = r.to_dict()
    fecha_r = r_dict.get("fecha")
    fecha_str = fecha_r.strftime("%d/%m/%Y") if fecha_r and hasattr(fecha_r, 'strftime') else str(fecha_r) if fecha_r else "Sin fecha"
    
    recibos_data.append({
        "Proveedor": r_dict.get("proveedor", ""),
        "Monto (S/)": r_dict.get("monto", 0),
        "Fecha": fecha_str,
        "Descripción": r_dict.get("descripcion", ""),
        "Subido por": r_dict.get("subido_por", ""),
        "URLs Fotos": ", ".join(r_dict.get("fotos", []))
    })

df_export_recibos = pd.DataFrame(recibos_data) if recibos_data else pd.DataFrame()

# Crear Excel con múltiples hojas
if not df_export_mats.empty or not df_export_recibos.empty:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        # Hoja de Materiales
        if not df_export_mats.empty:
            df_export_mats.to_excel(writer, index=False, sheet_name="Materiales")
        
        # Hoja de Recibos
        if not df_export_recibos.empty:
            df_export_recibos.to_excel(writer, index=False, sheet_name="Recibos")
    
    buffer.seek(0)

    st.download_button(
        label="📥 Descargar Excel completo",
        data=buffer,
        file_name=f"materiales_recibos_{obra_id}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.info("No hay materiales ni recibos para exportar")