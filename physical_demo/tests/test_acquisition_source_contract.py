import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BMP_CPP = (ROOT / "firmware" / "libraries" / "Adafruit_BMP280" / "Adafruit_BMP280.cpp").read_text()
BMP_H = (ROOT / "firmware" / "libraries" / "Adafruit_BMP280" / "Adafruit_BMP280.h").read_text()
BMP_PROPERTIES = (ROOT / "firmware" / "libraries" / "Adafruit_BMP280" / "library.properties").read_text()
FIRMWARE = (ROOT / "firmware" / "esp32_bme280" / "esp32_bme280.ino").read_text()


class AcquisitionSourceContractTests(unittest.TestCase):
    def test_checked_api_is_status_returning_and_preserves_legacy_api(self):
        self.assertIn("#define BMP280_CHIPID (0x58)", BMP_H)
        self.assertIn("float readTemperature();", BMP_H)
        self.assertIn("readTemperatureVerified(float *temperature)", BMP_H)
        self.assertIn("version=3.0.0", BMP_PROPERTIES)

    def test_transaction_results_are_checked_at_required_boundaries(self):
        self.assertIn("read8Checked(BMP280_REGISTER_CHIPID", BMP_CPP)
        self.assertIn("readCoefficientsVerified()", BMP_CPP)
        self.assertIn("setSamplingVerified", BMP_H)
        self.assertIn("bmp.setSamplingVerified(", FIRMWARE)
        self.assertIn("write8Checked(BMP280_REGISTER_CONTROL", BMP_CPP)
        self.assertIn("read8Checked(BMP280_REGISTER_STATUS", BMP_CPP)
        self.assertIn("read24Checked(BMP280_REGISTER_TEMPDATA", BMP_CPP)
        self.assertIn("read24Checked(BMP280_REGISTER_PRESSUREDATA", BMP_CPP)

    def test_firmware_maps_only_checked_success_to_verified_status(self):
        self.assertIn("bmp.takeForcedMeasurementVerified()", FIRMWARE)
        self.assertIn("bmp.readTemperatureVerified(&temperatureC)", FIRMWARE)
        self.assertIn("float pressurePa = NAN;", FIRMWARE)
        self.assertIn("bmp.readPressureVerified", FIRMWARE)
        self.assertIn("readPressureVerified", FIRMWARE)
        self.assertIn("pressureHpa = pressurePa / 100.0F;", FIRMWARE)
        conversion_index = FIRMWARE.index("pressureHpa = pressurePa / 100.0F;")
        validation_index = FIRMWARE.index("bool valid =")
        publication_index = FIRMWARE.index('Serial.print(",\\\"pressure_hpa\\\":");')
        self.assertLess(conversion_index, validation_index)
        self.assertLess(conversion_index, publication_index)
        self.assertIn("pressureHpa >= 300.0F", FIRMWARE)
        self.assertIn("pressureHpa <= 1100.0F", FIRMWARE)
        self.assertIn("BMP280 operating pressure range: 300-1100 hPa", FIRMWARE)
        self.assertNotIn("Serial.print(pressurePa, 2)", FIRMWARE)
        self.assertIn('"sensor_bus_unavailable"', FIRMWARE)
        self.assertIn('sensorStatus = "sensor_value_invalid"', FIRMWARE)
        self.assertIn('"measurement_verified"', FIRMWARE)
        self.assertNotIn('"value_present_read_status_unverified"', FIRMWARE)
        self.assertIn("bool plausibleReading = false;", FIRMWARE)
        self.assertIn("isfinite(temperatureC) && isfinite(pressurePa)", FIRMWARE)


if __name__ == "__main__":
    unittest.main()
