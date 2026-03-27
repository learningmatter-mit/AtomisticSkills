import warnings
from ase import units
from ase.geometry.analysis import Analysis
from ase.build import sort
from .moves import (
    Translate,
    Rotate,
    HMC,
    Volume,
    Insert,
    Delete,
)
from .utility import get_components
from ase.io import write
import numpy as np


def process_temperature(temperature, temperature_K, orig_unit):
    """Handle that temperature can be specified in multiple units.

    For at least a transition period, molecular dynamics in ASE can
    have the temperature specified in either Kelvin or Electron
    Volt.  The different MD algorithms had different defaults, by
    forcing the user to explicitly choose a unit we can resolve
    this.  Using the original method then will issue a
    FutureWarning.

    Four parameters:

    temperature: None or float
        The original temperature specification in whatever unit was
        historically used.  A warning is issued if this is not None and
        the historical unit was eV.

    temperature_K: None or float
        Temperature in Kelvin.

    orig_unit: str
        Unit used for the `temperature`` parameter.  Must be 'K' or 'eV'.

    Exactly one of the two temperature parameters must be different from
    None, otherwise an error is issued.

    Return value: Temperature in Kelvin.
    """
    if (temperature is not None) + (temperature_K is not None) != 1:
        raise TypeError(
            "Exactly one of the parameters 'temperature',"
            + " and 'temperature_K', must be given"
        )
    if temperature is not None:
        w = "Specify the temperature in K using the 'temperature_K' argument"
        if orig_unit == "K":
            return temperature
        elif orig_unit == "eV":
            warnings.warn(FutureWarning(w))
            return temperature / units.kB
        else:
            raise ValueError("Unknown temperature unit " + orig_unit)

    assert temperature_K is not None
    return temperature_K


class Ensemble:
    def __init__(
        self,
        species=None,
        temperature_K=None,
        temperature=None,
        pressure=None,
        ln_volume=True,
        reference_energy=None,
        starting_tag=0,
        b_parameter=None,
        grid_resolution=None,
        rcavity=None,
        cavity_bias=False,
        r_overlap=None,
        moves=None,
        exclusion_list=None,
        restart_file=None,
    ):
        self.species = species

        self.temp = units.kB * self._process_temperature(
            temperature, temperature_K, "eV"
        )
        self.beta = 1.0 / self.temp
        self.pressure = pressure
        self.ln_volume = ln_volume
        self.reference_energy = reference_energy
        self.b_parameter = b_parameter

        self.grid_resolution = grid_resolution
        self.rcavity = rcavity
        self.cavity_bias = cavity_bias
        self.r_overlap = r_overlap

        self.species = species
        self.starting_tag = starting_tag

        self.exclusion_list = exclusion_list

        if self.species is not None:
            self.species_tags = []
            for i, atoms in enumerate(self.species):
                tag = i + self.starting_tag
                self.species_tags.append(tag)
                # This is extremely obnoxious
                # write(f"species_{tag}.xyz", atoms)
                for atom in atoms:
                    atom.tag = tag

        if moves is None:
            self.moves = []
        else:
            self.moves = moves

    def get_moves(self):
        return self.moves

    def check_species_equivalence(self, atoms, species):
        atoms_sorted = sort(atoms)
        species_sorted = sort(species)
        if atoms_sorted.get_chemical_symbols() == species_sorted.get_chemical_symbols():
            # If they have the same number of elements, the last thing to do is check connectivity
            species_analysis = Analysis(species_sorted)
            species_bonds = species_analysis.unique_bonds[0]
            atoms_analysis = Analysis(atoms_sorted)
            atoms_bonds = atoms_analysis.unique_bonds[0]

            species_nodes = [ele for ele in species_bonds if ele != []]
            atoms_nodes = [ele for ele in atoms_bonds if ele != []]

            if len(species_nodes) == len(atoms_nodes):
                # TO DO: For my own sanity for now, let's return true and compare each bond later
                # If we get this far, the next step would be to topologically sort the bond list and compare the two
                # https://www.geeksforgeeks.org/python-program-for-topological-sorting/
                # More needs to be done though as directionality may not be the same
                # Flip directionality based on atomic number
                # If equivalent, no direction
                # VERY HARD, ML clustering on atomic environmnets probably going to be a better choice here...
                return True
            else:
                return False
        else:
            return False

    def set_species_tags(self, atoms):
        # Build the component list
        sys_n_components, sys_component_list, sys_connectivity_matrix = get_components(
            atoms
        )
        # Go through each component (molecule) in our system
        for mol_idx in range(sys_n_components):
            mol_idxs = [
                atom_idx
                for atom_idx in range(len(sys_component_list))
                if sys_component_list[atom_idx] == mol_idx
            ]
            observed_molecule = atoms[mol_idxs]
            for tag, species in zip(self.species_tags, self.species):
                equivalent = self.check_species_equivalence(observed_molecule, species)
                # If yes, assign it the appropriate tag
                # If not, do not change it's tag
                if equivalent:
                    for atom_idx in mol_idxs:
                        atoms[atom_idx].tag = tag
                else:
                    pass


    def set_thermal_moves(self, include_hmc=True):
        if include_hmc:
            self.moves += [
                HMC(
                    accepted=0,
                    attempted=0,
                    probability=0.17,
                    dt=1.0 * units.fs,
                    nsteps=10,
                    beta=self.beta,
                    r_overlap=0.5,
                    update_frequency=1000,
                    scale_delta=0.1,
                    target_acceptance=0.5,
                ),
            ]

        self.moves += [
            Translate(
                accepted=0,
                attempted=0,
                probability=0.17,
                beta=self.beta,
                max_delta=1.0,
                r_overlap=0.5,
                update_frequency=1000,
                scale_delta=0.1,
                target_acceptance=0.5,
                exclusion_list=self.exclusion_list,
            ),
        ]

        self.moves += [
            Rotate(
                accepted=0,
                attempted=0,
                probability=0.16,
                max_delta=180.0,
                beta=self.beta,
                r_overlap=0.5,
                update_frequency=1000,
                scale_delta=0.1,
                target_acceptance=0.5,
                exclusion_list=self.exclusion_list,
            ),
        ]


    def set_npt_mechanical_moves(self):
        if self.ln_volume:
            delta = 0.005
        else:
            delta = 500.0

        self.moves += [
            Volume(
                accepted=0,
                attempted=0,
                probability=0.5,
                update_frequency=100,
                max_delta=delta,
                beta=self.beta,
                ln_volume=self.ln_volume,
                pressure=self.pressure,
                # mask=[0, 1, 2],
                mask=None,
                scale_delta=0.1,
                target_acceptance=0.5,
            )
        ]

    def set_gcmc_moves(self):
        for species_tag, species, b_parameter, reference_energy in zip(
            self.species_tags, self.species, self.b_parameter, self.reference_energy
        ):
            self.moves += [
                Insert(
                    accepted=0,
                    attempted=0,
                    probability=0.25,
                    species=species,
                    species_tag=species_tag,
                    beta=self.beta,
                    b_parameter=b_parameter,
                    reference_energy=reference_energy,
                    grid_resolution=self.grid_resolution,
                    rcavity=self.rcavity,
                    cavity_bias=self.cavity_bias,
                    r_overlap=self.r_overlap,
                )
            ]

            self.moves += [
                Delete(
                    accepted=0,
                    attempted=0,
                    probability=0.25,
                    species=species,
                    species_tag=species_tag,
                    beta=self.beta,
                    b_parameter=b_parameter,
                    reference_energy=reference_energy,
                    grid_resolution=self.grid_resolution,
                    rcavity=self.rcavity,
                    cavity_bias=self.cavity_bias,
                )
            ]




    # Make the process_temperature function available to subclasses
    # as a static method.  This makes it easy for MC objects to use
    # it, while functions in mc have access to it
    # as a function.
    _process_temperature = staticmethod(process_temperature)


class NVT(Ensemble):
    def __init__(
        self,
        temperature=None,
        temperature_K=None,
        restart_file=None,
        exclusion_list=None,
    ):
        Ensemble.__init__(
            self,
            temperature=temperature,
            temperature_K=temperature_K,
            restart_file=restart_file,
            exclusion_list=exclusion_list,
        )

        self.set_thermal_moves()


class NPT(Ensemble):
    def __init__(
        self,
        pressure,
        temperature=None,
        temperature_K=None,
        ln_volume=True,
        restart_file=None,
        exclusion_list=None,
    ):
        Ensemble.__init__(
            self,
            pressure=pressure,
            temperature=temperature,
            temperature_K=temperature_K,
            ln_volume=ln_volume,
            restart_file=restart_file,
            exclusion_list=exclusion_list,
        )

        self.set_thermal_moves()
        self.set_npt_mechanical_moves()


class BVT(Ensemble):
    def __init__(
        self,
        b_parameter,
        species,
        reference_energy,
        starting_tag = 0,
        rmin=1.0,
        rcavity=4.0,
        grid_resolution=10,
        r_overlap = 1.0,
        cavity_bias=False,
        temperature=None,
        temperature_K=None,
        restart_file=None,
        exclusion_list=None,
    ):
        Ensemble.__init__(
            self,
            b_parameter=b_parameter,
            reference_energy=reference_energy,
            species=species,
            starting_tag=starting_tag,
            temperature=temperature,
            temperature_K=temperature_K,
            restart_file=restart_file,
            cavity_bias=cavity_bias,
            rcavity=rcavity,
            grid_resolution=grid_resolution,
            r_overlap = r_overlap,
            exclusion_list=exclusion_list,
        )

        self.set_thermal_moves()
        self.set_gcmc_moves()


class BVT_GCMCOnly(Ensemble):
    def __init__(
        self,
        b_parameter,
        species,
        reference_energy,
        starting_tag=0,
        rmin=1.0,
        rcavity=4.0,
        grid_resolution=10,
        r_overlap=1.0,
        cavity_bias=False,
        temperature=None,
        temperature_K=None,
        restart_file=None,
        exclusion_list=None,
    ):
        Ensemble.__init__(
            self,
            b_parameter=b_parameter,
            reference_energy=reference_energy,
            species=species,
            starting_tag=starting_tag,
            temperature=temperature,
            temperature_K=temperature_K,
            restart_file=restart_file,
            cavity_bias=cavity_bias,
            rcavity=rcavity,
            grid_resolution=grid_resolution,
            r_overlap=r_overlap,
            exclusion_list=exclusion_list,
        )

        self.set_thermal_moves(include_hmc=False)
        self.set_gcmc_moves()
