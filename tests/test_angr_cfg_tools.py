import sys
import unittest
from pathlib import Path

ANGR_AVAILABLE = True
try:
    import angr
except ImportError:
    ANGR_AVAILABLE = False


TEST_FILES = Path(__file__).parent / "data"


class TestAngrCFGTools(unittest.TestCase):
    def setUp(self):
        if not ANGR_AVAILABLE:
            self.skipTest("angr is not available")

    def test_block_matcher(self):
        from cfgutils.angr_utils.ail_converter import binary_to_ail_cfgs
        from cfgutils.angr_utils.block_matcher import AILBlockMatcher
        from angr.analyses.decompiler.utils import find_block_by_addr

        cfgs0, p0 = binary_to_ail_cfgs(
            TEST_FILES / "fmt_O0_noinline.o",
            functions=["main"],
            structuring_opts=False,
            return_project=True
        )
        cfgs2, p2 = binary_to_ail_cfgs(
            TEST_FILES / "fmt_O2_noinline.o",
            functions=["main"],
            structuring_opts=False,
            return_project=True
        )
        main_o0 = cfgs0["main"]
        main_o2 = cfgs2["main"]

        assert main_o0 is not None
        assert main_o2 is not None

        matcher = AILBlockMatcher(main_o0, main_o2, proj1=p0, proj2=p2)
        mappings = matcher.mapping

        # TODO: add more assertions
        o0_blk = find_block_by_addr(main_o0, 0x4005e6)
        o2_blk = find_block_by_addr(main_o2, 0x40cb40)
        assert mappings[o0_blk] == o2_blk


if __name__ == "__main__":
    unittest.main(argv=sys.argv)
