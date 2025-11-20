# services/logic.py
from database.models import Week, Order, MenuItem

def delete_week_data(db, week_id):
    """Elimina una semana y todos sus datos asociados (pedidos, menú)."""
    week = db.query(Week).filter(Week.id == week_id).first()
    
    if week:
        # 1. Eliminar items del menú (aunque el cascade debería hacerlo, aseguramos)
        db.query(MenuItem).filter(MenuItem.week_id == week_id).delete()
        
        # 2. Eliminar pedidos asociados
        db.query(Order).filter(Order.week_id == week_id).delete()
        
        # 3. Eliminar logs de exportación si existen
        # db.query(ExportLog).filter(ExportLog.week_id == week_id).delete() # Descomenta si usas logs
        
        # 4. Finalmente eliminar la semana
        db.delete(week)
        db.commit()
        return True
    return False