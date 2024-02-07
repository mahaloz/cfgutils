# This reimplementation was based on the code found in http://cfgsim.cs.arizona.edu/. The code found there is an
# implementation based on the following paper:
# "Large-Scale Malware Indexing Using Function-Call Graphs"
# by Hu et al. and published at CCS 2009.
#
# This reimplementation differs in how it handles the cost of relabeling nodes. The original paper
# uses instruction information to decide a score. We dont implement that here, and instead we add the extra
# constraint of illegal edits to the graph (swapping a start or exit with a non-start or non-exit).
#

import math
import sys

import networkx as nx

from cfgutils.matrix.munkres import Munkres
from cfgutils.similarity.ged import INVALID_CHOICE_PENALTY


class GraphCache:
    def __init__(self, graph: nx.DiGraph):
        self._graph = graph
        self.nodes = list(graph.nodes)
        self.node_count = len(self.nodes)
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


class CFGSimNM:
    def __init__(self, g1, g2, print_steps=False, normalize=False):
        self.__print_steps = print_steps
        self._normalize = normalize

        self.__eps = 0.0001
        self.__inf = float('inf')

        self._g1_graph = g1
        self._g2_graph = g2
        self._g1 = GraphCache(self._g1_graph)
        self._g2 = GraphCache(self._g2_graph)

    def relabel_cost(self, n1_idx, n2_idx):
        """
        This was previously contrastByInstr, which became contrast_by_instr, which became this.
        In the paper this algorithm is from the authors used it to decrease the cost of some operations if two
        nodes matched. If this function is not changed, the default cost is 1.

        In the case of CFGUtils, we consider swapping a start or exit with a non-start or non-exit to be an
        invalid choice. That is reflected in the cost returned by this function.
        """
        n1 = self._g1.nodes[n1_idx]
        n2 = self._g2.nodes[n2_idx]

        cost = 1
        if n1.is_entrypoint and not n2.is_entrypoint:
            cost = INVALID_CHOICE_PENALTY
        elif n1.is_exitpoint and not n2.is_exitpoint:
            cost = INVALID_CHOICE_PENALTY
        elif n2.is_entrypoint and not n1.is_entrypoint:
            cost = INVALID_CHOICE_PENALTY
        elif n2.is_exitpoint and not n1.is_exitpoint:
            cost = INVALID_CHOICE_PENALTY

        return cost

    def sim(self):
        n = self._g1.node_count
        m = self._g2.node_count

        sim = [None] * n
        for i in range(n):
            sim[i] = [1] * m
            for j in range(m):
                sim[i][j] = self.relabel_cost(i, j)

        if self.__print_steps:
            print('Initial cost matrix:')
            for i in range(n):
                for j in range(m):
                    sys.stdout.write(str(round(sim[i][j], 2)) + '\t')
                print('')

        finished = False    
        while not finished:
            # Since the calculation of the new sim matrix is based on the old one, we need to make
            # a copy of the old one first.
            old_sim = [None] * n
            for i in range(n):
                old_sim[i] = list(sim[i])
    
            precise = True
    
            for i in range(n):
                for j in range(m):
                    if self.__print_steps:
                        print('Current cost matrix:')
                        for k in range(n):
                            for l in range(m):
                                sys.stdout.write(str(round(sim[k][l], 2)))
                                if l < m - 1:
                                    sys.stdout.write(' & ')
                            print(' \\\\')
                        print('')
            
                    n1 = self._g1.nodes[i]
                    n2 = self._g2.nodes[j]

                    no_of_in_neighbors1 = self._g1.parent_count[n1]
                    no_of_in_neighbors2 = self._g2.parent_count[n2]
            
                    in_neighbor_sim = 0
                    if not max(no_of_in_neighbors1, no_of_in_neighbors2) == 0:
                        in_neighbors_matching_costs = [None] * no_of_in_neighbors1
                        for k in range(no_of_in_neighbors1):
                            in_neighbors_matching_costs[k] = [1] * no_of_in_neighbors2
                            for l in range(no_of_in_neighbors2):
                                #in_neighbors_matching_costs[k][l] = (1 - old_sim[n1.get_parent(k).index][n2.get_parent(l).index]) / self.__eps
                                in_neighbors_matching_costs[k][l] = ((
                                    1 - old_sim[self._g1.parent_node_idx(n1, k)][self._g2.parent_node_idx(n2, l)]
                                ) / self.__eps)
                                if self.__print_steps and i == 1 and j == 1:
                                    #print("in_neighbors_matching_costs[" + str(k) + "][" + str(l) + "] = (1 - old_sim[" + str(n1.get_parent(k).index) + "][" + str(n2.get_parent(l).index) + "]) / " + str(self.__eps))
                                    print("in_neighbors_matching_costs[" + str(k) + "][" + str(l) + "] = (1 - old_sim[" + str(self._g1.parent_node_idx(n1, k)) + "][" + str(self._g2.parent_node_idx(n2, l)) + "]) / " + str(self.__eps))
                                    #print("in_neighbors_matching_costs[" + str(k) + "][" + str(l) + "] = (1 -" + str(old_sim[n1.get_parent(k).index][n2.get_parent(l).index]) + ") / " + str(self.__eps))
                                    print("in_neighbors_matching_costs[" + str(k) + "][" + str(l) + "] = (1 -" + str(old_sim[self._g1.parent_node_idx(n1, k)][self._g2.parent_node_idx(n2, l)]) + ") / " + str(self.__eps))


                        #print("#### " + str(no_of_in_neighbors1) + " " + str(no_of_in_neighbors2) + " " + str(max(no_of_in_neighbors1, no_of_in_neighbors2)))
                        #print in_neighbors_matching_costs
                
                        # Print out the matrix for the paper
                        if self.__print_steps:
                            if i == 1 and j == 1:
                                print('Cost matrix for in neighbors of entry (2, 2):')
                                for k in range(no_of_in_neighbors1):
                                    for l in range(no_of_in_neighbors2):
                                        sys.stdout.write(str(in_neighbors_matching_costs[k][l]) + ' ')
                                    print('')
                
                        if no_of_in_neighbors1 > 0 and no_of_in_neighbors2 > 0:
                            munkres = Munkres()
                            indexes = munkres.compute(in_neighbors_matching_costs)
                            for row, column in indexes:
                                #value = old_sim[n1.get_parent(row).index][n2.get_parent(column).index]
                                value = old_sim[self._g1.parent_node_idx(n1, row)][self._g2.parent_node_idx(n2, column)]
                                if self.__print_steps and i == 1 and j == 1:
                                    #print(str(row) + ' ' + str(column) + ' ' + str(old_sim[n1.get_parent(row).index][n2.get_parent(column).index]))
                                    print('Match ' + str(row) + ' with ' + str(column) + '. Value: ' + str(old_sim[self._g1.parent_node_idx(n1, row)][self._g2.parent_node_idx(n2, column)]))
                                in_neighbor_sim += value
                            if self.__print_steps and i == 1 and j == 1:
                                print("s_in total: " + str(in_neighbor_sim))
                
                        in_neighbor_sim /= float(max(no_of_in_neighbors1, no_of_in_neighbors2))
                        if self.__print_steps and i == 1 and j == 1:
                            print("s_in / " + str(float(max(no_of_in_neighbors1, no_of_in_neighbors2))) + " = " + str(in_neighbor_sim))
                    else:
                        in_neighbor_sim = 1
                        if self.__print_steps and i == 1 and j == 1:
                            print("in_neighbor_sim = 1")
            
                    no_of_out_neighbors1 = self._g1.child_count[n1]
                    no_of_out_neighbors2 = self._g2.child_count[n2]
            
                    out_neighbor_sim = 0
                    if not max(no_of_out_neighbors1, no_of_out_neighbors2) == 0:
                        out_neighbors_matching_costs = [None] * no_of_out_neighbors1
                        for k in range(no_of_out_neighbors1):
                            out_neighbors_matching_costs[k] = [1] * no_of_out_neighbors2
                            for l in range(no_of_out_neighbors2):
                                #out_neighbors_matching_costs[k][l] = (1 - old_sim[n1.get_child(k).index][n2.get_child(l).index]) / self.__eps
                                out_neighbors_matching_costs[k][l] = (1 - old_sim[self._g1.child_node_idx(n1, k)][self._g2.child_node_idx(n2, l)]) / self.__eps

                        # Print out the matrix for the paper
                        if self.__print_steps and i == 1 and j == 1:
                            print('Cost matrix for out neighbors of entry (2, 2):')
                            for k in range(no_of_out_neighbors1):
                                for l in range(no_of_out_neighbors2):
                                    sys.stdout.write(str(out_neighbors_matching_costs[k][l]) + ' ')
                                print('')
                        
                        if self.__print_steps and i == 1 and j == 1:
                            print('Matching of out neighbors of entry (1, 1):')
                        if no_of_out_neighbors1 > 0 and no_of_out_neighbors2 > 0:
                            munkres = Munkres()
                            indexes = munkres.compute(out_neighbors_matching_costs)
                            for row, column in indexes:
                                #value = old_sim[n1.get_child(row).index][n2.get_child(column).index]
                                value = old_sim[self._g1.child_node_idx(n1, row)][self._g2.child_node_idx(n2, column)]
                                if self.__print_steps and i == 1 and j == 1:
                                    #print('Match ' + str(row) + ' with ' + str(column) + '. Value: ' + str(old_sim[n1.get_child(row).index][n2.get_child(column).index]))
                                    print('Match ' + str(row) + ' with ' + str(column) + '. Value: ' + str(old_sim[self._g1.child_node_idx(n1, row)][self._g2.child_node_idx(n2, column)]))
                                out_neighbor_sim += value
                            if self.__print_steps and i == 1 and j == 1:
                                print("s_out total: " + str(out_neighbor_sim))
                
                        out_neighbor_sim /= float(max(no_of_out_neighbors1, no_of_out_neighbors2))
                        if self.__print_steps and i == 1 and j == 1:
                            print("s_out / " + str(float(max(no_of_out_neighbors1, no_of_out_neighbors2))) + " = " + str(out_neighbor_sim))
                    else:
                        out_neighbor_sim = 1
            
                    #sim[i][j] = sqrt(n1.contrastByInstr(n2) * float(in_neighbor_sim + out_neighbor_sim) / 2)
                    sim[i][j] = float(in_neighbor_sim + out_neighbor_sim) / 2
            
                    if sim[i][j] - old_sim[i][j] >= self.__eps:
                        precise = False
    
            if precise:
                finished = True
    
            if self.__print_steps:
                print('Updated cost matrix:')
                for i in range(n):
                    for j in range(m):
                        sys.stdout.write(str(round(sim[i][j], 2)) + '\t')
                    print('')

        costs = [None] * n
        for i in range(n):
            costs[i] = [0] * m
            for j in range(m):
                costs[i][j] = float(1 - sim[i][j]) / self.__eps

        munkres = Munkres()
        indexes = munkres.compute(costs)

        matches = 0
        sim_score = 0
        for row, column in indexes:
            matches += 1
            sim_score += sim[row][column]

        if self._normalize:
            sim_score = float(sim_score) / matches

        return float(math.ceil(sim_score))


def hu_cfged(g1: nx.DiGraph, g2: nx.DiGraph, print_steps=False):
    ged = CFGSimNM(g1, g2, print_steps=print_steps)
    return ged.sim()
