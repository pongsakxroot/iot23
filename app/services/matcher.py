"""
Transaction matching service - matches inbound payments to orders
"""
from sqlalchemy.orm import Session
from app.models import Order, Transaction, OrderStatus
from datetime import datetime, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class TransactionMatcher:
    """Match incoming transactions to pending orders"""
    
    def __init__(self, time_window_minutes: int = 30):
        """
        Args:
            time_window_minutes: Max time difference between transaction and order creation
        """
        self.time_window_minutes = time_window_minutes
    
    def match_transaction(
        self, 
        db: Session, 
        transaction: Transaction,
        extracted_amount: float,
        extracted_datetime: Optional[datetime] = None
    ) -> Optional[Order]:
        """
        Match a transaction to a pending order
        
        Args:
            db: Database session
            transaction: The transaction record
            extracted_amount: Extracted payment amount
            extracted_datetime: When the payment was made (optional)
        
        Returns:
            Matched Order if found, None otherwise
        """
        logger.info(f"Attempting to match transaction amount: {extracted_amount}")
        
        # Check if this transaction was already matched
        if transaction.matched:
            logger.warning(f"Transaction {transaction.id} already matched")
            return None
        
        # Find exact amount match in pending orders
        query = db.query(Order).filter(
            Order.expected_amount == extracted_amount,
            Order.status == OrderStatus.PENDING,
            Order.expires_at > datetime.utcnow()
        )
        
        # Apply time window filter if datetime is provided
        if extracted_datetime:
            earliest_time = extracted_datetime - timedelta(minutes=self.time_window_minutes)
            query = query.filter(Order.created_at >= earliest_time)
        
        # Get the most recent matching order
        order = query.order_by(Order.created_at.desc()).first()
        
        if order:
            logger.info(f"Match found! Order ID: {order.id}, Amount: {order.expected_amount}")
            
            # Update order status
            order.status = OrderStatus.PAID
            order.paid_at = extracted_datetime or datetime.utcnow()
            
            # Link transaction to order
            transaction.order_id = order.id
            transaction.matched = True
            
            db.commit()
            db.refresh(order)
            db.refresh(transaction)
            
            logger.info(f"Order {order.id} marked as PAID")
            return order
        else:
            logger.warning(f"No matching order found for amount: {extracted_amount}")
            return None
    
    def check_duplicate_notification(
        self, 
        db: Session, 
        raw_payload: str, 
        source: str
    ) -> bool:
        """
        Check if this exact notification was already processed
        
        Args:
            db: Database session
            raw_payload: Raw notification text
            source: Source of notification
        
        Returns:
            True if duplicate exists, False otherwise
        """
        duplicate = db.query(Transaction).filter(
            Transaction.raw_payload == raw_payload,
            Transaction.source == source,
            Transaction.matched == True
        ).first()
        
        if duplicate:
            logger.warning(f"Duplicate notification detected from {source}")
            return True
        
        return False


# Singleton instance
matcher = TransactionMatcher()
