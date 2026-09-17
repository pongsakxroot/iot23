"""
SQLAlchemy database models for orders and transactions
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, Enum
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
import enum

Base = declarative_base()


class OrderStatus(str, enum.Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class TransactionSource(str, enum.Enum):
    MACRODROID = "macrodroid"
    IMAP = "imap"
    OTHER = "other"


class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    base_amount = Column(Float, nullable=False)
    expected_amount = Column(Float, nullable=False, unique=True, index=True)
    status = Column(Enum(OrderStatus), default=OrderStatus.PENDING, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    paid_at = Column(DateTime, nullable=True)
    
    customer_ref = Column(String(255), nullable=True)
    metadata = Column(Text, nullable=True)
    
    # Relationships
    transactions = relationship("Transaction", back_populates="order")
    
    def __repr__(self):
        return f"<Order(id={self.id}, expected_amount={self.expected_amount}, status={self.status})>"


class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, index=True)
    
    raw_payload = Column(Text, nullable=False)
    source = Column(Enum(TransactionSource), nullable=False)
    
    extracted_amount = Column(Float, nullable=True)
    extracted_datetime = Column(DateTime, nullable=True)
    extracted_reference = Column(String(255), nullable=True)
    
    matched = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    order = relationship("Order", back_populates="transactions")
    
    def __repr__(self):
        return f"<Transaction(id={self.id}, amount={self.extracted_amount}, matched={self.matched})>"
