from collections import defaultdict
import logging
from typing import List, Optional, Union

import networkx

from .graph_region import GraphRegion
from ..data.generic_block import GenericBlock
from ..dominator import dfs_back_edges, subgraph_between_nodes, dominates, shallow_reverse
from ..sorting import quasi_topological_sort_nodes


l = logging.getLogger(name=__name__)


class RegionIdentifier:
    """
    Identifies regions within a function.
    """

    def __init__(
        self,
        graph,
        largest_successor_tree_outside_loop=True,
        complete_successors=False,
        block_cls=None
    ):
        self._graph = graph
        if block_cls is not None:
            self._block_cls = block_cls
        else:
            node = list(self._graph)[0]
            self._block_cls = node.__class__

        if not issubclass(self._block_cls, GenericBlock):
            raise ValueError("Graph must contain nodes that are subclasses of GenericBlock!")

        self.regions_by_block_addrs = []

        self.region = None
        self._start_node = None
        self._loop_headers: Optional[List] = None
        self._largest_successor_tree_outside_loop = largest_successor_tree_outside_loop
        self._complete_successors = complete_successors

        self._analyze()

    @staticmethod
    def slice_graph(graph, node, frontier, include_frontier=False):
        """
        Generate a slice of the graph from the head node to the given frontier.

        :param networkx.DiGraph graph: The graph to work on.
        :param node: The starting node in the graph.
        :param frontier: A list of frontier nodes.
        :param bool include_frontier: Whether the frontier nodes are included in the slice or not.
        :return: A subgraph.
        :rtype: networkx.DiGraph
        """

        subgraph = subgraph_between_nodes(graph, node, frontier, include_frontier=include_frontier)
        if not list(subgraph.nodes):
            # HACK: FIXME: for infinite loop nodes, this would return an empty set, so we include the loop body itself
            # Make sure this makes sense (EDG thinks it does)
            if (node, node) in graph.edges:
                subgraph.add_edge(node, node, src=node, dst=node)
        return subgraph

    def _analyze(self):

        # make a copy of the graph
        graph = networkx.DiGraph(self._graph)

        # preprocess: make it a super graph
        self._make_supergraph(graph)

        self._start_node = self._get_start_node(graph)

        # preprocess: find loop headers
        self._loop_headers = self._find_loop_headers(graph)

        self.region = self._make_regions(graph)

        # make regions into block address lists
        self.regions_by_block_addrs = self._make_regions_by_block_addrs()

    def _make_regions_by_block_addrs(self) -> List[List[int]]:
        """
        Creates a list of addr lists representing each region without recursion. A single region is defined
        as a set of only blocks, no Graphs containing nested regions. The list contains the address of each
        block in the region, including the heads of each recursive region.

        @return: List of addr lists
        """

        work_list = [self.region]
        block_only_regions = []
        seen_regions = set()
        while work_list:
            children_regions = []
            for region in work_list:
                children_blocks = []
                for node in region.graph.nodes:
                    if isinstance(node, GenericBlock):
                        children_blocks.append(node.addr)
                    elif isinstance(node, GraphRegion):
                        if node not in seen_regions:
                            children_regions.append(node)
                            children_blocks.append(node.head.addr)
                            seen_regions.add(node)
                    else:
                        continue

                if children_blocks:
                    block_only_regions.append(children_blocks)

            work_list = children_regions

        return block_only_regions

    def _get_start_node(self, graph: networkx.DiGraph):
        try:
            return next(n for n in graph.nodes() if graph.in_degree(n) == 0)
        except StopIteration:
            pass

        try:
            return next(n for n in graph.nodes() if n.addr == self.function.addr)
        except StopIteration as ex:
            raise RuntimeError("Cannot find the start node from the graph!") from ex

    def _test_reducibility(self):

        # make a copy of the graph
        graph = networkx.DiGraph(self._graph)

        # preprocess: make it a super graph
        self._make_supergraph(graph)

        while True:

            changed = False

            # find a node with a back-edge, remove the edge (deleting the loop), and replace it with a MultiNode
            changed |= self._remove_self_loop(graph)

            # find a node that has only one predecessor, and merge it with its predecessor (replace them with a
            # MultiNode)
            changed |= self._merge_single_entry_node(graph)

            if not changed:
                # a fixed-point is reached
                break

        # Flow graph reducibility, Hecht and Ullman
        if len(graph.nodes) == 1:
            return True

        return False

    def _make_supergraph(self, graph: networkx.DiGraph):
        #return graph
        while True:
            for src, dst, data in graph.edges(data=True):
                type_ = data.get("type", None)
                if type_ == "fake_return":
                    if len(list(graph.successors(src))) == 1 and len(list(graph.predecessors(dst))) == 1:
                        self._merge_nodes(graph, src, dst, force_multinode=True)
                        break
                elif type_ == "call":
                    graph.remove_node(dst)
                    break
            else:
                break

    def _find_loop_headers(self, graph: networkx.DiGraph) -> List:

        heads = {t for _, t in dfs_back_edges(graph, self._start_node)}
        return quasi_topological_sort_nodes(graph, heads)

    def _find_initial_loop_nodes(self, graph: networkx.DiGraph, head):
        # TODO optimize
        latching_nodes = {s for s, t in dfs_back_edges(graph, self._start_node) if t == head}
        loop_subgraph = self.slice_graph(graph, head, latching_nodes, include_frontier=True)

        # special case: any node with more than two non-self successors are probably the head of a switch-case. we
        # should include all successors into the loop subgraph.
        while True:
            updated = False
            for node in list(loop_subgraph):
                nonself_successors = [succ for succ in graph.successors(node) if succ is not node]
                if len(nonself_successors) > 2:
                    for succ in nonself_successors:
                        if not loop_subgraph.has_edge(node, succ):
                            updated = True
                            loop_subgraph.add_edge(node, succ, src=node, dst=succ)
            if not updated:
                break

        nodes = set(loop_subgraph)
        return nodes

    def _refine_loop(self, graph: networkx.DiGraph, head, initial_loop_nodes, initial_exit_nodes):
        if len(initial_exit_nodes) <= 1:
            return initial_loop_nodes, initial_exit_nodes

        refined_loop_nodes = initial_loop_nodes.copy()
        refined_exit_nodes = initial_exit_nodes.copy()

        # simple optimization: include all single-in-degree successors of existing loop nodes
        while True:
            added = set()
            for exit_node in list(refined_exit_nodes):
                if graph.in_degree[exit_node] == 1 and graph.out_degree[exit_node] <= 1:
                    added.add(exit_node)
                    refined_loop_nodes.add(exit_node)
                    refined_exit_nodes |= {
                        succ for succ in graph.successors(exit_node) if succ not in refined_loop_nodes
                    }
                    refined_exit_nodes.remove(exit_node)
            if not added:
                break

        if len(refined_exit_nodes) <= 1:
            return refined_loop_nodes, refined_exit_nodes

        idom = networkx.immediate_dominators(graph, head)

        new_exit_nodes = refined_exit_nodes
        # a graph with only initial exit nodes and new loop nodes that are reachable from at least one initial exit
        # node.
        subgraph = networkx.DiGraph()

        sorted_refined_exit_nodes = quasi_topological_sort_nodes(graph, refined_exit_nodes)
        while len(sorted_refined_exit_nodes) > 1 and new_exit_nodes:
            # visit each node in refined_exit_nodes once and determine which nodes to consider as loop nodes
            candidate_nodes = {}
            for n in list(sorted_refined_exit_nodes):
                if all((pred is n or pred in refined_loop_nodes) for pred in graph.predecessors(n)) and dominates(
                        idom, head, n
                ):
                    to_add = set(graph.successors(n)) - refined_loop_nodes
                    candidate_nodes[n] = to_add

            # visit all candidate nodes and only consider candidates that will not be added as exit nodes
            all_new_exit_candidates = set()
            for new_exit_candidates in candidate_nodes.values():
                all_new_exit_candidates |= new_exit_candidates

            # to guarantee progressing, we must ensure all_new_exit_candidates cannot contain all candidate nodes
            if all(n in all_new_exit_candidates for n in candidate_nodes):
                all_new_exit_candidates = set()

            # do the actual work
            new_exit_nodes = set()
            for n in candidate_nodes:
                if n in all_new_exit_candidates:
                    continue
                refined_loop_nodes.add(n)
                sorted_refined_exit_nodes.remove(n)
                to_add = set(graph.successors(n)) - refined_loop_nodes
                new_exit_nodes |= to_add
                for succ in to_add:
                    subgraph.add_edge(n, succ, src=n, dst=succ)

            sorted_refined_exit_nodes += list(new_exit_nodes)
            sorted_refined_exit_nodes = list(set(sorted_refined_exit_nodes))
            sorted_refined_exit_nodes = quasi_topological_sort_nodes(graph, sorted_refined_exit_nodes)

        refined_exit_nodes = set(sorted_refined_exit_nodes)
        refined_loop_nodes = refined_loop_nodes - refined_exit_nodes

        if self._largest_successor_tree_outside_loop and not refined_exit_nodes:
            # figure out the new successor tree with the highest number of nodes
            initial_exit_to_newnodes = defaultdict(set)
            newnode_to_initial_exits = defaultdict(set)
            for initial_exit in initial_exit_nodes:
                if initial_exit in subgraph:
                    for _, succs in networkx.bfs_successors(subgraph, initial_exit):
                        initial_exit_to_newnodes[initial_exit] |= set(succs)
                        for succ in succs:
                            newnode_to_initial_exits[succ].add(initial_exit)

            for newnode, exits in newnode_to_initial_exits.items():
                for exit_ in exits:
                    initial_exit_to_newnodes[exit_].add(newnode)
            if initial_exit_to_newnodes:
                tree_sizes = {exit_: len(initial_exit_to_newnodes[exit_]) for exit_ in initial_exit_to_newnodes}
                max_tree_size = max(tree_sizes.values())
                if list(tree_sizes.values()).count(max_tree_size) == 1:
                    tree_size_to_exit = {v: k for k, v in tree_sizes.items()}
                    max_size_exit = tree_size_to_exit[max_tree_size]
                    if all(len(newnode_to_initial_exits[nn]) == 1 for nn in initial_exit_to_newnodes[max_size_exit]):
                        refined_loop_nodes = (
                                refined_loop_nodes - initial_exit_to_newnodes[max_size_exit] - {max_size_exit}
                        )
                        refined_exit_nodes.add(max_size_exit)

        return refined_loop_nodes, refined_exit_nodes

    def _remove_self_loop(self, graph: networkx.DiGraph):

        r = False

        while True:
            for node in graph.nodes():
                if node in graph[node]:
                    # found a self loop
                    self._remove_node(graph, node)
                    r = True
                    break
            else:
                break

        return r

    def _merge_single_entry_node(self, graph: networkx.DiGraph):

        r = False

        while True:
            for node in networkx.dfs_postorder_nodes(graph):
                preds = graph.predecessors(node)
                if len(preds) == 1:
                    # merge the two nodes
                    self._absorb_node(graph, preds[0], node)
                    r = True
                    break
            else:
                break

        return r

    def _make_regions(self, graph: networkx.DiGraph):

        structured_loop_headers = set()
        new_regions = []

        # FIXME: _get_start_node() will fail if the graph is just a loop

        # Find all loops
        while True:
            restart = False

            self._start_node = self._get_start_node(graph)

            # Start from loops
            for node in list(reversed(self._loop_headers)):
                if node in structured_loop_headers:
                    continue
                if node not in graph:
                    continue
                region = self._make_cyclic_region(node, graph)
                if region is None:
                    # failed to struct the loop region - remove the header node from loop headers
                    l.debug(
                        "Failed to structure a loop region starting at %#x. Remove it from loop headers.", node.addr
                    )
                    self._loop_headers.remove(node)
                else:
                    l.debug("Structured a loop region %r.", region)
                    new_regions.append(region)
                    structured_loop_headers.add(node)
                    restart = True
                    break

            if restart:
                continue

            break

        new_regions.append(GraphRegion(self._get_start_node(graph), graph, None, None, False, None))

        l.debug("Identified %d loop regions.", len(structured_loop_headers))
        l.debug("No more loops left. Start structuring acyclic regions.")
        # No more loops left. Structure acyclic regions.
        while new_regions:
            region = new_regions.pop(0)
            head = region.head
            subgraph = region.graph

            failed_region_attempts = set()
            while self._make_acyclic_region(
                    head, subgraph, region.graph_with_successors, failed_region_attempts, region.cyclic
            ):
                if head not in subgraph:
                    # update head
                    head = next(iter(n for n in subgraph.nodes() if n.addr == head.addr))

            head = next(iter(n for n in subgraph.nodes() if n.addr == head.addr))
            region.head = head

        if len(graph.nodes()) == 1 and isinstance(list(graph.nodes())[0], GraphRegion):
            return list(graph.nodes())[0]
        # create a large graph region
        new_head = self._get_start_node(graph)
        region = GraphRegion(new_head, graph, None, None, False, None)
        return region

    #
    # Cyclic regions
    #

    def _make_cyclic_region(self, head, graph: networkx.DiGraph):

        l.debug("Found cyclic region at %#08x", head.addr)
        initial_loop_nodes = self._find_initial_loop_nodes(graph, head)
        l.debug("Initial loop nodes %s", self._dbg_block_list(initial_loop_nodes))

        # Make sure no other loops are contained in the current loop
        if {n for n in initial_loop_nodes if n.addr != head.addr}.intersection(self._loop_headers):
            return None

        normal_entries = {n for n in graph.predecessors(head) if n not in initial_loop_nodes}
        abnormal_entries = set()
        for n in initial_loop_nodes:
            if n == head:
                continue
            preds = set(graph.predecessors(n))
            abnormal_entries |= preds - initial_loop_nodes
        l.debug("Normal entries %s", self._dbg_block_list(normal_entries))
        l.debug("Abnormal entries %s", self._dbg_block_list(abnormal_entries))

        initial_exit_nodes = set()
        for n in initial_loop_nodes:
            succs = set(graph.successors(n))
            initial_exit_nodes |= succs - initial_loop_nodes

        l.debug("Initial exit nodes %s", self._dbg_block_list(initial_exit_nodes))

        refined_loop_nodes, refined_exit_nodes = self._refine_loop(graph, head, initial_loop_nodes, initial_exit_nodes)
        l.debug("Refined loop nodes %s", self._dbg_block_list(refined_loop_nodes))
        l.debug("Refined exit nodes %s", self._dbg_block_list(refined_exit_nodes))

        # make sure there is a jump statement to the outside at the end of each node going to exit nodes.
        # this jump statement will be rewritten to a break statement during structuring.
        #for exit_node in refined_exit_nodes:
        #    for pred in graph.predecessors(exit_node):
        #        if pred in refined_loop_nodes:
        #            self._ensure_jump_at_loop_exit_ends(pred)

        if len(refined_exit_nodes) > 1:
            # self._get_start_node(graph)
            node_post_order = list(networkx.dfs_postorder_nodes(graph, head))
            sorted_exit_nodes = sorted(list(refined_exit_nodes), key=node_post_order.index)
            normal_exit_node = sorted_exit_nodes[0]
            abnormal_exit_nodes = set(sorted_exit_nodes[1:])
        else:
            normal_exit_node = next(iter(refined_exit_nodes)) if len(refined_exit_nodes) > 0 else None
            abnormal_exit_nodes = set()

        return self._abstract_cyclic_region(
            graph, refined_loop_nodes, head, normal_entries, abnormal_entries, normal_exit_node, abnormal_exit_nodes
        )

    #
    # Acyclic regions
    #

    def _make_acyclic_region(self, head, graph: networkx.DiGraph, secondary_graph, failed_region_attempts, cyclic):
        # pre-processing

        # we need to create a copy of the original graph if
        # - there are in edges to the head node, or
        # - there are more than one end nodes

        head_inedges = list(graph.in_edges(head))
        if head_inedges:
            # we need a copy of the graph to remove edges coming into the head
            graph_copy = networkx.DiGraph(graph)
            # remove any in-edge to the head node
            for src, _ in head_inedges:
                graph_copy.remove_edge(src, head)
        else:
            graph_copy = graph

        endnodes = [node for node in graph_copy.nodes() if graph_copy.out_degree(node) == 0]
        if len(endnodes) == 0:
            # sanity check: there should be at least one end node
            #l.critical("No end node is found in a supposedly acyclic graph. Is it really acyclic?")
            return False

        add_dummy_endnode = False
        if len(endnodes) > 1:
            # if this graph has multiple end nodes: create a single end node
            add_dummy_endnode = True
        elif head_inedges and len(endnodes) == 1 and endnodes[0] not in list(graph.predecessors(head)):
            # special case: there are in-edges to head, but the only end node is not a predecessor to head.
            # in this case, we will want to put the end node and a predecessor of the head into the same region.
            add_dummy_endnode = True

        if add_dummy_endnode:
            # we need a copy of the graph!
            graph_copy = networkx.DiGraph(graph_copy)
            dummy_endnode = "DUMMY_ENDNODE"
            for endnode in endnodes:
                graph_copy.add_edge(endnode, dummy_endnode, src=endnode, dst=dummy_endnode)
            endnodes = [dummy_endnode]
        else:
            dummy_endnode = None

        # compute dominator tree
        doms = networkx.immediate_dominators(graph_copy, head)

        # compute post-dominator tree
        inverted_graph = shallow_reverse(graph_copy)
        postdoms = networkx.immediate_dominators(inverted_graph, endnodes[0])

        # dominance frontiers
        df = networkx.algorithms.dominance_frontiers(graph_copy, head)

        # visit the nodes in post-order
        for node in networkx.dfs_postorder_nodes(graph_copy, source=head):
            if node is dummy_endnode:
                # skip the dummy endnode
                continue
            if cyclic and node is head:
                continue

            out_degree = graph_copy.out_degree[node]
            if out_degree == 0:
                # the root element of the region hierarchy should always be a GraphRegion,
                # so we transform it into one, if necessary
                if graph_copy.in_degree(node) == 0 and not isinstance(node, GraphRegion):
                    subgraph = networkx.DiGraph()
                    subgraph.add_node(node, node=node)
                    self._abstract_acyclic_region(
                        graph, GraphRegion(node, subgraph, None, None, False, None), [], secondary_graph=secondary_graph
                    )
                continue

            # test if this node is an entry to a single-entry, single-successor region
            levels = 0
            postdom_node = postdoms.get(node, None)
            while postdom_node is not None:
                if (node, postdom_node) not in failed_region_attempts:
                    if self._check_region(graph_copy, node, postdom_node, doms, df):
                        frontier = [postdom_node]
                        region = self._compute_region(graph_copy, node, frontier, dummy_endnode=dummy_endnode)
                        if region is not None:
                            # update region.graph_with_successors
                            if secondary_graph is not None:
                                if self._complete_successors:
                                    for nn in list(region.graph_with_successors.nodes):
                                        original_successors = secondary_graph.successors(nn)
                                        for succ in original_successors:
                                            if not region.graph_with_successors.has_edge(nn, succ):
                                                region.graph_with_successors.add_edge(nn, succ, src=nn, dst=succ)
                                                region.successors.add(succ)
                                else:
                                    for nn in list(region.graph_with_successors.nodes):
                                        original_successors = secondary_graph.successors(nn)
                                        for succ in original_successors:
                                            if succ not in graph_copy:
                                                # the successor wasn't added to the graph because it does not belong
                                                # to the frontier. we backpatch the successor graph here.
                                                region.graph_with_successors.add_edge(nn, succ, src=nn, dst=succ)
                                                region.successors.add(succ)

                            # l.debug("Walked back %d levels in postdom tree.", levels)
                            l.debug("Node %r, frontier %r.", node, frontier)
                            # l.debug("Identified an acyclic region %s.", self._dbg_block_list(region.graph.nodes()))
                            self._abstract_acyclic_region(
                                graph, region, frontier, dummy_endnode=dummy_endnode, secondary_graph=secondary_graph
                            )
                            # assert dummy_endnode not in graph
                            return True

                failed_region_attempts.add((node, postdom_node))
                if not dominates(doms, node, postdom_node):
                    break
                if postdom_node is postdoms.get(postdom_node, None):
                    break
                postdom_node = postdoms.get(postdom_node, None)
                levels += 1
            # l.debug("Walked back %d levels in postdom tree and did not find anything for %r. Next.", levels, node)

        return False

    @staticmethod
    def _check_region(graph, start_node, end_node, doms, df):
        """

        :param graph:
        :param start_node:
        :param end_node:
        :param doms:
        :param df:
        :return:
        """

        # if the exit node is the header of a loop that contains the start node, the dominance frontier should only
        # contain the exit node.
        if not dominates(doms, start_node, end_node):
            frontier = df.get(start_node, set())
            for node in frontier:
                if node is not start_node and node is not end_node:
                    return False

        # no edges should enter the region.
        for node in df.get(end_node, set()):
            if dominates(doms, start_node, node) and node is not end_node:
                return False

        # no edges should leave the region.
        for node in df.get(start_node, set()):
            if node is start_node or node is end_node:
                continue
            if node not in df.get(end_node, set()):
                return False
            for pred in graph.predecessors(node):
                if dominates(doms, start_node, pred) and not dominates(doms, end_node, pred):
                    return False

        return True

    @staticmethod
    def _compute_region(graph, node, frontier, include_frontier=False, dummy_endnode=None):

        subgraph = networkx.DiGraph()
        frontier_edges = []
        queue = [node]
        traversed = set()

        while queue:
            node_ = queue.pop()
            if node_ in frontier:
                continue
            traversed.add(node_)
            subgraph.add_node(node_, node=node_)

            for succ in graph.successors(node_):
                edge_data = graph.get_edge_data(node_, succ)

                if node_ in frontier and succ in traversed:
                    if include_frontier:
                        # if frontier nodes are included, do not keep traversing their successors
                        # however, if it has an edge to an already traversed node, we should add that edge
                        subgraph.add_edge(node_, succ, src=node_, dst=succ)
                    else:
                        frontier_edges.append((node_, succ, edge_data))
                    continue

                if succ is dummy_endnode:
                    continue

                if succ in frontier:
                    if not include_frontier:
                        # skip all frontier nodes
                        frontier_edges.append((node_, succ, edge_data))
                        continue
                subgraph.add_edge(node_, succ, src=node_, dst=succ)
                if succ in traversed:
                    continue
                queue.append(succ)

        if dummy_endnode is not None:
            frontier = {n for n in frontier if n is not dummy_endnode}

        if subgraph.number_of_nodes() > 1:
            subgraph_with_frontier = networkx.DiGraph(subgraph)
            for src, dst, edge_data in frontier_edges:
                if dst is not dummy_endnode:
                    subgraph_with_frontier.add_edge(src, dst, src=src, dst=dst)
            # assert dummy_endnode not in frontier
            # assert dummy_endnode not in subgraph_with_frontier
            return GraphRegion(node, subgraph, frontier, subgraph_with_frontier, False, None)
        else:
            return None

    def _abstract_acyclic_region(
            self, graph: networkx.DiGraph, region, frontier, dummy_endnode=None, secondary_graph=None
    ):

        in_edges = self._region_in_edges(graph, region, data=True)
        out_edges = self._region_out_edges(graph, region, data=True)

        nodes_set = set()
        for node_ in list(region.graph.nodes()):
            nodes_set.add(node_)
            if node_ is not dummy_endnode:
                graph.remove_node(node_)

        graph.add_node(region, node=region)

        for src, _, data in in_edges:
            if src not in nodes_set:
                graph.add_edge(src, region, src=src, dst=region)

        for _, dst, data in out_edges:
            if dst not in nodes_set:
                graph.add_edge(region, dst, src=region, dst=dst)

        if frontier:
            for frontier_node in frontier:
                if frontier_node is not dummy_endnode:
                    graph.add_edge(region, frontier_node, src=region, dst=frontier_node)

        if secondary_graph is not None:
            self._abstract_acyclic_region(secondary_graph, region, {})

    @staticmethod
    def _abstract_cyclic_region(
            graph: networkx.DiGraph,
            loop_nodes,
            head,
            normal_entries,
            abnormal_entries,
            normal_exit_node,
            abnormal_exit_nodes,
    ):
        region = GraphRegion(head, None, None, None, True, None)

        subgraph = networkx.DiGraph()
        region_outedges = []

        delayed_edges = []

        full_graph = networkx.DiGraph()

        for node in loop_nodes:
            subgraph.add_node(node, node=node)
            in_edges = list(graph.in_edges(node, data=True))
            out_edges = list(graph.out_edges(node, data=True))

            for src, dst, data in in_edges:
                full_graph.add_edge(src, dst, src=src, dst=dst)
                if src in loop_nodes:
                    subgraph.add_edge(src, dst, src=src, dst=dst)
                elif src is region:
                    subgraph.add_edge(head, dst, src=head, dst=dst)
                elif src in normal_entries:
                    # graph.add_edge(src, region, **data)
                    delayed_edges.append((src, region, data))
                elif src in abnormal_entries:
                    data["region_dst_node"] = dst
                    # graph.add_edge(src, region, **data)
                    delayed_edges.append((src, region, data))
                else:
                    assert 0

            for src, dst, data in out_edges:
                full_graph.add_edge(src, dst, src=src, dst=dst)
                if dst in loop_nodes:
                    subgraph.add_edge(src, dst, src=src, dst=dst)
                elif dst is region:
                    subgraph.add_edge(src, head, src=src, dst=head)
                elif dst is normal_exit_node:
                    region_outedges.append((node, dst))
                    # graph.add_edge(region, dst, **data)
                    delayed_edges.append((region, dst, data))
                elif dst in abnormal_exit_nodes:
                    region_outedges.append((node, dst))
                    # data['region_src_node'] = src
                    # graph.add_edge(region, dst, **data)
                    delayed_edges.append((region, dst, data))
                else:
                    assert 0

        subgraph_with_exits = networkx.DiGraph(subgraph)
        for src, dst in region_outedges:
            subgraph_with_exits.add_edge(src, dst, src=src, dst=dst)
        region.graph = subgraph
        region.graph_with_successors = subgraph_with_exits
        if normal_exit_node is not None:
            region.successors = [normal_exit_node]
        else:
            region.successors = []
        region.successors += list(abnormal_exit_nodes)

        for node in loop_nodes:
            graph.remove_node(node)

        # add delayed edges
        graph.add_node(region, node=region)
        for src, dst, data in delayed_edges:
            graph.add_edge(src, dst, src=src, dst=dst)

        region.full_graph = full_graph

        return region

    @staticmethod
    def _region_in_edges(graph, region, data=False):

        return list(graph.in_edges(region.head, data=data))

    @staticmethod
    def _region_out_edges(graph, region, data=False):

        out_edges = []
        for node in region.graph.nodes():
            out_ = graph.out_edges(node, data=data)
            for _, dst, data_ in out_:
                if dst in region.graph:
                    continue
                out_edges.append((region, dst, data_))
        return out_edges

    def _remove_node(self, graph: networkx.DiGraph, node):  # pylint:disable=no-self-use
        graph.remove_node(node)

    def _merge_nodes(
            self, graph: networkx.DiGraph, node_a, node_b, force_multinode=False
    ):  # pylint:disable=no-self-use

        in_edges = list(graph.in_edges(node_a, data=True))
        out_edges = list(graph.out_edges(node_b, data=True))

        if not force_multinode and len(in_edges) <= 1 and len(out_edges) <= 1:
            # it forms a region by itself :-)
            new_node = None

        else:
            new_node = self._block_cls.merge_blocks(node_a, node_b)

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

        assert not node_a in graph
        assert not node_b in graph

    def _absorb_node(
            self, graph: networkx.DiGraph, node_mommy, node_kiddie, force_multinode=False
    ):  # pylint:disable=no-self-use

        in_edges_mommy = graph.in_edges(node_mommy, data=True)
        out_edges_mommy = graph.out_edges(node_mommy, data=True)
        out_edges_kiddie = graph.out_edges(node_kiddie, data=True)

        if not force_multinode and len(in_edges_mommy) <= 1 and len(out_edges_kiddie) <= 1:
            # it forms a region by itself :-)
            new_node = None

        else:
            new_node = self._block_cls.merge_blocks(node_mommy, node_kiddie)

        graph.remove_node(node_mommy)
        graph.remove_node(node_kiddie)

        if new_node is not None:
            graph.add_node(new_node, node=new_node)

            for src, _, data in in_edges_mommy:
                if src == node_kiddie:
                    src = new_node
                graph.add_edge(src, new_node, src=src, dst=new_node)

            for _, dst, data in out_edges_mommy:
                if dst == node_kiddie:
                    continue
                if dst == node_mommy:
                    dst = new_node
                graph.add_edge(new_node, dst, src=new_node, dst=dst)

            for _, dst, data in out_edges_kiddie:
                if dst == node_mommy:
                    dst = new_node
                graph.add_edge(new_node, dst, src=new_node, dst=dst)

        assert not node_mommy in graph
        assert not node_kiddie in graph

    @staticmethod
    def _dbg_block_list(blocks):
        return [(hex(b.addr) if hasattr(b, "addr") else repr(b)) for b in blocks]
