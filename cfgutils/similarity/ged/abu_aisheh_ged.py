# Based on the default GED algorithm found in Networkx which is based on the following paper:
# "An Exact Graph Edit Distance Algorithm for Solving Pattern Recognition Problems" by Abu-Aisheh et al.
#

import logging

import networkx as nx

from cfgutils.os_utils import timeout
from cfgutils.similarity.ged import INVALID_CHOICE_PENALTY, collect_graph_roots

_l = logging.getLogger(__name__)
MAX_NODES_FOR_EXACT_GED = 12


#
# Edit distance
#

def ged_max(g1, g2):
    return len(g1.nodes) + len(g1.edges) + len(g2.nodes) + len(g2.edges)


def ged_exact(g1, g2, with_timeout=10, check_max=False):
    """
    Computes the exact Graph Edit Distance for two graphs. On the event of a timeout,
    a score of None is returned.
    """
    if check_max and (len(g1.nodes) > MAX_NODES_FOR_EXACT_GED or len(g2.nodes) > MAX_NODES_FOR_EXACT_GED):
        return None

    return graph_edit_distance_core_analysis(g1, g2, with_timeout=with_timeout, exact_score=True)


def ged_upperbound(g1, g2, with_timeout=5):
    """
    Does a single iterations of the GED algorithm and returns the upperbound.
    Note: this is not the max possible score.
    """
    return graph_edit_distance_core_analysis(g1, g2, upperbound_approx=True, with_timeout=with_timeout)


def ged_explained(g1, g2, print_explanation=True, only_addrs=True):
    """

    Possible operations:
    ins(node)
    del(node)
    ins((node1, node2))
    del((node1, node2))
    """
    paths, cost = nx.optimal_edit_paths(g1, g2, node_subst_cost=_cfg_node_sub_cost, edge_subst_cost=_cfg_edge_sub_cost)
    chosen_path = paths[0]
    vertex_edits = chosen_path[0]
    edge_edits = chosen_path[1]
    human_v_edits = []
    human_e_edits = []
    human_v_swaps = []

    for v_edit in vertex_edits:
        v1, v2 = v_edit
        if v1 is None and v2 is not None:
            human_v_edits.append(f"ins({v2.__repr__() if not only_addrs else v2.addr})")
        elif v1 is not None and v2 is None:
            human_v_edits.append(f"del({v1.__repr__() if not only_addrs else v1.addr})")
        elif v2 is not None and v1 is not None:
            human_v_swaps.append(f"{v1.__repr__()} = {v2.__repr__()}")

    for e_edit in edge_edits:
        e1, e2 = e_edit
        if e1 is None and e2 is not None:
            e_str = f"ins({e2})" if not only_addrs else f"ins({e2[0].addr}, {e2[1].addr})"
            human_e_edits.append(e_str)
        elif e1 is not None and e2 is None:
            e_str = f"del({e1})" if not only_addrs else f"del({e1[0].addr}, {e1[1].addr})"
            human_e_edits.append(e_str)
        else:
            pass

    # sort explanations by del always being first
    human_v_edits = list(sorted(human_v_edits, key=lambda x: x.startswith("del"), reverse=True))
    human_e_edits = list(sorted(human_e_edits, key=lambda x: x.startswith("del"), reverse=True))

    if print_explanation:
        print("\n=====================================================================")
        print(f"There are {len(paths)} possible edit strategies to turn g1 into g2")
        print(f"in {cost} steps. Showing the first one:")
        print("=====================================================================")

        if human_v_swaps:
            print("Vertex Swaps (free): ")
            for v_swap in human_v_swaps:
                print(f"    {v_swap}")
        print("Vertex Edits:")
        for v_edit in human_v_edits:
            print(f"    {v_edit}")
        print("Edge Edits:")
        for e_edit in human_e_edits:
            print(f"    {e_edit}")
        print("=====================================================================")

    # reupdate lists to only have addrs

    return human_v_edits + human_e_edits

#
# Updates to the original GED algorithm
#


def _cfg_node_sub_cost(*args, penalize_root_exit_edits=True):
    """
    Makes it illegal to delete function start nodes or end nodes
    """
    node_attrs = args[:2]
    n1, n2 = node_attrs[0].get('node', None), node_attrs[1].get('node', None)
    # 0 is the normal cost of a substitution that is valid, so we only update if we tried an illegal
    # subst on starts or exits
    cost = 0
    if n1 is None or n2 is None:
        print("HIT A CASE OF SOMEONE BEING NONE!")

    if penalize_root_exit_edits and (n1 and n2):
        if n1.is_entrypoint and not n2.is_entrypoint:
            cost = INVALID_CHOICE_PENALTY
        elif n1.is_exitpoint and not n2.is_exitpoint:
            cost = INVALID_CHOICE_PENALTY
        elif n2.is_entrypoint and not n1.is_entrypoint:
            cost = INVALID_CHOICE_PENALTY
        elif n2.is_exitpoint and not n1.is_exitpoint:
            cost = INVALID_CHOICE_PENALTY

    return cost


def _cfg_edge_sub_cost(*args, penalize_root_exit_edits=True):
    edge_attrs = args[:2]
    s1, d1 = edge_attrs[0].get('src', None), edge_attrs[0].get('dst', None)
    s2, d2 = edge_attrs[1].get('src', None), edge_attrs[1].get('dst', None)
    cost = 0
    if penalize_root_exit_edits and s1 and d1 and s2 and d2:
        node_pairs = {
            s1: s2,
            s2: s1,
            d1: d2,
            d2: d1,
        }

        for n1, n2 in node_pairs.items():
            if n1.is_entrypoint and not n2.is_entrypoint:
                cost = INVALID_CHOICE_PENALTY
            elif n1.is_exitpoint and not n2.is_exitpoint:
                cost = INVALID_CHOICE_PENALTY
            elif n2.is_entrypoint and not n1.is_entrypoint:
                cost = INVALID_CHOICE_PENALTY
            elif n2.is_exitpoint and not n1.is_exitpoint:
                cost = INVALID_CHOICE_PENALTY

            # early exit
            if cost != 0:
                break

    return cost


def graph_edit_distance_core_analysis(
    g1: nx.DiGraph, g2: nx.DiGraph, is_cfg=True, upperbound_approx=False, exact_score=False, with_timeout=10,
    penalize_root_exit_edits=True, recover_on_invalid_edits=True
):
    roots = collect_graph_roots(g1, g2) if is_cfg else None

    _node_sub_cost = None
    _edge_sub_cost = None
    if is_cfg and penalize_root_exit_edits:
        _node_sub_cost = _cfg_node_sub_cost
        _edge_sub_cost = _cfg_edge_sub_cost

    if exact_score or upperbound_approx:
        try:
            with timeout(seconds=with_timeout):
                if upperbound_approx:
                    dist = next(nx.optimize_graph_edit_distance(
                        g1, g2, node_subst_cost=_node_sub_cost, edge_subst_cost=_edge_sub_cost,
                    ))
                else:
                    dist = nx.graph_edit_distance(
                        g1, g2, roots=roots, node_subst_cost=_node_sub_cost, edge_subst_cost=_edge_sub_cost,
                    )
        except TimeoutError:
            dist = None
    else:
        dist = nx.graph_edit_distance(
            g1, g2, roots=roots, timeout=with_timeout, node_subst_cost=_node_sub_cost, edge_subst_cost=_edge_sub_cost,
        )

    # sometimes the score can be computed wrong, which we can fix with a recompute ONCE
    if dist is not None and dist >= INVALID_CHOICE_PENALTY and recover_on_invalid_edits:
        dist = graph_edit_distance_core_analysis(
            g1, g2, is_cfg=is_cfg, upperbound_approx=upperbound_approx, exact_score=exact_score,
            with_timeout=with_timeout, penalize_root_exit_edits=False, recover_on_invalid_edits=False
        )

    return dist
