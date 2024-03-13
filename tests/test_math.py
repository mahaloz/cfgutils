import sys
import unittest

from cfgutils.matrix.munkres import Munkres, print_matrix


class TestMatrixMath(unittest.TestCase):
    def test_munkres(self):
        matrices = [
            # Square
            ([[400, 150, 400],
              [400, 450, 600],
              [300, 225, 300]],
             850  # expected cost
             ),

            # Rectangular variant
            ([[400, 150, 400, 1],
              [400, 450, 600, 2],
              [300, 225, 300, 3]],
             452  # expected cost
             ),

            # Square
            ([[10, 10, 8],
              [9, 8, 1],
              [9, 7, 4]],
             18
             ),

            # Rectangular variant
            ([[10, 10, 8, 11],
              [9, 8, 1, 1],
              [9, 7, 4, 10]],
             15
             ),
        ]

        m = Munkres()
        for cost_matrix, expected_total in matrices:
            print_matrix(cost_matrix, msg='cost matrix')
            indexes = m.compute(cost_matrix)
            total_cost = 0
            for r, c in indexes:
                x = cost_matrix[r][c]
                total_cost += x
                print('(%d, %d) -> %d' % (r, c, x))
            print('lowest cost=%d' % total_cost)
            assert expected_total == total_cost


if __name__ == "__main__":
    unittest.main(argv=sys.argv)
