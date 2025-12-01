import streamlit as st
from sqlalchemy.orm import Session
from database.models import Week, MenuItem, Order
# Importamos las nuevas funciones de servicio que agregaste a admin_service.py
from services.admin_service import check_existing_order, get_menu_options_for_week

def get_menu_options_by_type(db: Session, week_id: int, day: str, meal_type: str):
    """Obtiene las opciones de menú para los selectores (dropdowns)."""
    items = db.query(MenuItem).filter(
        MenuItem.week_id == week_id,
        MenuItem.day == day,
        MenuItem.type == meal_type
    ).order_by(MenuItem.option_number).all()
    
    options = {"NO PEDIDO": None}
    for item in items:
        # Importante: Guardamos el ID (item.id) como valor
        options[f"Opción {item.option_number}: {item.description}"] = item.id
    return options

def get_user_order(db: Session, user_id: int, week_id: int):
    """Recupera el pedido existente del usuario."""
    return db.query(Order).filter(Order.user_id == user_id, Order.week_id == week_id).first()

def submit_weekly_order(db: Session, user_id: int, week_id: int, order_data: dict, notes: str):
    """Guarda o actualiza el pedido."""
    order = get_user_order(db, user_id, week_id)
    
    if order is None:
        order = Order(
            user_id=user_id, 
            week_id=week_id,
            details={}, 
            status="success"
        )
        db.add(order)

    order.details = order_data
    order.notes = notes
    
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
    # 2. CARRUSEL DE OPCIONES DE MENÚ (VISUALIZADOR)
    # =======================================================
    st.markdown("### 📖 Menú Disponible")
    
    # Obtenemos el menú completo estructurado desde el servicio
    full_menu = get_menu_options_for_week(db, current_week.id)
    days_list = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]

    # Inicializar estado para el carrusel
    if 'menu_day_idx' not in st.session_state:
        st.session_state.menu_day_idx = 0

    # Controles de Navegación del Carrusel
    col_prev, col_day, col_next = st.columns([1, 4, 1])
    
    with col_prev:
        if st.button("◀ Anterior"):
            st.session_state.menu_day_idx = max(0, st.session_state.menu_day_idx - 1)
            st.rerun()
            st.stop() # <-- CORRECCIÓN APLICADA
            
    with col_next:
        if st.button("Siguiente ▶"):
            st.session_state.menu_day_idx = min(4, st.session_state.menu_day_idx + 1)
            st.rerun()
            st.stop() # <-- CORRECCIÓN APLICADA

    # Mostrar el día actual del carrusel
    current_day_name = days_list[st.session_state.menu_day_idx]
    
    with col_day:
        st.markdown(f"<h3 style='text-align: center; margin: 0;'>{current_day_name}</h3>", unsafe_allow_html=True)

    st.divider()

    # Mostrar contenido del día seleccionado en 3 columnas
    day_data = full_menu.get(current_day_name, {})
    mc1, mc2, mc3 = st.columns(3)

    # Función auxiliar para mostrar items visualmente
    def show_items(column, title, items):
        column.markdown(f"**{title}**")
        if not items:
            column.caption("No hay opciones registradas.")
        for item_id, desc, opt_num in items:
            # Diseño de tarjeta simple
            column.info(f"**Opción {opt_num}**\n\n{desc}")

    # Usamos las claves correctas del diccionario retornado por get_menu_options_for_week
    show_items(mc1, "🍖 Almuerzo / Principal", day_data.get('principal', []))
    show_items(mc2, "🍚 Acompañamiento", day_data.get('side', []))
    show_items(mc3, "🥗 Ensalada", day_data.get('salad', []))

    st.divider()

    # =======================================================
    # 3. GESTIÓN DEL PEDIDO (RESTRICCIÓN 1 PEDIDO)
    # =======================================================
    
    # Verificar si ya existe un pedido confirmado
    already_ordered = check_existing_order(db, user_id, current_week.id)
    
    # Variable de estado para permitir editar si el usuario quiere
    if 'editing_mode' not in st.session_state:
        st.session_state.editing_mode = False

    # CASO A: YA PIDIÓ Y NO ESTÁ EDITANDO -> MOSTRAR SOLO RESUMEN (BLOQUEADO)
    if already_ordered and not st.session_state.editing_mode:
        st.success("✅ ¡Ya has enviado tu solicitud para esta semana!")
        st.info("Tu pedido está registrado. Si necesitas hacer cambios, haz clic en el botón de abajo.")
        
        # Recuperar para mostrar un mini resumen (opcional)
        order = get_user_order(db, user_id, current_week.id)
        if order and order.notes:
            st.write(f"**Notas enviadas:** {order.notes}")
            
        if st.button("✏️ Modificar mi Pedido"):
            st.session_state.editing_mode = True
            st.rerun()
            st.stop() # <-- CORRECCIÓN APLICADA
            
    # CASO B: NO HA PEDIDO O ESTÁ EDITANDO -> MOSTRAR FORMULARIO
    else:
        st.subheader("📝 Realizar tu Pedido")
        
        # Recuperar datos existentes por si está editando
        existing_order = get_user_order(db, user_id, current_week.id)
        existing_details = existing_order.details if existing_order and existing_order.details else {}
        
        # Mapeo para nombres de días en inglés (usados en claves de formulario)
        day_keys_map = ["monday", "tuesday", "wednesday", "thursday", "friday"]
        
        meal_types_config = [
            ("Plato Principal", "principal", "_principal"),
            ("Ensalada", "salad", "_salad"),
            ("Acompañamiento", "side", "_side")
        ]
        
        order_values = {}
        
        with st.form("weekly_order_form"):
            
            # Encabezados de Días para el formulario
            cols = st.columns(5)
            for idx, day in enumerate(days_list):
                cols[idx].write(f"**{day}**")

            # Matriz de selectores
            for title, db_type, suffix in meal_types_config:
                st.write(f"*{title}*")
                cols = st.columns(5)
                
                for i, day_key in enumerate(day_keys_map):
                    day_name_es = days_list[i]
                    
                    # Obtener opciones
                    options = get_menu_options_by_type(db, current_week.id, day_name_es, db_type)
                    
                    # Determinar valor preseleccionado
                    field_key = f"{day_key}{suffix}" 
                    current_val = existing_details.get(field_key)
                    
                    # Buscar el índice del valor guardado (ID)
                    default_index = 0
                    if current_val in options.values():
                        # Truco para encontrar el índice basado en el valor (ID)
                        values_list = list(options.values())
                        default_index = values_list.index(current_val)

                    # Renderizar Selectbox
                    selection = cols[i].selectbox(
                        f"{title} {day_name_es}", 
                        options=list(options.keys()),
                        index=default_index,
                        key=f"sel_{field_key}",
                        label_visibility="collapsed"
                    )
                    
                    order_values[field_key] = options[selection]

            st.markdown("---")
            
            initial_notes = existing_order.notes if existing_order else ""
            notes = st.text_area("Notas / Sugerencias", value=initial_notes)
            
            st.write(" ") 

            # Botón de Envío
            btn_text = "🔄 Actualizar Pedido" if already_ordered else "🚀 Enviar Pedido Semanal"
            submitted = st.form_submit_button(btn_text)
            
            if submitted:
                success = submit_weekly_order(db, user_id, current_week.id, order_values, notes)
                
                if success:
                    st.success("✅ ¡Pedido guardado exitosamente!")
                    st.session_state.editing_mode = False # Salir del modo edición
                    st.balloons()
                    st.rerun() 
                    st.stop() # <-- CORRECCIÓN APLICADA
                else:
                    st.error("❌ Error al guardar el pedido. Intenta de nuevo.")

    db.close()