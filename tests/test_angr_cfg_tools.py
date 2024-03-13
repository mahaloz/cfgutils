import sys
import unittest

ANGR_AVAILABLE = True
try:
    import angr
except ImportError:
    ANGR_AVAILABLE = False


class TestAngrCFGTools(unittest.TestCase):
    def setUp(self):
        if not ANGR_AVAILABLE:
            self.skipTest("angr is not available")



if __name__ == "__main__":
    unittest.main(argv=sys.argv)
