# CFGUtils 
A Utility library for working with Control Flow Graphs (CFGs) in Python. This library implements previous academic 
and industrial research in the field of CFGs. It is also the home of the CFGED algorithm, refered to as Basque-CFGED, created in the USENIX Security
2024 Paper ["Ahoy SAILR! There is No Need to DREAM of C: A Compiler-Aware Structuring Algorithm for Binary Decompilation"](https://www.zionbasque.com/files/publications/sailr_usenix24.pdf).

If you use this library in your research, please cite the SAILR paper. 


## Install
```bash 
pip3 install cfgutils
```

## Usage
CFGUtils is used on Networkx DiGraphs. Most analysis assumes the graph is composed of [GenericBlock](cfgutils/data/generic_block.py) nodes. 
The nodes a very simple and can be subclassed to represent different kinds of blocks.

All algorithms in this library have a testcase, which can be found in the [tests.py](tests/test_ged.py) file.

### Region Identification
Regions here are defined as [Single-Entry Single-Exit (SESE)](https://iss.oden.utexas.edu/Publications/Papers/PLDI1994.pdf) subgraphs of the CFG.
These regions are mostly used in the context of control flow recovery and decompilation. 

```python
from cfgutils.data.generic_block import GenericBlock
from cfgutils.regions.region_identifier import RegionIdentifier
import networkx as nx

blocks = [GenericBlock(i) for i in range(9)]
numbered_edges = [(1, 2), (1, 3), (2, 4), (3, 4), (4, 5), (4, 6), (5, 7), (6, 7)]
block_edges = [
    (blocks[in_e], blocks[out_e]) for (in_e, out_e) in numbered_edges
]
graph = nx.DiGraph(block_edges)
ri = RegionIdentifier(graph)
top_region = ri.region
print(top_region.graph.nodes)
```
Subclass `GenericBlock` to use different kinds of blocks in your graph.

### Basque CFGED
The Basque CFGED algorithm is a graph edit distance algorithm for CFGs. To use it you need to have two CFGs and a mapping of the nodes between the two graphs.
Not all nodes need to be mapped, just as many as you can do. 

```python
import networkx as nx
from cfgutils.similarity import cfg_edit_distance
from cfgutils.data import numbered_edges_to_block_graph


g1: nx.DiGraph = numbered_edges_to_block_graph([(1, 2), (1, 3), (3, 6.2), (3, 5), (5, 6.2), (2, 6.1)])
g2: nx.DiGraph = numbered_edges_to_block_graph([(1, 2), (1, 3), (3, 4), (3, 5), (4, 6), (5, 6), (2, 6)])
mapping = {n: {n} for n in range(7)}
# see tests for an explanation
assert cfg_edit_distance(g1, g2, mapping, mapping) == 5
```

## Features
- Region Identification
- Graph Edit Distance:
  - Basque CFGED
  - Abu-Aisheh GED
  - Hu CFGED 
- Dominator Trees

