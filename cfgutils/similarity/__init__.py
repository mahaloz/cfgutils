import networkx as nx
from cfgutils.os_utils import timeout

#
# Isomorphism
#

def fast_is_isomorphic(g1, g2):
    if len(g1.nodes) != len(g2.nodes):
        return False
    if len(g1.edges) != len(g2.edges):
        return False

    is_iso = False
    try:
        with timeout(seconds=2):
            is_iso = nx.is_isomorphic(g1, g2)
    except TimeoutError:
        pass

    return is_iso



from cfgutils.similarity.ged.abu_aisheh_ged import (
    ged_exact, ged_max, ged_upperbound, ged_explained, graph_edit_distance_core_analysis
)
from cfgutils.similarity.ged.basque_cfged import cfg_edit_distance
from cfgutils.similarity.ged.hu_cfged import hu_cfged
from cfgutils.similarity.block_matcher_base import BlockMatcherBase
