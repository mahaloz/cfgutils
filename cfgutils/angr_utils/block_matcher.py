from collections import defaultdict
from typing import List

import networkx as nx
from ailment import Block
from ailment.statement import Call

from cfgutils.sorting import quasi_topological_sort_nodes
from cfgutils.similarity.block_matcher_base import BlockMatcherBase
from .feat_extractor import AILBlockFeatureExtractor


class AILBlockMatcher(BlockMatcherBase):
    def __init__(self, g1: nx.DiGraph, g2: nx.DiGraph, proj1=None, proj2=None):
        super().__init__(g1, g2)
        self._proj1 = proj1
        self._proj2 = proj2
        self._g1_cache = defaultdict(dict)
        self._g2_cache = defaultdict(dict)
        self.generate_feat_cache()
        self.analyze()

    def generate_feat_cache(self):
        for g, proj, features in [(self._g1, self._proj1, self._g1_cache), (self._g2, self._proj2, self._g2_cache)]:
            proj_cfg = proj.kb.cfgs.get_most_accurate() if proj is not None else None
            for node in g.nodes:
                feat_extractor = AILBlockFeatureExtractor(proj, proj_cfg)
                feat_extractor.walk(node)
                features[node][self.TYP_NO_ARITHMETIC_INS] = len(feat_extractor.arith_ins)
                features[node][self.TYP_NO_CALLS] = len(feat_extractor.calls)
                features[node][self.TYP_NO_INS] = len(feat_extractor.ins)
                features[node][self.TYP_NO_LOGIC_INS] = len(feat_extractor.logic_ins)
                features[node][self.TYP_NO_BRANCH_INS] = len(feat_extractor.branch_ins)
                features[node][self.TYP_STR_CONST] = feat_extractor.str_consts
                features[node][self.TYP_NUM_CONST] = feat_extractor.num_consts

    def _get_correct_cache(self, graph):
        if graph == self._g1:
            return self._g1_cache
        elif graph == self._g2:
            return self._g2_cache
        else:
            raise ValueError("Graph not found")

    def get_number_of_arithmetic_ins(self, block, graph) -> int:
        cache = self._get_correct_cache(graph)
        return cache[block][self.TYP_NO_ARITHMETIC_INS]

    def get_number_of_calls(self, block, graph) -> int:
        cache = self._get_correct_cache(graph)
        return cache[block][self.TYP_NO_CALLS]

    def get_number_of_ins(self, block, graph) -> int:
        cache = self._get_correct_cache(graph)
        return cache[block][self.TYP_NO_INS]

    def get_number_of_logic_ins(self, block, graph) -> int:
        cache = self._get_correct_cache(graph)
        return cache[block][self.TYP_NO_LOGIC_INS]

    def get_number_of_branch_ins(self, block, graph) -> int:
        cache = self._get_correct_cache(graph)
        return cache[block][self.TYP_NO_BRANCH_INS]

    def get_str_consts(self, block, graph) -> List[str]:
        cache = self._get_correct_cache(graph)
        return cache[block][self.TYP_STR_CONST]

    def get_num_consts(self, block, graph) -> List[int]:
        cache = self._get_correct_cache(graph)
        return cache[block][self.TYP_NUM_CONST]
