import pandas as pd
import json
import os
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload
from database.models import Week, Order, User, MenuItem, ExportLog, AuditLog, Office

# --- UTILIDAD: HORA UTC-3 ---
def get_now_utc3():
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
    new_item = MenuItem(week_id=week_id, day=day, type=type, option_number=option_number, description=description)
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
    if isinstance(end_datetime, str): pass 
    new_week = Week(title=title, start_date=start_date, end_date=end_datetime)
    db.add(new_week)
    db.commit()
    db.refresh(new_week)
    return new_week

def update_week_closed_days(db: Session, week_id: int, closed_days_list: list):
    week = db.query(Week).filter(Week.id == week_id).first()
    if not week: return False, "Semana no encontrada."
    try:
        week.closed_days = closed_days_list
        db.commit()
        return True, "Días feriados actualizados."
    except Exception as e:
        db.rollback()
        return False, f"Error: {e}"

def check_and_auto_close_weeks(db: Session):
    now_utc3 = get_now_utc3()
    overdue_weeks = db.query(Week).filter(Week.is_open == True, Week.end_date < now_utc3).all()
    count = 0
    for week in overdue_weeks:
        finalize_week_logic(db, week.id)
        count += 1
    return count

# --- LOGICA DE CIERRE ---
def finalize_week_logic(db: Session, week_id: int):
    week = db.query(Week).filter(Week.id == week_id).first()
    if not week or not week.is_open: return None, "Error o ya cerrada."

    active_users = db.query(User).filter(User.is_active == True).all()
    existing_orders = db.query(Order).filter(Order.week_id == week_id).all()
    users_with_order_ids = {o.user_id for o in existing_orders}
    day_keys = ["monday", "tuesday", "wednesday", "thursday", "friday"]
    
    for user in active_users:
        if user.id not in users_with_order_ids:
            ghost_details = {day: {"tipo": "nada"} for day in day_keys}
            db.add(Order(user_id=user.id, week_id=week_id, status="no_pedido", details=ghost_details))
    
    week.is_open = False 
    db.commit()
    return export_week_to_excel(db, week_id)

# --- EXPORTACIÓN CORREGIDA ---
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
    
    final_cols = ["Usuario", "Oficina"]
    for d_key in day_keys:
        d_name = english_to_spanish[d_key]
        final_cols.append(d_name)

    menu_item_cache = {}
    
    def get_desc(item_id):
        if item_id is None: return None
        try: val_id = int(item_id)
        except: return "ID Inválido"

        if val_id not in menu_item_cache:
            mi = db.query(MenuItem).filter(MenuItem.id == val_id).first()
            if mi: menu_item_cache[val_id] = mi.description
            else: menu_item_cache[val_id] = None
        return menu_item_cache.get(val_id)

    closed_days_list = week.closed_days if week.closed_days else []

    for order in orders:
        details = order.details
        if isinstance(details, str):
            try: details = json.loads(details)
            except: details = {}
            
        user_office = order.user.office.name if order.user.office else "Sin Oficina"
        row = {"Usuario": order.user.full_name, "Oficina": user_office}
        
        for day in day_keys:
            d_es = english_to_spanish[day]
            
            if day in closed_days_list:
                row[d_es] = "FERIADO"
                continue
                
            day_order = details.get(day, {})
            tipo = day_order.get("tipo", "nada")
            
            texto_pedido = "NO PEDIDO"
            
            if order.status == "no_pedido" or tipo == "nada":
                texto_pedido = "NO PEDIDO"
            elif tipo == "completo":
                comp_id = day_order.get("plato_id")
                desc = get_desc(comp_id)
                if desc: texto_pedido = desc 
            elif tipo == "combinado":
                prot_id = day_order.get("proteina_id")
                guar_id = day_order.get("guarnicion_id")
                
                p_desc = get_desc(prot_id)
                g_desc = get_desc(guar_id)
                
                partes = []
                if p_desc: partes.append(p_desc)
                if g_desc: partes.append(g_desc)
                
                if partes:
                    texto_pedido = " + ".join(partes)
            
            row[d_es] = texto_pedido
            
        data.append(row)

    df = pd.DataFrame(data, columns=final_cols).fillna("")
    safe_title = "".join([c if c.isalnum() else "_" for c in week.title])
    filename = f"{safe_title}_{office_name_str}_{datetime.now().strftime('%Y%m%d')}.xlsx"
    path = f"data/exports/{filename}"
    os.makedirs("data/exports", exist_ok=True)
    df.to_excel(path, index=False) 
    log = ExportLog(week_id=week_id, filename=path); db.add(log); db.commit()
    return path, "Exportación exitosa"

def reopen_week_logic(db: Session, week_id: int):
    """Cambia el estado de una semana de Cerrada a Abierta."""
    week = db.query(Week).filter(Week.id == week_id).first()
    if not week:
        return False, "Semana no encontrada."
    if week.is_open:
        return False, "La semana ya está abierta."
    
    try:
        week.is_open = True
        db.commit()
        return True, "Semana reabierta exitosamente."
    except Exception as e:
        db.rollback()
        return False, f"Error al reabrir: {e}"

# --- FUNCIÓN ACTUALIZADA: CLONAR DESDE UNA SEMANA ESPECÍFICA ---
def clone_menu_from_week(db: Session, source_week_id: int, target_week_id: int):
    """Copia todos los platos de una semana elegida a la semana actual."""
    if source_week_id == target_week_id:
        return False, "⚠️ La semana de origen y destino no pueden ser la misma."

    source_week = db.query(Week).filter(Week.id == source_week_id).first()
    if not source_week:
        return False, "Semana de origen no encontrada."

    # Verifica que la semana origen tenga platos
    source_items = db.query(MenuItem).filter(MenuItem.week_id == source_week_id).all()
    if not source_items:
        return False, f"La semana '{source_week.title}' no tiene platos cargados para copiar."

    # Verifica que la semana actual esté VACÍA para evitar duplicados
    existing_items = db.query(MenuItem).filter(MenuItem.week_id == target_week_id).count()
    if existing_items > 0:
        return False, "⚠️ La semana actual ya tiene platos. Bórralos primero antes de clonar."

    # Realiza la copia
    try:
        for item in source_items:
            new_item = MenuItem(
                week_id=target_week_id,
                day=item.day,
                type=item.type,
                option_number=item.option_number,
                description=item.description
            )
            db.add(new_item)
        db.commit()
        return True, f"✅ Se copiaron {len(source_items)} platos desde '{source_week.title}' con éxito."
    except Exception as e:
        db.rollback()
        return False, f"Error al clonar: {e}"