from cfgutils.sorting import cfg_root_node

INVALID_CHOICE_PENALTY = 100000

#
# Helpers
#


def collect_graph_roots(g1, g2):
    # first, depend on the function start node
    g1_start, g2_start = cfg_root_node(g1), cfg_root_node(g2)
    if g1_start is not None and g2_start is not None:
        roots = (g1_start, g2_start,)
    else:
        roots = None

    # second attempt, use predecessors
    if roots is None:
        g1_starts = list(node for node in g1.nodes if len(list(g1.predecessors(node))) == 0)
        g2_starts = list(node for node in g2.nodes if len(list(g2.predecessors(node))) == 0)
        if len(g1_starts) == 1 == len(g2_starts):
            roots = (g1_starts[0], g2_starts[0],)

    return roots


