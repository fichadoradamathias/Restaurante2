import streamlit as st
from sqlalchemy.orm import Session
from database.models import Week, MenuItem, Order
from services.admin_service import get_now_utc3
import time

# --- FUNCIONES AUXILIARES ---

def get_full_week_menu(db: Session, week_id: int):
    """Descarga todo el menú de la semana y lo estructura por día."""
    items = db.query(MenuItem).filter(MenuItem.week_id == week_id).all()
    menu_structure = {day: {'principal': [], 'side': [], 'salad': []} 
                      for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']}
    
    for item in items:
        if item.day in menu_structure and item.type in menu_structure[item.day]:
            menu_structure[item.day][item.type].append(item)
    return menu_structure

def get_item_name_by_id(menu_structure, day_code, item_type, item_id):
    """Busca el nombre del plato en la estructura del menú usando su ID."""
    if not item_id: return None
    items = menu_structure.get(day_code, {}).get(item_type, [])
    for item in items:
        if item.id == item_id:
            return item.description
    return "Plato no encontrado"

def save_weekly_order_to_db(db: Session, user_id: int, week_id: int, collected_data: dict):
    try:
        existing_order = db.query(Order).filter(
            Order.user_id == user_id, 
            Order.week_id == week_id
        ).first()

        if existing_order:
            existing_order.details = collected_data
            existing_order.status = "actualizado"
            msg = "✅ Pedido actualizado correctamente."
        else:
            new_order = Order(
                user_id=user_id,
                week_id=week_id,
                status="confirmado",
                details=collected_data
            )
            db.add(new_order)
            msg = "🚀 Pedido creado exitosamente."
        
        db.commit()
        return True, msg
    except Exception as e:
        db.rollback()
        return False, f"Error al guardar: {e}"

# --- INTERFAZ DE USUARIO ---

def user_dashboard(db_session_maker):
    if 'user_id' not in st.session_state:
        st.error("Por favor inicia sesión.")
        return

    user_id = st.session_state.user_id
    db: Session = db_session_maker()

    try:
        # 1. VALIDAR SEMANA ACTIVA
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
        days_keys = ["monday", "tuesday", "wednesday", "thursday", "friday"]
        days_labels = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]

        # 2. CARGAR DATOS Y ESTADO DEL PEDIDO
        # Verificar si ya existe un pedido en DB
        existing_order = db.query(Order).filter(
            Order.user_id == user_id, 
            Order.week_id == current_week.id
        ).first()

        # Variable de estado para saber si estamos editando
        if "is_editing_order" not in st.session_state:
            st.session_state.is_editing_order = False

        # Si NO hay pedido, forzamos modo edición
        if not existing_order:
            st.session_state.is_editing_order = True

        # Cargar datos en memoria (Solo si no están cargados o cambió la semana)
        if "week_data_loaded" not in st.session_state or st.session_state.get("current_week_id") != current_week.id:
            saved_details = existing_order.details if existing_order else {}
            for d in days_keys:
                st.session_state[f"main_{d}"] = saved_details.get(f"{d}_principal", None)
                st.session_state[f"side_{d}"] = saved_details.get(f"{d}_side", None)
                st.session_state[f"salad_{d}"] = saved_details.get(f"{d}_salad", None)
                st.session_state[f"note_{d}"] = saved_details.get(f"{d}_note", "")
            
            st.session_state.week_data_loaded = True
            st.session_state.current_week_id = current_week.id

        # 3. HEADER
        st.title(f"🍽️ Menú: {current_week.title}")
        full_menu = get_full_week_menu(db, current_week.id)

        # ---------------------------------------------------------
        # VISTA 1: RESUMEN DE PEDIDO (Solo lectura)
        # ---------------------------------------------------------
        if existing_order and not st.session_state.is_editing_order:
            st.success("✅ Ya has enviado tu pedido para esta semana.")
            
            st.markdown("### 📋 Tu Selección Confirmada:")
            
            details = existing_order.details
            hay_pedidos = False

            # Contenedor con borde para que parezca un ticket
            with st.container(border=True):
                for i, d_key in enumerate(days_keys):
                    main_id = details.get(f"{d_key}_principal")
                    
                    # Solo mostrar días donde SE PIDIÓ comida (ID no es None)
                    if main_id:
                        hay_pedidos = True
                        day_name = days_labels[i]
                        
                        # Traducir IDs a Nombres
                        main_name = get_item_name_by_id(full_menu, d_key, 'principal', main_id)
                        side_name = get_item_name_by_id(full_menu, d_key, 'side', details.get(f"{d_key}_side"))
                        salad_name = get_item_name_by_id(full_menu, d_key, 'salad', details.get(f"{d_key}_salad"))
                        note = details.get(f"{d_key}_note", "")

                        st.markdown(f"**📅 {day_name}**")
                        st.markdown(f"- 🥘 **Plato:** {main_name}")
                        if side_name: st.markdown(f"- 🍟 **Guarnición:** {side_name}")
                        if salad_name: st.markdown(f"- 🥗 **Ensalada:** {salad_name}")
                        if note: st.caption(f"📝 Nota: {note}")
                        st.divider()
            
            if not hay_pedidos:
                st.warning("Tu pedido consta de 'No Pedido' para todos los días.")

            st.markdown("---")
            col_change, col_dummy = st.columns([1, 2])
            with col_change:
                # Botón para activar el modo edición
                if st.button("✏️ CAMBIAR / ACTUALIZAR PEDIDO", use_container_width=True):
                    st.session_state.is_editing_order = True
                    st.rerun()

        # ---------------------------------------------------------
        # VISTA 2: FORMULARIO DE EDICIÓN (Pestañas)
        # ---------------------------------------------------------
        else:
            if existing_order:
                st.info("✏️ Estás editando tu pedido actual. No olvides guardar los cambios al final.")
            else:
                st.caption("Selecciona una pestaña por día y elige tu comida.")

            # --- NAVEGACIÓN POR PESTAÑAS ---
            tabs = st.tabs(days_labels)
            
            for i, tab in enumerate(tabs):
                current_day_code = days_keys[i]
                current_day_name = days_labels[i]
                
                with tab:
                    st.subheader(f"📅 {current_day_name}")
                    day_items = full_menu.get(current_day_code)
                    
                    if current_day_code in closed_days:
                        st.error(f"⛔ {current_day_name}: FERIADO / SIN SERVICIO")
                        st.session_state[f"main_{current_day_code}"] = None
                    
                    elif not day_items or not day_items['principal']:
                        st.warning("⚠️ El menú de este día aún no ha sido cargado.")
                    
                    else:
                        # PLATO PRINCIPAL
                        mains = day_items['principal']
                        main_options = {f"Opción {m.option_number}: {m.description}": m.id for m in mains}
                        main_options["❌ No pedido"] = None 

                        current_val_main = st.session_state.get(f"main_{current_day_code}")
                        
                        try:
                            if current_val_main in main_options.values():
                                idx_main = list(main_options.values()).index(current_val_main)
                            else:
                                idx_main = len(main_options) - 1
                        except:
                            idx_main = len(main_options) - 1

                        selected_label = st.radio(
                            f"Plato Principal - {current_day_name}:",
                            options=list(main_options.keys()),
                            index=idx_main,
                            key=f"widget_main_{current_day_code}" 
                        )
                        st.session_state[f"main_{current_day_code}"] = main_options[selected_label]

                        # EXTRAS
                        if st.session_state[f"main_{current_day_code}"] is not None:
                            st.divider()
                            col_s1, col_s2 = st.columns(2)
                            
                            # Guarnición
                            with col_s1:
                                sides = day_items['side']
                                side_opts = {s.description: s.id for s in sides}
                                side_opts["Ninguno"] = None
                                curr_side = st.session_state.get(f"side_{current_day_code}")
                                idx_side = list(side_opts.values()).index(curr_side) if curr_side in side_opts.values() else len(side_opts)-1
                                sel_side_lbl = st.selectbox("Guarnición", list(side_opts.keys()), index=idx_side, key=f"widget_side_{current_day_code}")
                                st.session_state[f"side_{current_day_code}"] = side_opts[sel_side_lbl]

                            # Ensalada
                            with col_s2:
                                salads = day_items['salad']
                                salad_opts = {s.description: s.id for s in salads}
                                salad_opts["Ninguna"] = None
                                curr_salad = st.session_state.get(f"salad_{current_day_code}")
                                idx_salad = list(salad_opts.values()).index(curr_salad) if curr_salad in salad_opts.values() else len(salad_opts)-1
                                sel_salad_lbl = st.selectbox("Ensalada", list(salad_opts.keys()), index=idx_salad, key=f"widget_salad_{current_day_code}")
                                st.session_state[f"salad_{current_day_code}"] = salad_opts[sel_salad_lbl]
                            
                            st.markdown("###")
                            note_val = st.text_area("Nota especial:", value=st.session_state.get(f"note_{current_day_code}", ""), key=f"widget_note_{current_day_code}", height=70)
                            st.session_state[f"note_{current_day_code}"] = note_val
                        else:
                            # Limpiar extras
                            st.session_state[f"side_{current_day_code}"] = None
                            st.session_state[f"salad_{current_day_code}"] = None

            # --- BOTONES DE ACCIÓN (Enviar o Cancelar) ---
            st.markdown("---")
            
            # Si estamos editando un pedido existente, damos opción de CANCELAR los cambios
            if existing_order:
                col_cancel, col_save = st.columns([1, 2])
                with col_cancel:
                    if st.button("❌ Cancelar Cambios", use_container_width=True):
                        st.session_state.is_editing_order = False
                        st.rerun()
            else:
                col_save = st.container()

            with col_save:
                btn_text = "💾 ACTUALIZAR PEDIDO" if existing_order else "🚀 ENVIAR PEDIDO SEMANAL"
                if st.button(btn_text, type="primary", use_container_width=True):
                    final_data_payload = {}
                    count_meals = 0
                    
                    for d in days_keys:
                        m_id = st.session_state.get(f"main_{d}")
                        final_data_payload[f"{d}_principal"] = m_id
                        if m_id is not None:
                            final_data_payload[f"{d}_side"] = st.session_state.get(f"side_{d}")
                            final_data_payload[f"{d}_salad"] = st.session_state.get(f"salad_{d}")
                            final_data_payload[f"{d}_note"] = st.session_state.get(f"note_{d}", "")
                            count_meals += 1
                        else:
                            final_data_payload[f"{d}_side"] = None
                            final_data_payload[f"{d}_salad"] = None
                            final_data_payload[f"{d}_note"] = ""
                    
                    if count_meals == 0:
                        st.warning("⚠️ No has seleccionado ningún plato para ningún día.")
                    else:
                        success, msg = save_weekly_order_to_db(db, user_id, current_week.id, final_data_payload)
                        if success:
                            st.balloons()
                            st.success(msg)
                            st.session_state.is_editing_order = False # Salir del modo edición
                            time.sleep(1.5)
                            st.rerun()
                        else:
                            st.error(msg)

    except Exception as e:
        st.error(f"Ocurrió un error inesperado: {e}")
    finally:
        db.close()
