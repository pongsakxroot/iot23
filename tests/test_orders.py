"""
Unit tests for order service
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base, Order, OrderStatus
from app.services.order_service import OrderService


class TestOrderService:
    """Test order service functionality"""
    
    def setup_method(self):
        """Setup test database and fixtures"""
        # Create in-memory SQLite database
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        
        SessionLocal = sessionmaker(bind=self.engine)
        self.db = SessionLocal()
        
        self.service = OrderService()
    
    def teardown_method(self):
        """Cleanup"""
        self.db.close()
    
    def test_create_order_basic(self):
        """Test creating a basic order"""
        order = self.service.create_order(self.db, base_amount=100.0)
        
        assert order.id is not None
        assert order.base_amount == 100.0
        assert 100.01 <= order.expected_amount <= 100.99
        assert order.status == OrderStatus.PENDING
        assert order.expires_at > datetime.utcnow()
    
    def test_unique_amounts(self):
        """Test that multiple orders get unique amounts"""
        base_amount = 100.0
        orders = []
        
        # Create 10 orders
        for _ in range(10):
            order = self.service.create_order(self.db, base_amount=base_amount)
            orders.append(order)
        
        # Check all amounts are unique
        amounts = [order.expected_amount for order in orders]
        assert len(amounts) == len(set(amounts))
        
        # Check all amounts are in valid range
        for amount in amounts:
            assert 100.01 <= amount <= 100.99
    
    def test_collision_avoidance(self):
        """Test collision avoidance with existing orders"""
        base_amount = 100.0
        
        # Create first order
        order1 = self.service.create_order(self.db, base_amount=base_amount)
        amount1 = order1.expected_amount
        
        # Create second order - should get different amount
        order2 = self.service.create_order(self.db, base_amount=base_amount)
        amount2 = order2.expected_amount
        
        assert amount1 != amount2
    
    def test_amount_cleaning(self):
        """Test that base amount is cleaned (no cents)"""
        # Pass amount with cents
        order = self.service.create_order(self.db, base_amount=100.99)
        
        # Should be cleaned to 100.00
        assert order.base_amount == 100.0
        assert 100.01 <= order.expected_amount <= 100.99
    
    def test_order_ttl(self):
        """Test order expiration time"""
        order = self.service.create_order(self.db, base_amount=100.0)
        
        expected_expiry = order.created_at + timedelta(minutes=self.service.ttl_minutes)
        
        # Allow 1 second tolerance
        assert abs((order.expires_at - expected_expiry).total_seconds()) < 1
    
    def test_expire_old_orders(self):
        """Test expiring old orders"""
        # Create expired order
        order = Order(
            base_amount=100.0,
            expected_amount=100.25,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow() - timedelta(minutes=20),
            expires_at=datetime.utcnow() - timedelta(minutes=5)
        )
        self.db.add(order)
        self.db.commit()
        
        # Expire old orders
        count = self.service.expire_old_orders(self.db)
        
        assert count == 1
        
        self.db.refresh(order)
        assert order.status == OrderStatus.EXPIRED
    
    def test_no_expiry_for_valid_orders(self):
        """Test that valid orders are not expired"""
        order = self.service.create_order(self.db, base_amount=100.0)
        
        # Try to expire
        count = self.service.expire_old_orders(self.db)
        
        assert count == 0
        
        self.db.refresh(order)
        assert order.status == OrderStatus.PENDING
    
    def test_get_order(self):
        """Test getting order by ID"""
        created_order = self.service.create_order(self.db, base_amount=100.0)
        
        fetched_order = self.service.get_order(self.db, created_order.id)
        
        assert fetched_order is not None
        assert fetched_order.id == created_order.id
        assert fetched_order.expected_amount == created_order.expected_amount
    
    def test_get_nonexistent_order(self):
        """Test getting non-existent order"""
        order = self.service.get_order(self.db, 99999)
        
        assert order is None
    
    def test_cancel_order(self):
        """Test cancelling an order"""
        order = self.service.create_order(self.db, base_amount=100.0)
        
        cancelled = self.service.cancel_order(self.db, order.id)
        
        assert cancelled is not None
        assert cancelled.status == OrderStatus.CANCELLED
    
    def test_cannot_cancel_paid_order(self):
        """Test that paid orders cannot be cancelled"""
        order = Order(
            base_amount=100.0,
            expected_amount=100.25,
            status=OrderStatus.PAID,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(minutes=10),
            paid_at=datetime.utcnow()
        )
        self.db.add(order)
        self.db.commit()
        
        result = self.service.cancel_order(self.db, order.id)
        
        assert result is None
        
        self.db.refresh(order)
        assert order.status == OrderStatus.PAID
    
    def test_customer_ref_and_metadata(self):
        """Test creating order with customer reference and metadata"""
        order = self.service.create_order(
            self.db,
            base_amount=100.0,
            customer_ref="CUST-12345",
            metadata='{"product": "coffee"}'
        )
        
        assert order.customer_ref == "CUST-12345"
        assert order.metadata == '{"product": "coffee"}'
    
    def test_max_unique_amounts(self):
        """Test behavior when approaching maximum unique amounts"""
        base_amount = 100.0
        
        # Create 50 orders (should work fine)
        orders = []
        for _ in range(50):
            order = self.service.create_order(self.db, base_amount=base_amount)
            orders.append(order)
        
        # All should have unique amounts
        amounts = [o.expected_amount for o in orders]
        assert len(amounts) == len(set(amounts))
        
        # All should be in valid range
        for amount in amounts:
            cents = int(round((amount - base_amount) * 100))
            assert 1 <= cents <= 99
