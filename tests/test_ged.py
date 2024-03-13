import sys
import unittest

from cfgutils.data import numbered_edges_to_block_graph
from cfgutils.similarity.ged.abu_aisheh_ged import ged_exact, ged_max, ged_explained
from cfgutils.similarity.ged.basque_cfged import cfg_edit_distance
from cfgutils.similarity.ged.hu_cfged import hu_cfged


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


class TestBasqueCFGED(unittest.TestCase):
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
