import itertools
from collections import defaultdict
from typing import List, Dict, Tuple, Union

import networkx as nx

from ..sorting import quasi_topological_sort_nodes


class BlockMatcherBase:
    """
    This class takes two graphs and returns a dictionary of likely matches between the nodes in the two graphs.
    The key is nodes in g1 and the value is the corresponding node in g2. This class is expected to be used
    with two graphs you _know_ are implementing the same logic. This can happen in instances of a function being
    compiled with different optimization levels, or with different compilers.

    The core score of each block is based on the paper: "discovRE: Efficient Cross-Architecture Identification of Bugs
    in Binary Code" by Eschweiler et al. in NDSS 2016. After collecting these initial scores, we will do more analysis
    to get more matches.
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

    def __init__(
        self,
        g1: nx.DiGraph,
        g2: nx.DiGraph,
        use_new_weights=False,
        use_inv_map=False,
        assume_rooted=True,
        graph_match_pass=False,
        match_confidence=0.0,
        root_dist_tie_breaker=True,
        mapping=None,
        out_edges_must_match=True,
    ):
        self._g1 = g1
        self._g2 = g2
        self._use_new_weights = use_new_weights
        self._use_inv_map = use_inv_map
        self._graph_match_pass = graph_match_pass
        self._assume_rooted = assume_rooted
        self._root_dist_tie_breaker = root_dist_tie_breaker
        self._out_edges_must_match = out_edges_must_match
        self.match_confidence = match_confidence

        self._g1_nodes = list(g1.nodes)
        self._g2_nodes = list(g2.nodes)
        self._topo_dist = {
            g1: self._generate_topological_dist_map(g1),
            g2: self._generate_topological_dist_map(g2)
        }

        self._g1_root, self._g2_root = None, None
        if self._assume_rooted:
            self._g1_root = next(n for n in self._g1_nodes if self._g1.in_degree(n) == 0)
            self._g2_root = next(n for n in self._g2_nodes if self._g2.in_degree(n) == 0)

        self._root_dist = {}
        if self._root_dist_tie_breaker and self._assume_rooted:
            self._root_dist = {
                g1: nx.single_source_shortest_path_length(g1, self._g1_root),
                g2: nx.single_source_shortest_path_length(g2, self._g2_root),
            }

        self._used_b2 = set()
        self.mapping = mapping or {}

    def neighbour_match_nodes(self, g1: nx.DiGraph, g2: nx.DiGraph):
        changes = True
        max_attempts = 1000
        attempts = 0
        while changes and attempts < max_attempts:
            changes = False
            attempts += 1
            chosen_b2s = set(self.mapping.values())

            for b1, b2 in list(self.mapping.items()):
                uniq_b1_preds = list(pred for pred in g1.predecessors(b1) if pred not in self.mapping)
                uniq_b2_preds = list(pred for pred in g2.predecessors(b2) if pred not in chosen_b2s)

                # Case1: a matched set both have one parent not matched yet
                if len(uniq_b1_preds) == 1 and len(uniq_b2_preds) == 1:
                    self.mapping[uniq_b1_preds[0]] = uniq_b2_preds[0]
                    changes = True
                    break

                uniq_b1_succs = list(succ for succ in g1.successors(b1) if succ not in self.mapping)
                uniq_b2_succs = list(succ for succ in g2.successors(b2) if succ not in chosen_b2s)
                # Case2: a matched set both have one child
                if len(uniq_b1_succs) == 1 and len(uniq_b2_succs) == 1:
                    self.mapping[uniq_b1_succs[0]] = uniq_b2_succs[0]
                    changes = True
                    break

        return attempts > 1

    def analyze(self):
        # mark all nodes provided already as matches
        self._used_b2 = set()
        for _, g2_node in self.mapping.items():
            self._used_b2.add(g2_node)

        b1_b2_map, best_b2_scores = self.generate_similarities(get_best_inv_map=True)
        if self._assume_rooted:
            self.mapping[self._g1_root] = self._g2_root
            self._used_b2.add(self._g2_root)

            g1_exits = [n for n in self._g1_nodes if self._g1.out_degree(n) == 0]
            g2_exits = [n for n in self._g2_nodes if self._g2.out_degree(n) == 0]
            if len(g1_exits) == len(g2_exits) == 1:
                self.mapping[g1_exits[0]] = g2_exits[0]
                self._used_b2.add(g2_exits[0])

        if self._use_inv_map:
            # first, map every b2 to the b1 that matches it best
            for b2, b1 in best_b2_scores.items():
                if (b2 in self._used_b2) or (b1 in self.mapping):
                    continue

                self.mapping[b1] = b2
                self._used_b2.add(b2)

        # then, map the rest of the b1s to the b2s that match them best
        for b1, b2_scores in b1_b2_map.items():
            if b1 in self.mapping:
                continue

            best_matches = sorted(b2_scores.items(), key=lambda x: x[1], reverse=True)
            best_score = best_matches[0][1]
            top_score_matches = [b2 for b2, score in best_matches if score == best_score]
            # eliminate missing edge matches
            if self._out_edges_must_match:
                top_score_matches = [
                    b2 for b2 in top_score_matches if set(self._g1.successors(b1)) == set(self._g2.successors(b2))
                ]

            # if tie-break enable, attempt to resolve the top-level ties (anything after is ok...)
            if len(top_score_matches) > 1 and self._root_dist_tie_breaker:
                b1_dist = self._root_dist[self._g1][b1]
                _best_first_matches = sorted(
                    best_matches[:len(top_score_matches)], key=lambda x: abs(b1_dist - self._root_dist[self._g2][x[0]])
                )
                best_matches = _best_first_matches + best_matches[len(top_score_matches):]

            for blk_match, score in best_matches:
                # scores are ordered, so if the top score is below the confidence, we can break
                if score < self.match_confidence:
                    break

                if blk_match not in self._used_b2:
                    self.mapping[b1] = blk_match
                    self._used_b2.add(blk_match)
                    break
            else:
                # if no match was found at all, we must be out of b2s
                break

        if self._graph_match_pass:
            self.neighbour_match_nodes(self._g1, self._g2)

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
        }
        listed_feat_func_map = {
            self.get_str_consts: self.W_STR_CONST,
            self.get_num_consts: self.W_NUM_CONST
        }
        # use weights that are not from the paper, but might be useful
        if self._use_new_weights:
            feat_func_map[self.get_topological_dist] = self.W_TOPO_DIST

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
