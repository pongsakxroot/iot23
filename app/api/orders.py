"""
Order management API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

from app.database import get_db
from app.auth import verify_api_key
from app.services.order_service import order_service
from app.models import OrderStatus

router = APIRouter(prefix="/orders", tags=["orders"])


class CreateOrderRequest(BaseModel):
    base_amount: float = Field(..., gt=0, description="Base amount in THB")
    customer_ref: Optional[str] = Field(None, max_length=255, description="Customer reference")
    metadata: Optional[str] = Field(None, description="Optional JSON metadata")


class OrderResponse(BaseModel):
    id: int
    base_amount: float
    expected_amount: float
    status: str
    created_at: datetime
    expires_at: datetime
    paid_at: Optional[datetime]
    customer_ref: Optional[str]
    metadata: Optional[str]
    
    class Config:
        from_attributes = True


@router.post("/", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    request: CreateOrderRequest,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    Create a new order with unique random cent amount
    
    Protected by API key authentication
    """
    try:
        order = order_service.create_order(
            db=db,
            base_amount=request.base_amount,
            customer_ref=request.customer_ref,
            metadata=request.metadata
        )
        return order
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    Get order by ID
    
    Protected by API key authentication
    """
    order = order_service.get_order(db, order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {order_id} not found"
        )
    return order


@router.post("/{order_id}/cancel", response_model=OrderResponse)
async def cancel_order(
    order_id: int,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    Cancel a pending order
    
    Protected by API key authentication
    """
    order = order_service.cancel_order(db, order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {order_id} not found or cannot be cancelled"
        )
    return order


@router.post("/expire-old", status_code=status.HTTP_200_OK)
async def expire_old_orders(
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    Manually trigger expiration of old orders
    
    Protected by API key authentication
    """
    count = order_service.expire_old_orders(db)
    return {"expired_count": count}
