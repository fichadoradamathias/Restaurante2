import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON, UniqueConstraint, Date
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

# --- USUARIOS ---
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="user") # 'admin' o 'user'
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relaciones
    orders = relationship("Order", back_populates="user")

# --- SEMANAS ---
class Week(Base):
    __tablename__ = "weeks"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False, unique=True) # Ej: "Semana 3 Diciembre"
    start_date = Column(Date, nullable=False) # Usamos Date para rangos puros
    end_date = Column(Date, nullable=False)
    is_open = Column(Boolean, default=True)      # True = Acepta pedidos
    is_finalized = Column(Boolean, default=False) # True = Ya se procesó y cerró administrativamente
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Relaciones
    menu_items = relationship("MenuItem", back_populates="week", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="week")
    export_logs = relationship("ExportLog", back_populates="week")

# --- ITEMS DEL MENÚ ---
class MenuItem(Base):
    __tablename__ = "menu_items"
    id = Column(Integer, primary_key=True, index=True)
    week_id = Column(Integer, ForeignKey("weeks.id"), nullable=False)
    day = Column(String, nullable=False)   # Lunes, Martes...
    type = Column(String, nullable=False)  # main, salad, side
    option_number = Column(Integer, default=1) # Para ordenar (Opción 1, 2...)
    description = Column(String, nullable=False)
    
    week = relationship("Week", back_populates="menu_items")

# --- PEDIDOS (Con JSON para flexibilidad) ---
class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    week_id = Column(Integer, ForeignKey("weeks.id"), nullable=False)
    status = Column(String, default="success") # success, failed, no_pedido
    
    # Aquí guardamos todo el pedido: {"Lunes_main": "Carne", "Lunes_salad": "Mixta", ...}
    details = Column(JSON, nullable=False) 
    
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Constraint para evitar que un usuario tenga 2 pedidos en la misma semana
    __table_args__ = (
        UniqueConstraint('user_id', 'week_id', name='unique_order_per_week'),
    )

    week = relationship("Week", back_populates="orders")
    user = relationship("User", back_populates="orders")

# --- LOGS DE AUDITORÍA ---
class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    actor_id = Column(String, nullable=True)        # Guardamos el Username (String) para que persista si se borra el user ID
    target_username = Column(String, nullable=True) # A quién afectó
    action = Column(String, nullable=False)         # LOGIN, UPDATE_ORDER, CREATE_WEEK
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    old_value = Column(Text, nullable=True)         # Valor anterior (para trazabilidad)
    new_value = Column(Text, nullable=True)         # Valor nuevo
    details = Column(Text, nullable=True)           # Descripción extra

# --- LOGS DE EXPORTACIÓN ---
class ExportLog(Base):
    __tablename__ = "export_logs"
    id = Column(Integer, primary_key=True, index=True)
    week_id = Column(Integer, ForeignKey("weeks.id"))
    exported_at = Column(DateTime, default=datetime.datetime.utcnow)
    filename = Column(String, nullable=False)
    created_by = Column(String, nullable=True) # Quién descargó el archivo

    week = relationship("Week", back_populates="export_logs")