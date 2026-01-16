import networkx as nx

from cfgutils.matrix.munkres import Munkres
import sys

class CFGSimED:
    def __init__(self, print_steps=False, normalize=False):
        self.__print_steps = print_steps
        self._normalize = normalize
        self.__inf = float('inf')

    def __count_common(self, l1, l2):
        l2_copy = list(l2)
        counter = 0
        for i in l1:
            if i in l2_copy:
                counter+=1
                l2_copy.remove(i)
        return counter

    def __ED(self, g1, g2):
        n = g1.get_node_count()
        m = g2.get_node_count()

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
            node = g2.get_node(i)
            if self.__print_steps:
                if i == 0:
                    print("1 + " + str(node.get_parent_count()) + " + " + str(node.get_child_count()))
            cost = 1 + node.get_parent_count() + node.get_child_count()
            cost_matrix[row][col] = cost

        # Set the diagonal for the top right n x n matrix
        for i in range(n):
            row = i
            col = m + i
            node = g1.get_node(i)
            cost = 1 + node.get_parent_count() + node.get_child_count()
            cost_matrix[row][col] = cost

        # Set the top left n x m matrix
        for row in range(n):
            for col in range(m):
                CL1 = []
                CL2 = []
                PL1 = []
                PL2 = []
                node1 = g1.get_node(row)
                node2 = g2.get_node(col)
                for child_index in range(node1.get_child_count()):
                    #CL1.append(node1.getChild(child_index).color)
                    CL1.append('1')
                for child_index in range(node2.get_child_count()):
                    #CL2.append(node2.getChild(child_index).color)
                    CL2.append('1')
                for parent_index in range(node1.get_parent_count()):
                    #PL1.append(node1.getParent(parent_index).color)
                    PL1.append('1')
                for parent_index in range(node2.get_parent_count()):
                    #PL2.append(node2.getParent(parent_index).color)
                    PL2.append('1')

                if self.__print_steps:
                    if row == col and row == 0:
                        print (str(node1.get_child_count()) + " + " + str(node2.get_child_count()) + " - (2 * " + str(self.__count_common(CL1, CL2)) + ")")
                        print (str(node1.get_parent_count()) + " + " + str(node2.get_parent_count()) + " - (2 * " + str(self.__count_common(PL1, PL2)) + ")")

                cost = node1.get_child_count() + node2.get_child_count() - (2 * (self.__count_common(CL1, CL2)))
                cost += node1.get_parent_count() + node2.get_parent_count() - (2 * (self.__count_common(PL1, PL2)))
                cost_matrix[row][col] = cost

        if self.__print_steps:
            print('Cost matrix:')
            for i in range(n + m):
                for j in range(n + m):
                    sys.stdout.write(str(round(cost_matrix[i][j], 2)))
                    if not j == n + m - 1:
                        sys.stdout.write(" & ")
                print(' \\\\')

        m = Munkres()

        indexes = m.compute(cost_matrix)

        #print_matrix(matrix, msg='Lowest cost through this matrix:')
        total = 0
        if self.__print_steps:
            print(indexes)
        for row, column in indexes:
            value = cost_matrix[row][column]
            total += value
            if self.__print_steps:
                print((row, column, value))
            if self.__print_steps and row < g1.get_node_count() and column < g2.get_node_count():
                print(g1.get_node(row).name + ' ' + g2.get_node(column).name)
            elif self.__print_steps and row < g1.get_node_count():
                print(g1.get_node(row).name + ' dummy')
            elif self.__print_steps and column < g2.get_node_count():
                print(g2.get_node(column).name + ' dummy')
        if self.__print_steps:
            print(('total cost:', total))

        if self._normalize:
            simScore = 1 - (total / float(g1.get_node_count() + g1.get_edge_count() + g2.get_node_count() + g2.get_edge_count()))
        else:
            simScore = total

        return simScore

    def sim(self, g1, g2):
        return self.__ED(g1, g2)

def vj_ged(g1: nx.DiGraph, g2: nx.DiGraph[], print_steps=False):
    ged = CFGSimED(g1, g2, print_steps=print_steps)
    return ged.sim()