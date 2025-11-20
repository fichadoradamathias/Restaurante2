import pandas as pd
import json
import os
from datetime import datetime
from sqlalchemy.orm import Session
from database.models import Week, Order, User, MenuItem, ExportLog

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
            # Llenamos con un JSON vacío o explícito
            ghost_order = Order(
                user_id=user.id,
                week_id=week_id,
                status="no_pedido",
                details_json=json.dumps({day: "NO PEDIDO" for day in ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]})
            )
            db.add(ghost_order)
    
    week.is_open = False # Cerrar semana
    db.commit()

    # 3. Generar Excel
    return export_week_to_excel(db, week_id)

def export_week_to_excel(db: Session, week_id: int):
    week = db.query(Week).filter(Week.id == week_id).first()
    orders = db.query(Order).filter(Order.week_id == week_id).all()
    
    data = []
    days = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]

    for order in orders:
        details = json.loads(order.details_json)
        row = {
            "Nombre Completo": order.user.full_name,
            "Status": order.status,
            "Fecha Pedido": order.created_at.strftime("%Y-%m-%d %H:%M") if order.status == 'success' else ""
        }
        for day in days:
            # Extraer solo el nombre de la comida o "NO PEDIDO"
            val = details.get(day, "NO PEDIDO")
            if isinstance(val, dict): # Si guardamos objeto completo
                val = f"{val.get('opcion', '')} {val.get('extra', '')}"
            row[day] = val
        data.append(row)

    df = pd.DataFrame(data)
    
    # Nombre archivo seguro
    safe_title = "".join([c if c.isalnum() else "_" for c in week.title])
    filename = f"{safe_title}_{datetime.now().strftime('%Y%m%d')}.xlsx"
    path = f"data/exports/{filename}"
    
    os.makedirs("data/exports", exist_ok=True)
    df.to_excel(path, index=False)
    
    # Log
    log = ExportLog(week_id=week_id, filename=path)
    db.add(log)
    db.commit()
    
    return path, "Exportación exitosa"