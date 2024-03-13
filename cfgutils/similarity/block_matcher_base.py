import itertools
from collections import defaultdict
from typing import List, Dict

import networkx as nx


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

    TYP_NO_ARITHMETIC_INS = "arith_ins"
    TYP_NO_CALLS = "calls"
    TYP_NO_INS = "ins"
    TYP_NO_LOGIC_INS = "logic_ins"
    TYP_NO_BRANCH_INS = "branch_ins"
    TYP_STR_CONST = "str_consts"
    TYP_NUM_CONST = "num_consts"

    def __init__(self, g1: nx.DiGraph, g2: nx.DiGraph):
        self._g1 = g1
        self._g2 = g2
        self._g1_nodes = list(g1.nodes)
        self._g2_nodes = list(g2.nodes)

        self.mapping = {}

    def analyze(self):
        # TODO: add a way to first match nodes with exact call matches
        # TODO: add a way to match nodes with exact long string matches
        sim_map = self.generate_similarities()
        for b1, b2_scores in sim_map.items():
            # TODO: what happens if b1->b2 score is lower than another node could match to in b1?
            best_match = min(b2_scores, key=b2_scores.get)
            self.mapping[b1] = best_match

    def generate_similarities(self) -> Dict[object, Dict[object, float]]:
        scores = defaultdict(dict)
        for b1, b2 in itertools.product(self._g1_nodes, self._g2_nodes):
            scores[b1][b2] = self.block_similarity(b1, b2, self._g1, self._g2)

        return scores

    def block_similarity(self, b1, b2, g1, g2) -> float:
        feat_func_map = {
            self.get_number_of_arithmetic_ins: self.W_NO_ARITHMETIC_INS,
            self.get_number_of_calls: self.W_NO_CALLS,
            self.get_number_of_ins: self.W_NO_INS,
            self.get_number_of_logic_ins: self.W_NO_LOGIC_INS,
            self.get_number_of_branch_ins: self.W_NO_BRANCH_INS,
        }
        listed_feat_func_map = {
            self.get_str_consts: self.W_STR_CONST,
            self.get_num_consts: self.W_NUM_CONST
        }

        numerator = 0
        denominator = 0
        for feat_func, weight in feat_func_map.items():
            f1, f2 = feat_func(b1, g1), feat_func(b2, g2)
            numerator += weight * abs(f1 - f2)
            denominator += weight * max(f1, f2)

        # special case for lists of features
        for feat_func, weight in listed_feat_func_map.items():
            f1, f2 = feat_func(b1, g1), feat_func(b2, g2)
            # jaccard similarity
            numerator += (len(set.union(set(f1), set(f2))) - len(set.intersection(set(f1), set(f2)))) * weight
            denominator += len(set.union(set(f1), set(f2))) * weight

        return numerator / denominator

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
