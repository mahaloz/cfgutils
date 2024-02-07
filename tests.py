import sys

import unittest
from typing import List, Tuple

import networkx as nx

from cfgutils.data.generic_block import GenericBlock
from cfgutils.regions.region_identifier import RegionIdentifier
from cfgutils.similarity.ged.abu_aisheh_ged import ged_exact, ged_max, ged_explained
from cfgutils.similarity.ged.basque_cfged import cfg_edit_distance
from cfgutils.similarity.ged.hu_cfged import hu_cfged
from cfgutils.matrix.munkres import Munkres, print_matrix


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
    def test_explained_ged(self):
        """
        This tests utilizes the graph shown in `test_exact_ged_cfg` and validates the explanation function
        to match the expected edits as shown in the function docstring.
        """

        g1, g2 = CROSS_JUMP_OPT_GRAPHS
        human_readable_edits = ged_explained(g1, g2, print_explanation=True, only_addrs=True)
        real_ged_score = ged_exact(g1, g2)

        # gather expected edits from docstring
        tmp = self.test_exact_ged_cfg.__doc__.split("EDITS:\n")[1].split("\n")[0].strip().split("), ")
        expected_edits = [t + ")" if not t.endswith(")") else t for t in tmp]

        assert len(human_readable_edits) == real_ged_score
        assert all([edit in expected_edits for edit in human_readable_edits])

    def test_exact_ged_cfg(self):
        """
        This function validates that our GED algorithm is working as expected for CFGs. It's important to note
        that our GED algorithm is different from the traditional GED algorithm. We special rules to make it work
        with CFGs. For example, you are not allowed to ever substitute the start or end nodes of a CFG.

        The graphs bellow is based on the Cross Jump Optimization shown in the SAILR paper. g1 is the original CFG
        as you would see in a real program. g2 is the optimized version of g1, usually produced by `-O2` or `-O3`.

        g1:

               1
             /   \
            2     3
            |     | \
            |     |   5
            |     |  /
           6.1    6.2

        g2:

               1
             /   \
            2     3
            |    / \
            |    4  5
            |    \  /
            + ---> 6

        Since changing g2 to g1 is simpler, we will use that as the example. The expected edit distance is 5. The
        expected edits are as follows.
        EDITS:
        del(3, 6), del(6), ins(4), ins(3, 4), ins(4, 6)

        Those edits can be produced by using the `ged_explained` function.
        """
        g1, g2 = CROSS_JUMP_OPT_GRAPHS

        one_to_two_edit_distance = ged_exact(g1, g2, with_timeout=20)
        two_to_one_edit_distance = ged_exact(g2, g1, with_timeout=20)

        assert one_to_two_edit_distance == 5
        # note: rooted graph edit distance algorithms are not the same computed both ways
        assert two_to_one_edit_distance == 7


class TestControlFlowGraphEditDistance(unittest.TestCase):
    def test_exact_cfged(self):
        """
        The CFGED algorithm is a special version of GED that is designed to work with CFGs, quickly. To do this,
        we use node label information to point the algorithm to what we believe is matching regions. This allows us
        to run GED on the small regions, then sum up all the region scores. In the best case, the CFGED score is the
        same as the exact GED score. In the worst case, it's the max GED score. At all times, the score should be
        between the max and exact scores.

        For this test, we use the same graphs from `TestGraphEditDistance.test_exact_ged_cfg`.
        Turning g1 -> g2, we expect the CFGED score to be the exact score, 5. The other way around, we expect it to
        maintain its earlier stated bounds.
        """
        g1, g2 = CROSS_JUMP_OPT_GRAPHS

        # This map is critical to using the algorithm. You don't need to provide a mapping for every node (although
        # you can, and it won't hurt). You only need to provide mappings for tail regions, like node 3 in both graphs.
        # Since we know how every node maps to each other, we provide a map for all of them.
        node_map = {x: {x} for x in range(7)}

        combos = [(g1, g2), (g2, g1)]
        for i, graphs in enumerate(combos):
            first_g, second_g = graphs
            max_ged_score = ged_max(first_g, second_g)
            exact_ged_score = ged_exact(first_g, second_g)
            # the node map is the same for both graphs, so we can use it for both
            cfged_score = cfg_edit_distance(first_g, second_g, node_map, node_map)
            assert exact_ged_score <= cfged_score <= max_ged_score

            if i == 0:
                assert exact_ged_score == cfged_score


class TestHuCFGED(unittest.TestCase):
    def test_cross_jump_graphs(self):
        g1, g2 = CROSS_JUMP_OPT_GRAPHS
        score = hu_cfged(g1, g2)
        real_score = ged_exact(g1, g2)
        max_score = ged_max(g1, g2)
        print(f"score={score}, real_score={real_score}, max_score={max_score}")
        assert real_score <= score <= max_score


class TestMatrixMath(unittest.TestCase):
    def test_munkres(self):
        matrices = [
            # Square
            ([[400, 150, 400],
              [400, 450, 600],
              [300, 225, 300]],
             850  # expected cost
             ),

            # Rectangular variant
            ([[400, 150, 400, 1],
              [400, 450, 600, 2],
              [300, 225, 300, 3]],
             452  # expected cost
             ),

            # Square
            ([[10, 10, 8],
              [9, 8, 1],
              [9, 7, 4]],
             18
             ),

            # Rectangular variant
            ([[10, 10, 8, 11],
              [9, 8, 1, 1],
              [9, 7, 4, 10]],
             15
             ),
        ]

        m = Munkres()
        for cost_matrix, expected_total in matrices:
            print_matrix(cost_matrix, msg='cost matrix')
            indexes = m.compute(cost_matrix)
            total_cost = 0
            for r, c in indexes:
                x = cost_matrix[r][c]
                total_cost += x
                print('(%d, %d) -> %d' % (r, c, x))
            print('lowest cost=%d' % total_cost)
            assert expected_total == total_cost


#
# Utils
#

def numbered_edges_to_block_graph(numbered_edges: List[Tuple[int, int]]) -> nx.DiGraph:
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

#
# Some common graphs used among testcases
#


CROSS_JUMP_OPT_GRAPHS = (
    # g1
    numbered_edges_to_block_graph(
        [(1, 2), (1, 3), (3, 6.2), (3, 5), (5, 6.2), (2, 6.1)]
    ),
    # g2
    numbered_edges_to_block_graph(
        [(1, 2), (1, 3), (3, 4), (3, 5), (4, 6), (5, 6), (2, 6)]
    ),
)


if __name__ == "__main__":
    unittest.main(argv=sys.argv)
