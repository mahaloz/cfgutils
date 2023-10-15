import networkx as nx

from .data.generic_block import GenericBlock


def merge_graph_nodes(graph: nx.DiGraph, node_a: GenericBlock, node_b: GenericBlock):
    in_edges = list(graph.in_edges(node_a, data=True))
    out_edges = list(graph.out_edges(node_b, data=True))
    new_node = node_a.merge_blocks(node_a, node_b)

    graph.remove_node(node_a)
    graph.remove_node(node_b)

    if new_node is not None:
        graph.add_node(new_node, node=new_node)

        for src, _, data in in_edges:
            if src is node_b:
                src = new_node
            graph.add_edge(src, new_node, src=src, dst=new_node)

        for _, dst, data in out_edges:
            if dst is node_a:
                dst = new_node
            graph.add_edge(new_node, dst, src=new_node, dst=dst)

    return new_node


def to_supergraph(graph: nx.DiGraph):
    new_graph = nx.DiGraph(graph)
    while True:
        for src, dst in new_graph.edges():
            if len(list(new_graph.successors(src))) == 1 and len(list(new_graph.predecessors(dst))) == 1:
                if src is not dst:
                    merge_graph_nodes(new_graph, src, dst)
                    break
        else:
            break

    return new_graph
