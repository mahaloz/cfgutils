from typing import List, Tuple

import networkx as nx

from .generic_block import GenericBlock
from .generic_statement import GenericStatement


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

