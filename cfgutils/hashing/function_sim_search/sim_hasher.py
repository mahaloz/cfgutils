from collections import defaultdict
from typing import Dict, Optional

import networkx as nx

from .feat_weights import FeatureWeights
from ...sorting import quasi_topological_sort_nodes

mask64bit = 0xffffffffffffffff


def rotl64(data, n):
    _data = data & mask64bit
    return ((_data & mask64bit) << n) & mask64bit


# Some primes between 2^63 and 2^64 from CityHash.
seed0_ = 0xc3a5c85c97cb3127
seed1_ = 0xb492b66fbe98f273
seed2_ = 0x9ae16a3b2f90404f


class FunctionSimHasher:

    def __init__(self, weights: Optional[FeatureWeights] = None):
        self.weights = weights or FeatureWeights()

    #
    # Bit Utils
    #

    @staticmethod
    def GetNthBit(nbit_hash, bitindex):
        index = bitindex / 64
        value = nbit_hash[index]
        sub_word_index = bitindex % 64
        return (value >> sub_word_index) & 1

    @staticmethod
    def SeedXForHashY(seed_index, hash_index):
        if seed_index == 0:
            return rotl64(seed0_, hash_index % 7) * (hash_index + 1)
        elif seed_index == 1:
            return rotl64(seed1_, hash_index % 11) * (hash_index + 1)
        elif seed_index == 2:
            return rotl64(seed2_, hash_index % 13) * (hash_index + 1)
        else:
            raise ValueError("Invalid seed index")

    #
    #
    #

    #
    # Graphlet Hashing
    #

    def HashGraph(self, graph: nx.DiGraph, start_node, hash_index, counter):
        return self.CalculateDAGHash(
            graph,
            start_node,
            k0=self.SeedXForHashY(0, hash_index) * (counter + 1),
            k1=self.SeedXForHashY(1, hash_index) * (counter + 1),
            k2=self.SeedXForHashY(2, hash_index) * (counter + 1)
        )

    @staticmethod
    def CalculateDAGHash(graph: nx.DiGraph, start_node=None, k0=0, k1=0, k2=0):
        """
        TODO: test this against the original function output!
        """
        if start_node is None:
            _starts = list(node for node in graph.nodes if graph.in_degree(node) == 0)
            if len(_starts) != 1:
                raise ValueError("Graph must have exactly one start node is none is provided")

            start_node = _starts[0]

        if start_node not in graph.nodes:
            raise ValueError("Start node must be in the graph")

        # compute the topological order of the graph and reconstruct that order
        # for both the forward and backward edges based on the original code.
        out_edges = defaultdict(list)
        ordered_nodes = quasi_topological_sort_nodes(graph)
        ordered_nodes = ordered_nodes[ordered_nodes.index(start_node):]
        order_forward = {ordered_nodes[0]: 0}      # computed from out edges
        order_backward = {}     # computed from in edges
        order_both = {}         # computed from both edges
        back_idx = 0
        fwd_idx = 1
        bi_idx = 0
        for node in ordered_nodes:
            for pred in graph.predecessors(node):
                if pred not in order_backward:
                    order_backward[pred] = back_idx
                    back_idx += 1
                if pred not in order_both:
                    order_both[pred] = bi_idx
                    bi_idx += 1
                    order_both[node] = bi_idx
                    bi_idx += 1
            for succ in graph.successors(node):
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
        in_degrees = {node: graph.in_degree(node) for node in ordered_nodes}
        out_degrees = {node: graph.out_degree(node) for node in ordered_nodes}

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
                per_edge_hash += (k0 * in_degrees[source]) & mask64bit
                per_edge_hash = rotl64(per_edge_hash, 7)
                per_edge_hash += (k1 * out_degrees[source]) & mask64bit
                per_edge_hash = rotl64(per_edge_hash, 7)

                per_edge_hash += (k2 * order_forward[target]) & mask64bit
                per_edge_hash = rotl64(per_edge_hash, 7)
                per_edge_hash += (k0 * order_backward[target]) & mask64bit
                per_edge_hash = rotl64(per_edge_hash, 7)
                per_edge_hash += (k1 * order_both[target]) & mask64bit
                per_edge_hash = rotl64(per_edge_hash, 7)
                per_edge_hash += (k2 * in_degrees[target]) & mask64bit
                per_edge_hash = rotl64(per_edge_hash, 7)
                per_edge_hash += (k0 * out_degrees[target]) & mask64bit
                per_edge_hash = rotl64(per_edge_hash, 7)

            hash_result += per_edge_hash

        return hash_result




