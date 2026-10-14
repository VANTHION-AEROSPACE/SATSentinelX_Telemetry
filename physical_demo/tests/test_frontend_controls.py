import subprocess
import unittest
from pathlib import Path


class FrontendControlTests(unittest.TestCase):
    def test_browser_control_harness(self):
        script = Path(__file__).with_name("frontend_controls.mjs")
        result = subprocess.run(["node", str(script)], capture_output=True, text=True, check=False)
        if result.returncode != 0:
            self.fail(f"frontend harness failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
        self.assertIn("frontend controls: PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
