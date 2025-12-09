# init_db.py

# Importamos la función con el nombre correcto: get_password_hash
from database.models import Base, User 
from database.connection import engine, SessionLocal 
from services.auth import get_password_hash 

# 1. Crear todas las tablas
Base.metadata.create_all(engine) 

# 2. Crear usuario Admin inicial
db = SessionLocal()
try:
    if db.query(User).filter(User.username == "admin").first() is None:
        
        # Crear la contraseña hasheada usando la función correcta
        hashed_pw = get_password_hash("admin_pass") # ⬅️ FUNCIÓN CORREGIDA
        
        # NOTA CLAVE: office_id=None porque la tabla offices está vacía al inicio
        admin_user = User(
            username="admin", 
            full_name="Administrador Jefe",
            password_hash=hashed_pw,
            role="admin",
            office_id=None 
        )
        db.add(admin_user)
        db.commit()
        print("Usuario 'admin' creado exitosamente.")
    else:
        print("Usuario 'admin' ya existe.")
except Exception as e:
    print(f"Error al intentar crear el usuario admin: {e}")
    db.rollback()
finally:
    db.close()

print("Base de datos inicializada y tablas creadas exitosamente.")