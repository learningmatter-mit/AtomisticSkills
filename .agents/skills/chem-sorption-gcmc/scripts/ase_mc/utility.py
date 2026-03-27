import numpy as np
from scipy.constants import hbar, Avogadro, Boltzmann
from scipy import sparse
from ase import neighborlist, units
from ase.parallel import world, DummyMPI


def get_components(atoms, radii = None):
    '''Returns the total number of compontents, component list, and connectivity matrix of an ASE atoms object'''

    if radii is None:
        cut_offs = neighborlist.natural_cutoffs(atoms)
    else:
        cut_offs = radii

    neighbor_list = neighborlist.NeighborList(
        cut_offs, self_interaction=False, bothways=True
    )
    neighbor_list.update(atoms)
    connectivity_matrix = neighbor_list.get_connectivity_matrix()
    n_components, component_list = sparse.csgraph.connected_components(
        connectivity_matrix
    )
    return n_components, component_list, connectivity_matrix


def calculate_virial_pressure(atoms, temperature_K):
    temp = temperature_K
    natoms = len(atoms)
    volume = atoms.get_volume()
    number_density = natoms / volume

    pressure_ideal = number_density * units.kB * temp

    virial = 0
    r = atoms.get_positions()
    f = atoms.get_forces()
    for i in range(natoms):
        virial += np.dot(r[i], f[i])

    virial /= 3.0

    pressure_excess = virial / volume
    pressure = pressure_ideal + pressure_excess
    return pressure


def random_packing(atoms, adsorbate, n=1, tolerance=2.0, max_iter=1000, communicator=world):
    """A system setup function that tries to insert n number of probe molecules"""

    if communicator is None:
        communicator = DummyMPI()

    h = np.array(atoms.get_cell()).T
    adsorbate.set_cell(None)
    adsorbate.center()
    for probe_count in range(n):
        overlap = True
        attempt = 0
        while overlap:
            if attempt == max_iter:
                print(f"WARNING: MAX ITER REACHED.")
                print(f"WARNING: Could not pack system with {n} probe molecules.")
                print(f"WARNING: System currently has {probe_count + 1} molecules.")
                break

            adsorbate.set_cell(None)
            adsorbate.center()
            n_atoms = len(atoms)

            zeta_angles = np.random.rand(3)
            communicator.broadcast(zeta_angles, 0)

            phi = 2.0 * (zeta_angles[0] - 1.0) * 360.0
            phi -= np.rint(phi / 360.0) * 360.0

            costheta = 2.0 * (zeta_angles[1] - 1.0) * 1.0
            costheta -= np.rint((costheta / 2.0)) * 2.0
            theta = np.rad2deg(np.arccos(costheta))

            psi = 2.0 * (zeta_angles[2] - 1.0) * 360.0
            psi -= np.rint(psi / 360.0) * 360.0

            adsorbate.euler_rotate(phi, theta, psi, center="COM")

            zeta_dr = np.random.rand(3)
            communicator.broadcast(zeta_dr, 0)

            r = np.matmul(h, zeta_dr.T)
            adsorbate.center()
            adsorbate.translate(r)
            adsorbate.set_cell(h)
            s_ads = adsorbate.get_scaled_positions()

            # No other atoms are in the box
            if len(adsorbate) - len(atoms) == len(adsorbate):
                overlap = False

            # Check for overlap
            else:
                overlap = False
                s_atoms = atoms.get_scaled_positions()
                for s in s_ads:
                    ds = s - s_atoms
                    ds -= np.rint(ds)
                    drT = np.matmul(h, ds.T)
                    dr = drT.T
                    drnorm = np.linalg.norm(dr, axis=1)
                    if np.any(drnorm < tolerance):
                        overlap = True
                        break

        atoms += adsorbate


def thermal_debroglie(mass_amu, temperature_K):
    """Returns thermal Debroglie wavelength in angstrom"""
    kg_to_g = 1000.0
    m_to_angstrom = 1e10

    mass_kg = mass_amu / Avogadro / kg_to_g
    debroglie_m = np.sqrt(
        2.0 * np.pi * hbar * hbar / mass_kg / Boltzmann / temperature_K
    )
    debroglie_angstrom = debroglie_m * m_to_angstrom
    return debroglie_angstrom


def chemical_potential_to_activity(
    chemical_potential_kjpermol, mass_amu, temperature_K
):
    """converts chemical potential in kJ/mol to activity in 1/Angstrom^3"""
    kj_to_j = 1000.0
    debroglie_angstrom = thermal_debroglie(mass_amu, temperature_K)
    debroglie3 = debroglie_angstrom**3
    arg = chemical_potential_kjpermol * kj_to_j / Avogadro / Boltzmann / temperature_K
    activity_one_over_angstrom3 = np.exp(arg) / debroglie3
    return activity_one_over_angstrom3

