import hashlib
from collections import defaultdict
from typing import Dict, Optional, List, Tuple

from .flowgraph import FlowGraph
from . import rotl64, mask64bit, seed0_, seed1_, seed2_, k0, k1, k2, mask32bit


class FunctionSimHasher:
    TYP_GRAPH = "graph"
    TYPE_MNEM = "mnemonic"
    TYPE_IMM = "immediate"

    def __init__(self, w_graph=1.0, w_mnem=0.05, w_imm=4.0):
        # weights
        self.w_graph = w_graph
        self.w_mnem = w_mnem
        self.w_imm = w_imm

    def CalculateFunctionSimHash(self, graph, bit_size=128):
        if bit_size % 64 != 0:
            raise ValueError("Requested hash bit size must be a multiple of 64!")

        full_flow_graph = FlowGraph(graph)
        feature_cardnalities = defaultdict(int)
        final_floats = [0.0]*bit_size

        # graphlets (sub-graphs)
        for node, dist in full_flow_graph.nodes_and_distance:
            graphlet = full_flow_graph.GetSubgraph(graph, node, dist)
            if graphlet is None:
                continue

            _id = self._hash_graph(graphlet, node, hash_index=0, counter=0)
            card = feature_cardnalities[_id]
            feature_cardnalities[_id] += 1
            #feat_card_id = self._hash_graph(graphlet, node, card, 0)
            # XXX: since we dont support the getWeight() function, its just the weight of that feature
            weight = self.w_graph

            # start ProcessSubgraph here
            # calculate nbithash
            _hashes = [
                self._hash_graph(graphlet, node, hash_index=card, counter=(cntr + 1) * 64)
                for cntr in range(bit_size // 64)
            ]
            # skip adding to feature hashes
            self.AddWeightsInHashToOutput(final_floats, bit_size, weight, _hashes)

        # mnemonics (instruction operations)
        for mnem_tup in full_flow_graph.mnemonic_ngrams:
            _id = self._hash_mnemonic_tuple(mnem_tup, hash_index=0)
            card = feature_cardnalities[_id]
            feature_cardnalities[_id] += 1
            weight = self.w_mnem
            _hashes = [
                # TODO: might want to verify this is correct for hash_index
                self._hash_mnemonic_tuple(mnem_tup, hash_index=card + (((cntr + 1) * 64) + 1))
                for cntr in range(bit_size // 64)
            ]
            self.AddWeightsInHashToOutput(final_floats, bit_size, weight, _hashes)

        # immediates
        for imm in full_flow_graph.immediates:
            _id = self._hash_immediate(imm, hash_index=0, counter=0)
            card = feature_cardnalities[_id]
            feature_cardnalities[_id] += 1
            weight = self.w_imm
            _hashes = [
                self._hash_immediate(imm, hash_index=card, counter=(cntr + 1) * 64)
                for cntr in range(bit_size // 64)
            ]
            self.AddWeightsInHashToOutput(final_floats, bit_size, weight, _hashes)

        vals = self.FloatsToBits(final_floats)
        return vals[:-1]

    def AddWeightsInHashToOutput(self, final_floats, bit_size, weight, hashes):
        """
        Updates final_floats in place
        """
        for bit_n in range(bit_size):
            if self.GetNthBit(hashes, bit_n):
                final_floats[bit_n] += weight
            else:
                final_floats[bit_n] -= weight

    def _stable_hash(self, string: str) -> int:
        b_str = string.encode()
        return int(hashlib.md5(b_str).hexdigest(), 16)

    def _hash_mnemonic_tuple(self, mnem_tuple: Tuple[str, str, str], hash_index=0):
        m0, m1, m2 = mnem_tuple
        value1 = (
            self.SeedXForHashY(0, hash_index) ^ self.SeedXForHashY(1, hash_index) ^
            self.SeedXForHashY(2, hash_index)
        ) & mask64bit
        value1 *= self._stable_hash(m0) & mask64bit
        value1 = rotl64(value1, 7)
        value1 *= self._stable_hash(m1) & mask64bit
        value1 = rotl64(value1, 7)
        value1 *= self._stable_hash(m2) & mask64bit
        value1 = rotl64(value1, 7)
        value1 *= (k2 * (hash_index + 1)) & mask64bit
        return value1 & mask64bit

    def _hash_immediate(self, immediate, hash_index=0, counter=0):
        value1 = (
            self.SeedXForHashY(0, hash_index) & mask64bit +
            (counter * k0) & mask64bit +
            (counter * k1) & mask64bit +
            (counter * k2) & mask64bit
        ) & mask64bit
        value1 = rotl64(value1, 7)
        value1 *= (immediate ^ self.SeedXForHashY(0, hash_index)) & mask64bit
        value1 &= mask64bit
        value1 = rotl64(value1, 7)
        value1 *= (immediate ^ self.SeedXForHashY(1, hash_index)) & mask64bit
        value1 &= mask64bit
        value1 = rotl64(value1, 7)
        value1 *= (immediate ^ self.SeedXForHashY(2, hash_index)) & mask64bit
        value1 &= mask64bit
        value1 = rotl64(value1, 7)
        value1 *= ((k2 ^ immediate) * (hash_index + 1)) & mask64bit
        value1 &= mask64bit
        return value1

    def _hash_graph(self, flow_graph: FlowGraph, start_node, hash_index=0, counter=0):
        return flow_graph.CalculateHash(
            start_node=start_node,
            k0=self.SeedXForHashY(0, hash_index) * (counter + 1),
            k1=self.SeedXForHashY(1, hash_index) * (counter + 1),
            k2=self.SeedXForHashY(2, hash_index) * (counter + 1)
        )

    #
    # Bit Utils
    #

    @staticmethod
    def FloatsToBits(floats: List[float]):
        outputs = [0] * ((len(floats) // 64) + 1)
        for index, _float in enumerate(floats):
            vector_index = index // 64
            bit_index = index % 64
            if _float >= 0:
                outputs[vector_index] |= (1 << bit_index)

        return outputs

    @staticmethod
    def GetNthBit(nbit_hash: List[int], bitindex):
        index = bitindex // 64
        value = nbit_hash[index]
        sub_word_index = bitindex % 64
        return (value >> sub_word_index) & 1

    @staticmethod
    def SeedXForHashY(seed_index, hash_index):
        if seed_index == 0:
            return rotl64(seed0_, hash_index % 7) * (hash_index + 1)
        elif seed_index == 1:
            return rotl64(seed1_, hash_index % 11) * (hash_index + 1)
        elif seed_index == 2:
            return rotl64(seed2_, hash_index % 13) * (hash_index + 1)
        else:
            raise ValueError("Invalid seed index")

    @staticmethod
    def hash_distance(h1: List[int], h2: List[int]):
        total_dist = 0
        for _h1, _h2 in zip(h1, h2):
            total_dist += _h1 ^ _h2

        return total_dist