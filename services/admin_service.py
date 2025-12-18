# services/admin_service.py
import pandas as pd
import json
import os
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload
from database.models import Week, Order, User, MenuItem, ExportLog, AuditLog, Office

# --- UTILIDAD: HORA UTC-3 ---
def get_now_utc3():
    """Retorna la hora actual ajustada a UTC-3 (Paraguay/Argentina/Uruguay sin horario verano)"""
    return datetime.utcnow() - timedelta(hours=3)

# --- AUDITORÍA ---
def create_log_entry(db: Session, actor_id: int, target_username: str, action: str, old_value: str = None, new_value: str = None, details: str = None):
    new_log = AuditLog(
        actor_id=str(actor_id), target_username=target_username, action=action,
        old_value=old_value, new_value=new_value, details=details
    )
    db.add(new_log)
    db.commit()
    return True

# --- GESTIÓN DE OFICINAS ---
def create_office(db: Session, name: str):
    name = name.strip()
    if not name: return False, "El nombre no puede estar vacío."
    if db.query(Office).filter(Office.name == name).first(): return False, "La oficina ya existe."
    new_office = Office(name=name)
    db.add(new_office)
    try: db.commit(); return True, "Oficina creada."
    except Exception as e: db.rollback(); return False, f"Error: {e}"

def get_all_offices(db: Session):
    return db.query(Office).order_by(Office.name).all()

def delete_office(db: Session, office_id: int):
    users_count = db.query(User).filter(User.office_id == office_id).count()
    if users_count > 0: return False, f"⚠️ No se puede eliminar: Hay {users_count} usuarios vinculados."
    office = db.query(Office).filter(Office.id == office_id).first()
    if office:
        try: db.delete(office); db.commit(); return True, "Oficina eliminada."
        except Exception as e: db.rollback(); return False, f"Error: {e}"
    return False, "Oficina no encontrada."

# --- GESTIÓN DE MENÚ ---
def create_menu_item(db: Session, week_id: int, day: str, type: str, option_number: int, description: str):
    """Crea un nuevo plato en el menú."""
    new_item = MenuItem(
        week_id=week_id,
        day=day,
        type=type,
        option_number=option_number,
        description=description
    )
    db.add(new_item)
    try:
        db.commit()
        return True, "Plato agregado exitosamente."
    except Exception as e:
        db.rollback()
        return False, f"Error al agregar plato: {e}"

def update_menu_item(db: Session, item_id: int, new_desc: str, new_opt: int):
    item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
    if not item: return False, "Ítem no encontrado."
    item.description = new_desc; item.option_number = new_opt
    try: db.commit(); return True, "Actualizado."
    except: db.rollback(); return False, "Error."

def delete_menu_item(db: Session, item_id: int):
    item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
    if not item: return False, "No encontrado."
    try: db.delete(item); db.commit(); return True, "Eliminado."
    except: db.rollback(); return False, "Error."

# --- GESTIÓN DE SEMANAS Y LOGICA DE TIEMPO ---

def create_week(db: Session, title: str, start_date, end_datetime):
    """Crea semana con fecha y hora de cierre exactas."""
    # Validación básica por si llega un string en lugar de datetime
    if isinstance(end_datetime, str): 
        pass 
    
    new_week = Week(title=title, start_date=start_date, end_date=end_datetime)
    db.add(new_week)
    db.commit()
    db.refresh(new_week)
    return new_week

def update_week_closed_days(db: Session, week_id: int, closed_days_list: list):
    """Actualiza la lista de días cerrados (feriados) de una semana."""
    week = db.query(Week).filter(Week.id == week_id).first()
    if not week:
        return False, "Semana no encontrada."
    
    try:
        # Aseguramos que sea una lista de strings y se guarda como JSON
        week.closed_days = closed_days_list
        db.commit()
        return True, "Días feriados actualizados."
    except Exception as e:
        db.rollback()
        return False, f"Error: {e}"

def check_and_auto_close_weeks(db: Session):
    """Revisa y cierra semanas vencidas (Lazy Check)."""
    now_utc3 = get_now_utc3()
    # Semanas abiertas cuya fecha de fin ya pasó
    overdue_weeks = db.query(Week).filter(Week.is_open == True, Week.end_date < now_utc3).all()
    
    count = 0
    for week in overdue_weeks:
        finalize_week_logic(db, week.id)
        count += 1
    return count

def finalize_week_logic(db: Session, week_id: int):
    """Lógica principal de cierre y llenado de huecos."""
    week = db.query(Week).filter(Week.id == week_id).first()
    if not week or not week.is_open: return None, "Error o ya cerrada."

    active_users = db.query(User).filter(User.is_active == True).all()
    existing_orders = db.query(Order).filter(Order.week_id == week_id).all()
    users_with_order_ids = {o.user_id for o in existing_orders}
    day_keys = ["monday", "tuesday", "wednesday", "thursday", "friday"]
    
    for user in active_users:
        if user.id not in users_with_order_ids:
            ghost_details = {}
            for day in day_keys:
                for db_type in ["principal", "side", "salad"]: ghost_details[f"{day}_{db_type}"] = None 
            db.add(Order(user_id=user.id, week_id=week_id, status="no_pedido", details=ghost_details))
    
    week.is_open = False 
    db.commit()
    return export_week_to_excel(db, week_id)

# --- EXPORTACIÓN ---
def export_week_to_excel(db: Session, week_id: int, office_id: int = None):
    week = db.query(Week).filter(Week.id == week_id).first()
    query = db.query(Order).options(joinedload(Order.user)).filter(Order.week_id == week_id)
    
    office_name_str = "TODAS"
    if office_id is not None:
        query = query.join(Order.user).filter(User.office_id == office_id)
        office_obj = db.query(Office).filter(Office.id == office_id).first()
        if office_obj: office_name_str = office_obj.name.replace(" ", "_").upper()

    orders = query.all()
    data = []
    day_keys = ["monday", "tuesday", "wednesday", "thursday", "friday"] 
    english_to_spanish = {"monday": "Lunes", "tuesday": "Martes", "wednesday": "Miércoles", "thursday": "Jueves", "friday": "Viernes"}
    meal_types = [("principal", "Comida"), ("side", "Acompañamiento"), ("salad", "Ensalada")]
    final_cols = ["Usuario", "Oficina"]
    for d_key in day_keys:
        d_name = english_to_spanish[d_key]
        for _, label in meal_types: final_cols.append(f"{d_name} - {label}")

    menu_item_cache = {} 
    for order in orders:
        details = order.details 
        user_office = order.user.office.name if order.user.office else "Sin Oficina"
        row = {"Usuario": order.user.full_name, "Oficina": user_office}
        for day in day_keys:
            d_es = english_to_spanish[day]
            for db_type, label in meal_types:
                val = details.get(f"{day}_{db_type}")
                desc = "NO PEDIDO"
                if isinstance(val, int):
                    if val not in menu_item_cache:
                        mi = db.query(MenuItem).filter(MenuItem.id == val).first()
                        if mi: menu_item_cache[val] = mi.description
                    desc = menu_item_cache.get(val, "Opción Desconocida")
                elif order.status == "no_pedido" or val is None: desc = "NO PEDIDO"
                else: desc = "Dato Inválido"
                row[f"{d_es} - {label}"] = desc
        data.append(row)

    df = pd.DataFrame(data, columns=final_cols).fillna("")
    safe_title = "".join([c if c.isalnum() else "_" for c in week.title])
    filename = f"{safe_title}_{office_name_str}_{datetime.now().strftime('%Y%m%d')}.xlsx"
    path = f"data/exports/{filename}"
    os.makedirs("data/exports", exist_ok=True)
    df.to_excel(path, index=False) 
    log = ExportLog(week_id=week_id, filename=path); db.add(log); db.commit()
    return path, "Exportación exitosa"

# --- HELPERS (Legacy/User Panel) ---
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
