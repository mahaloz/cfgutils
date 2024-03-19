from collections import defaultdict
import logging
import re
from typing import Optional, List, Tuple

import networkx as nx
import itertools

from cfgutils.sorting import quasi_topological_sort_nodes
from . import seed0_, seed1_, seed2_, rotl64, mask64bit
from ...data import GenericBlock

_l = logging.getLogger(__name__)

CONST_RE = r"(?:\W|0x|^)([0-9a-fA-F]+)(?:h|\W|$)"


class FlowGraph:
    """
    A helper class that wraps networkx graphs to make the following attributes easier to access:
    - subgraph iteration
    - op iterations
    - immediate iteration
    """
    def __init__(self, graph: nx.DiGraph):
        self.graph = graph

        self._top_ordered_nodes = quasi_topological_sort_nodes(graph)
        self._addr_ordered_nodes = sorted(list(self.graph.nodes), key=lambda x: x.addr)
        self.statements = list(itertools.chain.from_iterable([blk.statements for blk in self._addr_ordered_nodes]))
        self._in_degrees = {node: graph.in_degree(node) for node in self._top_ordered_nodes}
        self._out_degrees = {node: graph.out_degree(node) for node in self._top_ordered_nodes}

        self.nodes_and_distance: List[Tuple[GenericBlock, int]] = self._build_nodes_and_distances()
        self.mnemonic_ngrams: List[Tuple[str, str, str]] = self.BuildMnemonicNgrams()
        self.immediates: List[int] = self.FindImmediateValues()

    def _build_nodes_and_distances(self):
        ones, twos, threes = [], [], []
        for node in self.graph.nodes:
            ones.append((node, 1))
            twos.append((node, 2))
            threes.append((node, 3))

        return ones + twos + threes

    def BuildMnemonicNgrams(self):
        mnemonics = [stmt.op for stmt in self.statements]
        mnem_tuples = []
        for index, mnem in enumerate(mnemonics):
            if index + 2 >= len(mnemonics):
                break

            mnem_tuples.append((
                mnem,
                mnemonics[index + 1],
                mnemonics[index + 2],
            ))

        return mnem_tuples

    def FindImmediateValues(self):
        """
        Only consider immediates as useful that are either greater than
        0x4000 or (not divisible by 4 and greater 10). This should remove
        most stack offsets.

        These are precisely the heuristics that should be removed by the
        machine-learning step, but since the baseline is supposed to work
        reasonably well even without the learning step, we need such stuff
        here.

        Also removes data structure offsets, though.
        """
        immediates = []
        for operand in itertools.chain.from_iterable([stmt.operands for stmt in self.statements]):
            _imms = self.ExtractImmediateFromString(operand)
            if not _imms:
                continue

            for _imm in _imms:
                # TODO: just a rule from the original implementation... maybe remove it to get smaller imms
                if (abs(_imm) > 0x4000) or ((_imm % 4 != 0) and (_imm > 10)):
                    immediates.append(_imm)

        return immediates

    def ExtractImmediateFromString(self, string):
        """
        Extracts all the Hex Digits from a string.
        """
        if isinstance(string, int):
            return [string]
        if not isinstance(string, str):
            return []

        imms = []
        for imm in re.findall(CONST_RE, string):
            try:
                val = int(imm, 16)
            except ValueError:
                continue

            imms.append(val)
        return imms

    def CalculateHash(self, start_node=None, k0=0xc3a5c85c97cb3127, k1=0xb492b66fbe98f273, k2=0x9ae16a3b2f90404f):
        """
        TODO: test this against the original function output!
        """
        if start_node is None:
            _starts = list(node for node in self.graph.nodes if self.graph.in_degree(node) == 0)
            if len(_starts) != 1:
                raise ValueError("Graph must have exactly one start node is none is provided")

            start_node = _starts[0]

        if start_node not in self.graph.nodes:
            raise ValueError("Start node must be in the graph")

        # compute the topological order of the graph and reconstruct that order
        # for both the forward and backward edges based on the original code.
        out_edges = defaultdict(list)
        ordered_nodes = self._top_ordered_nodes[self._top_ordered_nodes.index(start_node):]
        order_forward = {ordered_nodes[0]: 0}  # computed from out edges
        order_backward = {}  # computed from in edges
        order_both = {}  # computed from both edges
        back_idx = 0
        fwd_idx = 1
        bi_idx = 0
        for node in ordered_nodes:
            for pred in self.graph.predecessors(node):
                if pred not in order_backward:
                    order_backward[pred] = back_idx
                    back_idx += 1
                if pred not in order_both:
                    order_both[pred] = bi_idx
                    bi_idx += 1
                    order_both[node] = bi_idx
                    bi_idx += 1
            for succ in self.graph.successors(node):
                out_edges[node].append(succ)
                if succ not in order_forward:
                    order_forward[succ] = fwd_idx
                    fwd_idx += 1
                if succ not in order_both:
                    order_both[succ] = bi_idx
                    bi_idx += 1
                    order_both[node] = bi_idx
                    bi_idx += 1

        for node in ordered_nodes:
            if node not in order_backward:
                order_backward[node] = back_idx
                back_idx += 1

        hash_result = 0x0BADDEED600DDEED
        for source, dst_nodes in out_edges.items():
            per_edge_hash = 0x600DDEED0BADDEED
            for target in dst_nodes:
                per_edge_hash += (k0 * order_forward[source]) & mask64bit
                per_edge_hash = rotl64(per_edge_hash, 7)
                per_edge_hash += (k1 * order_backward[source]) & mask64bit
                per_edge_hash = rotl64(per_edge_hash, 7)
                per_edge_hash += (k2 * order_both[source]) & mask64bit
                per_edge_hash = rotl64(per_edge_hash, 7)
                per_edge_hash += (k0 * self._in_degrees[source]) & mask64bit
                per_edge_hash = rotl64(per_edge_hash, 7)
                per_edge_hash += (k1 * self._out_degrees[source]) & mask64bit
                per_edge_hash = rotl64(per_edge_hash, 7)

                per_edge_hash += (k2 * order_forward[target]) & mask64bit
                per_edge_hash = rotl64(per_edge_hash, 7)
                per_edge_hash += (k0 * order_backward[target]) & mask64bit
                per_edge_hash = rotl64(per_edge_hash, 7)
                per_edge_hash += (k1 * order_both[target]) & mask64bit
                per_edge_hash = rotl64(per_edge_hash, 7)
                per_edge_hash += (k2 * self._in_degrees[target]) & mask64bit
                per_edge_hash = rotl64(per_edge_hash, 7)
                per_edge_hash += (k0 * self._out_degrees[target]) & mask64bit
                per_edge_hash = rotl64(per_edge_hash, 7)

            hash_result += per_edge_hash

        return hash_result

    @staticmethod
    def GetSubgraph(graph: nx.DiGraph, node: GenericBlock, distance, max_size=30) -> Optional["FlowGraph"]:
        assert node in graph

        total_size = len(node.statements)
        new_nodes = [node]
        # TODO: add sorter for neighbors
        for src, succs in nx.bfs_successors(graph, node, depth_limit=distance):
            succ: GenericBlock
            for succ in succs:
                new_nodes.append(succ)
                total_size += len(succ.statements)

                if total_size > max_size:
                    _l.debug(f"Max size hit for the graph starting with %s of depth %s", node, distance)
                    return None

        return FlowGraph(nx.subgraph(graph, new_nodes))
