from database.models import Base
# Importamos la configuración de conexión que está en database/connection.py
from database.connection import engine 

# Esta línea le dice a SQLAlchemy que cree todas las tablas que definimos en models.py
Base.metadata.create_all(engine) 

print("Base de datos inicializada y tablas creadas exitosamente.")