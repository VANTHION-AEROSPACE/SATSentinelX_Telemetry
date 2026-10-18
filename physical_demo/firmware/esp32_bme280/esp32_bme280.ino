
#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_BMP280.h>
#include <math.h>

Adafruit_BMP280 bmp;

bool sensorReady = false;
uint32_t sequenceNumber = 0;

void setup() {
  Serial.begin(115200);
  delay(1500);

  Wire.begin(21, 22);
  Wire.setClock(100000);

  sensorReady = bmp.begin(0x76, BMP280_CHIPID);

  if (sensorReady &&
      !bmp.setSamplingVerified(
          Adafruit_BMP280::MODE_FORCED,
          Adafruit_BMP280::SAMPLING_X2,
          Adafruit_BMP280::SAMPLING_X16,
          Adafruit_BMP280::FILTER_OFF,
          Adafruit_BMP280::STANDBY_MS_1)) {
    sensorReady = false;
  }

  if (sensorReady) {
    Serial.println("{\"message\":\"BMP280_READY\",\"chip_id\":88}");
  } else {
    Serial.println("{\"message\":\"BMP280_INIT_FAILED\"}");
  }
}

void loop() {
  uint32_t deviceTimeMs = millis();

  float temperatureC = NAN;
  float pressurePa = NAN;
  float pressureHpa = NAN;

  const char *sensorStatus =
      sensorReady ? "sensor_bus_unavailable" : "sensor_init_failed";

  bool plausibleReading = false;

  if (sensorReady) {
    if (bmp.takeForcedMeasurementVerified()) {
      const bool temperatureReadOk =
          bmp.readTemperatureVerified(&temperatureC);
      const bool pressureReadOk =
          temperatureReadOk && bmp.readPressureVerified(&pressurePa);

      if (!temperatureReadOk || !pressureReadOk) {
        sensorStatus = "sensor_bus_unavailable";
      } else {
        pressureHpa = pressurePa / 100.0F;

        if (isfinite(temperatureC) && isfinite(pressurePa) &&
            isfinite(pressureHpa) && temperatureC >= -40.0F &&
            temperatureC <= 85.0F && pressureHpa >= 300.0F &&
            pressureHpa <= 1100.0F) {
          plausibleReading = true;
          sensorStatus = "measurement_verified";
        } else {
          sensorStatus = "sensor_value_invalid";
        }
      }
    }
  }

  bool valid = sensorReady &&
               plausibleReading &&
               isfinite(temperatureC) &&
               temperatureC >= -40.0F &&
               temperatureC <= 85.0F &&
               isfinite(pressureHpa) &&
               // BMP280 operating pressure range: 300-1100 hPa.
               pressureHpa >= 300.0F &&
               pressureHpa <= 1100.0F;

  Serial.print("{\"schema_version\":1");
  Serial.print(",\"message_type\":\"telemetry\"");
  Serial.print(",\"device_id\":\"esp32-bmp280-01\"");
  Serial.print(",\"seq\":");
  Serial.print(sequenceNumber++);
  Serial.print(",\"device_time_ms\":");
  Serial.print(deviceTimeMs);
  Serial.print(",\"temperature_c\":");

  if (valid) {
    Serial.print(temperatureC, 2);
  } else {
    Serial.print("null");
  }

  Serial.print(",\"pressure_hpa\":");
  if (valid) {
    Serial.print(pressureHpa, 2);
  } else {
    Serial.print("null");
  }

  Serial.print(",\"sensor_valid\":");
  Serial.print(valid ? "true" : "false");

  Serial.print(",\"sensor_status\":\"");
  Serial.print(sensorStatus);
  Serial.println("\"}");

  delay(150);
}
