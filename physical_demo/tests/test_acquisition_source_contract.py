import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BME_CPP = (ROOT / "firmware" / "libraries" / "Adafruit_BME280" / "Adafruit_BME280.cpp").read_text()
BME_H = (ROOT / "firmware" / "libraries" / "Adafruit_BME280" / "Adafruit_BME280.h").read_text()
FIRMWARE = (ROOT / "firmware" / "esp32_bme280" / "esp32_bme280.ino").read_text()


class AcquisitionSourceContractTests(unittest.TestCase):
    def test_checked_api_is_status_returning_and_preserves_legacy_api(self):
        self.assertIn("float readTemperature(void);", BME_H)
        self.assertIn("readTemperatureVerified(float *temperature)", BME_H)
        self.assertIn("TEMPERATURE_READ_TRANSACTION_FAILED", BME_H)
        self.assertIn("TEMPERATURE_READ_INVALID", BME_H)

    def test_transaction_results_are_checked_at_required_boundaries(self):
        self.assertIn("read8Checked(BME280_REGISTER_CHIPID", BME_CPP)
        self.assertIn("write8Checked(BME280_REGISTER_SOFTRESET", BME_CPP)
        self.assertIn("readCoefficientsChecked()", BME_CPP)
        self.assertIn("setSamplingVerified", BME_H)
        self.assertIn("setSamplingVerified", FIRMWARE)
        self.assertIn("isReadingCalibrationChecked", BME_CPP)
        self.assertIn("write8Checked(BME280_REGISTER_CONTROL", BME_CPP)
        self.assertIn("read8Checked(BME280_REGISTER_STATUS", BME_CPP)
        self.assertIn("read24Checked(BME280_REGISTER_TEMPDATA", BME_CPP)

    def test_firmware_maps_only_checked_success_to_verified_status(self):
        self.assertIn("bme.takeForcedMeasurement()", FIRMWARE)
        self.assertIn("bme.readTemperatureVerified(&temperatureC)", FIRMWARE)
        self.assertIn('"measurement_verified"', FIRMWARE)
        self.assertNotIn('"value_present_read_status_unverified"', FIRMWARE)


if __name__ == "__main__":
    unittest.main()
