import pandas as pd
import json
import os
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
from database.models import Week, Order, User, MenuItem, ExportLog

# --- FUNCIONES DE GESTIÓN DE MENÚ ---

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
    if start_date > end_date:
        raise ValueError("Fecha inicio debe ser anterior a fin.")
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

    day_keys = ["monday", "tuesday", "wednesday", "thursday", "friday"]
    
    # 2. Crear registros de 'no_pedido' para auditoría histórica
    for user in active_users:
        if user.id not in users_with_order_ids:
            # Crea un diccionario de detalles vacío para el "no_pedido"
            ghost_details = {}
            for day in day_keys:
                for db_type in ["principal", "side", "salad"]:
                    ghost_details[f"{day}_{db_type}"] = None 

            ghost_order = Order(
                user_id=user.id,
                week_id=week_id,
                status="no_pedido",
                details=ghost_details 
            )
            db.add(ghost_order)
    
    week.is_open = False # Cerrar semana
    db.commit()

    # 3. Generar Excel
    return export_week_to_excel(db, week_id)

def export_week_to_excel(db: Session, week_id: int):
    week = db.query(Week).filter(Week.id == week_id).first()
    orders = db.query(Order).options(joinedload(Order.user)).filter(Order.week_id == week_id).all()
    
    data = []
    
    # Definimos las claves internas (inglés) y las columnas externas (español)
    day_keys = ["monday", "tuesday", "wednesday", "thursday", "friday"] 
    english_to_spanish = {
        "monday": "Lunes",
        "tuesday": "Martes",
        "wednesday": "Miércoles",
        "thursday": "Jueves",
        "friday": "Viernes"
    }
    
    meal_types = [("principal", "Comida"), ("side", "Acompañamiento"), ("salad", "Ensalada")]

    # 1. Pre-definimos las columnas finales para evitar KeyErrors
    final_cols = ["Usuario"]
    for d_key in day_keys:
        d_name = english_to_spanish[d_key]
        for _, label in meal_types:
            final_cols.append(f"{d_name} - {label}")

    menu_item_cache = {} 

    for order in orders:
        details = order.details 
        row = { "Usuario": order.user.full_name }
        
        for day in day_keys:
            # Traducimos "monday" -> "Lunes" para que coincida con la columna
            day_name_es = english_to_spanish[day]
            
            for db_type, label in meal_types:
                # Clave para buscar en la BD (ej: monday_principal)
                field_key = f"{day}_{db_type}" 
                
                # Nombre de la columna en el Excel (ej: Lunes - Comida)
                col_name = f"{day_name_es} - {label}" 
                
                option_id_or_string = details.get(field_key) 
                
                item_description = "NO PEDIDO"

                if isinstance(option_id_or_string, int):
                    option_id = option_id_or_string
                    if option_id not in menu_item_cache:
                        menu_item = db.query(MenuItem).filter(MenuItem.id == option_id).first()
                        if menu_item:
                            menu_item_cache[option_id] = menu_item.description
                    item_description = menu_item_cache.get(option_id, "Opción Desconocida")
                elif order.status == "no_pedido" or option_id_or_string is None:
                     item_description = "NO PEDIDO"
                else:
                    item_description = "Dato Inválido"

                row[col_name] = item_description

        data.append(row)

    # Creamos el DataFrame forzando las columnas. Si falta algún dato, pondrá NaN (evita error)
    df = pd.DataFrame(data, columns=final_cols)
    
    # Rellenamos posibles NaNs con cadena vacía por limpieza
    df = df.fillna("")

    safe_title = "".join([c if c.isalnum() else "_" for c in week.title])
    filename = f"{safe_title}_DETALLADO_COCINA_{datetime.now().strftime('%Y%m%d')}.xlsx"
    path = f"data/exports/{filename}"
    
    os.makedirs("data/exports", exist_ok=True)
    df.to_excel(path, index=False) 
    
    log = ExportLog(week_id=week_id, filename=path)
    db.add(log)
    db.commit()
    
    return path, "Exportación exitosa"