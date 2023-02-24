# cfgutils
A Utility library for analysis of Control Flow Graphs

## Install
```bash 
pip3 install -e .
```

## Usage
### Region Identification
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
