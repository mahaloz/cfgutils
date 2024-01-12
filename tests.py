import sys

import unittest
from typing import List, Tuple

import networkx
import networkx as nx

from cfgutils.data.generic_block import GenericBlock
from cfgutils.regions.region_identifier import RegionIdentifier
from cfgutils.similarity.ged import ged_exact, ged_max
from cfgutils.similarity.cfged import cfg_edit_distance


def numbered_edges_to_block_graph(numbered_edges: List[Tuple[int, int]]) -> networkx.DiGraph:
    """
    Node numbering should start at 1. If a number is in the form of a float, like 1.1, then the number on
    the right of the decimal will be treated as the idx, which is a unique identifier. Please use small
    numbers for the block addresses.
    """

    # find max block number to create a block dictionary
    block_numbers = set()
    float_edges = []
    for src, dst in numbered_edges:
        block_numbers.add(src)
        block_numbers.add(dst)
        if type(src) is float or type(dst) is float:
            float_edges.append((src, dst))

    max_number = int(max(block_numbers))
    # None blocks added to make indexing for the right block addr easier
    blocks = [None] + [GenericBlock(i) for i in range(1, max_number+1)] + [None]

    # do all normal edges
    block_edges = [
        (blocks[in_e], blocks[out_e]) for (in_e, out_e) in numbered_edges
        if not type(in_e) is float and not type(out_e) is float
    ]
    # do all float edges (extra data)
    if float_edges:
        float_blocks = {}
        for edge in float_edges:
            for node in edge:
                if type(node) is float:
                    float_str = str(node)
                    if float_str not in float_blocks:
                        idx = int(float_str.split(".")[-1])
                        float_blocks[float_str] = GenericBlock(int(node), idx=idx)

        for src, dst in float_edges:
            src_blk = float_blocks[str(src)] if type(src) is float else blocks[src]
            dst_blk = float_blocks[str(dst)] if type(dst) is float else blocks[dst]
            block_edges.append((src_blk, dst_blk))

    graph = nx.DiGraph()
    graph.add_edges_from(block_edges)

    # find start and ends and update their attributes
    starts = [n for n in graph.nodes if graph.in_degree(n) == 0]
    ends = [n for n in graph.nodes if graph.out_degree(n) == 0]
    for node in starts:
        node.is_entrypoint = True
    for node in ends:
        node.is_exitpoint = True

    # update the node attr of every node in nx to be itself
    for node in graph.nodes:
        graph.nodes[node]["node"] = node

    # update the edge attr of every edge in nx to be itself
    for edge in graph.edges:
        graph.edges[edge]["src"] = edge[0]
        graph.edges[edge]["dst"] = edge[1]

    return graph


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


class TestGraphEditDistance(unittest.TestCase):
    """
    Test Graph Edit Distances (traditional algo) for Control Flow Graphs
    """
    def test_exact_ged_cfg(self):
        #
        # G1:
        #
        #       1
        #     /   \
        #    2     3
        #    |    / \
        #    |    4  5
        #    |    \  /
        #    + ---> 6
        #
        #
        # G2:
        #
        #       1
        #     /   \
        #    2     3
        #    |     | \
        #    |     |   5
        #    |     |  /
        #   6.1    6.2
        #
        # The real edit distance, based on it being a CFG, is 7.
        # Edits for G2 -> G1:
        # del(3, 6.2), ins(4), ins(3,4), ins(4, 6.2), del(2, 6.1), del(6.1), ins(2, 6.2)
        #
        # Note how this is different from the edit distance if you used traditional graph edit distance.
        # In this case it's higher since we set the special rule that you are not allowed to ever substitute
        # the start or end nodes of a CFG (unless they are subbed with themselves).
        #

        g1 = numbered_edges_to_block_graph(
            [(1, 2), (1, 3), (3, 4), (3, 5), (4, 6), (5, 6), (2, 6)]
        )
        g2 = numbered_edges_to_block_graph(
            [(1, 2), (1, 3), (3, 6.2), (3, 5), (5, 6.2), (2, 6.1)]
        )
        edit_distance = ged_exact(g2, g1, with_timeout=20)

        assert edit_distance == 7


class TestControlFlowGraphEditDistance(unittest.TestCase):
    def test_exact_cfged(self):
        #
        # G1:
        #
        #       1
        #     /   \
        #    2     3
        #    |    / \
        #    |    4  5
        #    |    \  /
        #    + ---> 6
        #
        #
        # G2:
        #
        #       1
        #     /   \
        #    2     3
        #    |     | \
        #    |     |   5
        #    |     |  /
        #   6.1    6.2
        #
        # same graphs from `TestGraphEditDistance.test_exact_ged_cfg`, therefore, the CFGED score should be
        # greater or equal to the exact score of 7 from that testcase.
        #
        g1 = numbered_edges_to_block_graph(
            [(1, 2), (1, 3), (3, 4), (3, 5), (4, 6), (5, 6), (2, 6)]
        )
        g2 = numbered_edges_to_block_graph(
            [(1, 2), (1, 3), (3, 6.2), (3, 5), (5, 6.2), (2, 6.1)]
        )
        max_ged_score = ged_max(g2, g1)
        exact_ged_score = ged_exact(g2, g1)

        g1_to_g2 = {x: {x} for x in range(7)}
        g2_to_g1 = g1_to_g2
        cfged_score = cfg_edit_distance(g2, g1, g2_to_g1, g1_to_g2)

        assert exact_ged_score <= cfged_score <= max_ged_score
        # in this case, since node matching is non-stochastic, the cfged score is the exact score
        assert cfged_score == exact_ged_score


if __name__ == "__main__":
    unittest.main(argv=sys.argv)
