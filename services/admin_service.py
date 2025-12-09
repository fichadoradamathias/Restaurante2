# services/admin_service.py
import pandas as pd
import json
import os
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
# IMPORTANTE: Agregamos Office a los imports
from database.models import Week, Order, User, MenuItem, ExportLog, AuditLog, Office 

# --- FUNCIONES DE AUDITORÍA ---
def create_log_entry(db: Session, actor_id: int, target_username: str, action: str, old_value: str = None, new_value: str = None, details: str = None):
    new_log = AuditLog(
        actor_id=str(actor_id),
        target_username=target_username,
        action=action,
        old_value=old_value,
        new_value=new_value,
        details=details
    )
    db.add(new_log)
    db.commit()
    return True

# --- FUNCIONES DE OFICINAS (NUEVO) ---
def create_office(db: Session, name: str):
    if db.query(Office).filter(Office.name == name).first():
        return False, "La oficina ya existe."
    new_office = Office(name=name)
    db.add(new_office)
    try:
        db.commit()
        return True, "Oficina creada."
    except Exception as e:
        db.rollback()
        return False, f"Error: {e}"

def get_all_offices(db: Session):
    return db.query(Office).order_by(Office.name).all()

def delete_office(db: Session, office_id: int):
    # Nota: Si borras una oficina con usuarios, estos quedarán con office_id inválido o null.
    # Idealmente reasignar antes.
    office = db.query(Office).filter(Office.id == office_id).first()
    if office:
        db.delete(office)
        db.commit()
        return True, "Oficina eliminada."
    return False, "Oficina no encontrada."

# --- FUNCIONES DE GESTIÓN DE MENÚ ---
def update_menu_item(db: Session, item_id: int, new_description: str, new_option_number: int):
    item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
    if not item: return False, "Ítem no encontrado."
    item.description = new_description
    item.option_number = new_option_number
    try:
        db.commit()
        return True, "Ítem actualizado."
    except Exception as e:
        db.rollback()
        return False, "Error al guardar."

def delete_menu_item(db: Session, item_id: int):
    item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
    if not item: return False, "Ítem no encontrado."
    try:
        db.delete(item)
        db.commit()
        return True, "Ítem eliminado."
    except Exception as e:
        db.rollback()
        return False, "Error al eliminar."

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
    week = db.query(Week).filter(Week.id == week_id).first()
    if not week or not week.is_open:
        return None, "Semana no encontrada o ya cerrada."

    active_users = db.query(User).filter(User.is_active == True).all()
    existing_orders = db.query(Order).filter(Order.week_id == week_id).all()
    users_with_order_ids = {o.user_id for o in existing_orders}
    day_keys = ["monday", "tuesday", "wednesday", "thursday", "friday"]
    
    for user in active_users:
        if user.id not in users_with_order_ids:
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
    
    week.is_open = False 
    db.commit()
    
    # Exportación por defecto (Todas las oficinas)
    return export_week_to_excel(db, week_id)

# --- EXPORTACIÓN CON FILTRO DE OFICINA ---
def export_week_to_excel(db: Session, week_id: int, office_id: int = None):
    week = db.query(Week).filter(Week.id == week_id).first()
    
    # Query Base
    query = db.query(Order).options(joinedload(Order.user)).filter(Order.week_id == week_id)
    
    # 1. FILTRO POR OFICINA
    office_name_str = "TODAS"
    if office_id is not None:
        query = query.join(Order.user).filter(User.office_id == office_id)
        office_obj = db.query(Office).filter(Office.id == office_id).first()
        if office_obj:
            office_name_str = office_obj.name.replace(" ", "_").upper()

    orders = query.all()
    
    data = []
    day_keys = ["monday", "tuesday", "wednesday", "thursday", "friday"] 
    english_to_spanish = {"monday": "Lunes", "tuesday": "Martes", "wednesday": "Miércoles", "thursday": "Jueves", "friday": "Viernes"}
    meal_types = [("principal", "Comida"), ("side", "Acompañamiento"), ("salad", "Ensalada")]

    # Pre-definimos columnas
    final_cols = ["Usuario", "Oficina"] # Agregamos columna Oficina visualmente también
    for d_key in day_keys:
        d_name = english_to_spanish[d_key]
        for _, label in meal_types:
            final_cols.append(f"{d_name} - {label}")

    menu_item_cache = {} 

    for order in orders:
        details = order.details 
        # Obtenemos nombre de oficina del usuario
        user_office = order.user.office.name if order.user.office else "Sin Oficina"
        
        row = {
            "Usuario": order.user.full_name,
            "Oficina": user_office
        }
        
        for day in day_keys:
            day_name_es = english_to_spanish[day]
            for db_type, label in meal_types:
                field_key = f"{day}_{db_type}" 
                col_name = f"{day_name_es} - {label}" 
                option_id_or_string = details.get(field_key) 
                item_description = "NO PEDIDO"

                if isinstance(option_id_or_string, int):
                    option_id = option_id_or_string
                    if option_id not in menu_item_cache:
                        menu_item = db.query(MenuItem).filter(MenuItem.id == option_id).first()
                        if menu_item: menu_item_cache[option_id] = menu_item.description
                    item_description = menu_item_cache.get(option_id, "Opción Desconocida")
                elif order.status == "no_pedido" or option_id_or_string is None:
                     item_description = "NO PEDIDO"
                else:
                    item_description = "Dato Inválido"
                row[col_name] = item_description
        data.append(row)

    df = pd.DataFrame(data, columns=final_cols)
    df = df.fillna("")

    safe_title = "".join([c if c.isalnum() else "_" for c in week.title])
    # Nombre del archivo incluye la oficina
    filename = f"{safe_title}_{office_name_str}_{datetime.now().strftime('%Y%m%d')}.xlsx"
    path = f"data/exports/{filename}"
    
    os.makedirs("data/exports", exist_ok=True)
    df.to_excel(path, index=False) 
    
    # Solo guardamos log si es exportación general (opcional, aquí guardamos todo)
    log = ExportLog(week_id=week_id, filename=path)
    db.add(log)
    db.commit()
    
    return path, "Exportación exitosa"

# Funciones extra para el usuario
def check_existing_order(db: Session, user_id: int, week_id: int):
    existing_order = db.query(Order).filter(Order.user_id == user_id, Order.week_id == week_id, Order.status != 'no_pedido').first()
    return existing_order is not None

def get_menu_options_for_week(db: Session, week_id: int):
    menu_items = db.query(MenuItem).filter(MenuItem.week_id == week_id).order_by(MenuItem.day, MenuItem.type, MenuItem.option_number).all()
    menu = {"Lunes": {"principal": [], "side": [], "salad": []}, "Martes": {"principal": [], "side": [], "salad": []}, "Miércoles": {"principal": [], "side": [], "salad": []}, "Jueves": {"principal": [], "side": [], "salad": []}, "Viernes": {"principal": [], "side": [], "salad": []}}
    for item in menu_items:
        if item.day in menu and item.type in menu[item.day]:
            menu[item.day][item.type].append((item.id, item.description, item.option_number))
    return menu