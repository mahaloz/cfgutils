import itertools
from collections import defaultdict
from typing import List, Dict, Tuple, Union

import networkx as nx

from ..sorting import quasi_topological_sort_nodes


class BlockMatcherBase:
    """
    This class takes two graphs and returns a dictionary of likley matches between the nodes in the two graphs.
    The key is nodes in g1 and the value is the corresponding node in g2. This class is expected to be used
    with two graphs you _know_ are implementing the same logic. This can happen in instances of a function being
    compiled with different optimization levels, or with different compilers.

    This implementation is based on the paper: "discovRE: Efficient Cross-Architecture Identification of Bugs
    in Binary Code" by Eschweiler et al. in NDSS 2016.
    """
    W_NO_ARITHMETIC_INS = 56.658
    W_NO_CALLS = 87.423
    W_NO_INS = 40.423
    W_NO_LOGIC_INS = 76.694
    W_NO_BRANCH_INS = 6.841
    W_STR_CONST = 11.998
    W_NUM_CONST = 15.382

    # guessed weights
    W_TOPO_DIST = 15.0  # as important a number matching across blocks

    TYP_NO_ARITHMETIC_INS = "arith_ins"
    TYP_NO_CALLS = "calls"
    TYP_NO_INS = "ins"
    TYP_NO_LOGIC_INS = "logic_ins"
    TYP_NO_BRANCH_INS = "branch_ins"
    TYP_STR_CONST = "str_consts"
    TYP_NUM_CONST = "num_consts"
    TYP_TOPO_DIST = "topo_dist"

    def __init__(self, g1: nx.DiGraph, g2: nx.DiGraph):
        self._g1 = g1
        self._g2 = g2
        self._g1_nodes = list(g1.nodes)
        self._g2_nodes = list(g2.nodes)
        self._topo_dist = {
            g1: self._generate_topological_dist_map(g1),
            g2: self._generate_topological_dist_map(g2)
        }

        self.mapping = {}

    def analyze(self):
        # TODO: add a way to first match nodes with exact call matches
        # TODO: add a way to match nodes with exact long string matches
        b1_b2_map, best_b2_scores = self.generate_similarities(get_best_inv_map=True)
        # first, map every b2 to the b1 that matches it best
        used_b2 = set()
        for b2, b1 in best_b2_scores.items():
            self.mapping[b1] = b2
            used_b2.add(b2)

        # then, map the rest of the b1s to the b2s that match them best
        for b1, b2_scores in b1_b2_map.items():
            if b1 in self.mapping:
                continue

            best_matches = sorted(b2_scores, key=b2_scores.get, reverse=True)
            for match in best_matches:
                if match not in used_b2:
                    self.mapping[b1] = match
                    used_b2.add(match)
                    break
            else:
                # if no match was found at all, we must be out of b2s
                break

    def generate_similarities(self, get_best_inv_map=False) -> \
            Union[Tuple[Dict[object, Dict[object, float]], Dict[object, float]], Dict[object, Dict[object, float]]]:
        b1_to_b2_scores = defaultdict(dict)
        best_b2_scores = {}
        for b1, b2 in itertools.product(self._g1_nodes, self._g2_nodes):
            b1_to_b2 = self.block_similarity(b1, b2, self._g1, self._g2)
            b1_to_b2_scores[b1][b2] = b1_to_b2
            best_b2_score, _ = best_b2_scores.get(b2, (0, None))
            if b1_to_b2 > best_b2_score:
                best_b2_scores[b2] = (b1_to_b2, b1)

        best_b2_scores = {k: v[1] for k, v in best_b2_scores.items()}
        if get_best_inv_map:
            return b1_to_b2_scores, best_b2_scores
        else:
            return b1_to_b2_scores

    def block_similarity(self, b1, b2, g1, g2) -> float:
        feat_func_map = {
            self.get_number_of_arithmetic_ins: self.W_NO_ARITHMETIC_INS,
            self.get_number_of_calls: self.W_NO_CALLS,
            self.get_number_of_ins: self.W_NO_INS,
            self.get_number_of_logic_ins: self.W_NO_LOGIC_INS,
            self.get_number_of_branch_ins: self.W_NO_BRANCH_INS,
            self.get_topological_dist: self.W_TOPO_DIST
        }
        listed_feat_func_map = {
            self.get_str_consts: self.W_STR_CONST,
            self.get_num_consts: self.W_NUM_CONST
        }

        numerator = 0
        denominator = 0
        # features that are a single value
        for feat_func, weight in feat_func_map.items():
            f1, f2 = feat_func(b1, g1), feat_func(b2, g2)
            numerator += weight * abs(f1 - f2)
            denominator += weight * max(f1, f2)

        # features that are a list
        for feat_func, weight in listed_feat_func_map.items():
            f1, f2 = feat_func(b1, g1), feat_func(b2, g2)
            # jaccard similarity
            numerator += (len(set.union(set(f1), set(f2))) - len(set.intersection(set(f1), set(f2)))) * weight
            denominator += len(set.union(set(f1), set(f2))) * weight

        # denominator == 0 when two empty blocks compared, they are equal
        dissimilarity = (numerator / denominator) if denominator else 0
        return 1 - dissimilarity

    @staticmethod
    def _generate_topological_dist_map(graph: nx.DiGraph) -> Dict[object, int]:
        return {
            node: dist for dist, node in enumerate(quasi_topological_sort_nodes(graph))
        }

    def get_topological_dist(self, block, graph: nx.DiGraph):
        return self._topo_dist[graph][block]

    #
    # Must be implemented by the user
    #

    def get_number_of_arithmetic_ins(self, block, graph) -> int:
        raise NotImplementedError()

    def get_number_of_calls(self, block, graph) -> int:
        raise NotImplementedError()

    def get_number_of_ins(self, block, graph) -> int:
        raise NotImplementedError()

    def get_number_of_logic_ins(self, block, graph) -> int:
        raise NotImplementedError()

    def get_number_of_branch_ins(self, block, graph) -> int:
        raise NotImplementedError()

    def get_str_consts(self, block, graph) -> List[str]:
        raise NotImplementedError()

    def get_num_consts(self, block, graph) -> List[int]:
        raise NotImplementedError()
