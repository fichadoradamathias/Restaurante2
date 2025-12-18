import streamlit as st
from sqlalchemy.orm import Session
from database.models import Week, MenuItem, Order
from datetime import datetime
from services.admin_service import get_now_utc3

# --- FUNCIONES AUXILIARES ---

def get_menu_items_by_day(db: Session, week_id: int, day_code: str):
    """
    Obtiene los ítems del menú filtrados por día específico.
    Retorna un diccionario: {'principal': [], 'side': [], 'salad': []}
    """
    items = db.query(MenuItem).filter(
        MenuItem.week_id == week_id,
        MenuItem.day == day_code
    ).all()
    
    categorized = {"principal": [], "side": [], "salad": []}
    for item in items:
        if item.type in categorized:
            categorized[item.type].append(item)
    return categorized

def save_single_day_order(db: Session, user_id: int, week_id: int, day_updates: dict):
    """
    Actualiza SOLO los campos del día modificado, manteniendo el resto de la semana intacta.
    """
    try:
        # 1. Buscar orden existente
        existing_order = db.query(Order).filter(
            Order.user_id == user_id, 
            Order.week_id == week_id
        ).first()

        if existing_order:
            # Si existe, tomamos los detalles actuales y los actualizamos
            current_details = dict(existing_order.details) if existing_order.details else {}
            current_details.update(day_updates) # Mezclamos lo nuevo con lo viejo
            
            existing_order.details = current_details
            existing_order.status = "actualizado" # O el estado que prefieras
            msg = "✅ Menú del día actualizado correctamente."
        else:
            # Si es nuevo, creamos la orden
            new_order = Order(
                user_id=user_id,
                week_id=week_id,
                status="confirmado",
                details=day_updates
            )
            db.add(new_order)
            msg = "✅ Primer pedido de la semana creado."
        
        db.commit()
        return True, msg
    except Exception as e:
        db.rollback()
        return False, f"Error al guardar: {e}"

# --- VISTA PRINCIPAL ---

def user_dashboard(db_session_maker):
    # Verificación de seguridad básica
    if 'user_id' not in st.session_state:
        st.error("Por favor inicia sesión.")
        return

    user_id = st.session_state.user_id
    db: Session = db_session_maker()

    try:
        # 1. OBTENER SEMANA ACTIVA (Lógica Original)
        now_utc3 = get_now_utc3()
        current_week = db.query(Week).filter(
            Week.is_open == True, 
            Week.end_date > now_utc3
        ).order_by(Week.start_date.desc()).first()

        if not current_week:
            st.info("🚫 No hay semanas habilitadas para pedidos en este momento.")
            return

        # Recuperar lista de días cerrados
        closed_days = current_week.closed_days if current_week.closed_days else []

        # 2. HEADER Y CONTADOR (Visualmente compactado)
        st.title(f"🍽️ Menú: {current_week.title}")
        
        time_left = current_week.end_date - now_utc3
        if time_left.days == 0 and time_left.seconds < 7200: # Menos de 2 horas
            st.error(f"🔥 CIERRE INMINENTE: {time_left.seconds // 3600}h {(time_left.seconds % 3600) // 60}m")
        else:
            st.caption(f"⏳ Cierre en: {time_left.days} días, {time_left.seconds // 3600} horas")

        st.divider()

        # 3. GESTIÓN DE ESTADO (NAVEGACIÓN)
        days_map = [
            ("monday", "Lunes"), ("tuesday", "Martes"), ("wednesday", "Miércoles"),
            ("thursday", "Jueves"), ("friday", "Viernes")
        ]
        
        if 'day_nav_index' not in st.session_state:
            st.session_state.day_nav_index = 0
            
        # Asegurar límites
        if st.session_state.day_nav_index >= len(days_map): st.session_state.day_nav_index = 0
        if st.session_state.day_nav_index < 0: st.session_state.day_nav_index = 0

        current_day_code, current_day_name = days_map[st.session_state.day_nav_index]

        # 4. BARRA DE NAVEGACIÓN
        col_prev, col_title, col_next = st.columns([1, 4, 1])
        
        with col_prev:
            if st.button("⬅ Ant", disabled=(st.session_state.day_nav_index == 0), use_container_width=True):
                st.session_state.day_nav_index -= 1
                st.rerun()
        
        with col_title:
            st.markdown(
                f"<div style='text-align: center; font-size: 1.5rem; font-weight: bold; padding-top: 5px; color:#FF4B4B;'>{current_day_name}</div>", 
                unsafe_allow_html=True
            )
            
        with col_next:
            if st.button("Sig ➡", disabled=(st.session_state.day_nav_index == len(days_map) - 1), use_container_width=True):
                st.session_state.day_nav_index += 1
                st.rerun()

        # 5. CARGAR DATOS EXISTENTES (Para pre-rellenar)
        existing_order = db.query(Order).filter(
            Order.user_id == user_id, 
            Order.week_id == current_week.id
        ).first()
        
        current_details = existing_order.details if existing_order else {}

        # 6. TARJETA DEL DÍA
        st.markdown("###") # Espaciador

        # -- CASO: DÍA CERRADO / FERIADO --
        if current_day_code in closed_days:
            st.warning(f"⛔ El {current_day_name} está marcado como FERIADO o SIN SERVICIO.")
        else:
            # -- CASO: DÍA HÁBIL --
            menu_items = get_menu_items_by_day(db, current_week.id, current_day_code)
            
            if not menu_items["principal"]:
                st.info("⚠️ Aún no se ha cargado el menú para este día.")
            else:
                with st.container(border=True):
                    with st.form(key=f"form_{current_day_code}"):
                        st.subheader(f"Selección para el {current_day_name}")
                        
                        # --- PLATO PRINCIPAL ---
                        mains = menu_items["principal"]
                        main_opts = {f"Opción {m.option_number}: {m.description}": m.id for m in mains}
                        
                        # --- CAMBIO REALIZADO AQUÍ ---
                        main_opts["❌ No pedido"] = None
                        
                        # Pre-selección lógica
                        saved_main_id = current_details.get(f"{current_day_code}_principal")
                        
                        # Buscar el índice correcto para el radio button
                        default_idx = 0
                        if saved_main_id in main_opts.values():
                            vals = list(main_opts.values())
                            default_idx = vals.index(saved_main_id)
                        elif saved_main_id is None and existing_order:
                            # Si ya existe orden y es None, es la opción "No pedido" (último index)
                             default_idx = len(main_opts) - 1 

                        selected_main_label = st.radio(
                            "🍛 Plato Principal:",
                            options=list(main_opts.keys()),
                            index=default_idx
                        )
                        selected_main_id = main_opts[selected_main_label]

                        st.markdown("---")
                        
                        # --- EXTRAS (Solo visualmente activos, lógica interna) ---
                        c1, c2 = st.columns(2)
                        
                        # Acompañamiento
                        sides = menu_items["side"]
                        side_opts = {s.description: s.id for s in sides}
                        side_opts["Ninguno"] = None
                        
                        saved_side_id = current_details.get(f"{current_day_code}_side")
                        # Lógica para index del selectbox
                        side_idx = 0
                        if saved_side_id in side_opts.values():
                             side_idx = list(side_opts.values()).index(saved_side_id)
                        
                        with c1:
                            selected_side_label = st.selectbox(
                                "🍟 Guarnición:", 
                                list(side_opts.keys()),
                                index=side_idx,
                                key=f"sb_side_{current_day_code}"
                            )
                            selected_side_id = side_opts[selected_side_label]

                        # Ensalada
                        salads = menu_items["salad"]
                        salad_opts = {s.description: s.id for s in salads}
                        salad_opts["Ninguna"] = None
                        
                        saved_salad_id = current_details.get(f"{current_day_code}_salad")
                        salad_idx = 0
                        if saved_salad_id in salad_opts.values():
                             salad_idx = list(salad_opts.values()).index(saved_salad_id)

                        with c2:
                            selected_salad_label = st.selectbox(
                                "🥗 Ensalada:", 
                                list(salad_opts.keys()),
                                index=salad_idx,
                                key=f"sb_salad_{current_day_code}"
                            )
                            selected_salad_id = salad_opts[selected_salad_label]
                        
                        # Nota Adicional
                        saved_note = current_details.get(f"{current_day_code}_note", "")
                        note = st.text_area("📝 Nota para cocina (opcional):", value=saved_note, height=80)

                        st.markdown("###")
                        
                        # --- BOTÓN DE GUARDADO ---
                        # Texto dinámico según si ya pidió algo ese día
                        btn_text = "💾 Guardar / Actualizar este día"
                        if saved_main_id: 
                            btn_text = "🔄 Actualizar Selección del Lunes".replace("Lunes", current_day_name)

                        submitted = st.form_submit_button(btn_text, use_container_width=True, type="primary")
                        
                        if submitted:
                            # Preparamos SOLO los datos de este día
                            day_data = {
                                f"{current_day_code}_principal": selected_main_id,
                                f"{current_day_code}_side": selected_side_id if selected_main_id else None,
                                f"{current_day_code}_salad": selected_salad_id if selected_main_id else None,
                                f"{current_day_code}_note": note
                            }
                            
                            success, msg = save_single_day_order(db, user_id, current_week.id, day_data)
                            
                            if success:
                                st.success(msg)
                                # Pequeña pausa visual o rerun para actualizar estado
                                st.rerun()
                            else:
                                st.error(msg)
        
        # 7. RESUMEN RÁPIDO AL PIE (Opcional, para que vea qué días le faltan)
        if existing_order and existing_order.details:
            st.divider()
            st.caption("Resumen de días con pedido guardado:")
            completed_days = []
            for code, name in days_map:
                if existing_order.details.get(f"{code}_principal"):
                    completed_days.append(name)
            
            if completed_days:
                st.info(f"✅ Días listos: {', '.join(completed_days)}")
            else:
                st.warning("⚠️ Aún no has guardado ningún plato.")

    except Exception as e:
        st.error(f"Error en el panel de usuario: {e}")
    finally:
        db.close()
