"""
Order service - handles order creation with unique random cent amounts
"""
from sqlalchemy.orm import Session
from app.models import Order, OrderStatus
from app.config import settings
from datetime import datetime, timedelta
from typing import Optional
import random
import logging

logger = logging.getLogger(__name__)


class OrderService:
    """Service for managing orders with unique random cent amounts"""
    
    def __init__(self):
        self.ttl_minutes = settings.order_ttl_minutes
        self.base_amount_min = settings.base_amount_min
        self.base_amount_max = settings.base_amount_max
    
    def create_order(
        self, 
        db: Session, 
        base_amount: float,
        customer_ref: Optional[str] = None,
        metadata: Optional[str] = None
    ) -> Order:
        """
        Create a new order with unique random cent amount
        
        Args:
            db: Database session
            base_amount: Base amount (e.g., 100.00)
            customer_ref: Optional customer reference
            metadata: Optional JSON metadata string
        
        Returns:
            Created Order with unique expected_amount
        
        Raises:
            ValueError: If base amount is out of range or unique amount cannot be generated
        """
        # Validate base amount
        if base_amount < self.base_amount_min or base_amount > self.base_amount_max:
            raise ValueError(
                f"Base amount must be between {self.base_amount_min} and {self.base_amount_max}"
            )
        
        # Ensure base amount has no cents or clean it
        base_amount = float(int(base_amount))
        
        # Generate unique random cent amount
        expected_amount = self._generate_unique_amount(db, base_amount)
        
        # Calculate expiry
        created_at = datetime.utcnow()
        expires_at = created_at + timedelta(minutes=self.ttl_minutes)
        
        # Create order
        order = Order(
            base_amount=base_amount,
            expected_amount=expected_amount,
            status=OrderStatus.PENDING,
            created_at=created_at,
            expires_at=expires_at,
            customer_ref=customer_ref,
            metadata=metadata
        )
        
        db.add(order)
        db.commit()
        db.refresh(order)
        
        logger.info(
            f"Created order {order.id}: base={base_amount}, "
            f"expected={expected_amount}, expires_at={expires_at}"
        )
        
        return order
    
    def _generate_unique_amount(self, db: Session, base_amount: float) -> float:
        """
        Generate unique amount by adding random cents (.01 to .99)
        Ensures no collision with active unpaid orders
        
        Args:
            db: Database session
            base_amount: Base amount (integer part)
        
        Returns:
            Unique amount with random cents
        
        Raises:
            ValueError: If cannot generate unique amount after max attempts
        """
        max_attempts = 100
        
        # Get all active unpaid orders with this base amount
        active_orders = db.query(Order).filter(
            Order.base_amount == base_amount,
            Order.status == OrderStatus.PENDING,
            Order.expires_at > datetime.utcnow()
        ).all()
        
        # Create set of used cents
        used_cents = set()
        for order in active_orders:
            cents = int(round((order.expected_amount - base_amount) * 100))
            used_cents.add(cents)
        
        logger.debug(f"Base {base_amount}: {len(used_cents)} active amounts in use")
        
        # Generate random cents from 1 to 99 (avoiding .00)
        available_cents = [c for c in range(1, 100) if c not in used_cents]
        
        if not available_cents:
            # All cents are taken, clean up expired orders and retry once
            self.expire_old_orders(db)
            active_orders = db.query(Order).filter(
                Order.base_amount == base_amount,
                Order.status == OrderStatus.PENDING,
                Order.expires_at > datetime.utcnow()
            ).all()
            
            used_cents = set()
            for order in active_orders:
                cents = int(round((order.expected_amount - base_amount) * 100))
                used_cents.add(cents)
            
            available_cents = [c for c in range(1, 100) if c not in used_cents]
            
            if not available_cents:
                raise ValueError(
                    f"Cannot generate unique amount for base {base_amount}. "
                    f"All 99 possible amounts are in use."
                )
        
        # Pick random cents from available
        cents = random.choice(available_cents)
        expected_amount = base_amount + (cents / 100.0)
        
        logger.debug(f"Generated unique amount: {expected_amount} (cents: {cents})")
        
        return round(expected_amount, 2)
    
    def expire_old_orders(self, db: Session) -> int:
        """
        Expire orders past their TTL
        
        Returns:
            Number of orders expired
        """
        now = datetime.utcnow()
        
        expired_orders = db.query(Order).filter(
            Order.status == OrderStatus.PENDING,
            Order.expires_at <= now
        ).all()
        
        count = 0
        for order in expired_orders:
            order.status = OrderStatus.EXPIRED
            count += 1
        
        if count > 0:
            db.commit()
            logger.info(f"Expired {count} old orders")
        
        return count
    
    def get_order(self, db: Session, order_id: int) -> Optional[Order]:
        """Get order by ID"""
        return db.query(Order).filter(Order.id == order_id).first()
    
    def cancel_order(self, db: Session, order_id: int) -> Optional[Order]:
        """Cancel an order"""
        order = self.get_order(db, order_id)
        if order and order.status == OrderStatus.PENDING:
            order.status = OrderStatus.CANCELLED
            db.commit()
            db.refresh(order)
            logger.info(f"Cancelled order {order_id}")
            return order
        return None


# Singleton instance
order_service = OrderService()
