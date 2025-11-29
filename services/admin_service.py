import pandas as pd
import json
import os
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
from database.models import Week, Order, User, MenuItem, ExportLog

# --- FUNCIONES DE GESTIÓN DE MENÚ (Nuevas para la edición) ---

def update_menu_item(db: Session, item_id: int, new_description: str, new_option_number: int):
    """Actualiza la descripción y número de opción de un ítem del menú."""
    item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
    if not item:
        return False, "Ítem no encontrado."
    
    item.description = new_description
    item.option_number = new_option_number
    try:
        db.commit()
        return True, "Ítem actualizado correctamente."
    except Exception as e:
        db.rollback()
        print(f"Error al actualizar ítem: {e}")
        return False, "Error al guardar en la base de datos."

def delete_menu_item(db: Session, item_id: int):
    """Elimina un ítem del menú."""
    item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
    if not item:
        return False, "Ítem no encontrado."
    
    try:
        db.delete(item)
        db.commit()
        return True, "Ítem eliminado correctamente."
    except Exception as e:
        db.rollback()
        print(f"Error al eliminar ítem: {e}")
        return False, "Error al eliminar de la base de datos."

# --- FUNCIONES DE SEMANA ---

def create_week(db: Session, title, start_date, end_date):
    # Validación: Fechas coherentes
    if start_date > end_date:
        raise ValueError("Fecha inicio debe ser anterior a fin.")
    # TODO: Validar superposición de fechas con semanas abiertas existente
    new_week = Week(title=title, start_date=start_date, end_date=end_date)
    db.add(new_week)
    db.commit()
    db.refresh(new_week)
    return new_week

def finalize_week_logic(db: Session, week_id: int):
    """
    1. Cierra la semana.
    2. Detecta usuarios sin pedido y crea registros 'no_pedido'.
    3. Genera Excel.
    """
    week = db.query(Week).filter(Week.id == week_id).first()
    if not week or not week.is_open:
        return None, "Semana no encontrada o ya cerrada."

    # 1. Identificar quién no pidió
    active_users = db.query(User).filter(User.is_active == True).all()
    existing_orders = db.query(Order).filter(Order.week_id == week_id).all()
    users_with_order_ids = {o.user_id for o in existing_orders}

    # 2. Crear registros de 'no_pedido' para auditoría histórica
    for user in active_users:
        if user.id not in users_with_order_ids:
            # CORRECCIÓN 1: Usar 'details' en lugar de 'details_json' y sin json.dumps
            ghost_order = Order(
                user_id=user.id,
                week_id=week_id,
                status="no_pedido",
                details={day: "NO PEDIDO" for day in ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]}
            )
            db.add(ghost_order)
    
    week.is_open = False # Cerrar semana
    db.commit()

    # 3. Generar Excel
    return export_week_to_excel(db, week_id)

def export_week_to_excel(db: Session, week_id: int):
    week = db.query(Week).filter(Week.id == week_id).first()
    # Usamos joinedload para traer el usuario de inmediato
    orders = db.query(Order).options(joinedload(Order.user)).filter(Order.week_id == week_id).all()
    
    data = []
    
    # Días clave usados en el menú y el pedido (en minúsculas)
    day_keys = ["monday", "tuesday", "wednesday", "thursday", "friday"] 
    # Nombres de columna en Excel
    day_names = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]

    # Tipos de plato y sus etiquetas para la exportación
    meal_types = [("principal", "Comida"), ("side", "Acompañamiento"), ("salad", "Ensalada")]

    # Crear un caché para no consultar la base de datos por cada ítem
    menu_item_cache = {} # Key: item_id, Value: description

    for order in orders:
        # CORRECCIÓN 2: Usar order.details y no order.details_json ni json.loads
        details = order.details 
        
        row = {
            "Usuario": order.user.full_name,
            # Se eliminan Status y Fecha Pedido según tu solicitud de sólo 5 columnas
        }
        
        # Iterar por cada día y por cada tipo de plato
        for day_index, day in enumerate(day_keys):
            full_day_details = []
            
            # Nombre de la columna en el Excel: Lunes, Martes, etc.
            col_name = day_names[day_index]
            
            for db_type, label in meal_types:
                # La clave en el JSON es (ej: monday_principal)
                field_key = f"{day}_{db_type}" 
                
                # option_id es el ID numérico del item seleccionado (o None si NO PEDIDO)
                option_id = details.get(field_key) 
                
                item_description = "NO PEDIDO"

                if option_id:
                    # Si el item_id no está en caché, lo buscamos en la base de datos
                    if option_id not in menu_item_cache:
                        menu_item = db.query(MenuItem).filter(MenuItem.id == option_id).first()
                        if menu_item:
                            menu_item_cache[option_id] = menu_item.description
                    
                    item_description = menu_item_cache.get(option_id, "Opción Desconocida")

                # Formato solicitado: "Comida: Pollo"
                full_day_details.append(f"{label}: {item_description}")
            
            # Unir los 3 detalles en una sola celda, separados por salto de línea
            row[col_name] = "\n".join(full_day_details)

        data.append(row)

    df = pd.DataFrame(data)
    
    # Definir el orden y las columnas finales solicitadas
    final_cols = ["Usuario"] + day_names 
    
    # Creamos un nuevo DataFrame con el orden de columnas deseado
    df_final = df[final_cols] 
    
    # Nombre archivo seguro
    safe_title = "".join([c if c.isalnum() else "_" for c in week.title])
    filename = f"{safe_title}_{datetime.now().strftime('%Y%m%d')}.xlsx"
    path = f"data/exports/{filename}"
    
    os.makedirs("data/exports", exist_ok=True)
    df_final.to_excel(path, index=False) 
    
    # Log
    log = ExportLog(week_id=week_id, filename=path)
    db.add(log)
    db.commit()
    
    return path, "Exportación exitosa"