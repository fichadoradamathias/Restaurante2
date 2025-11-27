import streamlit as st
from sqlalchemy.orm import Session
from database.models import Week, MenuItem, Order
#from services.user_service import get_menu_items_for_week
from datetime import date

def get_menu_options_by_type(db: Session, week_id: int, day: str, meal_type: str):
    """Obtiene las opciones de menú para un día y tipo de plato específicos."""
    items = db.query(MenuItem).filter(
        MenuItem.week_id == week_id,
        MenuItem.day == day,
        MenuItem.type == meal_type # <-- CORRECCIÓN APLICADA
    ).order_by(MenuItem.option_number).all()
    
    options = {"NO PEDIDO": None}
    for item in items:
        options[f"Opción {item.option_number}: {item.description}"] = item.option_number
    return options

def get_user_order(db: Session, user_id: int, week_id: int):
    """Recupera el pedido del usuario."""
    return db.query(Order).filter(Order.user_id == user_id, Order.week_id == week_id).first()

def submit_weekly_order(db: Session, user_id: int, week_id: int, order_data: dict, notes: str):
    """Guarda o actualiza el pedido semanal con las 15 opciones."""
    order = get_user_order(db, user_id, week_id)
    
    if order is None:
        order = Order(user_id=user_id, week_id=week_id)
        db.add(order)

    # Actualizar los 15 campos
    for key, value in order_data.items():
        setattr(order, key, value)
    
    # Actualizar notas
    order.notes = notes
    
    db.commit()
    return True

def user_dashboard(db_session_maker, user_id):
    st.title(f"🍽️ Pedido Semanal")
    
    db = db_session_maker()
    
    # 1. ENCONTRAR SEMANA ABIERTA
    current_week = db.query(Week).filter(Week.is_open == True).first()
    
    if not current_week:
        st.info("Actualmente no hay una semana de pedidos abierta.")
        db.close()
        return

    st.subheader(f"Semana Activa: {current_week.title}")
    
    # 2. RECUPERAR DATOS EXISTENTES
    existing_order = get_user_order(db, user_id, current_week.id)
    
    # Lista de días y tipos de plato
    days = ["monday", "tuesday", "wednesday", "thursday", "friday"]
    meal_types = ["principal", "salad", "side"]
    day_names = {"monday": "Lunes", "tuesday": "Martes", "wednesday": "Miércoles", "thursday": "Jueves", "friday": "Viernes"}
    
    order_values = {}
    
    with st.form("weekly_order_form"):
        st.markdown("---")
        
        # UI DE TÍTULOS DE COLUMNAS
        c_title_1, c_title_2, c_title_3, c_title_4, c_title_5 = st.columns(5)
        c_title_1.subheader("Lunes")
        c_title_2.subheader("Martes")
        c_title_3.subheader("Miércoles")
        c_title_4.subheader("Jueves")
        c_title_5.subheader("Viernes")

        # --- FILA 1: PLATO PRINCIPAL ---
        st.markdown("### Plato Principal") # NUEVO TÍTULO
        cols_principal = st.columns(5)
        
        # --- FILA 2: ENSALADA ---
        st.markdown("### Ensalada") # NUEVO TÍTULO
        cols_salad = st.columns(5)
        
        # --- FILA 3: ACOMPAÑAMIENTO ---
        st.markdown("### Acompañamiento") # NUEVO TÍTULO
        cols_side = st.columns(5)

        # 3. GENERAR SELECTORES DINÁMICOS
        for i, day_key in enumerate(days):
            
            # 1. PLATO PRINCIPAL
            options_principal = get_menu_options_by_type(db, current_week.id, day_names[day_key], 'principal')
            field_key = f"{day_key}_principal"
            
            current_val = getattr(existing_order, field_key) if existing_order else None
            default_index = list(options_principal.values()).index(current_val) if current_val in options_principal.values() else 0
            
            selection = cols_principal[i].selectbox(
                f"Plato Principal {day_names[day_key]}", 
                options=list(options_principal.keys()),
                index=default_index,
                key=f"{day_key}_p",
                label_visibility="collapsed"
            )
            order_values[field_key] = options_principal[selection]

            # 2. ENSALADA
            options_salad = get_menu_options_by_type(db, current_week.id, day_names[day_key], 'salad')
            field_key = f"{day_key}_salad"
            
            current_val = getattr(existing_order, field_key) if existing_order else None
            default_index = list(options_salad.values()).index(current_val) if current_val in options_salad.values() else 0
            
            selection = cols_salad[i].selectbox(
                f"Ensalada {day_names[day_key]}", 
                options=list(options_salad.keys()),
                index=default_index,
                key=f"{day_key}_s",
                label_visibility="collapsed"
            )
            order_values[field_key] = options_salad[selection]
            
            # 3. ACOMPAÑAMIENTO
            options_side = get_menu_options_by_type(db, current_week.id, day_names[day_key], 'side')
            field_key = f"{day_key}_side"
            
            current_val = getattr(existing_order, field_key) if existing_order else None
            default_index = list(options_side.values()).index(current_val) if current_val in options_side.values() else 0
            
            selection = cols_side[i].selectbox(
                f"Acompañamiento {day_names[day_key]}", 
                options=list(options_side.keys()),
                index=default_index,
                key=f"{day_key}_o",
                label_visibility="collapsed"
            )
            order_values[field_key] = options_side[selection]


        st.markdown("---")
        
        # CAMPO DE NOTAS ACTUALIZADO
        initial_notes = existing_order.notes if existing_order else ""
        notes = st.text_area("Notas / Sugerencias", value=initial_notes, help="(Agrega sugerencia o aviso si deseas)")
        
        st.write(" ") # Espacio

        if st.form_submit_button("🚀 Enviar Pedido Semanal"):
            success = submit_weekly_order(db, user_id, current_week.id, order_values, notes)
            
            if success:
                st.success("✅ ¡Pedido semanal guardado exitosamente!")
                st.balloons()
            else:
                st.error("❌ Error al guardar el pedido. Intenta de nuevo.")

    db.close()
