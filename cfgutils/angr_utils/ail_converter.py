import pickle
from pathlib import Path
import logging

import networkx as nx
import angr

from .prettyify_ail import stmt_to_pretty_text
from cfgutils.data.generic_block import GenericBlock

_l = logging.getLogger(__name__)


def _binary_to_ail_cfgs(binary_path: Path, functions=None):
    binary_path = Path(binary_path).absolute()
    if not binary_path.exists():
        raise FileNotFoundError(f"{binary_path} does not exist")

    proj = angr.Project(binary_path, auto_load_libs=False)
    cfg = proj.analyses.CFG(show_progressbar=False, normalize=True, data_references=True)
    try:
        proj.analyses.CompleteCallingConventions(cfg=cfg, recover_variables=True, analyze_callsites=True)
        cc_failed = False
    except Exception:
        cc_failed = True

    if cc_failed:
        _l.warning(f"CallingConvention Analysis failed on {binary_path}. Trying again without variable recovery...")
        try:
            # try it again without variable recovery
            proj.analyses.CompleteCallingConventions(cfg=cfg, recover_variables=False)
            cc_failed = False
        except Exception:
            pass

    if cc_failed:
        _l.critical(f"All attempts to run CallingConvention Analysis failed on {binary_path}.")

    # clean up function names
    functions = functions or cfg.functions
    for func in list(cfg.functions.values()):
        if "." in func.name:
            func.name = func.name[:func.name.index(".")]

    # generate a cfg for each function
    ail_cfgs = []
    for func_idx, func_addr in enumerate(functions):
        try:
            f = cfg.functions[func_addr]
        except Exception:
            _l.critical(f"Function at {func_addr} not found in CFG")
            continue

        if f is None or f.is_plt:
            continue

        dec = proj.analyses.Decompiler(f, cfg=cfg, kb=cfg.kb)
        ail_cfgs.append(dec.clinic.cc_graph)

    return ail_cfgs


def ail_cfg_to_generic(cfg: nx.DiGraph, project=None):
    new_cfg = nx.DiGraph()
    new_cfg.name = cfg.name
    proj_cfg = project.kb.cfgs.get_most_accurate() if project is not None else None
    node_map = {}
    for node in cfg.nodes:
        new_node = GenericBlock(node.addr, idx=node.idx if hasattr(node, "idx") else None)
        for stmt in node.statements:
            str_stmt = stmt_to_pretty_text(stmt, project, proj_cfg) if project is not None else str(stmt)
            new_node.statements.append(str_stmt)

        new_cfg.add_node(new_node, node=new_node)
        node_map[node] = new_node

    for src, dst in cfg.edges:
        new_src = node_map[src]
        new_dst = node_map[dst]
        new_cfg.add_edge(new_src, new_dst, src=new_src, dst=new_dst)

    return new_cfg


def binary_to_cfgs(binary_path: Path, functions=None):
    ail_cfgs = _binary_to_ail_cfgs(binary_path, functions)
    cfgs = [ail_cfg_to_generic(cfg) for cfg in ail_cfgs]
    return cfgs


def ail_pickle_to_cfg(pickle_path: Path):
    """
    This function converts a pickle files, containing an AIL CFG, into a GenericBlock CFG for use with
    CFGUtils functions. Note: this pickled AIL CFG is a little special. All the nodes in the CFG are just
    the addresses of the blocks (not real AIL nodes). The 'label' attribute of each node is a list of strings,
    which is simply each AIL stmt stringed.
    """

    with open(pickle_path, "rb") as fp:
        ail_str_cfg: nx.DiGraph = pickle.load(fp)

    new_cfg = nx.DiGraph()
    node_map = {}
    for node in ail_str_cfg.nodes:
        new_node = GenericBlock(int(node), statements=ail_str_cfg.nodes[node]["label"])
        new_cfg.add_node(new_node, node=new_node)
        node_map[node] = new_node

    for src, dst in ail_str_cfg.edges:
        new_src = node_map[src]
        new_dst = node_map[dst]
        new_cfg.add_edge(new_src, new_dst, src=new_src, dst=new_dst)

    return new_cfg

