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
        """Test SCB notification format 1 with 2-digit Buddhist year"""
        text = "SCB: รับเงิน 150.25 บาท 12/01/67 14:30 คงเหลือ 5000.00 บาท"
        
        result = self.extractor.extract(text)
        
        assert result is not None
        assert result['amount'] == 150.25
        assert isinstance(result['datetime'], datetime)
        assert result['datetime'].day == 12
        assert result['datetime'].month == 1
        assert result['datetime'].year == 2024  # 67 = พ.ศ. 2567 = CE 2024
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
        """Test KBank notification with 2-digit Buddhist year"""
        text = "K-Mobile: บัญชี xxx-x-12345-x รับเงิน 200.50 บาท 15/06/67 10:15"
        
        result = self.extractor.extract(text)
        
        assert result is not None
        assert result['amount'] == 200.50
        assert result['datetime'].day == 15
        assert result['datetime'].month == 6
        assert result['datetime'].year == 2024  # 67 = พ.ศ. 2567 = CE 2024
    
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
    
    def test_buddhist_year_2digit_current(self):
        """Test 2-digit Buddhist year for current era (2026)"""
        # 69 = พ.ศ. 2569 = CE 2026
        text = "SCB: รับเงิน 100.00 บาท 17/09/69 13:24"
        
        result = self.extractor.extract(text)
        
        assert result is not None
        assert result['datetime'].year == 2026
        assert result['datetime'].month == 9
        assert result['datetime'].day == 17
    
    def test_buddhist_year_2digit_edge_cases(self):
        """Test 2-digit Buddhist year edge cases"""
        # Test year 00 = พ.ศ. 2500 = CE 1957
        text1 = "รับเงิน 100.00 บาท 01/01/00 10:00"
        result1 = self.extractor.extract(text1)
        assert result1 is not None
        assert result1['datetime'].year == 1957
        
        # Test year 99 = พ.ศ. 2599 = CE 2056
        text2 = "รับเงิน 100.00 บาท 31/12/99 23:59"
        result2 = self.extractor.extract(text2)
        assert result2 is not None
        assert result2['datetime'].year == 2056
        
        # Test year 43 = พ.ศ. 2543 = CE 2000
        text3 = "รับเงิน 100.00 บาท 01/01/43 00:00"
        result3 = self.extractor.extract(text3)
        assert result3 is not None
        assert result3['datetime'].year == 2000
    
    def test_buddhist_year_4digit_full(self):
        """Test full 4-digit Buddhist year"""
        # 2569 = CE 2026
        text = "SCB: รับเงิน 100.00 บาท 17/09/2569 13:24"
        
        result = self.extractor.extract(text)
        
        assert result is not None
        assert result['datetime'].year == 2026
        assert result['datetime'].month == 9
        assert result['datetime'].day == 17
