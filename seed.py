from database.connection import init_db, SessionLocal
from database.models import User
from services.auth import get_password_hash

def create_initial_data():
    init_db() # Crea las tablas si no existen
    db = SessionLocal()

    # Verificar si ya existe admin
    if db.query(User).filter(User.username == "admin").first():
        print("El usuario admin ya existe.")
        return

    print("Creando usuario admin...")
    admin_user = User(
        username="admin",
        full_name="Administrador Sistema",
        password_hash=get_password_hash("admin123"), # CAMBIA ESTO LUEGO
        role="admin",
        is_active=True
    )
    
    # Crear un usuario de prueba
    test_user = User(
        username="empleado",
        full_name="Juan Perez",
        password_hash=get_password_hash("1234"),
        role="user",
        is_active=True
    )

    db.add(admin_user)
    db.add(test_user)
    db.commit()
    print("¡Datos iniciales creados! Usuario: 'admin', Pass: 'admin123'")
    db.close()

if __name__ == "__main__":
    create_initial_data()