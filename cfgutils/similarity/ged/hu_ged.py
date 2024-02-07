import sys

import networkx as nx

from cfgutils.matrix.munkres import Munkres


class CFGSimNM:
    def __init__(self, print_steps=False):
        self.__print_steps = print_steps
        self.__eps = 0.0001
        self.__inf = float('inf')
    
    def sim(self, g1, g2):
        n = g1.get_node_count()
        m = g2.get_node_count()

        sim = [None] * n
        for i in range(n):
            sim[i] = [1] * m
            for j in range(m):
                sim[i][j] = 1#g1.get_node(i).contrastByInstr(g2.get_node(j))

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
            
                    n1 = g1.get_node(i)
                    n2 = g2.get_node(j)
            
                    no_of_in_neighbors1 = n1.get_parent_count()
                    no_of_in_neighbors2 = n2.get_parent_count()
            
                    in_neighbor_sim = 0
                    if not max(no_of_in_neighbors1, no_of_in_neighbors2) == 0:
                        in_neighbors_matching_costs = [None] * no_of_in_neighbors1
                        for k in range(no_of_in_neighbors1):
                            in_neighbors_matching_costs[k] = [1] * no_of_in_neighbors2
                            for l in range(no_of_in_neighbors2):
                                in_neighbors_matching_costs[k][l] = (1 - old_sim[n1.get_parent(k).index][n2.get_parent(l).index]) / self.__eps
                                if self.__print_steps and i == 1 and j == 1:
                                    print("in_neighbors_matching_costs[" + str(k) + "][" + str(l) + "] = (1 - old_sim[" + str(n1.get_parent(k).index) + "][" + str(n2.get_parent(l).index) + "]) / " + str(self.__eps))
                                    print("in_neighbors_matching_costs[" + str(k) + "][" + str(l) + "] = (1 -" + str(old_sim[n1.get_parent(k).index][n2.get_parent(l).index]) + ") / " + str(self.__eps))
            
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
                                value = old_sim[n1.get_parent(row).index][n2.get_parent(column).index]
                                if self.__print_steps and i == 1 and j == 1:
                                    print(str(row) + ' ' + str(column) + ' ' + str(old_sim[n1.get_parent(row).index][n2.get_parent(column).index]))
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
            
                    no_of_out_neighbors1 = n1.get_child_count()
                    no_of_out_neighbors2 = n2.get_child_count()
            
                    out_neighbor_sim = 0
                    if not max(no_of_out_neighbors1, no_of_out_neighbors2) == 0:
                        out_neighbors_matching_costs = [None] * no_of_out_neighbors1
                        for k in range(no_of_out_neighbors1):
                            out_neighbors_matching_costs[k] = [1] * no_of_out_neighbors2
                            for l in range(no_of_out_neighbors2):
                                out_neighbors_matching_costs[k][l] = (1 - old_sim[n1.get_child(k).index][n2.get_child(l).index]) / self.__eps
                
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
                                value = old_sim[n1.get_child(row).index][n2.get_child(column).index]
                                if self.__print_steps and i == 1 and j == 1:
                                    print('Match ' + str(row) + ' with ' + str(column) + '. Value: ' + str(old_sim[n1.get_child(row).index][n2.get_child(column).index]))
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

        sim_score = float(sim_score) / matches
        return sim_score


def hu_ged(g1: nx.DiGraph, g2: nx.DiGraph, print_steps=False):
    ged = CFGSimNM(print_steps=print_steps)
    return ged.sim(g1, g2)
