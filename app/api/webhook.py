"""
Webhook API endpoints for receiving bank notifications
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

from app.database import get_db
from app.auth import verify_webhook_secret
from app.models import Transaction, TransactionSource
from app.services.extractor import extractor
from app.services.matcher import matcher
from app.services.mqtt_client import mqtt_client
from app.services.notifier import notifier
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhooks"])


class BankNotificationRequest(BaseModel):
    notification_text: str = Field(..., description="Raw bank notification text")
    source: str = Field("other", description="Source: macrodroid, imap, other")
    timestamp: Optional[str] = Field(None, description="ISO timestamp of notification")


class WebhookResponse(BaseModel):
    success: bool
    message: str
    transaction_id: Optional[int] = None
    order_id: Optional[int] = None
    matched: bool = False


@router.post("/bank-notification", response_model=WebhookResponse)
async def receive_bank_notification(
    request: BankNotificationRequest,
    db: Session = Depends(get_db),
    webhook_secret: str = Depends(verify_webhook_secret)
):
    """
    Receive bank/PromptPay notification from external sources
    
    Supports:
    - MacroDroid HTTP POST from Android notification listener
    - IMAP worker forwarding parsed email notifications
    - Other integrations
    
    Protected by webhook secret authentication
    """
    try:
        # Map source string to enum
        source_map = {
            "macrodroid": TransactionSource.MACRODROID,
            "imap": TransactionSource.IMAP,
            "other": TransactionSource.OTHER
        }
        source_enum = source_map.get(request.source.lower(), TransactionSource.OTHER)
        
        # Check for duplicate notification
        if matcher.check_duplicate_notification(
            db, 
            request.notification_text, 
            source_enum.value
        ):
            logger.warning("Duplicate notification ignored")
            return WebhookResponse(
                success=False,
                message="Duplicate notification",
                matched=False
            )
        
        # Extract transaction details
        extracted = extractor.extract(request.notification_text)
        
        if not extracted:
            # Create unmatched transaction record
            transaction = Transaction(
                raw_payload=request.notification_text,
                source=source_enum,
                extracted_amount=None,
                extracted_datetime=None,
                matched=False
            )
            db.add(transaction)
            db.commit()
            db.refresh(transaction)
            
            logger.warning("Failed to extract transaction details from notification")
            return WebhookResponse(
                success=False,
                message="Could not extract transaction details",
                transaction_id=transaction.id,
                matched=False
            )
        
        # Create transaction record
        transaction = Transaction(
            raw_payload=request.notification_text,
            source=source_enum,
            extracted_amount=extracted['amount'],
            extracted_datetime=extracted['datetime'],
            extracted_reference=extracted.get('reference'),
            matched=False
        )
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
        
        logger.info(f"Created transaction {transaction.id}: amount={extracted['amount']}")
        
        # Try to match with an order
        matched_order = matcher.match_transaction(
            db,
            transaction,
            extracted['amount'],
            extracted['datetime']
        )
        
        if matched_order:
            # Dispatch notifications and MQTT trigger
            try:
                # Publish MQTT trigger
                mqtt_client.publish_payment_trigger(matched_order)
                
                # Send notifications
                notification_results = notifier.send_payment_notification(matched_order)
                logger.info(f"Notifications sent: {notification_results}")
                
            except Exception as e:
                logger.error(f"Error dispatching payment trigger: {e}")
            
            return WebhookResponse(
                success=True,
                message="Payment matched and processed",
                transaction_id=transaction.id,
                order_id=matched_order.id,
                matched=True
            )
        else:
            return WebhookResponse(
                success=True,
                message="Transaction recorded but no matching order found",
                transaction_id=transaction.id,
                matched=False
            )
    
    except Exception as e:
        logger.error(f"Webhook processing error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error: {str(e)}"
        )


@router.get("/test")
async def test_webhook(webhook_secret: str = Depends(verify_webhook_secret)):
    """
    Test webhook endpoint - verify authentication
    """
    return {"message": "Webhook authentication successful"}
