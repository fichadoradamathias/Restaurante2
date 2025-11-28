import streamlit as st
from sqlalchemy.orm import Session
from database.models import Week, MenuItem, Order
from datetime import date

def get_menu_options_by_type(db: Session, week_id: int, day: str, meal_type: str):
    """Obtiene las opciones de menú para un día y tipo de plato específicos."""
    items = db.query(MenuItem).filter(
        MenuItem.week_id == week_id,
        MenuItem.day == day,
        MenuItem.type == meal_type
    ).order_by(MenuItem.option_number).all()
    
    options = {"NO PEDIDO": None}
    for item in items:
        # Crea una etiqueta legible: "Opción 1: Pollo al horno"
        options[f"Opción {item.option_number}: {item.description}"] = item.option_number
    return options

def get_user_order(db: Session, user_id: int, week_id: int):
    """Recupera el pedido existente del usuario si lo hay."""
    return db.query(Order).filter(Order.user_id == user_id, Order.week_id == week_id).first()

def submit_weekly_order(db: Session, user_id: int, week_id: int, order_data: dict, notes: str):
    """Guarda o actualiza el pedido empaquetando los datos en el JSON 'details'."""
    order = get_user_order(db, user_id, week_id)
    
    if order is None:
        # Si no existe, creamos uno nuevo
        order = Order(
            user_id=user_id, 
            week_id=week_id,
            details={}, # Inicializamos el JSON vacío
            status="success"
        )
        db.add(order)

    # --- CORRECCIÓN LÓGICA IMPORTANTE ---
    # En lugar de hacer setattr(order, "lunes_principal"), guardamos todo en 'details'
    # porque tu modelo de base de datos usa una columna JSON para esto.
    order.details = order_data  # SQLAlchemy maneja la conversión a JSON automáticamente
    order.notes = notes
    
    try:
        db.commit()
        return True
    except Exception as e:
        print(f"Error al guardar pedido: {e}")
        db.rollback()
        return False

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
    
    # Extraer los detalles del JSON si existen, para pre-llenar el formulario
    existing_details = existing_order.details if existing_order and existing_order.details else {}
    
    # Configuración de días y tipos
    days = ["monday", "tuesday", "wednesday", "thursday", "friday"]
    day_names = {"monday": "Lunes", "tuesday": "Martes", "wednesday": "Miércoles", "thursday": "Jueves", "friday": "Viernes"}
    
    # Estructura para iterar y generar la UI
    meal_types_config = [
        ("Plato Principal", "principal", "_principal"),
        ("Ensalada", "salad", "_salad"),
        ("Acompañamiento", "side", "_side")
    ]
    
    order_values = {}
    
    with st.form("weekly_order_form"):
        st.markdown("---")
        
        # Encabezados de Días
        cols = st.columns(5)
        for idx, day in enumerate(days):
            cols[idx].subheader(day_names[day])

        # Generar matriz de selectores (Filas: Tipos, Columnas: Días)
        for title, db_type, suffix in meal_types_config:
            st.markdown(f"### {title}")
            cols = st.columns(5)
            
            for i, day_key in enumerate(days):
                # 1. Obtener opciones de la BD para este día/tipo
                options = get_menu_options_by_type(db, current_week.id, day_names[day_key], db_type)
                
                # 2. Determinar valor actual (si ya pidió antes)
                field_key = f"{day_key}{suffix}" # ej: monday_principal
                current_val = existing_details.get(field_key)
                
                # 3. Buscar el índice correcto para el select