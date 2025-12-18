import streamlit as st
from sqlalchemy.orm import Session
from database.models import Week, MenuItem, Order
from services.admin_service import get_now_utc3
import time

# --- GESTIÓN DE BASE DE DATOS (Sin cambios) ---

def get_full_week_menu(db: Session, week_id: int):
    """Descarga todo el menú de la semana y lo estructura por día."""
    items = db.query(MenuItem).filter(MenuItem.week_id == week_id).all()
    menu_structure = {day: {'principal': [], 'side': [], 'salad': []} 
                      for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']}
    
    for item in items:
        if item.day in menu_structure and item.type in menu_structure[item.day]:
            menu_structure[item.day][item.type].append(item)
    return menu_structure

def save_weekly_order_to_db(db: Session, user_id: int, week_id: int, collected_data: dict):
    """Recibe la data de TODOS los días y hace un solo guardado/update."""
    try:
        existing_order = db.query(Order).filter(
            Order.user_id == user_id, 
            Order.week_id == week_id
        ).first()

        if existing_order:
            existing_order.details = collected_data
            existing_order.status = "actualizado"
            msg = "✅ Pedido semanal actualizado correctamente."
        else:
            new_order = Order(
                user_id=user_id,
                week_id=week_id,
                status="confirmado",
                details=collected_data
            )
            db.add(new_order)
            msg = "🚀 Pedido semanal creado exitosamente."
        
        db.commit()
        return True, msg
    except Exception as e:
        db.rollback()
        return False, f"Error al guardar: {e}"

# --- INTERFAZ DE USUARIO (Refactorizada) ---

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

        # 2. INICIALIZAR ESTADO (Solo una vez al cargar la página)
        days_keys = ["monday", "tuesday", "wednesday", "thursday", "friday"]
        days_labels = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
        
        if "week_data_loaded" not in st.session_state or st.session_state.get("current_week_id") != current_week.id:
            # Buscar si ya hay pedido guardado en DB
            existing_order = db.query(Order).filter(
                Order.user_id == user_id, 
                Order.week_id == current_week.id
            ).first()
            
            saved_details = existing_order.details if existing_order else {}
            
            # Cargar en session_state
            for d in days_keys:
                st.session_state[f"main_{d}"] = saved_details.get(f"{d}_principal", None)
                st.session_state[f"side_{d}"] = saved_details.get(f"{d}_side", None)
                st.session_state[f"salad_{d}"] = saved_details.get(f"{d}_salad", None)
                st.session_state[f"note_{d}"] = saved_details.get(f"{d}_note", "")
            
            st.session_state.week_data_loaded = True
            st.session_state.current_week_id = current_week.id

        # 3. HEADER
        st.title(f"🍽️ Menú: {current_week.title}")
        st.caption("Selecciona una pestaña por día y elige tu comida.")
        
        # 4. NAVEGACIÓN POR PESTAÑAS (SOLUCIÓN RESPONSIVE)
        # Esto reemplaza al st.columns(5) y al carrusel.
        # st.tabs se ve horizontal en PC y scrolleable horizontal en Móvil.
        tabs = st.tabs(days_labels)
        
        # Obtenemos el menú completo una sola vez
        full_menu = get_full_week_menu(db, current_week.id)

        # Iteramos sobre las pestañas y los días simultáneamente
        for i, tab in enumerate(tabs):
            current_day_code = days_keys[i]
            current_day_name = days_labels[i]
            
            with tab:
                st.subheader(f"📅 {current_day_name}")
                
                day_items = full_menu.get(current_day_code)
                
                # --- LOGICA DEL FORMULARIO POR DÍA ---
                if current_day_code in closed_days:
                    st.error(f"⛔ {current_day_name}: FERIADO / SIN SERVICIO")
                    st.session_state[f"main_{current_day_code}"] = None
                
                elif not day_items or not day_items['principal']:
                    st.warning("⚠️ El menú de este día aún no ha sido cargado.")
                
                else:
                    # --- PLATO PRINCIPAL ---
                    mains = day_items['principal']
                    main_options = {f"Opción {m.option_number}: {m.description}": m.id for m in mains}
                    main_options["❌ No pedido"] = None 

                    current_val_main = st.session_state.get(f"main_{current_day_code}")
                    
                    # Calcular índice
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
                    
                    # Guardar en memoria
                    st.session_state[f"main_{current_day_code}"] = main_options[selected_label]

                    # --- EXTRAS (Solo si hay plato seleccionado) ---
                    if st.session_state[f"main_{current_day_code}"] is not None:
                        st.divider()
                        col_s1, col_s2 = st.columns(2)
                        
                        # GUARNICIÓN
                        with col_s1:
                            sides = day_items['side']
                            side_opts = {s.description: s.id for s in sides}
                            side_opts["Ninguno"] = None
                            
                            curr_side = st.session_state.get(f"side_{current_day_code}")
                            idx_side = list(side_opts.values()).index(curr_side) if curr_side in side_opts.values() else len(side_opts)-1
                            
                            sel_side_lbl = st.selectbox(
                                "Guarnición", 
                                list(side_opts.keys()), 
                                index=idx_side,
                                key=f"widget_side_{current_day_code}"
                            )
                            st.session_state[f"side_{current_day_code}"] = side_opts[sel_side_lbl]

                        # ENSALADA
                        with col_s2:
                            salads = day_items['salad']
                            salad_opts = {s.description: s.id for s in salads}
                            salad_opts["Ninguna"] = None
                            
                            curr_salad = st.session_state.get(f"salad_{current_day_code}")
                            idx_salad = list(salad_opts.values()).index(curr_salad) if curr_salad in salad_opts.values() else len(salad_opts)-1
                            
                            sel_salad_lbl = st.selectbox(
                                "Ensalada", 
                                list(salad_opts.keys()), 
                                index=idx_salad,
                                key=f"widget_salad_{current_day_code}"
                            )
                            st.session_state[f"salad_{current_day_code}"] = salad_opts[sel_salad_lbl]
                        
                        # NOTA
                        st.markdown("###")
                        note_val = st.text_area(
                            "Nota especial:", 
                            value=st.session_state.get(f"note_{current_day_code}", ""),
                            key=f"widget_note_{current_day_code}",
                            height=70,
                            placeholder="Ej: Sin sal, salsa aparte..."
                        )
                        st.session_state[f"note_{current_day_code}"] = note_val
                    
                    else:
                        # Limpiar extras si elige 'No pedido'
                        st.session_state[f"side_{current_day_code}"] = None
                        st.session_state[f"salad_{current_day_code}"] = None


        # 5. BOTÓN DE ENVÍO FINAL (GLOBAL, Fuera de los tabs)
        st.markdown("---")
        submit_col1, submit_col2, submit_col3 = st.columns([1, 3, 1])
        with submit_col2:
            btn_submit = st.button(
                "💾 CONFIRMAR Y ENVIAR PEDIDO SEMANAL", 
                type="primary", 
                use_container_width=True
            )

        if btn_submit:
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
                    time.sleep(2)
                    st.rerun()
                else:
                    st.error(msg)

    except Exception as e:
        st.error(f"Ocurrió un error inesperado: {e}")
    finally:
        db.close()
