#include <Arduino.h>

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("SATSENTINEL-X USB TEST OK");
}

void loop() {
  Serial.println("ESP32 serial communication working");
  delay(1000);
}
