from typing import Set, Union

import networkx as nx

from .graph_region import GraphRegion
from ..data.generic_block import GenericBlock


def destroy_old_region(cfg: nx.DiGraph, expanded_region_graph: nx.DiGraph, r_head: GenericBlock):
    r_nodes = list(expanded_region_graph.nodes)
    r_preds = list(pred for pred in cfg.predecessors(r_head))
    r_succs = list()

    for r_node in r_nodes:
        for suc in cfg.successors(r_node):
            if suc not in r_nodes:
                r_succs.append(suc)

    cfg.remove_nodes_from(r_nodes)
    first_node: GenericBlock = list(r_nodes)[0]
    merged_node = first_node.merge_many_blocks(r_head.addr, r_nodes)
    cfg.add_node(merged_node)
    for pred in r_preds:
        cfg.add_edge(pred, merged_node)

    for suc in r_succs:
        cfg.add_edge(merged_node, suc)


def expand_region_to_block_graph(region: GraphRegion, graph: nx.DiGraph):
    def _expand_region_to_blocks(_region: GraphRegion):
        all_nodes = list()
        for node in _region.graph.nodes:
            if isinstance(node, GenericBlock):
                all_nodes.append(node)
            elif isinstance(node, GraphRegion):
                all_nodes += _expand_region_to_blocks(node)

        return all_nodes

    region_blocks = _expand_region_to_blocks(region)
    return nx.subgraph(graph, region_blocks)


def is_only_blocks(region: GraphRegion):
    for node in region.graph.nodes:
        if isinstance(node, GenericBlock):
            continue
        if isinstance(node, GraphRegion):
            return False

    return True


def find_containing_block_addrs(graph: nx.DiGraph, lines: Set):
    containing_addrs = set()
    line_has_container = set()
    graph_nodes = list(graph.nodes)
    for node in graph_nodes:
        for line in lines:
            if node.contains_addr(line):
                line_has_container.add(line)
                containing_addrs.add(node.addr)

    for line in lines:
        if line in line_has_container:
            continue

        closest_node = min(graph_nodes, key=lambda x: x.addr)
        for node in graph_nodes:
            if line >= node.addr >= closest_node.addr:
                closest_node = node

        containing_addrs.add(closest_node.addr)
    return containing_addrs


def find_matching_regions_with_lines(region: GraphRegion, lines: Set):
    if region.head.addr in lines:
        yield region

    for node in region.graph.nodes:
        if isinstance(node, GenericBlock):
            continue
        if isinstance(node, GraphRegion):
            yield from find_matching_regions_with_lines(node, lines)


def dfs_region_for_parent(region: GraphRegion, child: GenericBlock):
    for node in region.graph.nodes:
        if isinstance(node, GraphRegion):
            if node.head.addr == child.addr:
                yield region

            yield from dfs_region_for_parent(node, child)


def dfs_region_for_leafs(region: GraphRegion):
    has_block = False
    only_blocks = True
    for node in region.graph.nodes:
        if isinstance(node, GraphRegion):
            yield from dfs_region_for_leafs(node)
            only_blocks = False
        elif isinstance(node, GenericBlock):
            has_block = True

    if only_blocks and has_block:
        yield region.head, region.graph


def find_some_leaf_region(region: Union[GenericBlock, GraphRegion], node_blacklist, og_cfg: nx.DiGraph):
    # sanity check
    if isinstance(region, GenericBlock):
        return GenericBlock, None
    elif not isinstance(region, GraphRegion):
        return None, None

    leaf_regions = list(dfs_region_for_leafs(region))
    if not leaf_regions:
        return None, None

    # find a region we did not blacklist
    leaf_regions = sorted(leaf_regions, key=lambda x: x[0].addr, reverse=True)
    for leaf_region in leaf_regions:
        if leaf_region[0].addr not in node_blacklist:
            return leaf_region

    # if we are all out of non blacklisted regions, let's try to find a parent of each leaf
    # for leaf_region in leaf_regions:
    #    head, graph = leaf_region
    #    parents = list(dfs_region_for_parent(region, head))
    #    if not parents:
    #        continue

    #    parents = sorted(parents, key=lambda x: x.head.addr)
    #    for parent in parents:
    #        if parent.head.addr in node_blacklist:
    #            continue

    #        expanded_parent = expand_region_to_block_graph(parent, og_cfg)
    #        return parent.head, expanded_parent

    return None, None


def expand_region_head_to_block(region: GraphRegion):
    region_head = region.head
    if isinstance(region_head, GenericBlock):
        return region_head

    if isinstance(region_head, GraphRegion):
        return expand_region_head_to_block(region_head)

    raise ValueError(f"Invalid region head type {type(region_head)}")


def node_is_function_end(node: Union[GenericBlock, GraphRegion]):
    if node is None:
        return False

    node = expand_region_head_to_block(node) if isinstance(node, GraphRegion) else node
    if not node.statements:
        return False

    return node.is_exitpoint


def node_is_function_start(node: Union[GenericBlock, GraphRegion]):
    if node is None:
        return False

    node = expand_region_head_to_block(node) if isinstance(node, GraphRegion) else node
    if not node.statements:
        return False

    return node.is_entrypoint
