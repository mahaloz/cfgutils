import pickle
from pathlib import Path
import logging
from typing import Union, Dict, Tuple

import ailment
import networkx as nx
import angr
from angr.analyses.decompiler.optimization_passes import DUPLICATING_OPTS, CONDENSING_OPTS, LoweredSwitchSimplifier

HAS_PRESETS = True
try:
    from angr.analyses.decompiler import DECOMPILATION_PRESETS
except ImportError:
    DECOMPILATION_PRESETS = None
    HAS_PRESETS = False

from .prettyify_ail import stmt_to_pretty_text
from cfgutils.data.generic_block import GenericBlock

_l = logging.getLogger(__name__)


def _set_decompiler_option(decompiler_options_strs: tuple[str, object]) -> list[tuple]:
    decompiler_options = []
    if not decompiler_options_strs:
        return decompiler_options

    for param, value in decompiler_options_strs:
        for option in angr.analyses.decompiler.decompilation_options.options:
            if param == option.param:
                decompiler_options.append((option, value))

    return decompiler_options


def binary_to_ail_cfgs(
    binary_path: Path, functions=None, make_generic=False, structuring_opts=True, supergraph=True,
    return_project=False, decompiler_options=None
) -> Union[Dict[str, nx.DiGraph], Tuple[Dict[str, nx.DiGraph], angr.Project]]:
    """
    A simple wrapper around the angr decompiler to simply use the defaults and return the AIL CFGs which
    are present at the end of the decompilation process. Using make_generic, you can convert the AIL CFGs
    into GenericBlock CFGs for use with CFGUtils functions. You can also disable some of the structuring
    optimizations if you want to see the raw CFGs.

    :param binary_path: Path to the binary to decompile
    :param functions: List of function addresses to decompile. If None, all functions will be decompiled
    :param make_generic: Convert the AIL CFGs to GenericBlock CFGs
    :param structuring_opts: Enable or disable structuring optimizations
    :param supergraph: Convert the AIL CFGs to supergraphs
    :param return_project: Return the angr Project object as well
    :param decompiler_options: A list of tuples containing the decompiler options to set. Each tuple should be
        in the format (option_name, option_value). See angr documentation for available options.
    """
    binary_path = Path(binary_path).absolute()
    if not binary_path.exists():
        raise FileNotFoundError(f"{binary_path} does not exist")

    proj = angr.Project(binary_path, auto_load_libs=False)
    func_starts = None
    if functions is not None and all(isinstance(func, int) for func in functions):
        func_starts = functions

    cfg = proj.analyses.CFG(
        show_progressbar=False, normalize=True, data_references=True, resolve_indirect_jumps=True,
        function_starts=func_starts
    )
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

    # some optimizations can drastically change the structure of the CFG, so we should disable some if wanted
    if HAS_PRESETS:
        dec_opts = DECOMPILATION_PRESETS["fast"].get_optimization_passes("AMD64", "linux",)
    else:
        dec_opts = angr.analyses.decompiler.optimization_passes.get_optimization_passes(
            proj.arch, "linux"
        )
    if not structuring_opts:
        dec_opts = [opt for opt in dec_opts if opt not in DUPLICATING_OPTS + CONDENSING_OPTS]
        if LoweredSwitchSimplifier in dec_opts:
            dec_opts.remove(LoweredSwitchSimplifier)

    # generate a cfg for each function
    ail_cfgs = {}
    for func_idx, func_addr in enumerate(functions):
        try:
            f = cfg.functions[func_addr]
        except Exception:
            _l.critical(f"Function at {func_addr} not found in CFG")
            continue

        if f is None or f.is_plt:
            continue

        # for this function you don't actually need the linear decompilation, but we run through the entire
        # decompilation process to assure every optimization is run that would be done on a normal Clinic graph
        dec = proj.analyses.Decompiler(
            f, cfg=cfg, kb=cfg.kb, optimization_passes=dec_opts, generate_code=False,
            options=_set_decompiler_option(decompiler_options)
        )
        dec.ail_graph.name = str(f.name)
        ail_cfgs[str(f.name)] = dec.ail_graph if not supergraph else to_ail_supergraph(dec.ail_graph)

    if make_generic:
        cfgs = [ail_cfg_to_generic(cfg, proj) for name, cfg in ail_cfgs.items()]
    else:
        cfgs = list(ail_cfgs.values())

    named_cfgs = {cfg.name or str(i): cfg for i, cfg in enumerate(cfgs)}
    if return_project:
        return named_cfgs, proj
    else:
        return named_cfgs


def ail_cfg_to_generic(cfg: nx.DiGraph, project=None):
    new_cfg = nx.DiGraph()
    new_cfg.name = cfg.name
    proj_cfg = project.kb.cfgs.get_most_accurate() if project is not None else None
    node_map = {}
    for node, attr in cfg.nodes(data=True):
        new_node = GenericBlock(node.addr, idx=node.idx if hasattr(node, "idx") else None)
        for stmt in node.statements:
            str_stmt = stmt_to_pretty_text(stmt, project, proj_cfg) if project is not None else str(stmt)
            new_node.statements.append(str_stmt)

        attr = attr or {}
        new_attr = attr.copy()
        if "node" in new_attr:
            del new_attr["node"]

        new_cfg.add_node(new_node, node=new_node, **new_attr)
        node_map[node] = new_node

    for src, dst in cfg.edges:
        new_src = node_map[src]
        new_dst = node_map[dst]
        new_cfg.add_edge(new_src, new_dst, src=new_src, dst=new_dst)

    return new_cfg


def binary_to_generic_cfgs(binary_path: Path, functions=None):
    return binary_to_ail_cfgs(binary_path, functions, make_generic=True)


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


#
# TODO: all of the following functions need to be removed when  is fixed
#   this code was added as a hotfix to make the AIL CFGs supergraphs
#

def _merge_ail_nodes(graph, node_a: ailment.Block, node_b: ailment.Block) -> ailment.Block:
    in_edges = list(graph.in_edges(node_a, data=True))
    out_edges = list(graph.out_edges(node_b, data=True))

    a_ogs = graph.nodes[node_a].get("original_nodes", set())
    b_ogs = graph.nodes[node_b].get("original_nodes", set())
    new_node = node_a.copy() if node_a.addr <= node_b.addr else node_b.copy()
    old_node = node_b if new_node == node_a else node_a
    # remove jumps in the middle of nodes when merging
    if new_node.statements and isinstance(new_node.statements[-1], ailment.Stmt.Jump):
        new_node.statements = new_node.statements[:-1]
    new_node.statements += old_node.statements
    new_node.original_size += old_node.original_size

    graph.remove_node(node_a)
    graph.remove_node(node_b)

    if new_node is not None:
        graph.add_node(new_node, original_nodes=a_ogs.union(b_ogs))
        for src, _, data in in_edges:
            if src is node_b:
                src = new_node
            graph.add_edge(src, new_node, **data)

        for _, dst, data in out_edges:
            if dst is node_a:
                dst = new_node
            graph.add_edge(new_node, dst, **data)

    return new_node


def to_ail_supergraph(transition_graph: nx.DiGraph) -> nx.DiGraph:
    """
    Takes an AIL graph and converts it into a AIL graph that treats calls and redundant jumps
    as parts of a bigger block instead of transitions. Calls to returning functions do not terminate basic blocks.

    Based on region_identifier super_graph

    :return: A converted super transition graph
    """
    # make a copy of the graph
    transition_graph = nx.DiGraph(transition_graph)
    nx.set_node_attributes(transition_graph, {node: {node} for node in transition_graph.nodes}, "original_nodes")

    while True:
        for src, dst, data in transition_graph.edges(data=True):
            type_ = data.get("type", None)

            if len(list(transition_graph.successors(src))) == 1 and len(list(transition_graph.predecessors(dst))) == 1:
                # calls in the middle of blocks OR boring jumps
                # XXX: patch is here
                _merge_ail_nodes(transition_graph, src, dst)
                break

            # calls to functions with no return
            elif type_ == "call":
                transition_graph.remove_node(dst)
                break
        else:
            break

    return transition_graph
