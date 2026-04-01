
import os
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils.dft.atomate2_utils import Atomate2Handler
from src.mcp_server.atomate2_server import run_atomate2_vasp_calculation

class TestRemoteSubmissionCheck(unittest.TestCase):
    def setUp(self):
        self.output_dir = ".agents/test/remote_check_test"
        os.makedirs(self.output_dir, exist_ok=True)
        self.handler = Atomate2Handler(self.output_dir)

    def tearDown(self):
        import shutil
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)

    def test_check_sshproxy_not_perlmutter(self):
        """Test that check passes if worker is not perlmutter."""
        is_ok, msg = self.handler._check_sshproxy("other_worker")
        self.assertTrue(is_ok)
        self.assertEqual(msg, "")

    @patch("src.utils.dft.atomate2_utils.Path.exists")
    def test_check_sshproxy_missing_key(self, mock_exists):
        """Test failure when key is missing for perlmutter worker."""
        # Mock .ssh/nersc does not exist
        # We need to make sure we only affect the nersc key check
        def side_effect(self):
            return False
            
        mock_exists.return_value = False
        
        is_ok, msg = self.handler._check_sshproxy("perlmutter_worker")
        self.assertFalse(is_ok)
        self.assertIn("NERSC SSH key not found", msg)

    @patch("src.utils.dft.atomate2_utils.Path.exists")
    def test_check_sshproxy_success(self, mock_exists):
        """Test success when key exists."""
        # Force exists to return True
        mock_exists.return_value = True
        
        is_ok, msg = self.handler._check_sshproxy("perlmutter_worker")
        self.assertTrue(is_ok)
        self.assertEqual(msg, "SSHProxy appears configured.")

if __name__ == "__main__":
    unittest.main()
