from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from database.models import Order
import json

def submit_order(db: Session, user_id: int, week_id: int, details: dict):
    try:
        # Convertir dict a JSON string para almacenar
        details_json = json.dumps(details)
        
        # Intentar insertar
        new_order = Order(
            user_id=user_id, 
            week_id=week_id, 
            details_json=details_json,
            status="success"
        )
        db.add(new_order)
        db.commit()
        return True, "Pedido guardado con éxito."
        
    except IntegrityError:
        db.rollback()
        # Si falla la constraint, significa que ya existe.
        # Aquí decidimos: ¿Actualizamos o damos error?
        # Para esta demo, actualizamos el existente:
        existing_order = db.query(Order).filter(Order.user_id == user_id, Order.week_id == week_id).first()
        if existing_order:
            existing_order.details_json = details_json
            existing_order.created_at = datetime.utcnow() # Actualizamos timestamp
            db.commit()
            return True, "Pedido actualizado correctamente."
        return False, "Error desconocido al procesar pedido."