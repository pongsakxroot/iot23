/*
 * PromptPay Payment Trigger - ESP32 Firmware
 * 
 * Connects to Wi-Fi and MQTT broker
 * Subscribes to payment trigger topic
 * Activates relay when payment is received
 * 
 * Hardware:
 * - ESP32 Development Board
 * - Relay Module (Active HIGH) connected to GPIO_RELAY_PIN
 * 
 * Required Libraries:
 * - WiFi (built-in)
 * - PubSubClient by Nick O'Leary (install from Library Manager)
 * - ArduinoJson by Benoit Blanchon (install from Library Manager)
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// Load secrets from secrets.h
// Copy secrets.h.example to secrets.h and fill in your credentials
#include "secrets.h"

// Pin Configuration
#define GPIO_RELAY_PIN 2          // GPIO pin for relay control
#define GPIO_LED_PIN LED_BUILTIN  // Built-in LED for status

// Relay Configuration
#define RELAY_ACTIVE_HIGH true    // Set to false if relay is Active LOW
#define RELAY_TRIGGER_DURATION 5000  // Relay active duration in milliseconds (5 seconds)

// MQTT Configuration
const char* mqtt_topic_trigger = MQTT_TOPIC_TRIGGER;  // From secrets.h

// Global Objects
WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);

// State Variables
bool relayActive = false;
unsigned long relayActivatedAt = 0;

// Function Declarations
void setup_wifi();
void setup_mqtt();
void mqtt_callback(char* topic, byte* payload, unsigned int length);
void reconnect_mqtt();
void activate_relay(int order_id, float amount);
void deactivate_relay();
void blink_led(int times, int delay_ms = 200);

/*
 * Setup - runs once on boot
 */
void setup() {
  // Initialize serial
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n=================================");
  Serial.println("PromptPay Payment Trigger v1.0");
  Serial.println("=================================\n");
  
  // Initialize GPIO
  pinMode(GPIO_RELAY_PIN, OUTPUT);
  pinMode(GPIO_LED_PIN, OUTPUT);
  
  // Ensure relay is OFF
  digitalWrite(GPIO_RELAY_PIN, RELAY_ACTIVE_HIGH ? LOW : HIGH);
  digitalWrite(GPIO_LED_PIN, LOW);
  
  Serial.println("GPIO initialized");
  Serial.printf("Relay pin: %d (Active %s)\n", GPIO_RELAY_PIN, RELAY_ACTIVE_HIGH ? "HIGH" : "LOW");
  
  // Connect to Wi-Fi
  setup_wifi();
  
  // Setup MQTT
  setup_mqtt();
  
  Serial.println("\nSetup complete. Waiting for payment triggers...\n");
  blink_led(3, 100);
}

/*
 * Main Loop
 */
void loop() {
  // Maintain MQTT connection
  if (!mqttClient.connected()) {
    reconnect_mqtt();
  }
  mqttClient.loop();
  
  // Check relay timer
  if (relayActive && (millis() - relayActivatedAt >= RELAY_TRIGGER_DURATION)) {
    deactivate_relay();
  }
  
  // Small delay to prevent watchdog issues
  delay(10);
}

/*
 * Setup Wi-Fi Connection
 */
void setup_wifi() {
  Serial.printf("Connecting to Wi-Fi: %s\n", WIFI_SSID);
  
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWi-Fi connected!");
    Serial.printf("IP Address: %s\n", WiFi.localIP().toString().c_str());
    Serial.printf("Signal Strength: %d dBm\n", WiFi.RSSI());
  } else {
    Serial.println("\nWi-Fi connection failed!");
    Serial.println("Check credentials in secrets.h");
    ESP.restart();
  }
}

/*
 * Setup MQTT Client
 */
void setup_mqtt() {
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setCallback(mqtt_callback);
  
  Serial.printf("MQTT Broker: %s:%d\n", MQTT_BROKER, MQTT_PORT);
}

/*
 * Reconnect to MQTT Broker
 */
void reconnect_mqtt() {
  while (!mqttClient.connected()) {
    Serial.print("Connecting to MQTT broker... ");
    
    String client_id = String(MQTT_CLIENT_ID) + "-" + String(WiFi.macAddress());
    
    bool connected;
    if (strlen(MQTT_USERNAME) > 0 && strlen(MQTT_PASSWORD) > 0) {
      connected = mqttClient.connect(client_id.c_str(), MQTT_USERNAME, MQTT_PASSWORD);
    } else {
      connected = mqttClient.connect(client_id.c_str());
    }
    
    if (connected) {
      Serial.println("Connected!");
      Serial.printf("Client ID: %s\n", client_id.c_str());
      
      // Subscribe to trigger topic
      if (mqttClient.subscribe(mqtt_topic_trigger, 1)) {
        Serial.printf("Subscribed to: %s\n", mqtt_topic_trigger);
      } else {
        Serial.println("Subscription failed!");
      }
      
      blink_led(2, 100);
      
    } else {
      Serial.printf("Failed! (rc=%d) Retrying in 5 seconds...\n", mqttClient.state());
      delay(5000);
    }
  }
}

/*
 * MQTT Message Callback
 */
void mqtt_callback(char* topic, byte* payload, unsigned int length) {
  Serial.println("\n--- MQTT Message Received ---");
  Serial.printf("Topic: %s\n", topic);
  Serial.printf("Length: %d bytes\n", length);
  
  // Parse JSON payload
  StaticJsonDocument<512> doc;
  DeserializationError error = deserializeJson(doc, payload, length);
  
  if (error) {
    Serial.printf("JSON parse error: %s\n", error.c_str());
    Serial.print("Raw payload: ");
    Serial.write(payload, length);
    Serial.println();
    return;
  }
  
  // Extract payment details
  int order_id = doc["order_id"] | 0;
  float amount = doc["amount"] | 0.0;
  const char* paid_at = doc["paid_at"] | "unknown";
  const char* customer_ref = doc["customer_ref"] | "";
  
  Serial.println("Payment Details:");
  Serial.printf("  Order ID: %d\n", order_id);
  Serial.printf("  Amount: %.2f THB\n", amount);
  Serial.printf("  Paid At: %s\n", paid_at);
  if (strlen(customer_ref) > 0) {
    Serial.printf("  Customer Ref: %s\n", customer_ref);
  }
  
  // Activate relay
  if (order_id > 0 && amount > 0) {
    activate_relay(order_id, amount);
  } else {
    Serial.println("Invalid payment data - relay not activated");
  }
  
  Serial.println("-----------------------------\n");
}

/*
 * Activate Relay
 */
void activate_relay(int order_id, float amount) {
  if (relayActive) {
    Serial.println("Relay already active - ignoring trigger");
    return;
  }
  
  Serial.printf(">> ACTIVATING RELAY for Order #%d (%.2f THB)\n", order_id, amount);
  
  digitalWrite(GPIO_RELAY_PIN, RELAY_ACTIVE_HIGH ? HIGH : LOW);
  digitalWrite(GPIO_LED_PIN, HIGH);
  
  relayActive = true;
  relayActivatedAt = millis();
  
  Serial.printf("Relay will deactivate after %d ms\n", RELAY_TRIGGER_DURATION);
}

/*
 * Deactivate Relay
 */
void deactivate_relay() {
  if (!relayActive) {
    return;
  }
  
  Serial.println(">> DEACTIVATING RELAY");
  
  digitalWrite(GPIO_RELAY_PIN, RELAY_ACTIVE_HIGH ? LOW : HIGH);
  digitalWrite(GPIO_LED_PIN, LOW);
  
  relayActive = false;
  
  Serial.println("Relay idle. Waiting for next payment...\n");
}

/*
 * Blink LED
 */
void blink_led(int times, int delay_ms) {
  for (int i = 0; i < times; i++) {
    digitalWrite(GPIO_LED_PIN, HIGH);
    delay(delay_ms);
    digitalWrite(GPIO_LED_PIN, LOW);
    delay(delay_ms);
  }
}
