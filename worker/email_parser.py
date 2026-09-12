"""
Email parser for Thai bank notification emails
"""
import email
from email.message import Message
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class EmailParser:
    """Parse email messages to extract bank notification text"""
    
    @staticmethod
    def parse_email(email_message: Message) -> Optional[str]:
        """
        Parse email message and extract notification text
        
        Args:
            email_message: Email message object
        
        Returns:
            Extracted text content or None
        """
        try:
            # Get email subject
            subject = email_message.get("Subject", "")
            
            # Get email body
            body = EmailParser._get_email_body(email_message)
            
            # Combine subject and body for extraction
            full_text = f"{subject}\n{body}" if body else subject
            
            logger.debug(f"Parsed email: {full_text[:100]}...")
            return full_text
            
        except Exception as e:
            logger.error(f"Error parsing email: {e}")
            return None
    
    @staticmethod
    def _get_email_body(email_message: Message) -> str:
        """
        Extract body text from email message
        
        Handles multipart and plain text messages
        """
        body = ""
        
        if email_message.is_multipart():
            # Walk through email parts
            for part in email_message.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))
                
                # Skip attachments
                if "attachment" in content_disposition:
                    continue
                
                # Get text/plain parts
                if content_type == "text/plain":
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            body = payload.decode("utf-8", errors="ignore")
                            break
                    except Exception as e:
                        logger.warning(f"Error decoding email part: {e}")
                        continue
        else:
            # Simple non-multipart message
            try:
                payload = email_message.get_payload(decode=True)
                if payload:
                    body = payload.decode("utf-8", errors="ignore")
            except Exception as e:
                logger.warning(f"Error decoding email body: {e}")
        
        return body.strip()


parser = EmailParser()
