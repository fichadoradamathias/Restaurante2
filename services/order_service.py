from sqlalchemy.orm import Session
from database.models import Order
from datetime import datetime

def submit_order(db: Session, user_id: int, week_id: int, details: dict):
    try:
        # 1. Buscamos si el usuario ya tiene un pedido para esta semana
        existing_order = db.query(Order).filter(
            Order.user_id == user_id, 
            Order.week_id == week_id
        ).first()

        if existing_order:
            # 2. Si existe, simplemente actualizamos el diccionario directamente
            existing_order.details = details
            existing_order.status = "actualizado"
            existing_order.created_at = datetime.utcnow() # Actualizamos la fecha
            msg = "Pedido actualizado correctamente."
        else:
            # 3. Si no existe, creamos uno nuevo pasándole el diccionario (details)
            new_order = Order(
                user_id=user_id, 
                week_id=week_id, 
                details=details, # SQLAlchemy lo convierte a JSON automáticamente
                status="success"
            )
            db.add(new_order)
            msg = "Pedido guardado con éxito."
            
        # Guardamos los cambios
        db.commit()
        return True, msg
        
    except Exception as e:
        # Si algo raro pasa (ej. se cae la conexión a Neon), deshacemos los cambios
        db.rollback()
        return False, f"Error al procesar el pedido: {e}"