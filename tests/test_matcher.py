"""
Unit tests for transaction matcher
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base, Order, Transaction, OrderStatus, TransactionSource
from app.services.matcher import TransactionMatcher


class TestTransactionMatcher:
    """Test transaction matching logic"""
    
    def setup_method(self):
        """Setup test database and fixtures"""
        # Create in-memory SQLite database
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        
        SessionLocal = sessionmaker(bind=self.engine)
        self.db = SessionLocal()
        
        self.matcher = TransactionMatcher(time_window_minutes=30)
    
    def teardown_method(self):
        """Cleanup"""
        self.db.close()
    
    def test_exact_amount_match(self):
        """Test matching transaction with exact amount"""
        # Create pending order
        order = Order(
            base_amount=100.0,
            expected_amount=100.25,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(minutes=10)
        )
        self.db.add(order)
        self.db.commit()
        
        # Create transaction
        transaction = Transaction(
            raw_payload="Test notification",
            source=TransactionSource.MACRODROID,
            extracted_amount=100.25,
            extracted_datetime=datetime.utcnow(),
            matched=False
        )
        self.db.add(transaction)
        self.db.commit()
        
        # Match transaction
        matched_order = self.matcher.match_transaction(
            self.db,
            transaction,
            100.25,
            datetime.utcnow()
        )
        
        assert matched_order is not None
        assert matched_order.id == order.id
        assert matched_order.status == OrderStatus.PAID
        assert transaction.matched is True
        assert transaction.order_id == order.id
    
    def test_no_match_different_amount(self):
        """Test no match when amount differs"""
        # Create pending order
        order = Order(
            base_amount=100.0,
            expected_amount=100.25,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(minutes=10)
        )
        self.db.add(order)
        self.db.commit()
        
        # Create transaction with different amount
        transaction = Transaction(
            raw_payload="Test notification",
            source=TransactionSource.MACRODROID,
            extracted_amount=100.50,  # Different amount
            extracted_datetime=datetime.utcnow(),
            matched=False
        )
        self.db.add(transaction)
        self.db.commit()
        
        # Try to match
        matched_order = self.matcher.match_transaction(
            self.db,
            transaction,
            100.50,
            datetime.utcnow()
        )
        
        assert matched_order is None
        assert transaction.matched is False
    
    def test_no_match_expired_order(self):
        """Test no match when order is expired"""
        # Create expired order
        order = Order(
            base_amount=100.0,
            expected_amount=100.25,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow() - timedelta(minutes=20),
            expires_at=datetime.utcnow() - timedelta(minutes=5)  # Expired
        )
        self.db.add(order)
        self.db.commit()
        
        # Create transaction
        transaction = Transaction(
            raw_payload="Test notification",
            source=TransactionSource.IMAP,
            extracted_amount=100.25,
            extracted_datetime=datetime.utcnow(),
            matched=False
        )
        self.db.add(transaction)
        self.db.commit()
        
        # Try to match
        matched_order = self.matcher.match_transaction(
            self.db,
            transaction,
            100.25,
            datetime.utcnow()
        )
        
        assert matched_order is None
    
    def test_no_match_paid_order(self):
        """Test no match when order is already paid"""
        # Create paid order
        order = Order(
            base_amount=100.0,
            expected_amount=100.25,
            status=OrderStatus.PAID,  # Already paid
            created_at=datetime.utcnow() - timedelta(minutes=5),
            expires_at=datetime.utcnow() + timedelta(minutes=5),
            paid_at=datetime.utcnow() - timedelta(minutes=2)
        )
        self.db.add(order)
        self.db.commit()
        
        # Create transaction
        transaction = Transaction(
            raw_payload="Test notification",
            source=TransactionSource.MACRODROID,
            extracted_amount=100.25,
            extracted_datetime=datetime.utcnow(),
            matched=False
        )
        self.db.add(transaction)
        self.db.commit()
        
        # Try to match
        matched_order = self.matcher.match_transaction(
            self.db,
            transaction,
            100.25,
            datetime.utcnow()
        )
        
        assert matched_order is None
    
    def test_duplicate_detection(self):
        """Test duplicate notification detection"""
        raw_payload = "Duplicate notification text"
        
        # Create first transaction (matched)
        transaction1 = Transaction(
            raw_payload=raw_payload,
            source=TransactionSource.MACRODROID,
            extracted_amount=100.25,
            matched=True
        )
        self.db.add(transaction1)
        self.db.commit()
        
        # Check for duplicate
        is_duplicate = self.matcher.check_duplicate_notification(
            self.db,
            raw_payload,
            TransactionSource.MACRODROID.value
        )
        
        assert is_duplicate is True
    
    def test_no_duplicate_different_source(self):
        """Test no duplicate when source differs"""
        raw_payload = "Same text different source"
        
        # Create transaction from macrodroid
        transaction = Transaction(
            raw_payload=raw_payload,
            source=TransactionSource.MACRODROID,
            extracted_amount=100.25,
            matched=True
        )
        self.db.add(transaction)
        self.db.commit()
        
        # Check for duplicate from imap (different source)
        is_duplicate = self.matcher.check_duplicate_notification(
            self.db,
            raw_payload,
            TransactionSource.IMAP.value
        )
        
        assert is_duplicate is False
    
    def test_most_recent_order_matched(self):
        """Test that most recent matching order is selected"""
        # Create two pending orders with different amounts
        order1 = Order(
            base_amount=100.0,
            expected_amount=100.25,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow() - timedelta(minutes=5),
            expires_at=datetime.utcnow() + timedelta(minutes=5)
        )
        order2 = Order(
            base_amount=100.0,
            expected_amount=100.47,  # Different amount (unique constraint)
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow() - timedelta(minutes=2),  # More recent
            expires_at=datetime.utcnow() + timedelta(minutes=8)
        )
        self.db.add_all([order1, order2])
        self.db.commit()
        
        # Create transaction matching second order
        transaction = Transaction(
            raw_payload="Test",
            source=TransactionSource.MACRODROID,
            extracted_amount=100.47,  # Matches order2
            matched=False
        )
        self.db.add(transaction)
        self.db.commit()
        
        # Match
        matched_order = self.matcher.match_transaction(
            self.db,
            transaction,
            100.47,  # Matches order2
            datetime.utcnow()
        )
        
        assert matched_order is not None
        assert matched_order.id == order2.id  # Should match the second order by amount
