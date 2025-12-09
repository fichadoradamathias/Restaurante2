import streamlit as st
from sqlalchemy.orm import Session
from database.models import Week, MenuItem, Order
from services.admin_service import check_existing_order, get_menu_options_for_week

# NOTA: get_menu_options_by_type ya no es tan crítico si usamos el nuevo método
# pero lo mantenemos por si acaso.

def get_user_order(db: Session, user_id: int, week_id: int):
    """Recupera el pedido existente del usuario (o None si no existe)."""
    return db.query(Order).filter(Order.user_id == user_id, Order.week_id == week_id).first()

def submit_weekly_order(db: Session, user_id: int, week_id: int, order_data: dict, notes: str = ""):
    """Guarda o actualiza el pedido. El campo notes es opcional en esta nueva lógica."""
    order = get_user_order(db, user_id, week_id)
    
    if order is None:
        # Si no existe, creamos uno nuevo
        order = Order(
            user_id=user_id, 
            week_id=week_id,
            details=order_data, 
            status="success"
        )
        db.add(order)
    else:
        # Si existe, actualizamos los detalles
        order.details = order_data
        order.status = "success"
    
    # Mantener las notas si ya existen, si no se usan en el nuevo flujo
    if order.notes is None:
        order.notes = ""

    try:
        db.commit()
        return True
    except Exception as e:
        print(f"Error al guardar pedido: {e}")
        db.rollback()
        return False

# --- FUNCIÓN PRINCIPAL DE LA VISTA ---

def user_dashboard(db_session_maker, user_id):
    st.title(f"🍽️ Panel de Pedidos")
    
    db = db_session_maker()
    
    # 1. ENCONTRAR SEMANA ABIERTA
    current_week = db.query(Week).filter(Week.is_open == True).first()
    
    if not current_week:
        st.info("Actualmente no hay una semana de pedidos abierta.")
        db.close()
        return

    st.subheader(f"📅 Semana: {current_week.title}")

    # =======================================================
    # 2. LÓGICA DE PEDIDO EN SESIÓN Y RECUPERACIÓN DE DATOS
    # =======================================================
    days_list = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
    day_keys_map = ["monday", "tuesday", "wednesday", "thursday", "friday"]
    
    # Clave de sesión para almacenar el pedido temporalmente
    order_key = f"current_order_{current_week.id}_{user_id}"
    
    # Recuperar pedido existente o inicializar la sesión
    existing_order = get_user_order(db, user_id, current_week.id)
    
    if order_key not in st.session_state:
        # Inicializar el pedido de sesión con los detalles guardados o vacío
        initial_details = existing_order.details if existing_order and existing_order.details else {}
        st.session_state[order_key] = initial_details
        
        # Asegurar que todas las claves existan para evitar errores de llave
        for day in day_keys_map:
            for meal in ["_principal", "_side", "_salad"]:
                key = f"{day}{meal}"
                if key not in st.session_state[order_key]:
                    # Por defecto es None (NO PEDIDO)
                    st.session_state[order_key][key] = None 

    # =======================================================
    # 3. GESTIÓN DEL PEDIDO (RESTRICCIÓN Y MODO EDICIÓN)
    # =======================================================
    
    already_ordered = check_existing_order(db, user_id, current_week.id)
    if 'editing_mode' not in st.session_state:
        st.session_state.editing_mode = False

    # Bloqueo si ya pidió y no está en modo edición
    if already_ordered and not st.session_state.editing_mode:
        st.success("✅ ¡Ya has enviado tu solicitud para esta semana!")
        st.info("Tu pedido está registrado. Si necesitas hacer cambios, haz clic en el botón de abajo.")
        
        if existing_order and existing_order.notes:
            st.write(f"**Notas enviadas:** {existing_order.notes}")
            
        if st.button("✏️ Modificar mi Pedido"):
            st.session_state.editing_mode = True
            st.rerun()
            st.stop()
            
        db.close()
        return

    # =======================================================
    # 4. CARRUSEL DE OPCIONES DE MENÚ (VISUALIZADOR Y SELECCIÓN)
    # =======================================================
    
    st.markdown("### 👆 Selecciona tu opción haciendo clic en la tarjeta")
    
    # Obtenemos el menú completo estructurado
    full_menu = get_menu_options_for_week(db, current_week.id)

    if 'menu_day_idx' not in st.session_state:
        st.session_state.menu_day_idx = 0

    # Funciones de Manejo de Selección y Navegación
    
    def handle_selection(day_key, meal_type_suffix, item_id):
        """Guarda la selección en el estado de la sesión."""
        field_key = f"{day_key}{meal_type_suffix}"
        st.session_state[order_key][field_key] = item_id
    
    def navigate(direction):
        """Maneja la navegación del carrusel."""
        if direction == 'prev':
            st.session_state.menu_day_idx = max(0, st.session_state.menu_day_idx - 1)
        elif direction == 'next':
            st.session_state.menu_day_idx = min(len(days_list) - 1, st.session_state.menu_day_idx + 1)
        
        # Forzamos el rerun para actualizar la vista
        st.rerun()
        st.stop()

    # Controles de Navegación del Carrusel
    col_prev, col_day, col_next = st.columns([1, 4, 1])
    
    with col_prev:
        if st.button("◀ Anterior"):
            navigate('prev')
            
    with col_next:
        if st.button("Siguiente ▶"):
            navigate('next')

    # Mostrar el día actual del carrusel
    current_day_index = st.session_state.menu_day_idx
    current_day_name = days_list[current_day_index]
    current_day_key = day_keys_map[current_day_index] # 'monday', 'tuesday', etc.

    with col_day:
        st.markdown(f"<h3 style='text-align: center; margin: 0;'>{current_day_name}</h3>", unsafe_allow_html=True)

    st.divider()

    # Mostrar contenido del día seleccionado y permitir selección
    day_data = full_menu.get(current_day_name, {})
    
    # Configuración de los tipos de plato para iterar
    meal_types_config = [
        ("🍖 Almuerzo / Principal", "principal", "_principal"),
        ("🍚 Acompañamiento", "side", "_side"),
        ("🥗 Ensalada", "salad", "_salad")
    ]
    
    cols = st.columns(3)

    for i, (title, db_type, suffix) in enumerate(meal_types_config):
        
        column = cols[i]
        column.markdown(f"**{title}**")
        
        field_key = f"{current_day_key}{suffix}" # ej: monday_principal
        current_selection_id = st.session_state[order_key].get(field_key)

        # 1. OPCIÓN "NO PEDIDO" (Fija, ID=None)
        is_selected = current_selection_id is None
        
        # Usamos un truco con st.empty() y st.button() para simular una tarjeta clickeable
        card_style = "background-color: #0b1a2e; padding: 10px; border-radius: 5px; cursor: pointer;"
        selected_style = "background-color: #0d47a1; border: 2px solid #4caf50;" 

        with column:
            # Botón / Tarjeta para NO PEDIDO
            if is_selected:
                st.markdown(f"<div style='{selected_style} {card_style}'>**NO PEDIDO** (Seleccionado)</div>", unsafe_allow_html=True)
            elif st.button("NO PEDIDO", key=f"btn_none_{field_key}", use_container_width=True):
                handle_selection(current_day_key, suffix, None)
                st.rerun()
                st.stop()
        
        # 2. OPCIONES REALES DEL MENÚ
        items = day_data.get(db_type, [])
        if not items:
            column.caption("No hay opciones registradas.")
        
        for item_id, desc, opt_num in items:
            is_selected = item_id == current_selection_id

            with column:
                if is_selected:
                    st.markdown(f"<div style='{selected_style} {card_style}'>**Opción {opt_num}** (Seleccionado)<br>{desc}</div>", unsafe_allow_html=True)
                elif st.button(f"Opción {opt_num}: {desc}", key=f"btn_{item_id}", use_container_width=True):
                    handle_selection(current_day_key, suffix, item_id)
                    st.rerun()
                    st.stop()
                    
    st.divider()

    # =======================================================
    # 5. BOTÓN FINAL DE ENVÍO
    # =======================================================
    
    # Campo de Notas (lo mantenemos opcional)
    initial_notes = existing_order.notes if existing_order else ""
    notes = st.text_area("Notas / Sugerencias", value=initial_notes, help="(Agrega sugerencia o aviso si deseas)")
    
    st.write(" ") 

    btn_text = "🔄 Actualizar Pedido" if already_ordered else "🚀 Finalizar y Enviar Pedido Semanal"
    
    if st.button(btn_text, key="final_submit_button", type="primary"):
        # Guardamos el pedido de la sesión en la base de datos
        success = submit_weekly_order(db, user_id, current_week.id, st.session_state[order_key], notes)
        
        if success:
            st.success("✅ ¡Pedido guardado exitosamente!")
            st.session_state.editing_mode = False # Salir del modo edición
            st.balloons()
            
            # Borrar el estado de sesión temporal para asegurar que se cargue desde la BD en el próximo inicio
            if order_key in st.session_state:
                del st.session_state[order_key]
                
            st.rerun() 
            st.stop()
        else:
            st.error("❌ Error al guardar el pedido. Intenta de nuevo.")

    db.close()