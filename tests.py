import sys

import unittest
import networkx as nx

from cfgutils.data.generic_block import GenericBlock
from cfgutils.regions.region_identifier import RegionIdentifier


class TestRegionIdentification(unittest.TestCase):
    def test_region_identification(self):
        """
        Graph:
                1
               / \
              2   3
              \   /
                4
               / \
              5   6
               \ /
                7
        """
        blocks = [None] + [GenericBlock(i) for i in range(1, 8)] + [None]
        numbered_edges = [(1, 2), (1, 3), (2, 4), (3, 4), (4, 5), (4, 6), (5, 7), (6, 7)]
        block_edges = [
            (blocks[in_e], blocks[out_e]) for (in_e, out_e) in numbered_edges
        ]
        graph = nx.DiGraph(block_edges)
        ri = RegionIdentifier(graph)
        top_region = ri.region
        self.assertTrue(top_region.head.head.head, blocks[1])
        self.assertIn((top_region.head, blocks[7]), ri.region.graph.edges)


if __name__ == "__main__":
    unittest.main(argv=sys.argv)
