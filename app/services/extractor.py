"""
Thai bank notification text extraction service
Supports: SCB, KBank, KTB, PromptPay notifications
"""
import re
from typing import Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class BankNotificationExtractor:
    """Extract transaction details from Thai bank notification strings"""
    
    # SCB (Siam Commercial Bank) patterns
    SCB_PATTERNS = [
        # Format: "SCB: รับเงิน 100.25 บาท 12/01/67 14:30 คงเหลือ 5000.00 บาท"
        r'(?:SCB|ธ\.ไทยพาณิชย์).*?รับเงิน\s*([0-9,]+\.?\d{0,2})\s*บาท.*?(\d{1,2}/\d{1,2}/\d{2,4})\s*(\d{1,2}:\d{2})',
        # Format: "รับเงินเข้าบัญชี 100.50 บาท"
        r'รับเงิน(?:เข้าบัญชี)?\s*([0-9,]+\.?\d{0,2})\s*บาท.*?(\d{1,2}/\d{1,2}/\d{2,4})\s*(\d{1,2}:\d{2})',
    ]
    
    # KBank (Kasikorn Bank) patterns
    KBANK_PATTERNS = [
        # Format: "K-Mobile: บัญชี xxx-x-xxxxx-x รับเงิน 100.75 บาท 12/01/67 14:30"
        r'(?:K-?Mobile|กสิกร).*?รับเงิน\s*([0-9,]+\.?\d{0,2})\s*บาท.*?(\d{1,2}/\d{1,2}/\d{2,4})\s*(\d{1,2}:\d{2})',
        # Format: "บัญชี xxx รับโอน 100.25 บาท"
        r'รับโอน\s*([0-9,]+\.?\d{0,2})\s*บาท.*?(\d{1,2}/\d{1,2}/\d{2,4})\s*(\d{1,2}:\d{2})',
    ]
    
    # KTB (Krung Thai Bank) patterns
    KTB_PATTERNS = [
        # Format: "KTB: รับเงิน 100.99 บาท 12/01/2567 14:30:00"
        r'(?:KTB|กรุงไทย).*?รับเงิน\s*([0-9,]+\.?\d{0,2})\s*บาท.*?(\d{1,2}/\d{1,2}/\d{2,4})\s*(\d{1,2}:\d{2}(?::\d{2})?)',
        r'รับโอนเงิน\s*([0-9,]+\.?\d{0,2})\s*บาท.*?(\d{1,2}/\d{1,2}/\d{2,4})\s*(\d{1,2}:\d{2}(?::\d{2})?)',
    ]
    
    # PromptPay generic patterns
    PROMPTPAY_PATTERNS = [
        # Format: "PromptPay รับเงิน 100.00 บาท 12/01/67 14:30 อ้างอิง: REF12345"
        r'(?:PromptPay|พร้อมเพย์).*?รับเงิน\s*([0-9,]+\.?\d{0,2})\s*บาท.*?(\d{1,2}/\d{1,2}/\d{2,4})\s*(\d{1,2}:\d{2})',
        # Generic transfer received
        r'โอนเข้า\s*([0-9,]+\.?\d{0,2})\s*บาท.*?(\d{1,2}/\d{1,2}/\d{2,4})\s*(\d{1,2}:\d{2})',
    ]
    
    # Reference number pattern (optional)
    REFERENCE_PATTERN = r'(?:อ้างอิง|Ref|Reference)[:\s]*([A-Z0-9]+)'
    
    def __init__(self):
        self.all_patterns = (
            self.SCB_PATTERNS + 
            self.KBANK_PATTERNS + 
            self.KTB_PATTERNS + 
            self.PROMPTPAY_PATTERNS
        )
    
    def extract(self, notification_text: str) -> Optional[Dict[str, Any]]:
        """
        Extract transaction details from notification text
        
        Returns:
            Dict with keys: amount, datetime, reference (optional), raw_text
            None if extraction fails
        """
        if not notification_text:
            return None
        
        logger.debug(f"Extracting from: {notification_text[:100]}...")
        
        # Try all patterns
        for pattern in self.all_patterns:
            match = re.search(pattern, notification_text, re.IGNORECASE)
            if match:
                try:
                    amount_str = match.group(1).replace(',', '')
                    amount = float(amount_str)
                    
                    date_str = match.group(2)
                    time_str = match.group(3)
                    
                    # Parse datetime
                    extracted_datetime = self._parse_datetime(date_str, time_str)
                    
                    # Try to extract reference
                    reference = self._extract_reference(notification_text)
                    
                    result = {
                        'amount': amount,
                        'datetime': extracted_datetime,
                        'reference': reference,
                        'raw_text': notification_text
                    }
                    
                    logger.info(f"Extracted: amount={amount}, datetime={extracted_datetime}")
                    return result
                    
                except (ValueError, IndexError) as e:
                    logger.warning(f"Failed to parse matched data: {e}")
                    continue
        
        logger.warning(f"No pattern matched for notification: {notification_text[:100]}")
        return None
    
    def _parse_datetime(self, date_str: str, time_str: str) -> datetime:
        """
        Parse Thai date/time format
        Supports: DD/MM/YY, DD/MM/YYYY
        Buddhist year (25xx) is converted to CE year
        """
        # Parse date parts
        day, month, year = map(int, date_str.split('/'))
        
        # Convert Buddhist year to CE if needed
        if year > 2400:
            year = year - 543
        elif year < 100:
            # Two digit year
            year = 2000 + year if year < 70 else 1900 + year
        
        # Parse time
        time_parts = time_str.split(':')
        hour = int(time_parts[0])
        minute = int(time_parts[1])
        second = int(time_parts[2]) if len(time_parts) > 2 else 0
        
        return datetime(year, month, day, hour, minute, second)
    
    def _extract_reference(self, text: str) -> Optional[str]:
        """Extract reference number if present"""
        match = re.search(self.REFERENCE_PATTERN, text, re.IGNORECASE)
        if match:
            return match.group(1)
        return None


# Singleton instance
extractor = BankNotificationExtractor()
