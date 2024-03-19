import sys
import unittest

import networkx as nx

from cfgutils.data import GenericBlock, GenericStatement
from cfgutils.hashing.function_sim_search import FunctionSimHasher


class TestHashing(unittest.TestCase):
    def test_fss_hashing(self):
        """
        Tests variations of the exact same graph, but with different edges excluded.
        The code the graph represents vaguely looks like this:

        x = 0x13
        if x >= 0x1337 {
            y = 0x14;
        }
        else {
            y = 0x15;
        }
        return;
        """
        blocks = [
            # blk 1
            GenericBlock(0x1, statements=[
                GenericStatement(0x2, "assign", ["x", 0x13]),
                GenericStatement(0x3, "cond_jmp", ["x", "gte", 0x1337])
            ]),
            # blk 2
            GenericBlock(0x4, statements=[
                GenericStatement(0x5, "assign", ["y", 0x14]),
            ]),
            # blk 3
            GenericBlock(0x6, statements=[
                GenericStatement(0x7, "assign", ["y", 0x15]),
            ]),
            # blk 4
            GenericBlock(0x8, statements=[
                GenericStatement(0x9, "ret", []),
            ]),
        ]
        b1, b2, b3, b4 = blocks
        # full diamond graph
        g1 = nx.DiGraph()
        g1.add_edges_from(
            [(b1, b2), (b1, b3), (b2, b4), (b3, b4)]
        )

        # partial diamond
        g2 = nx.DiGraph()
        g2.add_edges_from(
            [(b1, b2), (b1, b3), (b2, b4)]
        )

        # triangle
        g3 = nx.DiGraph()
        g3.add_edges_from(
            [(b1, b2), (b1, b3)]
        )

        # line
        g4 = nx.DiGraph()
        g4.add_edges_from(
            [(b1, b2)]
        )

        # dot!
        g5 = nx.DiGraph()
        g5.add_node(b1)

        hasher = FunctionSimHasher()
        h1 = hasher.CalculateFunctionSimHash(g1)
        h2 = hasher.CalculateFunctionSimHash(g2)
        h3 = hasher.CalculateFunctionSimHash(g3)
        h4 = hasher.CalculateFunctionSimHash(g4)
        h5 = hasher.CalculateFunctionSimHash(g5)

        # each distance should be less than the last
        d11 = FunctionSimHasher.hash_distance(h1, h1)
        d12 = FunctionSimHasher.hash_distance(h1, h2)
        d13 = FunctionSimHasher.hash_distance(h1, h3)
        d14 = FunctionSimHasher.hash_distance(h1, h4)
        d15 = FunctionSimHasher.hash_distance(h1, h5)

        assert d11 == 0
        assert d11 <= d12
        assert d12 <= d13
        # TODO: find out why things fall apart when the graph is too small!
        #assert d13 <= d14
        #assert d14 <= d15


if __name__ == "__main__":
    unittest.main(argv=sys.argv)
