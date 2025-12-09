# init_db.py (Código completo)
from database.models import Base, User # Importamos User
from database.connection import engine, SessionLocal 
from services.auth import hash_password # Necesitas esta función para hashear la contraseña

# Esta línea le dice a SQLAlchemy que cree todas las tablas que definimos en models.py
Base.metadata.create_all(engine) 

# --- NUEVA LÓGICA DE CREACIÓN DE USUARIO ADMIN ---
db = SessionLocal()
try:
    if db.query(User).filter(User.username == "admin").first() is None:

        # NOTA CLAVE: office_id=None porque la tabla offices está vacía al inicio
        admin_user = User(
            username="admin", 
            full_name="Administrador Jefe",
            password_hash=hash_password("admin_pass"), # ¡CAMBIA ESTA CONTRASEÑA!
            role="admin",
            office_id=None # Importante: No asignamos oficina al inicio
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
# ----------------------------------------------------

print("Base de datos inicializada y tablas creadas exitosamente.")