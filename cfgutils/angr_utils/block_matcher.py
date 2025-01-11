from collections import defaultdict
from typing import List

import networkx as nx
from ailment import Block
from ailment.statement import Call

from cfgutils.sorting import quasi_topological_sort_nodes
from cfgutils.similarity.block_matcher_base import BlockMatcherBase
from .feat_extractor import AILBlockFeatureExtractor


class AILBlockMatcher(BlockMatcherBase):
    TYP_VAR_NAMES = "var_names"
    TYP_STACK_ADDRS = "stack_addrs"
    TYP_FUNC_NAMES = "func_names"

    def __init__(
        self,
        g1: nx.DiGraph,
        g2: nx.DiGraph,
        proj1=None,
        proj2=None,
        match_confidence=0.6,
        graph_match_pass=True,
        mapping=None,
        use_var_names=True,
        use_caller_names=True,
        caller_name_mapping=None,
        root_dist_tie_breaker=True,
        match_exact_calls=True,
        assume_rooted=True,
    ):
        super().__init__(
            g1,
            g2,
            match_confidence=match_confidence,
            graph_match_pass=graph_match_pass,
            mapping=mapping,
            root_dist_tie_breaker=root_dist_tie_breaker,
            assume_rooted=assume_rooted,
        )
        self._proj1 = proj1
        self._proj2 = proj2
        self._use_var_names = use_var_names
        self._use_caller_names = use_caller_names
        self._caller_name_mapping = caller_name_mapping or {}

        self._g1_cache = defaultdict(dict)
        self._g2_cache = defaultdict(dict)
        self.generate_feat_cache()

        if match_exact_calls:
            self.mapping = self.match_exact_calls()

        self.analyze()

    def match_exact_calls(self):
        """
        Finds all calls which are exactly the same with the same root distance.

        :return:
        """
        mapping = {}
        for b1 in self._g1.nodes:
            choices = []
            # search all cases of names and amount lining up
            for b2 in self._g2.nodes:
                if (
                    self.get_number_of_calls(b1, self._g1) == self.get_number_of_calls(b2, self._g2) != 0 and
                    # XXX: this could be bad, order should matter...
                    set(self._g1_cache[b1][self.TYP_FUNC_NAMES]) == set(self._g2_cache[b2][self.TYP_FUNC_NAMES])
                ):
                    choices.append(b2)

            # since there can be multiple blocks that meet the above criteria, if we have to choose,
            # then we must be sure its the same. To do that, we use their distance from the root.
            if len(choices) == 1:
                mapping[b1] = choices[0]
            else:
                # first attempt to eliminate all choices with different edge amounts
                same_edge_choices = [
                    choice for choice in choices
                    if len(list(self._g2.predecessors(choice))) == len(list(self._g1.predecessors(b1))) and
                    len(list(self._g2.successors(choice))) == len(list(self._g1.successors(b1)))
                ]
                if len(same_edge_choices) == 1:
                    mapping[b1] = same_edge_choices[0]
                # if we still have multiple choices, we must use root distance to know truth
                # go back to before and use root distance to choose
                else:
                    for choice in choices:
                        if self._root_dist[self._g1][b1] == self._root_dist[self._g2][choice]:
                            mapping[b1] = choice
                            break

        return mapping

    def generate_feat_cache(self):
        for g, proj, features in [(self._g1, self._proj1, self._g1_cache), (self._g2, self._proj2, self._g2_cache)]:
            proj_cfg = proj.kb.cfgs.get_most_accurate() if proj is not None else None
            for node in g.nodes:
                feat_extractor = AILBlockFeatureExtractor(proj, proj_cfg, call_name_fallback=self._caller_name_mapping)
                feat_extractor.walk(node)
                features[node][self.TYP_NO_ARITHMETIC_INS] = len(feat_extractor.arith_ins)
                features[node][self.TYP_NO_CALLS] = len(feat_extractor.calls)
                features[node][self.TYP_NO_INS] = len(feat_extractor.ins)
                features[node][self.TYP_NO_LOGIC_INS] = len(feat_extractor.logic_ins)
                features[node][self.TYP_NO_BRANCH_INS] = len(feat_extractor.branch_ins)
                features[node][self.TYP_STR_CONST] = feat_extractor.str_consts
                features[node][self.TYP_NUM_CONST] = feat_extractor.num_consts
                features[node][self.TYP_VAR_NAMES] = feat_extractor.var_names
                features[node][self.TYP_STACK_ADDRS] = feat_extractor.stack_addrs
                features[node][self.TYP_FUNC_NAMES] = feat_extractor.call_names

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
        str_consts = cache[block][self.TYP_STR_CONST]
        if self._use_var_names:
            str_consts += cache[block][self.TYP_VAR_NAMES]
        if self._use_caller_names:
            str_consts += cache[block][self.TYP_FUNC_NAMES]

        return str_consts

    def get_num_consts(self, block, graph) -> List[int]:
        cache = self._get_correct_cache(graph)
        return cache[block][self.TYP_NUM_CONST] + cache[block][self.TYP_STACK_ADDRS]
