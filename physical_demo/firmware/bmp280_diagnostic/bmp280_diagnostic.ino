
#include <Arduino.h>
#include <Wire.h>

const uint8_t BMP_ADDR = 0x76;

bool readReg(uint8_t reg, uint8_t &value) {
  Wire.beginTransmission(BMP_ADDR);
  Wire.write(reg);

  uint8_t error = Wire.endTransmission(false);
  if (error != 0) {
    Serial.printf("Register 0x%02X: address phase error %u\n",
                  reg, error);
    return false;
  }

  uint8_t received = Wire.requestFrom(BMP_ADDR, (uint8_t)1);
  if (received != 1) {
    Serial.printf("Register 0x%02X: received %u bytes\n",
                  reg, received);
    while (Wire.available()) Wire.read();
    return false;
  }

  value = Wire.read();
  return true;
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  Wire.begin(21, 22);
  Wire.setClock(100000);

  Serial.println("\nSATSentinel-X BMP280 register test");

  const uint8_t regs[] = {
    0xD0, 0xF3,
    0x88, 0x89, 0x8A, 0x8B,
    0x8E, 0x8F,
    0xF7, 0xF8, 0xF9, 0xFA, 0xFB, 0xFC
  };

  for (uint8_t reg : regs) {
    uint8_t value = 0;
    if (readReg(reg, value)) {
      Serial.printf("Register 0x%02X = 0x%02X\n", reg, value);
    }
  }
}

void loop() {
  delay(5000);
}
