import sys
import unittest

from cfgutils.regions.region_identifier import RegionIdentifier
from cfgutils.data import numbered_edges_to_block_graph


class TestRegionIdentification(unittest.TestCase):
    def test_region_identification(self):
        #
        # Graph:
        #         1
        #        / \
        #       2   3
        #       \   /
        #         4
        #        / \
        #       5   6
        #        \ /
        #         7
        #
        # Regions:
        # [1,2,3]
        # [4,5,6]
        # [1,7]
        # None blocks added to start and end to make indexing easier
        graph = numbered_edges_to_block_graph(
            [(1, 2), (1, 3), (2, 4), (3, 4), (4, 5), (4, 6), (5, 7), (6, 7)]
        )
        ri = RegionIdentifier(graph)
        top_region = ri.region

        # the node to start all the regions should be 1
        assert top_region.head.head.head.addr == 1

        # check known regions
        region_blk_sets = [set(blks) for blks in ri.regions_by_block_addrs]
        assert {1, 2, 3} in region_blk_sets
        assert {4, 5, 6} in region_blk_sets
        assert {1, 7} in region_blk_sets


if __name__ == "__main__":
    unittest.main(argv=sys.argv)