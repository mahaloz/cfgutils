from pathlib import Path

import networkx as nx
import graphviz


def save_cfg_as_png(cfg: nx.DiGraph, output_path: Path):
    tmp_path = output_path.with_suffix(".dot")
    nx.drawing.nx_agraph.write_dot(cfg, str(tmp_path))
    dot_src = graphviz.Source(open(tmp_path).read(), format="png")
    dot_src.render(outfile=str(output_path.with_suffix(".png")))
    tmp_path.with_suffix(".gv").unlink()
    tmp_path.unlink()
    return output_path.with_suffix(".png")
