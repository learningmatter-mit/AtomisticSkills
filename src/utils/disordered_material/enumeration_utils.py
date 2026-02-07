"""Structure enumeration and selection logic for Cluster Expansion."""

import logging
import numpy as np
import os
import json
import glob
from itertools import chain
from warnings import warn
from copy import deepcopy
from typing import List, Dict, Any, Optional, Union, Tuple
from pymatgen.core import Lattice, Structure
from pymatgen.entries.computed_entries import ComputedStructureEntry
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
from smol.moca import CompositionSpace, Ensemble, ClusterExpansionProcessor
from smol.cofe import ClusterSubspace, ClusterExpansion
from tqdm import tqdm

logger = logging.getLogger(__name__)

def get_three_factors(n: int) -> List[Tuple[int, int, int]]:
    """Get all triplets of integers (a, b, c) such that a*b*c = n."""
    factors = []
    for i in range(1, int(n ** (1/3)) + 1):
        if n % i == 0:
            for j in range(i, int((n / i) ** 0.5) + 1):
                if (n / i) % j == 0:
                    factors.append((i, j, int(n / (i * j))))
    return factors

def is_duplicate_sc(m1: np.ndarray, m2: np.ndarray, structure: Structure) -> bool:
    """Check if two supercell matrices are symmetrically equivalent."""
    l1 = Lattice(m1 @ structure.lattice.matrix)
    l2 = Lattice(m2 @ structure.lattice.matrix)
    return np.allclose(l1.abc, l2.abc) and np.allclose(l1.angles, l2.angles)

def deduplicate_by_correlation(structures, features, matrices, previous_femat=None, atol=1e-10, rtol=1e-10):
    """Remove structures with duplicate correlation vectors."""
    unique_structures = []
    unique_features = []
    unique_matrices = []
    
    seen_features = []
    if previous_femat is not None:
        seen_features = [np.array(f) for f in previous_femat]
    
    for s, f, m in zip(structures, features, matrices):
        f_array = np.array(f)
        is_duplicate = False
        for seen_f in seen_features:
            if np.allclose(f_array, seen_f, atol=atol, rtol=rtol):
                is_duplicate = True
                break
        
        if not is_duplicate:
            unique_structures.append(s)
            unique_features.append(f)
            unique_matrices.append(m)
            seen_features.append(f_array)
    
    return unique_structures, unique_features, unique_matrices

def enumerate_matrices(
    objective_sc_size: int,
    cluster_subspace: ClusterSubspace,
    supercell_from_conventional: bool = True,
    max_sc_cond: float = 8.0,
    min_sc_angle: float = 30.0,
    num_sizes: int = 3,
    **kwargs,
) -> List[List[List[int]]]:
    """Enumerate proper matrices across multiple supercell sizes."""
    prim = cluster_subspace.structure
    n_sites_prim = len(prim)
    target_det = objective_sc_size / n_sites_prim
    
    if not supercell_from_conventional:
        conv_mat = np.eye(3, dtype=int)
    else:
        try:
            sa = SpacegroupAnalyzer(prim, **kwargs)
            t_inv = sa.get_conventional_to_primitive_transformation_matrix()
            conv_mat = np.round(np.linalg.inv(t_inv)).astype(int)
        except Exception:
            conv_mat = np.eye(3, dtype=int)

    conv_det = int(round(abs(np.linalg.det(conv_mat))))
    base_det = max(1, int(round(target_det / conv_det)))
    
    m_dets = []
    for divisor in [1, 2, 4]:
        det = max(1, base_det // divisor)
        if det not in m_dets:
            m_dets.append(det)
        if len(m_dets) >= num_sizes:
            break
    
    if len(m_dets) < num_sizes and base_det > 1:
        double_det = base_det * 2
        if double_det not in m_dets:
            m_dets.append(double_det)
    
    logger.info(f"Enumerating supercell matrices for determinants: {m_dets}")
    
    all_results = []
    lat = prim.lattice

    for m_det in m_dets:
        factors = get_three_factors(m_det)
        scs_diagonal = [np.diag(sorted(m, reverse=True)) for m in factors]

        def cond_and_angle(sc):
            new_mat = sc @ lat.matrix
            new_lat = Lattice(new_mat)
            return (np.linalg.cond(sc), 
                    min([new_lat.alpha, new_lat.beta, new_lat.gamma, 
                         180 - new_lat.alpha, 180 - new_lat.beta, 180 - new_lat.gamma]))

        def filt_func(sc):
            cond, angle = cond_and_angle(sc @ conv_mat)
            return cond <= max_sc_cond and angle >= min_sc_angle

        scs_filtered = list(filter(filt_func, scs_diagonal))
        if scs_filtered:
            # Sort by condition number
            scs_filtered = sorted(scs_filtered, key=lambda sc: cond_and_angle(sc @ conv_mat)[0])
            all_results.append(np.round(scs_filtered[0] @ conv_mat).astype(int).tolist())
        
    # Ensure they are unique
    final_results = []
    seen = set()
    for r in all_results:
        t = tuple(np.array(r).flatten())
        if t not in seen:
            seen.add(t)
            final_results.append(r)
    
    return final_results

def truncate_cluster_subspace(cluster_subspace: ClusterSubspace, sc_matrices: List[np.ndarray]) -> ClusterSubspace:
    """Remove aliased orbits from subspace given supercell matrices."""
    all_aliases = []
    for m in sc_matrices:
        m_aliases = cluster_subspace.get_aliased_orbits(m)
        alias_m = {sorted(sub_orbit)[0]: set(sorted(sub_orbit)[1:]) for sub_orbit in m_aliases}
        all_aliases.append(alias_m)
        
    if not all_aliases:
        return cluster_subspace
        
    to_remove_dict = deepcopy(all_aliases[0])
    for alias_m in all_aliases[1:]:
        for key in list(to_remove_dict.keys()):
            if key in alias_m:
                to_remove_dict[key] = to_remove_dict[key].intersection(alias_m[key])
            else:
                del to_remove_dict[key]
                
    indices_to_remove = sorted(list(set(chain(*to_remove_dict.values()))))
    if indices_to_remove:
        logger.warning(f"Orbits {indices_to_remove} are aliased in all supercells and will be removed.")
        cluster_subspace.remove_orbits(indices_to_remove)
    
    return cluster_subspace

def enumerate_compositions_as_counts(sc_size: int, comp_space: CompositionSpace, comp_enumeration_step: int = 1) -> List[List[int]]:
    """Enumerate compositions in a given supercell size."""
    xs = comp_space.get_composition_grid(supercell_size=sc_size, step=comp_enumeration_step)
    ns = [comp_space.translate_format(x, sc_size, from_format="coordinates", to_format="counts", rounding=True) for x in xs]
    return np.array(ns).astype(int).tolist()

def get_random_occupancy_from_counts(ensemble: Ensemble, counts: List[int]) -> np.ndarray:
    """Generate random occupancy from species counts."""
    n_species = 0
    occu = np.zeros(ensemble.num_sites, dtype=np.int32) - 1
    for sublatt in ensemble.sublattices:
        if sublatt.is_active:
            n_sublatt = counts[n_species : n_species + len(sublatt.encoding)]
            if np.sum(n_sublatt) != len(sublatt.sites):
                raise ValueError(f"Composition: {counts} does not match sublattice size: {len(sublatt.sites)}!")
            occu_sublatt = [code for code, n in zip(sublatt.encoding, n_sublatt) for _ in range(n)]
            np.random.shuffle(occu_sublatt)
            occu[sublatt.sites] = occu_sublatt
            n_species += len(sublatt.encoding)
        else:
            occu[sublatt.sites] = sublatt.encoding[0]
    return occu

def select_initial_rows(femat: np.ndarray, n_select: int = 10, method: str = "leverage", num_external_terms: int = 0) -> List[int]:
    """Select structures to initialize an empty CE project using D-optimality (leverage-like)."""
    a = femat[:, : femat.shape[1] - num_external_terms]
    n, d = a.shape
    if n <= n_select: return list(range(n))

    selected_indices = [np.argmax(np.linalg.norm(a, axis=1))] # Start with max norm
    available_indices = list(set(range(n)) - set(selected_indices))

    for _ in range(n_select - 1):
        if method == "leverage":
            a_sel = a[selected_indices]
            cov_sel = a_sel.T @ a_sel
            # We want to minimize the variance error, essentially D-optimality
            # Here we use a simpler greedy approach: pick point that maximizes det increase
            # Which is equivalent to maximizing leverage score relative to current set
            inv_cov = np.linalg.pinv(cov_sel + 1e-6 * np.eye(d))
            leverages = np.sum((a[available_indices] @ inv_cov) * a[available_indices], axis=1)
            select_idx = available_indices[np.argmax(leverages)]
        else:
             select_idx = np.random.choice(available_indices)
             
        selected_indices.append(select_idx)
        available_indices.remove(select_idx)

    return selected_indices

def sample_ordered_structures(subspace: ClusterSubspace, sc_matrices: List[List[List[int]]], comp_space: CompositionSpace, max_structures: int = 100) -> Tuple[List[Structure], List[List[float]], List[List[List[int]]]]:
    """Enumerate structures for iteration 0 using systematic generation."""
    dummy_ce = ClusterExpansion(subspace, np.zeros(subspace.num_corr_functions))
    structures, features, matrices = [], [], []
    
    all_configs = []
    for mat in sc_matrices:
        mat_np = np.array(mat)
        sc_size = int(round(abs(np.linalg.det(mat_np))))
        counts_list = enumerate_compositions_as_counts(sc_size, comp_space)
        for c in counts_list:
            all_configs.append((mat, c))
    
    if not all_configs: return [], [], []
    
    num_per_config = max(1, max_structures // len(all_configs))
    logger.info(f"Generating ~{num_per_config} structures for each of {len(all_configs)} compositions...")
    
    for mat, counts in all_configs:
        mat_np = np.array(mat)
        ensemble = Ensemble.from_cluster_expansion(dummy_ce, mat_np, processor_type="expansion")
        processor = ClusterExpansionProcessor(subspace, mat_np, dummy_ce.coefs)
        
        for _ in range(num_per_config):
            occu = get_random_occupancy_from_counts(ensemble, counts)
            structures.append(processor.structure_from_occupancy(occu))
            features.append((processor.compute_feature_vector(occu) / processor.size).tolist())
            matrices.append(mat)
            if len(structures) >= max_structures: break
        if len(structures) >= max_structures: break
            
    return structures, features, matrices

def generate_training_structures(
    subspace: ClusterSubspace,
    sc_matrices: List[List[List[int]]],
    comp_space: CompositionSpace,
    num_structs: int = 100,
    previous_femat: Optional[np.ndarray] = None
) -> Tuple[List[Structure], List[List[float]], List[List[List[int]]]]:
    """Generate and select training structures via enumeration and D-optimality."""
    # 1. Enumerate candidates
    structures, features, matrices = sample_ordered_structures(
        subspace, sc_matrices, comp_space, max_structures=max(num_structs * 3, 1000)
    )
    
    if not structures: return [], [], []
    
    # 2. Deduplicate
    structures, features, matrices = deduplicate_by_correlation(
        structures, features, matrices, previous_femat=previous_femat
    )
    
    if len(structures) <= num_structs:
        return structures, features, matrices
        
    # 3. Select via D-optimality
    femat = np.array(features)
    selected_ids = select_initial_rows(femat, n_select=num_structs, num_external_terms=len(subspace.external_terms))
    
    return [structures[i] for i in selected_ids], [features[i] for i in selected_ids], [matrices[i] for i in selected_ids]
