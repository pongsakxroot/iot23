"""
Unit tests for Thai bank notification extractor
"""
import pytest
from datetime import datetime
from app.services.extractor import BankNotificationExtractor


class TestBankNotificationExtractor:
    """Test bank notification text extraction"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.extractor = BankNotificationExtractor()
    
    def test_scb_notification_1(self):
        """Test SCB notification format 1"""
        text = "SCB: รับเงิน 150.25 บาท 12/01/67 14:30 คงเหลือ 5000.00 บาท"
        
        result = self.extractor.extract(text)
        
        assert result is not None
        assert result['amount'] == 150.25
        assert isinstance(result['datetime'], datetime)
        assert result['datetime'].day == 12
        assert result['datetime'].month == 1
        assert result['datetime'].hour == 14
        assert result['datetime'].minute == 30
    
    def test_scb_notification_2(self):
        """Test SCB notification format 2"""
        text = "ธ.ไทยพาณิชย์: รับเงินเข้าบัญชี 99.99 บาท 25/12/2566 23:59"
        
        result = self.extractor.extract(text)
        
        assert result is not None
        assert result['amount'] == 99.99
        assert result['datetime'].year == 2023  # 2566 BE = 2023 CE
    
    def test_kbank_notification(self):
        """Test KBank notification"""
        text = "K-Mobile: บัญชี xxx-x-12345-x รับเงิน 200.50 บาท 15/06/67 10:15"
        
        result = self.extractor.extract(text)
        
        assert result is not None
        assert result['amount'] == 200.50
        assert result['datetime'].day == 15
        assert result['datetime'].month == 6
    
    def test_ktb_notification(self):
        """Test KTB notification"""
        text = "KTB: รับเงิน 1000.01 บาท 01/01/2567 00:00:00"
        
        result = self.extractor.extract(text)
        
        assert result is not None
        assert result['amount'] == 1000.01
        assert result['datetime'].year == 2024
        assert result['datetime'].hour == 0
    
    def test_promptpay_notification(self):
        """Test PromptPay notification"""
        text = "PromptPay รับเงิน 555.55 บาท 20/03/67 16:45 อ้างอิง: REF12345"
        
        result = self.extractor.extract(text)
        
        assert result is not None
        assert result['amount'] == 555.55
        assert result['reference'] == "REF12345"
    
    def test_thai_text_with_comma(self):
        """Test amount with comma separator"""
        text = "SCB: รับเงิน 1,234.56 บาท 10/10/67 12:00"
        
        result = self.extractor.extract(text)
        
        assert result is not None
        assert result['amount'] == 1234.56
    
    def test_generic_transfer(self):
        """Test generic transfer text"""
        text = "โอนเข้า 300.75 บาท 05/05/67 18:30"
        
        result = self.extractor.extract(text)
        
        assert result is not None
        assert result['amount'] == 300.75
    
    def test_no_match(self):
        """Test text with no matching pattern"""
        text = "This is not a bank notification"
        
        result = self.extractor.extract(text)
        
        assert result is None
    
    def test_empty_text(self):
        """Test empty text"""
        result = self.extractor.extract("")
        
        assert result is None
    
    def test_reference_extraction(self):
        """Test reference number extraction"""
        text = "รับเงิน 100.00 บาท 01/01/67 10:00 อ้างอิง: ABC123"
        
        result = self.extractor.extract(text)
        
        assert result is not None
        assert result['reference'] == "ABC123"
    
    def test_multiple_patterns(self):
        """Test that first matching pattern wins"""
        texts = [
            "SCB รับเงิน 100.25 บาท 01/01/67 10:00",
            "กสิกร รับโอน 100.25 บาท 01/01/67 10:00",
            "กรุงไทย รับโอนเงิน 100.25 บาท 01/01/67 10:00"
        ]
        
        for text in texts:
            result = self.extractor.extract(text)
            assert result is not None
            assert result['amount'] == 100.25
