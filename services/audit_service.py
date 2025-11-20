from sqlalchemy.orm import Session
from database.models import AuditLog

def create_log_entry(db: Session, actor_id: int, target_username: str, action: str, old_value: str = None, new_value: str = None, details: str = None):
    """Crea una nueva entrada en el log de auditoría con detalles del cambio."""
    
    new_log = AuditLog(
        actor_id=actor_id,
        target_username=target_username,
        action=action,
        old_value=old_value,
        new_value=new_value,
        details=details
    )
    
    db.add(new_log)
    db.commit()
    return True