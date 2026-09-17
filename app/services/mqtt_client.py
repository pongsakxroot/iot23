"""
MQTT client service for publishing payment triggers to ESP32 devices
"""
import paho.mqtt.client as mqtt
from app.config import settings
from app.models import Order
from datetime import datetime
import json
import logging
import threading
import time

logger = logging.getLogger(__name__)


class MQTTClientService:
    """MQTT client for publishing payment trigger events"""
    
    def __init__(self):
        self.broker = settings.mqtt_broker
        self.port = settings.mqtt_port
        self.username = settings.mqtt_username
        self.password = settings.mqtt_password
        self.client_id = settings.mqtt_client_id
        self.topic_trigger = settings.mqtt_topic_trigger
        
        self.client = None
        self.connected = False
        self._lock = threading.Lock()
    
    def connect(self):
        """Connect to MQTT broker"""
        if self.client is not None and self.connected:
            return
        
        with self._lock:
            try:
                self.client = mqtt.Client(client_id=self.client_id, protocol=mqtt.MQTTv311)
                
                if self.username and self.password:
                    self.client.username_pw_set(self.username, self.password)
                
                self.client.on_connect = self._on_connect
                self.client.on_disconnect = self._on_disconnect
                
                logger.info(f"Connecting to MQTT broker {self.broker}:{self.port}")
                self.client.connect(self.broker, self.port, keepalive=60)
                
                # Start network loop in background
                self.client.loop_start()
                
                # Wait for connection
                timeout = 5
                start_time = time.time()
                while not self.connected and (time.time() - start_time) < timeout:
                    time.sleep(0.1)
                
                if not self.connected:
                    logger.error("MQTT connection timeout")
                
            except Exception as e:
                logger.error(f"MQTT connection error: {e}")
                self.connected = False
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        if self.client:
            with self._lock:
                self.client.loop_stop()
                self.client.disconnect()
                self.connected = False
                logger.info("Disconnected from MQTT broker")
    
    def publish_payment_trigger(self, order: Order) -> bool:
        """
        Publish payment trigger event to MQTT
        
        Args:
            order: The paid order
        
        Returns:
            True if published successfully, False otherwise
        """
        if not self.connected:
            self.connect()
        
        if not self.connected:
            logger.error("Cannot publish: MQTT not connected")
            return False
        
        try:
            payload = {
                "order_id": order.id,
                "amount": order.expected_amount,
                "base_amount": order.base_amount,
                "paid_at": order.paid_at.isoformat() if order.paid_at else datetime.utcnow().isoformat(),
                "timestamp": datetime.utcnow().isoformat(),
                "customer_ref": order.customer_ref
            }
            
            payload_json = json.dumps(payload)
            
            result = self.client.publish(
                self.topic_trigger,
                payload_json,
                qos=1,
                retain=False
            )
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"Published payment trigger for order {order.id} to {self.topic_trigger}")
                return True
            else:
                logger.error(f"MQTT publish failed with code {result.rc}")
                return False
                
        except Exception as e:
            logger.error(f"Error publishing MQTT message: {e}")
            return False
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT broker"""
        if rc == 0:
            self.connected = True
            logger.info("Connected to MQTT broker successfully")
        else:
            self.connected = False
            logger.error(f"MQTT connection failed with code {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from MQTT broker"""
        self.connected = False
        if rc != 0:
            logger.warning(f"Unexpected MQTT disconnection (code {rc})")
        else:
            logger.info("MQTT disconnected")


# Singleton instance
mqtt_client = MQTTClientService()
