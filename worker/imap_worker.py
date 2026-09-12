"""
IMAP worker - polls Gmail for bank notification emails
"""
import time
import sys
import os
import email
from email.message import Message
from datetime import datetime
from imapclient import IMAPClient
import requests
import logging
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from worker.email_parser import parser

# Load environment variables
load_dotenv()

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IMAPWorker:
    """IMAP worker for polling Gmail and forwarding bank notifications"""
    
    def __init__(self):
        self.imap_server = os.getenv("IMAP_SERVER", "imap.gmail.com")
        self.imap_port = int(os.getenv("IMAP_PORT", "993"))
        self.imap_email = os.getenv("IMAP_EMAIL", "")
        self.imap_password = os.getenv("IMAP_PASSWORD", "")
        self.imap_mailbox = os.getenv("IMAP_MAILBOX", "INBOX")
        self.poll_interval = int(os.getenv("IMAP_POLL_INTERVAL", "15"))
        
        # Webhook configuration
        self.webhook_url = os.getenv("WEBHOOK_URL", "http://localhost:8000/webhook/bank-notification")
        self.webhook_secret = os.getenv("WEBHOOK_SECRET", "")
        
        # Validate configuration
        if not self.imap_email or not self.imap_password:
            raise ValueError("IMAP_EMAIL and IMAP_PASSWORD must be set")
        
        if not self.webhook_secret:
            logger.warning("WEBHOOK_SECRET not set - webhook may fail")
        
        self.client = None
    
    def connect(self):
        """Connect to IMAP server"""
        try:
            logger.info(f"Connecting to {self.imap_server}:{self.imap_port}")
            
            self.client = IMAPClient(self.imap_server, port=self.imap_port, use_uid=True)
            self.client.login(self.imap_email, self.imap_password)
            
            # Select mailbox
            self.client.select_folder(self.imap_mailbox)
            
            logger.info(f"Connected successfully as {self.imap_email}")
            return True
            
        except Exception as e:
            logger.error(f"IMAP connection error: {e}")
            self.client = None
            return False
    
    def disconnect(self):
        """Disconnect from IMAP server"""
        if self.client:
            try:
                self.client.logout()
                logger.info("Disconnected from IMAP server")
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")
            finally:
                self.client = None
    
    def reconnect(self):
        """Reconnect to IMAP server"""
        logger.info("Attempting to reconnect...")
        self.disconnect()
        time.sleep(5)
        return self.connect()
    
    def fetch_unseen_messages(self):
        """
        Fetch unseen messages from mailbox
        
        Returns:
            List of message IDs
        """
        try:
            # Search for unseen messages
            messages = self.client.search(['UNSEEN'])
            
            if messages:
                logger.info(f"Found {len(messages)} unseen message(s)")
            
            return messages
            
        except Exception as e:
            logger.error(f"Error fetching messages: {e}")
            return []
    
    def process_message(self, msg_id):
        """
        Process a single email message
        
        Args:
            msg_id: Message ID/UID
        """
        try:
            # Fetch message data
            msg_data = self.client.fetch([msg_id], ['RFC822'])
            
            if not msg_data or msg_id not in msg_data:
                logger.warning(f"Could not fetch message {msg_id}")
                return
            
            # Parse email
            raw_email = msg_data[msg_id][b'RFC822']
            email_message = email.message_from_bytes(raw_email)
            
            # Extract notification text
            notification_text = parser.parse_email(email_message)
            
            if not notification_text:
                logger.warning(f"No text extracted from message {msg_id}")
                return
            
            # Check if this looks like a bank notification
            if not self._is_bank_notification(notification_text):
                logger.debug(f"Message {msg_id} does not appear to be a bank notification")
                return
            
            # Forward to webhook
            success = self._forward_to_webhook(notification_text)
            
            if success:
                logger.info(f"Successfully processed message {msg_id}")
            else:
                logger.warning(f"Failed to forward message {msg_id} to webhook")
            
        except Exception as e:
            logger.error(f"Error processing message {msg_id}: {e}", exc_info=True)
    
    def _is_bank_notification(self, text: str) -> bool:
        """
        Check if text looks like a bank notification
        
        Simple heuristic - contains common Thai bank keywords
        """
        bank_keywords = [
            'รับเงิน', 'รับโอน', 'โอนเข้า', 'เงินเข้า',
            'SCB', 'กสิกร', 'K-Mobile', 'KTB', 'กรุงไทย',
            'PromptPay', 'พร้อมเพย์', 'บาท'
        ]
        
        text_lower = text.lower()
        return any(keyword.lower() in text_lower for keyword in bank_keywords)
    
    def _forward_to_webhook(self, notification_text: str) -> bool:
        """
        Forward notification to webhook endpoint
        
        Args:
            notification_text: Extracted notification text
        
        Returns:
            True if successful, False otherwise
        """
        try:
            headers = {
                "Content-Type": "application/json",
                "X-Webhook-Secret": self.webhook_secret
            }
            
            payload = {
                "notification_text": notification_text,
                "source": "imap",
                "timestamp": datetime.utcnow().isoformat()
            }
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers=headers,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"Webhook response: {response.json()}")
                return True
            else:
                logger.error(f"Webhook error: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error forwarding to webhook: {e}")
            return False
    
    def run(self):
        """Main worker loop"""
        logger.info("Starting IMAP worker")
        logger.info(f"Poll interval: {self.poll_interval} seconds")
        logger.info(f"Webhook URL: {self.webhook_url}")
        
        # Initial connection
        if not self.connect():
            logger.error("Initial connection failed. Exiting.")
            return
        
        try:
            while True:
                try:
                    # Fetch unseen messages
                    messages = self.fetch_unseen_messages()
                    
                    # Process each message
                    for msg_id in messages:
                        self.process_message(msg_id)
                    
                    # Wait before next poll
                    time.sleep(self.poll_interval)
                    
                except Exception as e:
                    logger.error(f"Error in worker loop: {e}", exc_info=True)
                    
                    # Try to reconnect
                    if not self.reconnect():
                        logger.error("Reconnection failed. Waiting 30 seconds before retry...")
                        time.sleep(30)
        
        except KeyboardInterrupt:
            logger.info("Worker stopped by user")
        finally:
            self.disconnect()


def main():
    """Entry point"""
    try:
        worker = IMAPWorker()
        worker.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
