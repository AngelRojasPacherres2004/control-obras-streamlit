# partidas.py
import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
from firebase_admin import firestore

# ================= CONFIGURACIÓN DE ZONA HORARIA =================
local_tz = pytz.timezone('America/Lima')

# ================= DB =================
db = firestore.client()

# ================= SEGURIDAD =================
if "auth" not in st.session_state:
    st.error("Por favor, inicia sesión.")
    st.stop()

auth = st.session_state["auth"]
if auth["role"] != "jefe":
    st.warning("No tienes permisos para gestionar partidas.")
    st.stop()
def recalcular_stock_sin_asignar(obra_id):
    obra_ref = db.collection("obras").document(obra_id)
    
    # Carga masiva de materiales y partidas para evitar múltiples viajes a la red
    materiales_ref = obra_ref.collection("materiales").stream()
    materiales = {m.id: m.to_dict() for m in materiales_ref}
    
    asignados = {mid: 0.0 for mid in materiales.keys()}
    partidas = obra_ref.collection("partidas").stream()
    
    for p in partidas:
        data = p.to_dict()
        for mat in data.get("materiales", []):
            mid = mat.get("material_id")
            if mid in asignados:
                asignados[mid] += float(mat.get("cantidad_asignada", 0))

    batch = db.batch()
    for mid, mat in materiales.items():
        stock_inicial = float(mat.get("stock_inicial", mat.get("stock", 0)))
        sin_asignar = max(stock_inicial - asignados[mid], 0)
        
        mat_ref = obra_ref.collection("materiales").document(mid)
        batch.update(mat_ref, {"stock_sin_asignar": round(sin_asignar, 2)})
    
    batch.commit()
    # IMPORTANTE: Limpiar caché después de actualizar la DB
    st.cache_data.clear()

# ================= FUNCIONES OPTIMIZADAS CON CACHÉ =================
@st.cache_data(ttl=600)  # Caché por 10 minutos
def obtener_obras():
    return {d.id: d.to_dict().get("nombre", d.id) for d in db.collection("obras").stream()}

@st.cache_data(ttl=300)
def obtener_trabajadores_obra(obra_id):
    docs = db.collection("obras").document(obra_id).collection("trabajadores").stream()
    return [{"id": d.id, **d.to_dict()} for d in docs]

@st.cache_data(ttl=300)
def obtener_materiales_obra(obra_id):
    docs = db.collection("obras").document(obra_id).collection("materiales").stream()
    return [{"id": d.id, **d.to_dict()} for d in docs]

@st.cache_data(ttl=300)
def obtener_partidas_obra(obra_id):
    docs = db.collection("obras").document(obra_id).collection("partidas").order_by("codigo").stream()
    return [{"id": d.id, **d.to_dict()} for d in docs]

# ================= UI =================
st.title("📋 Gestión de Secciones de Obra")

# ================= SELECCIÓN DE OBRA SINCRONIZADA =================
OBRAS = obtener_obras()
lista_ids = list(OBRAS.keys())

if "obra_id_global" not in st.session_state and lista_ids:
    st.session_state["obra_id_global"] = lista_ids[0]

indice_actual = 0
if st.session_state.get("obra_id_global") in lista_ids:
    indice_actual = lista_ids.index(st.session_state["obra_id_global"])

obra_id_sel = st.sidebar.selectbox(
    "Seleccionar Obra",
    options=lista_ids,
    format_func=lambda x: OBRAS.get(x, x),
    index=indice_actual,
    key="selector_partidas_global"
)

st.session_state["obra_id_global"] = obra_id_sel

if not obra_id_sel:
    st.info("💡 Por favor, selecciona una obra para gestionar sus secciones.")
    st.stop()

nombre_obra = OBRAS.get(obra_id_sel, "Desconocida")
st.sidebar.success(f"📍 Obra actual: **{nombre_obra}**")
obra_ref = db.collection("obras").document(obra_id_sel)

# 🔁 Recalcular stock una sola vez por sesión y obra
if "stock_recalculado" not in st.session_state:
    recalcular_stock_sin_asignar(obra_id_sel)
    st.session_state.stock_recalculado = True

# Reemplaza el bloque de visualización de stock (aprox. líneas 113-140)
st.subheader("📦 Stock de Materiales por Secciones")

materiales_lista = obtener_materiales_obra(obra_id_sel)
if materiales_lista:
    df_stock = pd.DataFrame(materiales_lista)
    
    # Procesamiento eficiente de columnas con Pandas
    df_stock["Stock inicial"] = df_stock.apply(lambda x: float(x.get("stock_inicial", x.get("stock", 0))), axis=1)
    df_stock["Stock sin asignar"] = df_stock["stock_sin_asignar"].fillna(df_stock["Stock inicial"]).astype(float)
    df_stock["Stock asignado"] = df_stock["Stock inicial"] - df_stock["Stock sin asignar"]
    df_stock["Precio unitario"] = df_stock["precio_unitario"].fillna(0).astype(float)
    
    # Renombrar y seleccionar columnas para mostrar
    df_mostrar = df_stock[[
        "nombre", "unidad", "Stock inicial", "Stock asignado", "Stock sin asignar", "Precio unitario"
    ]].rename(columns={"nombre": "Material", "unidad": "Unidad"})

    st.dataframe(
        df_mostrar,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Precio unitario": st.column_config.NumberColumn("Precio unitario", format="S/ %.2f"),
            "Stock inicial": st.column_config.NumberColumn(format="%.2f"),
            "Stock asignado": st.column_config.NumberColumn(format="%.2f"),
            "Stock sin asignar": st.column_config.NumberColumn(format="%.2f"),
        }
    )


# ================= PESTAÑAS PRINCIPALES =================
tab1, tab2 = st.tabs(["➕ Crear Sección", "📋 Ver Secciones"])
# ================= INICIALIZAR ESTADO DE EDICIÓN =================
if "seccion_en_edicion" not in st.session_state:
    st.session_state.seccion_en_edicion = None
# ================= TAB 1: CREAR SECCIÓN =================
with tab1:
    st.subheader("➕ Crear Nueva Sección")
    
    # Inicializar estado
    if "seccion_editando" not in st.session_state:
        st.session_state.seccion_editando = None
    
    # PASO 1: Datos básicos de la sección
    with st.form("form_datos_seccion", clear_on_submit=False):
        st.markdown("#### 📝 Información de la Sección")
        
        col1, col2 = st.columns(2)
        codigo = col1.text_input("Código de Sección", placeholder="05,05,01")
        nombre = col2.text_input("Nombre de la Sección", placeholder="CONCRETO PREMEZCLADO F'C=210 KG/CM2")
        
        # 🆕 NUEVOS CAMPOS
        col3, col4 = st.columns(2)
        valor_rendimiento = col3.number_input(
            "Valor de Rendimiento",
            min_value=0.0,
            step=1.0,
            format="%.2f",
            placeholder="250000.00"
        )
        
        unidad_rendimiento = col4.selectbox(
            "Unidad de Rendimiento",
            options=["m³", "m²", "kg", "und", "m", "glb", "ton", "lt"],
            index=0
        )
        
        submit_datos = st.form_submit_button("💾 Crear Sección", type="primary")
        
        if submit_datos:
            if not codigo or not nombre:
                st.error("Por favor completa el código y el nombre.")
            elif valor_rendimiento <= 0:
                st.error("El valor de rendimiento debe ser mayor a 0.")
            else:
                st.session_state.seccion_editando = {
                    "codigo": codigo,
                    "nombre": nombre,
                    "valor_rendimiento": valor_rendimiento,  # 🆕
                    "unidad_rendimiento": unidad_rendimiento,  # 🆕
                    "mano_obra": [],
                    "materiales": [],
                    "equipos": []
                }
                st.success("✅ Sección creada. Ahora asigna recursos.")
                st.rerun()
    
    # PASO 2: Asignar recursos a la sección
    if st.session_state.seccion_editando:
        st.divider()
        seccion = st.session_state.seccion_editando
        
        # 🆕 MOSTRAR INFO COMPLETA DE LA SECCIÓN
        st.info(f"📌 **{seccion['codigo']}** - {seccion['nombre']}")
        col_info1, col_info2 = st.columns(2)
        col_info1.metric("Valor de Rendimiento", f"{seccion['valor_rendimiento']:,.2f}")
        col_info2.metric("Unidad", seccion['unidad_rendimiento'])
        
        # ================= ASIGNAR MANO DE OBRA =================
        st.markdown("### 👷 Asignar Mano de Obra")
        
        trabajadores_disponibles = obtener_trabajadores_obra(obra_id_sel)
        
        if trabajadores_disponibles:
            # Filtrar trabajadores ya asignados
            trabajadores_asignados_ids = [t["trabajador_id"] for t in seccion["mano_obra"]]
            trabajadores_sin_asignar = [t for t in trabajadores_disponibles if t["id"] not in trabajadores_asignados_ids]
            
            if trabajadores_sin_asignar:
                trab_sel = st.selectbox(
                    "Seleccionar Trabajador",
                    options=trabajadores_sin_asignar,
                    format_func=lambda x: f"{x['nombre']} - {x['rol']}",
                    key="select_trabajador"
                )
                
                if st.button("➕ Agregar Trabajador", key="btn_add_trab"):
                    seccion["mano_obra"].append({
                        "trabajador_id": trab_sel["id"],
                        "nombre": trab_sel["nombre"],
                        "rol": trab_sel["rol"]
                    })
                    st.success(f"✅ {trab_sel['nombre']} agregado")
                    st.rerun()
            else:
                st.info("Todos los trabajadores disponibles ya están asignados a esta sección.")
        else:
            st.warning("No hay trabajadores registrados en esta obra.")
        
        # Mostrar trabajadores asignados
        if seccion["mano_obra"]:
            st.markdown("**👷 Trabajadores Asignados:**")
            df_mo = pd.DataFrame(seccion["mano_obra"])
            st.dataframe(df_mo[["nombre", "rol"]], use_container_width=True, hide_index=True)
            
            # Opción para eliminar
            if st.checkbox("Mostrar opciones de eliminación (Mano de Obra)"):
                for idx, trab in enumerate(seccion["mano_obra"]):
                    if st.button(f"🗑️ Quitar {trab['nombre']}", key=f"del_trab_{idx}"):
                        seccion["mano_obra"].pop(idx)
                        st.rerun()
        
        st.divider()
        
        # ================= ASIGNAR MATERIALES =================
        st.markdown("### 🧱 Asignar Materiales")
        
        materiales_disponibles = obtener_materiales_obra(obra_id_sel)
        
        if materiales_disponibles:
            # Filtrar materiales ya asignados en esta sesión de edición
            materiales_asignados_ids = [m["material_id"] for m in seccion["materiales"]]
            materiales_sin_asignar = [m for m in materiales_disponibles if m["id"] not in materiales_asignados_ids]
            
            if materiales_sin_asignar:
                # 1. Selector de material
                mat_sel = st.selectbox(
                    "Seleccionar Material",
                    options=materiales_sin_asignar,
                    format_func=lambda x: f"{x['nombre']} (Disp: {x.get('stock_sin_asignar', 0)} {x['unidad']})",

                    key="select_material"
                )
                # 2. Input de cantidad con límite de stock
                stock_disponible = float(
                    mat_sel.get(
                        "stock_sin_asignar",
                        mat_sel.get("stock_inicial", mat_sel.get("stock", 0))
                    )
                )


                col_c1, col_c2 = st.columns([2, 1])

                cant_sel = col_c1.number_input(
                    f"Cantidad a usar ({mat_sel['unidad']})",
                    min_value=0.0,
                    max_value=stock_disponible,
                    step=1.0,                  # ⬅️ + y - de 1.00
                    format="%.2f",              # ⬅️ muestra 1.00
                    disabled=stock_disponible <= 0,
                    help=f"Stock disponible: {stock_disponible} {mat_sel['unidad']}"
                )

                # 3. Botón agregar con validación
                if col_c2.button("➕ Agregar Material", key="btn_add_mat", use_container_width=True):
                    if stock_disponible <= 0:
                        st.error("No hay stock disponible de este material.")
                    elif cant_sel <= 0:
                        st.error("La cantidad debe ser mayor a 0.")
                    elif cant_sel > stock_disponible:
                        st.error(f"No puedes asignar más de {stock_disponible}")
                    else:
                        seccion["materiales"].append({
                            "material_id": mat_sel["id"],
                            "nombre": mat_sel["nombre"],
                            "unidad": mat_sel["unidad"],
                            "cantidad_asignada": cant_sel,
                            "gastado": 0.0,
                            "stock_al_asignar": stock_disponible
                        })
                        st.success(f"✅ {mat_sel['nombre']} ({cant_sel}) agregado")
                        st.rerun()


            else:
                st.info("Todos los materiales disponibles ya están asignados a esta sección.")
        else:
            st.warning("No hay materiales registrados en esta obra.")
        
        # Mostrar materiales asignados con la nueva columna de cantidad
        if seccion["materiales"]:
            st.markdown("**🧱 Materiales Asignados:**")
            df_mat = pd.DataFrame(seccion["materiales"])
            # Ajustamos las columnas a mostrar
            st.dataframe(
                df_mat[["nombre", "cantidad_asignada", "unidad"]], 
                use_container_width=True, 
                hide_index=True
            )
            
            if st.checkbox("Mostrar opciones de eliminación (Materiales)"):
                for idx, mat in enumerate(seccion["materiales"]):
                    if st.button(f"🗑️ Quitar {mat['nombre']}", key=f"del_mat_{idx}"):
                        seccion["materiales"].pop(idx)
                        st.rerun()
        st.divider()
        
        # ================= ASIGNAR EQUIPOS =================
        st.markdown("### 🔧 Asignar Equipos")
        
        with st.form("form_agregar_equipo", clear_on_submit=True):
            col_eq1, col_eq2 = st.columns(2)
            nombre_eq = col_eq1.text_input("Nombre del Equipo", placeholder="HERRAMIENTAS MANUALES")
            codigo_eq = col_eq2.text_input("Código del Equipo", placeholder="570101")
            
            if st.form_submit_button("➕ Agregar Equipo"):
                if nombre_eq and codigo_eq:
                    seccion["equipos"].append({
                        "nombre": nombre_eq,
                        "codigo": codigo_eq
                    })
                    st.success(f"✅ {nombre_eq} agregado")
                    st.rerun()
                else:
                    st.error("Por favor completa nombre y código del equipo.")
        
        # Mostrar equipos asignados
        if seccion["equipos"]:
            st.markdown("**🔧 Equipos Asignados:**")
            df_eq = pd.DataFrame(seccion["equipos"])
            st.dataframe(df_eq[["codigo", "nombre"]], use_container_width=True, hide_index=True)
            
            # Opción para eliminar
            if st.checkbox("Mostrar opciones de eliminación (Equipos)"):
                for idx, eq in enumerate(seccion["equipos"]):
                    if st.button(f"🗑️ Quitar {eq['nombre']}", key=f"del_eq_{idx}"):
                        seccion["equipos"].pop(idx)
                        st.rerun()
        
        st.divider()

        # ================= GUARDAR SECCIÓN COMPLETA =================
        st.markdown("### 💾 Guardar Sección")

        col_final1, col_final2 = st.columns(2)

        if col_final1.button(
            "💾 GUARDAR SECCIÓN COMPLETA",
            type="primary",
            use_container_width=True
        ):
            if (
                not seccion["mano_obra"]
                and not seccion["materiales"]
                and not seccion["equipos"]
            ):
                st.error(
                    "Debes asignar al menos un recurso "
                    "(mano de obra, material o equipo)"
                )
            else:
                seccion["fecha_creacion"] = datetime.now(local_tz)


                # 🔹 GUARDAR SECCIÓN
                db.collection("obras") \
                    .document(obra_id_sel) \
                    .collection("partidas") \
                    .add(seccion)
                # 🔹 RECALCULAR STOCK SIN ASIGNAR
                recalcular_stock_sin_asignar(obra_id_sel)
                st.session_state.seccion_editando = None
                st.success("✅ Sección guardada y stock actualizado")
                st.rerun()

        if col_final2.button(
            "❌ Cancelar y Limpiar",
            use_container_width=True
        ):
            st.session_state.seccion_editando = None
            st.rerun()

# ================= TAB 2: VER / EDITAR SECCIONES =================
with tab2:
    st.subheader("📋 Secciones Registradas")
    
    # USA LA FUNCIÓN OPTIMIZADA AQUÍ:
    partidas = obtener_partidas_obra(obra_id_sel)
    
    if not partidas:
        st.info("No hay secciones registradas en esta obra.")
    else:
        st.success(f"**Total de Secciones:** {len(partidas)}")
        st.divider()
        
        # 🔥 MODO EDICIÓN ACTIVO
        if st.session_state.seccion_en_edicion:
            sec_edit = st.session_state.seccion_en_edicion
            
            st.warning(f"✏️ **EDITANDO:** {sec_edit['codigo']} - {sec_edit['nombre']}")
            
            # ================= EDITAR MANO DE OBRA =================
            st.markdown("### 👷 Mano de Obra")
            
            trabajadores_disponibles = obtener_trabajadores_obra(obra_id_sel)
            trabajadores_asignados_ids = [t["trabajador_id"] for t in sec_edit["mano_obra"]]
            trabajadores_sin_asignar = [t for t in trabajadores_disponibles if t["id"] not in trabajadores_asignados_ids]
            
            if trabajadores_sin_asignar:
                trab_sel = st.selectbox(
                    "Agregar Trabajador",
                    options=trabajadores_sin_asignar,
                    format_func=lambda x: f"{x['nombre']} - {x['rol']}",
                    key="edit_select_trabajador"
                )
                
                if st.button("➕ Agregar Trabajador", key="edit_btn_add_trab"):
                    sec_edit["mano_obra"].append({
                        "trabajador_id": trab_sel["id"],
                        "nombre": trab_sel["nombre"],
                        "rol": trab_sel["rol"]
                    })
                    st.rerun()
            
            # Mostrar y eliminar trabajadores
            if sec_edit["mano_obra"]:
                df_mo = pd.DataFrame(sec_edit["mano_obra"])
                st.dataframe(df_mo[["nombre", "rol"]], use_container_width=True, hide_index=True)
                
                if st.checkbox("Mostrar opciones de eliminación (Mano de Obra)", key="edit_check_mo"):
                    for idx, trab in enumerate(sec_edit["mano_obra"]):
                        if st.button(f"🗑️ Quitar {trab['nombre']}", key=f"edit_del_trab_{idx}"):
                            sec_edit["mano_obra"].pop(idx)
                            st.rerun()
            
            st.divider()
            
            # ================= EDITAR MATERIALES =================
            st.markdown("### 🧱 Materiales")
            
            materiales_disponibles = obtener_materiales_obra(obra_id_sel)

            # 🔧 DEVOLVER STOCK DE ESTA SECCIÓN
            for m in materiales_disponibles:
                for mat_sec in sec_edit["materiales"]:
                    if m["id"] == mat_sec["material_id"]:
                        m["stock_sin_asignar"] = float(m.get("stock_sin_asignar", 0)) + float(mat_sec.get("cantidad_asignada", 0))

            materiales_asignados_ids = [m["material_id"] for m in sec_edit["materiales"]]
            materiales_sin_asignar = [
                m for m in materiales_disponibles
                if m["id"] not in materiales_asignados_ids
            ]

            if materiales_sin_asignar:
                mat_sel = st.selectbox(
                    "Agregar Material",
                    options=materiales_sin_asignar,
                    format_func=lambda x: f"{x['nombre']} (Disp: {x.get('stock_sin_asignar', 0)} {x['unidad']})",

                    key="edit_select_material"
                )
                
                stock_disponible = float(mat_sel.get("stock_sin_asignar", 0))

                
                col_c1, col_c2 = st.columns([2, 1])
                
                cant_sel = col_c1.number_input(
                    f"Cantidad ({mat_sel['unidad']})",
                    min_value=0.0,
                    max_value=stock_disponible,
                    step=1.0,
                    format="%.2f",
                    disabled=stock_disponible <= 0,
                    key="edit_cant_material"
                )
                
                # En la línea 245 (cuando agregas material a una sección)
            if col_c2.button("➕ Agregar Material", key="btn_add_mat", use_container_width=True):
                if stock_disponible <= 0:
                    st.error("No hay stock disponible de este material.")
                elif cant_sel <= 0:
                    st.error("La cantidad debe ser mayor a 0.")
                elif cant_sel > stock_disponible:
                    st.error(f"No puedes asignar más de {stock_disponible}")
                else:
                    seccion["materiales"].append({
                    "material_id": mat_sel["id"],
                    "nombre": mat_sel["nombre"],
                    "unidad": mat_sel["unidad"],
                    "cantidad_asignada": cant_sel,
                    "gastado": 0.0,
                    "stock_al_asignar": stock_disponible
                })
                st.success(f"✅ {mat_sel['nombre']} ({cant_sel}) agregado")
                st.rerun()
            
            # Mostrar y eliminar materiales
            if sec_edit["materiales"]:
                df_mat = pd.DataFrame(sec_edit["materiales"])
                
                if "cantidad_asignada" not in df_mat.columns:
                    df_mat["cantidad_asignada"] = 0.0
                
                st.dataframe(
                    df_mat[["nombre", "cantidad_asignada", "unidad"]],
                    use_container_width=True,
                    hide_index=True
                )
                
                if st.checkbox("Mostrar opciones de eliminación (Materiales)", key="edit_check_mat"):
                    for idx, mat in enumerate(sec_edit["materiales"]):
                        if st.button(f"🗑️ Quitar {mat['nombre']}", key=f"edit_del_mat_{idx}"):
                            sec_edit["materiales"].pop(idx)
                            st.rerun()
            
            st.divider()
            
            # ================= EDITAR EQUIPOS =================
            st.markdown("### 🔧 Equipos")
            
            with st.form("edit_form_agregar_equipo", clear_on_submit=True):
                col_eq1, col_eq2 = st.columns(2)
                nombre_eq = col_eq1.text_input("Nombre del Equipo")
                codigo_eq = col_eq2.text_input("Código del Equipo")
                
                if st.form_submit_button("➕ Agregar Equipo"):
                    if nombre_eq and codigo_eq:
                        sec_edit["equipos"].append({
                            "nombre": nombre_eq,
                            "codigo": codigo_eq
                        })
                        st.success(f"✅ {nombre_eq} agregado")
                        st.rerun()
            
            # Mostrar y eliminar equipos
            if sec_edit["equipos"]:
                df_eq = pd.DataFrame(sec_edit["equipos"])
                st.dataframe(df_eq[["codigo", "nombre"]], use_container_width=True, hide_index=True)
                
                if st.checkbox("Mostrar opciones de eliminación (Equipos)", key="edit_check_eq"):
                    for idx, eq in enumerate(sec_edit["equipos"]):
                        if st.button(f"🗑️ Quitar {eq['nombre']}", key=f"edit_del_eq_{idx}"):
                            sec_edit["equipos"].pop(idx)
                            st.rerun()
            
            st.divider()
            
            # ================= GUARDAR CAMBIOS =================
            col_save1, col_save2 = st.columns(2)
            
            if col_save1.button("💾 GUARDAR CAMBIOS", type="primary", use_container_width=True):
                db.collection("obras").document(obra_id_sel).collection("partidas").document(sec_edit["id"]).update({
                    "mano_obra": sec_edit["mano_obra"], 
                    "materiales": sec_edit["materiales"],
                    "equipos": sec_edit["equipos"],
                    "fecha_modificacion": datetime.now(local_tz)
                })
                recalcular_stock_sin_asignar(obra_id_sel)
                st.session_state.seccion_en_edicion = None
                st.success("✅ Cambios guardados")
                st.rerun()
            
            if col_save2.button("❌ Cancelar Edición", use_container_width=True):
                st.session_state.seccion_en_edicion = None
                st.rerun()
        
        # 🔥 MODO VISTA (cuando no hay edición activa)
        else:
            for partida in partidas:
                with st.expander(f"**{partida.get('codigo')}** - {partida.get('nombre')}", expanded=False):
                    
                    # Mano de Obra
                    if partida.get("mano_obra"):
                        st.markdown("**👷 Mano de Obra:**")
                        df_mo = pd.DataFrame(partida["mano_obra"])
                        st.dataframe(df_mo[["nombre", "rol"]], use_container_width=True, hide_index=True)
                    
                    # Materiales
                    if partida.get("materiales"):
                        st.markdown("**🧱 Materiales:**")
                        df_mat = pd.DataFrame(partida["materiales"])
                        
                        if "cantidad_asignada" not in df_mat.columns:
                            df_mat["cantidad_asignada"] = 0.0
                        
                        st.dataframe(
                            df_mat[["nombre", "cantidad_asignada", "unidad"]],
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "cantidad_asignada": st.column_config.NumberColumn(
                                    "Cantidad",
                                    format="%.2f"
                                )
                            }
                        )
                    
                    # Equipos
                    if partida.get("equipos"):
                        st.markdown("**🔧 Equipos:**")
                        df_eq = pd.DataFrame(partida["equipos"])
                        st.dataframe(df_eq[["codigo", "nombre"]], use_container_width=True, hide_index=True)
                    
                    # Botones de acción
                    col_btn1, col_btn2 = st.columns(2)
                    
                    if col_btn1.button("✏️ Editar", key=f"edit_{partida['id']}", use_container_width=True):
                        st.session_state.seccion_en_edicion = partida
                        st.rerun()
                    
                    if col_btn2.button("🗑️ Eliminar", key=f"del_{partida['id']}", use_container_width=True):
                        db.collection("obras").document(obra_id_sel).collection("partidas").document(partida["id"]).delete()
                        recalcular_stock_sin_asignar(obra_id_sel)
                        st.success("Sección eliminada")
                        st.rerun()