import sys

import networkx as nx

from cfgutils.matrix.munkres import Munkres
from cfgutils.similarity.ged import INVALID_CHOICE_PENALTY


class GraphCache:
    def __init__(self, graph: nx.DiGraph):
        self._graph = graph
        self.nodes = list(graph.nodes)
        self.node_count = len(self.nodes)
        self.edge_count = len(graph.edges)
        self.node_to_index = {node: i for i, node in enumerate(graph.nodes)}

        self._parents = {node: list(graph.predecessors(node)) for node in graph.nodes}
        self.parent_count = {node: len(parents) for node, parents in self._parents.items()}

        self._children = {node: list(graph.successors(node)) for node in graph.nodes}
        self.child_count = {node: len(children) for node, children in self._children.items()}

    def get_parent(self, node, i):
        return self._parents[node][i]

    def parent_node_idx(self, node, parent_i):
        return self.node_to_index[self.get_parent(node, parent_i)]

    def get_child(self, node, i):
        return self._children[node][i]

    def child_node_idx(self, node, child_i):
        return self.node_to_index[self.get_child(node, child_i)]


class CFGSimED:
    def __init__(self, g1: nx.DiGraph, g2: nx.DiGraph, print_steps=False, normalize=False):
        self.__print_steps = print_steps
        self._normalize = normalize
        self.__inf = float('inf')

        self._g1_graph = g1
        self._g2_graph = g2
        self._g1 = GraphCache(self._g1_graph)
        self._g2 = GraphCache(self._g2_graph)

    def __count_common(self, l1, l2):
        l2_copy = list(l2)
        counter = 0
        for i in l1:
            if i in l2_copy:
                counter += 1
                l2_copy.remove(i)
        return counter

    def __ED(self):
        n = self._g1.node_count
        m = self._g2.node_count

        cost_matrix = [None] * (n + m)
        for i in range(n + m):
            cost_matrix[i] = [0] * (n + m)

        # Set the bottom left m x m matrix to a matrix filled with self.__infinity
        for row in range(n, n + m):
            for col in range(m):
                cost_matrix[row][col] = self.__inf

        # Set the top right n x n matrix to a matrix filled with self.__infinity
        for row in range(n):
            for col in range(m, m + n):
                cost_matrix[row][col] = self.__inf

        # Set the diagonal for the bottom left m x m matrix
        for i in range(m):
            row = n + i
            col = i
            node = self._g2.nodes[i]
            parent_count = self._g2.parent_count[node]
            child_count = self._g2.child_count[node]
            if self.__print_steps:
                if i == 0:
                    print("1 + " + str(parent_count) + " + " + str(child_count))
            cost = 1 + parent_count + child_count
            cost_matrix[row][col] = cost

        # Set the diagonal for the top right n x n matrix
        for i in range(n):
            row = i
            col = m + i
            node = self._g1.nodes[i]
            parent_count = self._g1.parent_count[node]
            child_count = self._g1.child_count[node]
            cost = 1 + parent_count + child_count
            cost_matrix[row][col] = cost

        # Set the top left n x m matrix
        for row in range(n):
            for col in range(m):
                CL1 = []
                CL2 = []
                PL1 = []
                PL2 = []
                node1 = self._g1.nodes[row]
                node2 = self._g2.nodes[col]
                node1_child_count = self._g1.child_count[node1]
                node2_child_count = self._g2.child_count[node2]
                node1_parent_count = self._g1.parent_count[node1]
                node2_parent_count = self._g2.parent_count[node2]

                for child_index in range(node1_child_count):
                    CL1.append('1')
                for child_index in range(node2_child_count):
                    CL2.append('1')
                for parent_index in range(node1_parent_count):
                    PL1.append('1')
                for parent_index in range(node2_parent_count):
                    PL2.append('1')

                if self.__print_steps:
                    if row == col and row == 0:
                        print(str(node1_child_count) + " + " + str(node2_child_count) + " - (2 * " + str(self.__count_common(CL1, CL2)) + ")")
                        print(str(node1_parent_count) + " + " + str(node2_parent_count) + " - (2 * " + str(self.__count_common(PL1, PL2)) + ")")

                cost = node1_child_count + node2_child_count - (2 * (self.__count_common(CL1, CL2)))
                cost += node1_parent_count + node2_parent_count - (2 * (self.__count_common(PL1, PL2)))

                # Penalize matching entry/exit nodes with non-entry/non-exit nodes
                if node1.is_entrypoint and not node2.is_entrypoint:
                    cost += INVALID_CHOICE_PENALTY
                elif node1.is_exitpoint and not node2.is_exitpoint:
                    cost += INVALID_CHOICE_PENALTY
                elif node2.is_entrypoint and not node1.is_entrypoint:
                    cost += INVALID_CHOICE_PENALTY
                elif node2.is_exitpoint and not node1.is_exitpoint:
                    cost += INVALID_CHOICE_PENALTY

                cost_matrix[row][col] = cost

        if self.__print_steps:
            print('Cost matrix:')
            for i in range(n + m):
                for j in range(n + m):
                    sys.stdout.write(str(round(cost_matrix[i][j], 2)))
                    if not j == n + m - 1:
                        sys.stdout.write(" & ")
                print(' \\\\')

        munkres = Munkres()

        indexes = munkres.compute(cost_matrix)

        total = 0
        if self.__print_steps:
            print(indexes)
        for row, column in indexes:
            value = cost_matrix[row][column]
            total += value
            if self.__print_steps:
                print((row, column, value))
            if self.__print_steps and row < self._g1.node_count and column < self._g2.node_count:
                node1 = self._g1.nodes[row]
                node2 = self._g2.nodes[column]
                print(str(node1) + ' ' + str(node2))
            elif self.__print_steps and row < self._g1.node_count:
                node1 = self._g1.nodes[row]
                print(str(node1) + ' dummy')
            elif self.__print_steps and column < self._g2.node_count:
                node2 = self._g2.nodes[column]
                print('dummy ' + str(node2))
        if self.__print_steps:
            print(('total cost:', total))

        if self._normalize:
            simScore = 1 - (total / float(self._g1.node_count + self._g1.edge_count + self._g2.node_count + self._g2.edge_count))
        else:
            simScore = total

        return simScore

    def sim(self):
        return self.__ED()


def vj_ged(g1: nx.DiGraph, g2: nx.DiGraph, print_steps=False, normalize=False):
    ged = CFGSimED(g1, g2, print_steps=print_steps, normalize=normalize)
    return ged.sim()
