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

# ================= FUNCIONES =================
def obtener_obras():
    return {d.id: d.to_dict().get("nombre", d.id) for d in db.collection("obras").stream()}

def obtener_trabajadores_obra(obra_id):
    docs = db.collection("obras").document(obra_id).collection("trabajadores").stream()
    return [{"id": d.id, **d.to_dict()} for d in docs]

def obtener_materiales_obra(obra_id):
    docs = db.collection("obras").document(obra_id).collection("materiales").stream()
    return [{"id": d.id, **d.to_dict()} for d in docs]

def obtener_partidas_obra(obra_id):
    docs = db.collection("obras").document(obra_id).collection("partidas").order_by("codigo").stream()
    return [{"id": d.id, **d.to_dict()} for d in docs]

def calcular_subtotal_partida(partida_data):
    """Calcula el subtotal de una partida sumando mano de obra, materiales y equipos"""
    total = 0.0
    
    # Mano de obra
    for mo in partida_data.get("mano_obra", []):
        total += float(mo.get("subtotal", 0))
    
    # Materiales
    for mat in partida_data.get("materiales", []):
        total += float(mat.get("subtotal", 0))
    
    # Equipos
    for eq in partida_data.get("equipos", []):
        total += float(eq.get("subtotal", 0))
    
    return round(total, 2)

# ================= UI =================
st.title("📋 Gestión de Partidas de Obra")

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
    st.info("💡 Por favor, selecciona una obra para gestionar sus partidas.")
    st.stop()

nombre_obra = OBRAS.get(obra_id_sel, "Desconocida")
st.sidebar.success(f"📍 Obra actual: **{nombre_obra}**")

# ================= PESTAÑAS PRINCIPALES =================
tab1, tab2 = st.tabs(["➕ Crear/Editar Partida", "📋 Ver Partidas"])

# ================= TAB 1: CREAR/EDITAR PARTIDA =================
with tab1:
    st.subheader("➕ Crear Nueva Partida")
    
    # Inicializar estados
    if "partida_editando" not in st.session_state:
        st.session_state.partida_editando = None
    
    # Datos básicos
    with st.form("form_datos_partida", clear_on_submit=False):
        st.markdown("#### 📝 Información General")
        
        col1, col2 = st.columns(2)
        codigo = col1.text_input("Código de Partida", placeholder="05,05,01")
        descripcion = col2.text_input("Descripción", placeholder="CONCRETO PREMEZCLADO...")
        
        col3, col4 = st.columns(2)
        unidad = col3.selectbox("Unidad de Medida", ["M3", "M2", "ML", "KG", "UND", "GLB"])
        rendimiento = col4.number_input("Rendimiento", min_value=0.0, step=1.0, help="Ej: 250.000 M3/DIA")
        
        submit_datos = st.form_submit_button("💾 Guardar Datos Básicos y Continuar")
        
        if submit_datos:
            if not codigo or not descripcion:
                st.error("Por favor completa el código y la descripción.")
            else:
                st.session_state.partida_editando = {
                    "codigo": codigo,
                    "descripcion": descripcion,
                    "unidad": unidad,
                    "rendimiento": rendimiento,
                    "mano_obra": [],
                    "materiales": [],
                    "equipos": []
                }
                st.success("✅ Datos básicos guardados. Ahora agrega recursos.")
                st.rerun()
    
    # Si ya se guardaron los datos básicos, mostrar formularios de recursos
    if st.session_state.partida_editando:
        st.divider()
        partida = st.session_state.partida_editando
        
        st.info(f"📌 Partida: **{partida['codigo']}** - {partida['descripcion']}")
        
        # ================= SECCIÓN: MANO DE OBRA =================
        st.markdown("### 👷 Mano de Obra")
        
        trabajadores_disponibles = obtener_trabajadores_obra(obra_id_sel)
        
        if trabajadores_disponibles:
            with st.form("form_agregar_mano_obra", clear_on_submit=True):
                trab_sel = st.selectbox(
                    "Seleccionar Trabajador",
                    options=trabajadores_disponibles,
                    format_func=lambda x: f"{x['nombre']} - {x['rol']}"
                )
                
                col_mo1, col_mo2, col_mo3 = st.columns(3)
                cuadrilla = col_mo1.number_input("Cuadrilla", min_value=0.0, step=0.1, value=1.0)
                cantidad = col_mo2.number_input("Cantidad (HH)", min_value=0.0, step=0.001, value=0.032)
                precio_unitario = col_mo3.number_input("Precio (S/)", min_value=0.0, step=0.01, value=float(trab_sel.get("presupuesto", 25.0)))
                
                subtotal_mo = cuadrilla * cantidad * precio_unitario
                st.caption(f"💵 Subtotal: S/ {subtotal_mo:,.2f}")
                
                if st.form_submit_button("➕ Agregar Mano de Obra"):
                    partida["mano_obra"].append({
                        "trabajador_id": trab_sel["id"],
                        "nombre": trab_sel["nombre"],
                        "rol": trab_sel["rol"],
                        "unidad": "HH",
                        "cuadrilla": cuadrilla,
                        "cantidad": cantidad,
                        "precio": precio_unitario,
                        "parcial": cuadrilla * cantidad,
                        "subtotal": subtotal_mo
                    })
                    st.success(f"✅ {trab_sel['nombre']} agregado")
                    st.rerun()
        else:
            st.warning("No hay trabajadores registrados en esta obra. Ve a la sección de Trabajadores.")
        
        # Mostrar mano de obra agregada
        if partida["mano_obra"]:
            st.markdown("**Mano de Obra Agregada:**")
            df_mo = pd.DataFrame(partida["mano_obra"])
            st.dataframe(df_mo[["nombre", "rol", "cuadrilla", "cantidad", "precio", "subtotal"]], use_container_width=True)
            total_mo = sum(m["subtotal"] for m in partida["mano_obra"])
            st.success(f"**Total Mano de Obra:** S/ {total_mo:,.2f}")
        
        st.divider()
        
        # ================= SECCIÓN: MATERIALES =================
        st.markdown("### 🧱 Materiales")
        
        materiales_disponibles = obtener_materiales_obra(obra_id_sel)
        
        if materiales_disponibles:
            with st.form("form_agregar_material", clear_on_submit=True):
                mat_sel = st.selectbox(
                    "Seleccionar Material",
                    options=materiales_disponibles,
                    format_func=lambda x: f"{x['nombre']} ({x['unidad']})"
                )
                
                col_mat1, col_mat2 = st.columns(2)
                cantidad_mat = col_mat1.number_input("Cantidad", min_value=0.0, step=0.01, value=0.022)
                precio_mat = col_mat2.number_input("Precio Unitario (S/)", min_value=0.0, step=0.01, value=float(mat_sel.get("precio_unitario", 3.80)))
                
                subtotal_mat = cantidad_mat * precio_mat
                st.caption(f"💵 Subtotal: S/ {subtotal_mat:,.2f}")
                
                if st.form_submit_button("➕ Agregar Material"):
                    partida["materiales"].append({
                        "material_id": mat_sel["id"],
                        "nombre": mat_sel["nombre"],
                        "unidad": mat_sel["unidad"],
                        "cantidad": cantidad_mat,
                        "precio": precio_mat,
                        "subtotal": subtotal_mat
                    })
                    st.success(f"✅ {mat_sel['nombre']} agregado")
                    st.rerun()
        else:
            st.warning("No hay materiales registrados en esta obra. Ve a la sección de Materiales.")
        
        # Mostrar materiales agregados
        if partida["materiales"]:
            st.markdown("**Materiales Agregados:**")
            df_mat = pd.DataFrame(partida["materiales"])
            st.dataframe(df_mat[["nombre", "unidad", "cantidad", "precio", "subtotal"]], use_container_width=True)
            total_mat = sum(m["subtotal"] for m in partida["materiales"])
            st.success(f"**Total Materiales:** S/ {total_mat:,.2f}")
        
        st.divider()
        
        # ================= SECCIÓN: EQUIPOS =================
        st.markdown("### 🔧 Equipos")
        
        with st.form("form_agregar_equipo", clear_on_submit=True):
            col_eq1, col_eq2 = st.columns(2)
            nombre_eq = col_eq1.text_input("Nombre del Equipo", placeholder="HERRAMIENTAS MANUALES")
            unidad_eq = col_eq2.selectbox("Unidad", ["%MO", "HM", "M3", "UND"])
            
            col_eq3, col_eq4, col_eq5 = st.columns(3)
            cuadrilla_eq = col_eq3.number_input("Cuadrilla", min_value=0.0, step=0.1, value=1.0, key="cuad_eq")
            cantidad_eq = col_eq4.number_input("Cantidad", min_value=0.0, step=0.001, value=5.0, key="cant_eq")
            precio_eq = col_eq5.number_input("Precio (S/)", min_value=0.0, step=0.01, value=1.47, key="precio_eq")
            
            subtotal_eq = cuadrilla_eq * cantidad_eq * precio_eq
            st.caption(f"💵 Subtotal: S/ {subtotal_eq:,.2f}")
            
            if st.form_submit_button("➕ Agregar Equipo"):
                if nombre_eq:
                    partida["equipos"].append({
                        "nombre": nombre_eq,
                        "unidad": unidad_eq,
                        "cuadrilla": cuadrilla_eq,
                        "cantidad": cantidad_eq,
                        "precio": precio_eq,
                        "parcial": cuadrilla_eq * cantidad_eq,
                        "subtotal": subtotal_eq
                    })
                    st.success(f"✅ {nombre_eq} agregado")
                    st.rerun()
        
        # Mostrar equipos agregados
        if partida["equipos"]:
            st.markdown("**Equipos Agregados:**")
            df_eq = pd.DataFrame(partida["equipos"])
            st.dataframe(df_eq[["nombre", "unidad", "cuadrilla", "cantidad", "precio", "subtotal"]], use_container_width=True)
            total_eq = sum(e["subtotal"] for e in partida["equipos"])
            st.success(f"**Total Equipos:** S/ {total_eq:,.2f}")
        
        st.divider()
        
        # ================= GUARDAR PARTIDA COMPLETA =================
        total_partida = sum(m["subtotal"] for m in partida["mano_obra"]) + \
                       sum(m["subtotal"] for m in partida["materiales"]) + \
                       sum(e["subtotal"] for e in partida["equipos"])
        
        st.markdown(f"### 💰 **TOTAL PARTIDA: S/ {total_partida:,.2f}**")
        
        col_final1, col_final2 = st.columns(2)
        
        if col_final1.button("💾 GUARDAR PARTIDA COMPLETA", type="primary", use_container_width=True):
            if not partida["mano_obra"] and not partida["materiales"] and not partida["equipos"]:
                st.error("Debes agregar al menos un recurso (mano de obra, material o equipo)")
            else:
                partida["total"] = total_partida
                partida["fecha_creacion"] = datetime.now(local_tz)
                
                db.collection("obras").document(obra_id_sel).collection("partidas").add(partida)
                
                st.session_state.partida_editando = None
                st.success("✅ Partida guardada exitosamente")
                st.rerun()
        
        if col_final2.button("❌ Cancelar y Limpiar", use_container_width=True):
            st.session_state.partida_editando = None
            st.rerun()

# ================= TAB 2: VER PARTIDAS =================
with tab2:
    st.subheader("📋 Partidas de la Obra")
    
    partidas = obtener_partidas_obra(obra_id_sel)
    
    if not partidas:
        st.info("No hay partidas registradas. Crea una en la pestaña anterior.")
    else:
        # Resumen general
        total_general = sum(p.get("total", 0) for p in partidas)
        st.metric("💰 Presupuesto Total de Partidas", f"S/ {total_general:,.2f}")
        
        st.divider()
        
        # Mostrar cada partida
        for partida in partidas:
            with st.expander(f"**{partida.get('codigo')}** - {partida.get('descripcion')} | S/ {partida.get('total', 0):,.2f}", expanded=False):
                
                col_info1, col_info2, col_info3 = st.columns(3)
                col_info1.write(f"**Unidad:** {partida.get('unidad')}")
                col_info2.write(f"**Rendimiento:** {partida.get('rendimiento')}")
                col_info3.write(f"**Total:** S/ {partida.get('total', 0):,.2f}")
                
                # Mano de Obra
                if partida.get("mano_obra"):
                    st.markdown("**👷 Mano de Obra:**")
                    df_mo = pd.DataFrame(partida["mano_obra"])
                    st.dataframe(df_mo, use_container_width=True, hide_index=True)
                
                # Materiales
                if partida.get("materiales"):
                    st.markdown("**🧱 Materiales:**")
                    df_mat = pd.DataFrame(partida["materiales"])
                    st.dataframe(df_mat, use_container_width=True, hide_index=True)
                
                # Equipos
                if partida.get("equipos"):
                    st.markdown("**🔧 Equipos:**")
                    df_eq = pd.DataFrame(partida["equipos"])
                    st.dataframe(df_eq, use_container_width=True, hide_index=True)
                
                # Botón eliminar
                if st.button(f"🗑️ Eliminar Partida", key=f"del_{partida['id']}"):
                    db.collection("obras").document(obra_id_sel).collection("partidas").document(partida["id"]).delete()
                    st.success("Partida eliminada")
                    st.rerun()
        
        # Exportar a Excel
        st.divider()
        if st.button("📥 Exportar Partidas a Excel"):
            # Aquí puedes agregar lógica de exportación
            st.info("Funcionalidad de exportación en desarrollo")
