import streamlit as st
from sqlalchemy.orm import Session
from database.models import Week, MenuItem, Order
from datetime import datetime
from services.admin_service import get_now_utc3

# --- FUNCIONES DE BASE DE DATOS ---

def get_menu_items_structure(db: Session, week_id: int):
    """
    Obtiene TODO el menú de la semana y lo organiza en un diccionario fácil de consultar.
    Retorna: { 'monday': {'principal': [obj...], 'side': [...], 'salad': [...]}, 'tuesday': ... }
    """
    items = db.query(MenuItem).filter(MenuItem.week_id == week_id).all()
    
    # Estructura base
    structure = {day: {'principal': [], 'side': [], 'salad': []} for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']}
    
    for item in items:
        if item.day in structure and item.type in structure[item.day]:
            structure[item.day][item.type].append(item)
            
    return structure

def save_weekly_order(db: Session, user_id: int, week_id: int, full_details: dict):
    """
    Guarda o actualiza el pedido COMPLETO de la semana.
    """
    try:
        existing_order = db.query(Order).filter(
            Order.user_id == user_id, 
            Order.week_id == week_id
        ).first()

        if existing_order:
            existing_order.details = full_details
            existing_order.status = "actualizado"
            msg = "✅ ¡Pedido semanal actualizado correctamente!"
        else:
            new_order = Order(
                user_id=user_id,
                week_id=week_id,
                status="confirmado",
                details=full_details
            )
            db.add(new_order)
            msg = "🚀 ¡Pedido semanal enviado exitosamente!"
        
        db.commit()
        return True, msg
    except Exception as e:
        db.rollback()
        return False, f"Error al guardar: {e}"

# --- VISTA PRINCIPAL ---

def user_dashboard(db_session_maker):
    if 'user_id' not in st.session_state:
        st.error("Por favor inicia sesión.")
        return

    user_id = st.session_state.user_id
    db: Session = db_session_maker()

    try:
        # 1. OBTENER SEMANA ACTIVA
        now_utc3 = get_now_utc3()
        current_week = db.query(Week).filter(
            Week.is_open == True, 
            Week.end_date > now_utc3
        ).order_by(Week.start_date.desc()).first()

        if not current_week:
            st.info("🚫 No hay semanas habilitadas para pedidos.")
            db.close()
            return

        closed_days = current_week.closed_days if current_week.closed_days else []

        # 2. HEADER
        st.title(f"🍽️ Menú: {current_week.title}")
        time_left = current_week.end_date - now_utc3
        if time_left.days == 0 and time_left.seconds < 7200:
            st.error(f"🔥 CIERRE INMINENTE: {time_left.seconds // 3600}h {(time_left.seconds % 3600) // 60}m")
        else:
            st.caption(f"⏳ Cierre en: {time_left.days} días")
        st.divider()

        # 3. CARGAR DATOS PREVIOS E INICIALIZAR ESTADO
        # Esto es crucial: Cargamos la DB en el session_state UNA sola vez para que el usuario pueda editar
        if "data_initialized" not in st.session_state:
            existing_order = db.query(Order).filter(
                Order.user_id == user_id, 
                Order.week_id == current_week.id
            ).first()
            
            saved_details = existing_order.details if existing_order else {}
            
            days = ["monday", "tuesday", "wednesday", "thursday", "friday"]
            for d in days:
                # Inicializamos las keys en session_state con lo que haya en la DB o None
                st.session_state[f"sel_main_{d}"] = saved_details.get(f"{d}_principal")
                st.session_state[f"sel_side_{d}"] = saved_details.get(f"{d}_side")
                st.session_state[f"sel_salad_{d}"] = saved_details.get(f"{d}_salad")
                st.session_state[f"sel_note_{d}"] = saved_details.get(f"{d}_note", "")
            
            st.session_state.data_initialized = True

        # 4. NAVEGACIÓN ENTRE DÍAS
        days_map = [
            ("monday", "Lunes"), ("tuesday", "Martes"), ("wednesday", "Miércoles"),
            ("thursday", "Jueves"), ("friday", "Viernes")
        ]
        
        if 'day_nav_index' not in st.session_state: st.session_state.day_nav_index = 0
        # Validar límites
        if st.session_state.day_nav_index >= len(days_map): st.session_state.day_nav_index = 0
        if st.session_state.day_nav_index < 0: st.session_state.day_nav_index = 0

        curr_code, curr_name = days_map[st.session_state.day_nav_index]

        c1, c2, c3 = st.columns([1, 4, 1])
        with c1:
            if st.button("⬅ Ant", use_container_width=True):
                st.session_state.day_nav_index -= 1
                st.rerun()
        with c2:
            st.markdown(f"<h3 style='text-align: center; color:#FF4B4B; margin:0;'>{curr_name}</h3>", unsafe_allow_html=True)
        with c3:
            if st.button("Sig ➡", use_container_width=True):
                st.session_state.day_nav_index += 1
                st.rerun()

        st.markdown("###")

        # 5. RENDERIZADO DEL DÍA ACTUAL
        # Obtenemos todo el menú de una vez para no hacer queries constantes
        full_menu = get_menu_items_structure(db, current_week.id)
        day_menu = full_menu.get(curr_code)

        # Contenedor visual del día
        with st.container(border=True):
            if curr_code in closed_days:
                st.warning(f"⛔ {curr_name}: FERIADO / SIN SERVICIO")
                # Limpiamos selección interna por si acaso
                st.session_state[f"sel_main_{curr_code}"] = None
            
            elif not day_menu['principal']:
                st.info("⚠️ Menú no cargado para este día.")
            
            else:
                # --- PLATO PRINCIPAL ---
                mains = day_menu['principal']
                # Creamos mapa {Descripción: ID}
                main_map = {f"Opción {m.option_number}: {m.description}": m.id for m in mains}
                main_map["❌ No pedido"] = None # Opción nula
                
                # Recuperar valor actual del estado
                current_val = st.session_state.get(f"sel_main_{curr_code}")
                
                # Calcular índice
                idx = len(main_map) - 1 # Por defecto: No pedido
                if current_val in main_map.values():
                    idx = list(main_map.values()).index(current_val)

                # WIDGET DIRECTO (Sin Form) - Se guarda solo en session_state al cambiar
                selected_label = st.radio(
                    f"🍛 Plato Principal ({curr_name})",
                    options=list(main_map.keys()),
                    index=idx,
                    key=f"radio_main_{curr_code}" # Key única para el widget
                )
                # Actualizamos manualmente el estado que usaremos para guardar
                st.session_state[f"sel_main_{curr_code}"] = main_map[selected_label]

                st.markdown("---")

                # --- EXTRAS ---
                c_side, c_salad = st.columns(2)
                
                # Guarnición
                with c_side:
                    sides = day_menu['side']
                    side_map = {s.description: s.id for s in sides}
                    side_map["Ninguno"] = None
                    
                    cur_side = st.session_state.get(f"sel_side_{curr_code}")
                    s_idx = list(side_map.values()).index(cur_side) if cur_side in side_map.values() else len(side_map)-1
                    
                    sel_side_lbl = st.selectbox(f"🍟 Guarnición", list(side_map.keys()), index=s_idx, key=f"sb_side_{curr_code}")
                    st.session_state[f"sel_side_{curr_code}"] = side_map[sel_side_lbl]

                # Ensalada
                with c_salad:
                    salads = day_menu['salad']
                    salad_map = {s.description: s.id for s in salads}
                    salad_map["Ninguna"] = None
                    
                    cur_salad = st.session_state.get(f"sel_salad_{curr_code}")
                    sl_idx = list(salad_map.values()).index(cur_salad) if cur_salad in salad_map.values() else len(salad_map)-1
                    
                    sel_salad_lbl = st.selectbox(f"🥗 Ensalada", list(salad_map.keys()), index=sl_idx, key=f"sb_salad_{curr_code}")
                    st.session_state[f"sel_salad_{curr_code}"] = salad_map[sel_salad_lbl]

                # Nota
                st.markdown("###")
                note_val = st.text_area("📝 Nota:", value=st.session_state.get(f"sel_note_{curr_code}", ""), key=f"txt_note_{curr_code}")
                st.session_state[f"sel_note_{curr_code}"] = note_val

        st.markdown("###")

        # 6. BOTÓN DE ENVÍO GLOBAL (Fuera del contenedor del día)
        st.divider()
        st.caption("Revisa tus selecciones navegando por los días. Cuando estés listo, envía todo el pedido.")
        
        # Botón grande y llamativo
        btn_col1, btn_col2 = st.columns([1, 2])
        with btn_col2:
            submitted = st.button("💾 ENVIAR PEDIDO SEMANAL COMPLETO", type="primary", use_container_width=True)

        if submitted:
            # Recopilar datos de TODOS los días desde session_state
            full_details = {}
            days_keys = ["monday", "tuesday", "wednesday", "thursday", "friday"]
            
            has_at_least_one = False
            
            for d in days_keys:
                main_id = st.session_state.get(f"sel_main_{d}")
                side_id = st.session_state.get(f"sel_side_{d}")
                salad_id = st.session_state.get(f"sel_salad_{d}")
                note = st.session_state.get(f"sel_note_{d}", "")
                
                # Construir objeto
                full_details[f"{d}_principal"] = main_id
                
                # Lógica: Si hay plato principal, guardamos extras. Si es "No pedido" (None), extras son None.
                if main_id is not None:
                    full_details[f"{d}_side"] = side_id
                    full_details[f"{d}_salad"] = salad_id
                    full_details[f"{d}_note"] = note
                    has_at_least_one = True
                else:
                    full_details[f"{d}_side"] = None
                    full_details[f"{d}_salad"] = None
                    full_details[f"{d}_note"] = ""

            if not has_at_least_one:
                st.warning("⚠️ No has seleccionado ningún plato para ningún día. Selecciona al menos uno.")
            else:
                success, msg = save_weekly_order(db, user_id, current_week.id, full_details)
                if success:
                    st.balloons()
                    st.success(msg)
                    # Forzar recarga para asegurar que se muestre el estado actualizado
                    import time
                    time.sleep(1.5)
                    st.rerun()
                else:
                    st.error(msg)
                    
        # Visualizador rápido de estado (Resumen)
        with st.expander("👀 Ver Resumen de mi Selección actual"):
            summary_cols = st.columns(5)
            d_codes = ["monday", "tuesday", "wednesday", "thursday", "friday"]
            d_shorts = ["LUN", "MAR", "MIE", "JUE", "VIE"]
            
            for i, d in enumerate(d_codes):
                is_selected = st.session_state.get(f"sel_main_{d}") is not None
                icon = "✅" if is_selected else "❌"
                summary_cols[i].markdown(f"**{d_shorts[i]}**<br>{icon}", unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Error en dashboard: {e}")
    finally:
        db.close()
