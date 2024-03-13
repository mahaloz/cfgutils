from typing import List

import networkx as nx
from ailment import Block
from ailment.statement import Call

from cfgutils.sorting import quasi_topological_sort_nodes
from cfgutils.similarity.block_matcher_base import BlockMatcherBase
from .call_collector import AILBlockCallCounter


class AILBlockMatcher(BlockMatcherBase):
    def analyze(self):
        pass

    def get_number_of_calls(self, block) -> int:
        cntr = AILBlockCallCounter()
        cntr.walk(block)
        return len(cntr.calls)