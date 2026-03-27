import numpy as np
from scipy import sparse
from copy import deepcopy
from ase import neighborlist, Atoms, units
from ase.parallel import world, DummyMPI
from ase.calculators.singlepoint import SinglePointCalculator


class MCMove:
    def __init__(
        self,
        name,
        accepted,
        attempted,
        probability,
        twobox=False,
        beta=None,
        r_overlap=None,
        max_delta=None,
        update_frequency=None,
        scale_delta=None,
        target_acceptance=None,
        communicator=world,
        rng=None,

        nsteps=None,

        pressure=None,
        mask=None,
        ln_volume=True,

        b_parameter=None,
        reference_energy=None,

        grid_resolution=None,
        rcavity=None,
        cavity_bias=None,

        species=None,
        species_tag=None,

        limits = None,

        ):
        if communicator is None:
            communicator = DummyMPI()
        self.communicator = communicator
        if rng is None:
            self.rng = np.random
        else:
            self.rng = rng

        self.name = name
        self.accepted = accepted
        self.attempted = attempted
        self.probability = probability
        self.twobox = twobox

        self.beta = beta
        self.r_overlap = r_overlap
        self.max_delta = max_delta
        self.update_frequency = update_frequency
        self.scale_delta = scale_delta
        self.target_acceptance = target_acceptance

        self.nsteps = nsteps

        self.pressure = pressure
        self.mask = mask
        self.ln_volume = ln_volume

        self.b_parameter = b_parameter
        self.reference_energy = reference_energy
        self.grid_resolution = grid_resolution
        self.rcavity = rcavity
        self.cavity_bias = cavity_bias

        self.component_list = None
        self.n_components = None
        self.species = species
        self.species_tag = species_tag

        self.limits = limits

        # 0 means no bias and is metropolis sampling
        self.ln_alpha_no = 0.0
        self.ln_alpha_on = 0.0
        self.ln_pcav = 0.0

        if grid_resolution is not None:
            res_x = np.linspace(0, 1, num=grid_resolution, endpoint=False)
            res_y = np.linspace(0, 1, num=grid_resolution, endpoint=False)
            res_z = np.linspace(0, 1, num=grid_resolution, endpoint=False)


            self.ncavities = 0
            self.ngrid_points = grid_resolution**3
            self.iscavity = np.ones(self.ngrid_points, dtype=bool)

            xx, yy, zz = np.meshgrid(res_x, res_y, res_z)
            self.grid_points = np.vstack((xx.ravel(), yy.ravel(), zz.ravel())).T

            #r_grid = (hmat @ s_grid.T).T
            #self.grid_points = np.zeros((self.ngrid_points, 3))
            #i = 0
            #for gx in res_x:
            #    for gy in res_y:
            #        for gz in res_z:
            #            self.grid_points[i] = np.array([gx, gy, gz])
            #            i += 1



    def generate_uniform_random_number(self, n=1):
        zeta = self.rng.rand(n)
        self.communicator.broadcast(zeta, 0)
        if n == 1:
            zeta = zeta[0]
        return zeta

    def random_choice_from_array(self, arr):
        zeta = np.array([self.rng.randint(len(arr))]) # Do this bc MPI4Py only works with NumPy arrays
        self.communicator.broadcast(zeta, 0)
        choice = arr[zeta[0]]
        return choice

    def initialize_bookkeeping(self, atoms, results_o=None, need_forces=False):
        if (results_o is None) or ("energy" not in results_o):
            potential_energy_o = atoms.get_potential_energy()
        else:
            potential_energy_o = results_o["energy"]

        forces_o = None
        if need_forces:
            if (results_o is None) or ("forces" not in results_o):
                forces_o = atoms.get_forces()
            else:
                forces_o = results_o["forces"]

        return potential_energy_o, forces_o

    def set_component_list(self, atoms):
        n_components, component_list, _ = self.get_components(atoms)
        self.component_list = component_list
        self.n_components = n_components

    def get_mol_idxs(self, atom_idx):
        mol_idx = self.component_list[atom_idx]
        mol_idxs = [ atom_idx for atom_idx in range(len(self.component_list)) if self.component_list[atom_idx] == mol_idx ]
        return np.array(mol_idxs)

    def get_components(self, atoms, radii = None):

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

    def get_random_molecule_otf(self, atoms, exclusion_list = None):
        """Choose a random molecule as array of atom indicies using ASE's neighbor list and SciPy"""
        # Ensures we do not pick an index in the exclusion_list
        if exclusion_list is None:
            index_list = np.arange(len(atoms))
        else:
            x = np.arange(len(atoms))
            index_list = np.delete(x, exclusion_list)
        atom_idx = self.random_choice_from_array(index_list)

        # Setting the component list does not take into account the exclusion list
        self.set_component_list(atoms)
        mol_idxs = self.get_mol_idxs(atom_idx)

        # If any indexes are in the exclusion list, we need to remove those from mol_idxs
        if exclusion_list is None:
            return mol_idxs
        else:
            mol_idxs = np.setdiff1d(mol_idxs, exclusion_list)
            return mol_idxs


    def check_overlap(self, atoms, selection = None):
        if selection is None:
            distances = atoms.get_all_distances(mic = True)
            # Drop diagonal entries
            m = distances.shape[0]
            strided = np.lib.stride_tricks.as_strided
            s0, s1 = distances.strides
            distances_dropped = strided(
                distances.ravel()[1:], shape=(m - 1, m), strides=(s0 + s1, s1)
            ).reshape(m, -1)
            overlap = np.any(distances_dropped < self.r_overlap)

        else:
            overlap = False
            natoms = len(atoms)
            all_atom_indices = np.arange(0, natoms)
            other_atom_indices = np.delete(all_atom_indices, selection)
            for atomidx in selection:
                distances = atoms.get_distances(atomidx, other_atom_indices, mic = True)
                if np.any(distances < self.r_overlap):
                    overlap = True
                    break

        return overlap


    def get_acceptance_rate(self):
        return self.accepted / self.attempted

    def copy_with_properties(self, atoms, results):
        atoms_copy = atoms.copy()
        atoms_copy.calc = SinglePointCalculator(atoms_copy, **results)
        return atoms_copy

    def random_unit_vector(self):
        ransq = 2.0
        while ransq >= 1.0:
            zeta = self.generate_uniform_random_number(n=2)
            ran1 = 1.0 - 2.0*zeta[0]
            ran2 = 1.0 - 2.0*zeta[1]
            ransq = ran1*ran1 + ran2*ran2

        ranh = 2.0 * np.sqrt(1.0 - ransq)
        ux = ran1 * ranh
        uy = ran2 * ranh
        uz = 1.0 - 2.0*ransq
        u = np.array([ux, uy, uz])
        return u


    def random_rotation_angles(self, max_angle = 180.0):
        twopi_rad = 2.0 * np.pi
        twopi_deg = 360.0
        zeta_angles = self.generate_uniform_random_number(n=3)
        zeta = 2.0 * (zeta_angles - 1.0)

        phi = max_angle * zeta[0]
        phi -= np.rint(phi / twopi_deg) * twopi_deg

        costheta = np.cos(np.radians(max_angle)) * zeta[1]
        costheta -= np.rint(costheta / 2.0) * 2.0
        theta = np.degrees(np.arccos(costheta))

        psi = max_angle * zeta[2]
        psi -= np.rint(psi / twopi_deg) * twopi_deg

        return phi, theta, psi

    def gen_random_orientation(self):
        # Generate a random orientation for your species
        r = self.species.get_positions()
        s = self.species.get_chemical_symbols()
        atoms = Atoms(s, r)
        atoms.center()

        for idx, atom in enumerate(atoms):
            atom.tag = self.species[idx].tag

        phi, theta, psi = self.random_rotation_angles()
        atoms.euler_rotate(phi, theta, psi, center="COM")
        return atoms

    def generate_v_n(self, atoms):
        v_o = atoms.get_volume()
        zeta = self.generate_uniform_random_number(n=1)

        if self.ln_volume:
            dlnV = (2.0 * zeta - 1.0) * self.max_delta
            v_n = np.exp(dlnV) * v_o
        else:
            dV = (2.0 * zeta - 1.0) * self.max_delta
            v_n = v_o + dV

        if self.mask is not None:
            # Pick one of the vectors to scale in our mask
            lattice_vector_idx = self.random_choice_from_array(self.mask)
            s = v_n / v_o
            cell_o = atoms.get_cell()
            vector_o = cell_o[lattice_vector_idx]
            vector_n = vector_o * s
            cell_n = deepcopy(cell_o)
            cell_n[lattice_vector_idx] = vector_n
        else:
            s = (v_n / v_o) ** (1.0 / 3.0)
            cell_o = atoms.get_cell()
            cell_n = cell_o * s

        return cell_n, v_n

    def MBDistribution(self, atoms):
        masses = atoms.get_masses()
        zeta_momenta = np.random.standard_normal((len(atoms), 3))
        self.communicator.broadcast(zeta_momenta, 0)
        momenta = zeta_momenta * np.sqrt(masses / self.beta)[:, np.newaxis]
        atoms.set_momenta(momenta)

    def velocity_verlet_step(self, atoms, forces):
        '''Copied mostly from ase.md.verlet, here, we use self.max_delta as the timestep for MD'''

        p = atoms.get_momenta()
        p += 0.5 * self.max_delta * forces
        masses = atoms.get_masses()[:, np.newaxis]
        r = atoms.get_positions()

        atoms.set_positions(r + self.max_delta * p / masses)
        if atoms.constraints:
            p = (atoms.get_positions() - r) * masses / self.max_delta

        atoms.set_momenta(p, apply_constraint=False)

        # We might have overlap here, check if we do before computing forces
        overlap = self.check_overlap(atoms)
        if overlap:
            pass
        else:
            forces_n = atoms.get_forces(md=True)
            atoms.set_momenta(atoms.get_momenta() + 0.5 * self.max_delta * forces_n)
        return overlap


    def update_max_delta(self):
        if self.attempted % self.update_frequency == 0 and self.attempted != 0:
            if self.get_acceptance_rate() >= self.target_acceptance:
                self.max_delta *= 1.0 + self.scale_delta
            else:
                self.max_delta *= 1.0 - self.scale_delta

            if self.limits is not None:
                if self.max_delta < self.limits[0]:
                    self.max_delta = self.limits[0]
                elif self.max_delta  > self.limits[1]:
                    self.max_delta = self.limits[1]



    def find_cavities(self, hmat, s):
        for grid_idx, grid_s in enumerate(self.grid_points):
            ds = s - grid_s
            ds -= np.rint(ds)
            dr = (hmat @ ds.T).T
            distances = np.linalg.norm(dr, axis=1)
            self.iscavity[grid_idx] = np.logical_not(np.any(distances < self.rcavity))
        return self.grid_points[self.iscavity]

    def acceptance_rule(self):
        pass

    def execute(self):
        pass

    def get_move_stats(self):
        pass



class Thermal(MCMove):
    def __init__(
        self,
        accepted,
        attempted,
        probability,
        update_frequency,
        max_delta,
        beta,
        r_overlap,
        target_acceptance,
        scale_delta,
        exclusion_list = None,
        limits = None,
        name="Thermal",
        communicator=world,
        rng=None,
    ):
        MCMove.__init__(
            self,
            name=name,
            accepted=accepted,
            attempted=attempted,
            probability=probability,
            r_overlap=r_overlap,
            update_frequency = update_frequency,
            max_delta = max_delta,
            limits = limits,
            beta = beta,
            target_acceptance = target_acceptance,
            scale_delta = scale_delta,
            communicator=communicator,
            rng=rng,
        )
        self.exclusion_list = exclusion_list

    def execute(self, atoms, results_o):
        r_o = atoms.get_positions()
        potential_energy_o, forces_o = self.initialize_bookkeeping(
            atoms, results_o, need_forces=False
        )

        autoreject = False
        if self.exclusion_list is not None:
            if len(atoms) - len(self.exclusion_list) == 0:
                autoreject = True

        if autoreject:
            accepted = False

        else:
            self.generate_r_n(atoms)

            if self.check_overlap(atoms):
                accepted = False

            else:
                potential_energy_n = atoms.get_potential_energy()
                results_n = atoms.calc.results
                energy_n = atoms.get_potential_energy()
                accepted = self.acceptance_rule(potential_energy_n, potential_energy_o)

        if accepted:
            energy = energy_n
            results = atoms.calc.results
            self.accepted += 1
        else:
            atoms.set_positions(r_o)
            results = results_o

        self.attempted += 1
        self.update_max_delta()

        return accepted, results

    def acceptance_rule(self, pe_n, pe_o):
        zeta = self.generate_uniform_random_number(n=1)
        ln_zeta = np.log(zeta)
        energetic = -self.beta * (pe_n - pe_o)
        return ln_zeta < energetic

    def generate_r_n(self, atoms):
        pass

    def get_move_stats(self):
        s = ""
        s += f"move:{self.name}#"
        s += f"accepted:{self.accepted}#"
        s += f"attempted:{self.attempted}#"
        s += f"max_delta:{self.max_delta:.3f}#"
        return s



class Translate(Thermal):
    def __init__(
        self,
        accepted,
        attempted,
        probability,
        update_frequency,
        max_delta,
        beta,
        target_acceptance,
        scale_delta,
        r_overlap,
        exclusion_list = None,
        limits=(0.1, 14.0),
        name="Translate",
        communicator=world,
        rng=None,
        ):

        Thermal.__init__(
            self,
            name=name,
            accepted=accepted,
            attempted=attempted,
            probability=probability,
            update_frequency=update_frequency,
            max_delta=max_delta,
            beta=beta,
            target_acceptance=target_acceptance,
            scale_delta=scale_delta,
            r_overlap=r_overlap,
            exclusion_list = exclusion_list,
            limits=limits,
            communicator=communicator,
            rng=rng,
            )

    def generate_r_n(self, atoms):
        r_o = atoms.get_positions()
        mol_idxs = self.get_random_molecule_otf(atoms, self.exclusion_list)
        unit_vector = self.random_unit_vector()
        zeta = self.generate_uniform_random_number(n=1)
        dr = np.zeros(r_o.shape)
        dr[mol_idxs] = zeta * self.max_delta * unit_vector
        r_n = r_o + dr
        atoms.set_positions(r_n)


class Rotate(Thermal):
    def __init__(
        self,
        accepted,
        attempted,
        probability,
        update_frequency,
        max_delta,
        beta,
        r_overlap,
        target_acceptance,
        scale_delta,
        limits = (0.1, 180.0),
        exclusion_list = None,
        name="Rotate",
        communicator=world,
        rng=None,
        ):

        Thermal.__init__(
            self,
            name=name,
            accepted=accepted,
            attempted=attempted,
            probability=probability,
            update_frequency=update_frequency,
            max_delta=max_delta,
            limits = limits,
            beta=beta,
            r_overlap=r_overlap,
            target_acceptance=target_acceptance,
            exclusion_list = exclusion_list,
            scale_delta=scale_delta,
            communicator=communicator,
            rng=rng,
            )

    def generate_r_n(self, atoms):
        r_o = atoms.get_positions()
        mol_idxs = self.get_random_molecule_otf(atoms, self.exclusion_list)
        atoms_tmp = atoms[mol_idxs]
        phi, theta, psi = self.random_rotation_angles(max_angle = self.max_delta)
        atoms_tmp.euler_rotate(phi, theta, psi, center="COM")
        dr = np.zeros(r_o.shape)
        dr[mol_idxs] = atoms_tmp.get_positions() - r_o[mol_idxs]
        r_n = r_o + dr
        atoms.set_positions(r_n)



class HMC(MCMove):
    def __init__(
        self,
        accepted,
        attempted,
        probability,
        dt,
        nsteps,
        beta,
        r_overlap,
        update_frequency,
        scale_delta,
        target_acceptance,
        limits=(0.5 * units.fs, 5 * units.fs),
        name="HMC",
        communicator=world,
        rng=None,
    ):
        MCMove.__init__(
            self,
            name=name,
            accepted=accepted,
            attempted=attempted,
            probability=probability,
            max_delta=dt,
            nsteps=nsteps,
            beta=beta,
            r_overlap=r_overlap,
            update_frequency=update_frequency,
            scale_delta=scale_delta,
            target_acceptance=target_acceptance,
            communicator=communicator,
            rng=rng,
        )

        self.limits = limits

    def acceptance_rule(self, pe_o, pe_n, ke_o, ke_n):
        zeta = self.generate_uniform_random_number(n=1)
        ln_zeta = np.log(zeta)
        dE = pe_n - pe_o
        dK = ke_n - ke_o
        dH = dE + dK
        return ln_zeta < -self.beta * dH

    def execute(self, atoms, results_o):
        potential_energy_o, forces_o = self.initialize_bookkeeping(
            atoms, results_o, need_forces=True
        )

        self.MBDistribution(atoms)
        position_o = atoms.get_positions()
        kinetic_energy_o = atoms.get_kinetic_energy()

        first_step = True
        for _ in range(self.nsteps):
            if first_step:
                forces = atoms.get_forces()
                first_step = False
            else:
                forces = atoms.get_forces(md=True)

            overlap = self.velocity_verlet_step(atoms, forces)
            if overlap:
                break


        if overlap:
            accepted = False
        else:
            potential_energy_n = atoms.get_potential_energy()
            kinetic_energy_n = atoms.get_kinetic_energy()
            results_n = atoms.calc.results

            accepted = self.acceptance_rule(
                potential_energy_o,
                potential_energy_n,
                kinetic_energy_o,
                kinetic_energy_n,
            )

        if accepted:
            results = results_n
            self.accepted += 1
        else:
            atoms.set_positions(position_o)
            results = results_o

        self.attempted += 1
        self.update_max_delta()
        return accepted, results

    def get_move_stats(self):
        s = ""
        s += f"move:{self.name}#"
        s += f"accepted:{self.accepted}#"
        s += f"attempted:{self.attempted}#"
        s += f"dt_fs:{self.max_delta/units.fs:.3f}#"
        return s


class Volume(MCMove):
    def __init__(
        self,
        accepted,
        attempted,
        probability,
        update_frequency,
        max_delta,
        beta,
        pressure,
        ln_volume,
        mask,
        scale_delta,
        target_acceptance,
        limits = None,
        name="Volume",
        communicator=world,
        rng=None,
    ):

        if limits is None:
            if ln_volume:
                limits = (0.001, 0.1)
            else:
                limits = (100, 1000)

        MCMove.__init__(
            self,
            name=name,
            accepted=accepted,
            attempted=attempted,
            probability=probability,
            update_frequency=update_frequency,
            max_delta=max_delta,
            limits = limits,
            beta=beta,
            pressure=pressure,
            ln_volume=ln_volume,
            target_acceptance=target_acceptance,
            scale_delta=scale_delta,
            mask=mask,
            communicator=communicator,
            rng=rng,
        )

    def acceptance_rule(self, n_components, energy_n, energy_o, volume_n, volume_o):
        dE = energy_n - energy_o
        dV = volume_n - volume_o
        zeta = self.generate_uniform_random_number(n=1)
        energetic = dE + self.pressure * dV

        if self.ln_volume:
            mechanical = (n_components + 1) * np.log(volume_n / volume_o)
        else:
            mechanical = n_components * np.log(volume_n / volume_o)

        return np.log(zeta) < -self.beta * energetic + mechanical

    def execute(self, atoms, results_o):
        energy_o, _ = self.initialize_bookkeeping(atoms, results_o, need_forces=False)

        v_o = atoms.get_volume()
        cell_o = atoms.get_cell()

        cell_n, v_n = self.generate_v_n(atoms)
        atoms.set_cell(cell_n, scale_atoms=True)
        energy_n = atoms.get_potential_energy()
        results_n = atoms.calc.results

        #self.set_component_list(atoms)
        #accepted = self.acceptance_rule(self.n_components, energy_n, energy_o, v_n, v_o)
        accepted = self.acceptance_rule(len(atoms), energy_n, energy_o, v_n, v_o)

        if accepted:
            results = results_n
            self.accepted += 1
        else:
            atoms.set_cell(cell_o, scale_atoms=True)
            atoms.calc.results = results_o
            results = results_o

        self.attempted += 1
        self.update_max_delta()
        return accepted, results

    def get_move_stats(self):
        s = ""
        s += f"move:{self.name}#"
        s += f"accepted:{self.accepted}#"
        s += f"attempted:{self.attempted}#"
        s += f"max_delta:{self.max_delta:.3f}#"
        return s






class Insert(MCMove):
    def __init__(
        self,
        accepted,
        attempted,
        probability,
        species,
        species_tag,
        beta,
        b_parameter,
        reference_energy,
        grid_resolution,
        rcavity,
        cavity_bias,
        r_overlap,
        name="Insert",
        communicator=world,
        rng=None,
    ):
        MCMove.__init__(
            self,
            name=name,
            accepted=accepted,
            attempted=attempted,
            probability=probability,
            beta=beta,
            b_parameter=b_parameter,
            reference_energy=reference_energy,
            species=species,
            grid_resolution=grid_resolution,
            r_overlap = r_overlap,
            rcavity=rcavity,
            cavity_bias=cavity_bias,
            species_tag=species_tag,
            communicator=communicator,
            rng=rng,
            )

        self.n_molecules = 0
        self.original_natoms = 0

    def acceptance_rule(self, energy_o, energy_n, n_molecules):
        dE = energy_n - energy_o
        zeta = self.generate_uniform_random_number(n=1)
        energetic = -self.beta * (dE - self.reference_energy)
        chemical = self.b_parameter - np.log(n_molecules + 1) + self.ln_pcav
        return np.log(zeta) < energetic + chemical


    def restore_r_o(self, atoms):
        del atoms[self.original_natoms :]

    def generate_r_n(self, atoms):
        natoms_o = len(atoms)
        self.original_natoms = natoms_o
        trial_species = self.gen_random_molecule(
            atoms.get_cell(), atoms.get_scaled_positions()
        )

        atoms += trial_species

        if len(atoms) - len(trial_species) == 0:
            autoreject = False

        else:
            natoms_n = len(atoms)
            new_atom_indices = np.arange(natoms_n)
            old_atom_indices = np.arange(natoms_o)
            trial_atom_indices = np.delete(new_atom_indices, old_atom_indices)
            autoreject = self.check_overlap(atoms, selection = trial_atom_indices)

        return autoreject

    def gen_random_molecule(self, cell, s):
        # Generate a random orientation for your species
        atoms = self.gen_random_orientation()
        hmat = np.array(cell).T

        if self.cavity_bias:
            # s contains the scaled coordinates of the old config, so the cavities returned here will be for the old configuration
            cavities = self.find_cavities(hmat, s)
            ncavities = len(cavities)
            zeta_insertion_point = self.run_cavity_bias(hmat, ncavities, cavities)
            self.ncavities = ncavities

        # Otherwise, use metropolis sampling and pray!
        else:
            zeta_s = self.generate_uniform_random_number(n=3)
            zeta_insertion_point = hmat @ zeta_s.T
            self.ln_pcav = 0  # No bias added

        atoms.translate(zeta_insertion_point)
        return atoms

    def run_cavity_bias(self, hmat, ncavities, cavities):
        # If there is a cavity, apply the bias algorithm
        # For deletions, apply the bias algorithm if zeta < (1-Pc^{N-1})^Ngridpts
        pcav = ncavities / self.ngrid_points

        # For creations, we attempt Metropolis Sampling if there are no cavities available
        if ncavities != 0:
            cav_idxs = np.arange(len(cavities))
            zeta_cav = self.random_choice_from_array(cav_idxs)
            zeta_insertion_point = hmat @ cavities[zeta_cav].T
            self.ln_pcav = np.log(pcav)

        # Otherwise, use metropolis sampling and pray!
        else:
            zeta_s = self.generate_uniform_random_number(n=3)
            zeta_insertion_point = hmat @ zeta_s.T
            self.ln_pcav = 0  # No bias added

        return zeta_insertion_point

    def execute(self, atoms, results_o):
        if len(atoms) != 0:
            species_index_list = [
                atom.index for atom in atoms if atom.tag == self.species_tag
            ]

            if len(species_index_list) == 0:
                self.n_molecules = 0

            else:
                self.n_molecules = len(species_index_list) // len(self.species)

            energy_o, _ = self.initialize_bookkeeping(
                atoms, results_o, need_forces=False
            )

        else:
            self.n_molecules = 0
            species_index_list = []
            energy_o = 0.0
            results_o = None


        autoreject = self.generate_r_n(atoms)

        if autoreject:
            accepted = False
        else:
            energy_n = atoms.get_potential_energy()
            results_n = atoms.calc.results
            accepted = self.acceptance_rule(energy_o, energy_n, self.n_molecules)

        if accepted:
            results = results_n
            self.accepted += 1
            self.n_molecules += 1

        else:
            self.restore_r_o(atoms)
            atoms.calc.results = results_o
            results = results_o

        self.attempted += 1
        return accepted, results

    def get_move_stats(self):
        s = ""
        s += f"move:{self.name}#"
        s += f"accepted:{self.accepted}#"
        s += f"attempted:{self.attempted}#"
        s += f"species_tag:{self.species_tag}#"
        s += f"n_species:{self.n_molecules}#"
        s += f"n_cavities: {self.ncavities}"
        return s


class Delete(MCMove):
    def __init__(
        self,
        accepted,
        attempted,
        probability,
        species,
        species_tag,
        beta,
        b_parameter,
        reference_energy,
        grid_resolution,
        rcavity,
        cavity_bias,
        name="Delete",
        communicator=world,
        rng=None,
    ):
        MCMove.__init__(
            self,
            name=name,
            accepted=accepted,
            attempted=attempted,
            probability=probability,
            beta=beta,
            b_parameter=b_parameter,
            reference_energy=reference_energy,
            species=species,
            grid_resolution=grid_resolution,
            rcavity=rcavity,
            cavity_bias=cavity_bias,
            species_tag=species_tag,
            communicator=communicator,
            rng=rng,
        )

        self.n_molecules = 0
        self.destroyed_atoms = None

    def acceptance_rule(self, energy_o, energy_n, n_molecules):
        dE = energy_n - energy_o
        zeta = self.generate_uniform_random_number(n=1)
        energetic = -self.beta * (dE + self.reference_energy)
        chemical = -self.b_parameter + np.log(n_molecules) - self.ln_pcav
        return np.log(zeta) < energetic + chemical

    def execute(self, atoms, results_o):
        species_index_list = [atom.index for atom in atoms if atom.tag == self.species_tag]
        self.n_molecules = len(species_index_list) // len(self.species)
        energy_o, _ = self.initialize_bookkeeping(atoms, results_o, need_forces=False)

        # Assume there is at least 1 species to delete, if there is not, autoreject the move
        if self.n_molecules == 0:
            autoreject = True
            self.destroyed_atoms = None
        else:
            species_index_list = np.array(species_index_list)
            autoreject = self.generate_r_n(atoms, species_index_list)

            if len(atoms) == 0:
                energy_n = 0.0
                results_n = None

            else:
                energy_n = atoms.get_potential_energy()
                results_n = atoms.calc.results

        if autoreject:
            accepted = False
        else:
            accepted = self.acceptance_rule(energy_o, energy_n, self.n_molecules)

        if accepted:
            results = results_n
            self.accepted += 1
            self.n_molecules -= 1
        else:
            self.restore_r_o(atoms)
            atoms.calc.results = results_o
            results = results_o

        self.attempted += 1
        return accepted, results


    def generate_r_n(self, atoms, species_index_list):
        autoreject = False

        molecule_species_array = species_index_list.reshape((self.n_molecules, len(self.species)))
        mol_idxs = self.random_choice_from_array(molecule_species_array)


        #random_species_index = self.random_choice_from_array(species_index_list)
        #mol_idxs = self.get_mol_idxs(random_species_index)

        # If a mol_idxs can contain more atoms if a reaction occured or if a
        # probe molecule adsorbed on a metal slab
        # only delete molecules part of the species

        # TEMPORARY FIX, autoreject the move if a "reaction" occured
        #autoreject = False
        #if len(mol_idxs) != len(self.species):
        #    autoreject = True

        syms = atoms[mol_idxs].get_chemical_symbols()
        r = atoms[mol_idxs].get_positions()


        self.destroyed_atoms = Atoms(syms, r)
        for atom in self.destroyed_atoms:
            atom.tag = self.species_tag

        # Delete atoms before applying cavity bias
        del atoms[mol_idxs]

        if self.cavity_bias:
            # Apply the cavity bias algorithm in the new config
            hmat = np.array(atoms.get_cell()).T
            s = atoms.get_scaled_positions()
            cavities = self.find_cavities(hmat, s)
            self.ncavities = len(cavities)
            self.run_cavity_bias(hmat, self.ncavities, cavities)

        # Otherwise, use metropolis sampling and pray!
        else:
            self.ln_pcav = 0  # No bias added

        return autoreject

    def restore_r_o(self, atoms):
        if self.destroyed_atoms is None:
            pass
        else:
            atoms += self.destroyed_atoms

    def run_cavity_bias(self, hmat, ncavities, cavities):
        # For deletions, run metropolis MC if zeta < (1-Pc^{N-1})^Ngridpts
        pcav = ncavities / self.ngrid_points
        zeta = self.generate_uniform_random_number(n=1)

        if zeta < (1.0 - pcav)**self.ngrid_points:
            self.ln_pcav = 0  # Running Metropolis MC

        else:
            self.ln_pcav = np.log(pcav)


        #attempt_cavbias = not (zeta_attempt < 1.0 - pcav)

        #if attempt_cavbias:
        #    self.ln_pcav = np.log(pcav)

        # Otherwise, use metropolis sampling and pray!
        #else:
        #    self.ln_pcav = 0  # No bias added


    def get_move_stats(self):
        s = ""
        s += f"move:{self.name}#"
        s += f"accepted:{self.accepted}#"
        s += f"attempted:{self.attempted}#"
        s += f"species_tag:{self.species_tag}#"
        s += f"n_species:{self.n_molecules}#"
        s += f"n_cavities: {self.ncavities}"
        return s

