"""Molecular Dynamics."""

import warnings
import numpy as np
from ase.optimize.optimize import Dynamics
from .logger import MCLogger
from ase.parallel import world, DummyMPI
from ase.io.trajectory import Trajectory
from ase import units
from ase.calculators.calculator import all_properties
from ase.calculators.singlepoint import SinglePointCalculator


class MonteCarlo(Dynamics):
    """Base-class for all MC classes."""

    def __init__(
        self,
        atoms,
        moveset,
        dft_calc,
        trajectory=None,
        logfile=None,
        loginterval=1,
        communicator=world,
        rng=None,
        wrap_atoms=False,
        gcmc_energy_only=False,
    ):
        """The Monte Carlo object.

        Parameters:

        atoms: Atoms object
            The Atoms object to operate on. Can either be a list (Gibbs ensemble) or a single Atoms object

        moveset: Moveset object
            The Moveset object used to control MC moves.

        dft_calc: ASE calculator object
            Calculator intended to perform DFT calculations. We pass it in this way to
            keep from doing more calculations than neccessary and also for not running multiple instances of a
            calculator at once

        trajectory: Trajectory object or str
            Attach trajectory object.  If *trajectory* is a string a
            Trajectory will be constructed.  Use *None* for no
            trajectory. If running in the GE, then the trajectory file will be prefixed by the box index.

        logfile: file object or str (optional)
            If *logfile* is a string, a file with that name will be opened.
            Use '-' for stdout.

        loginterval: int (optional)
            Only write a log line for every *loginterval* time steps.
            Default: 1

        rng: RNG object (optional)
            Random number generator, by default numpy.random.  Must have a
            standard_normal method matching the signature of
            numpy.random.standard_normal.

        communicator: MPI communicator (optional)
            Communicator used to distribute random numbers to all tasks.
            Default: ase.parallel.world. Set to None to disable communication.

        """

        # We need to set the calculator at first for when Dynamics get's initialized
        self.gibbs = isinstance(atoms, list)
        if self.gibbs:
            atoms[0].calc = dft_calc
            Dynamics.__init__(self, atoms, logfile=None, trajectory=None)
            self.potential_energy = atoms[0].get_potential_energy()
            self.natoms = len(atoms[0])

            self.last_accepted_config = []
            self.calculator_results = []

            for box_idx in len(atoms):
                atoms[box_idx].calc = dft_calc
                _ = atoms[box_idx].get_potential_energy()

                self.last_accepted_config.append(
                    self.copy_with_properties(
                        atoms[box_idx], atoms[box_idx].calc.results
                    )
                )

                self.calculator_results.append(atoms[box_idx].calc.results)

        else:
            atoms.calc = dft_calc
            Dynamics.__init__(self, atoms, logfile=None, trajectory=None)
            self.potential_energy = atoms.get_potential_energy()
            self.natoms = len(atoms)
            self.last_accepted_config = self.copy_with_properties(
                atoms, atoms.calc.results
            )
            self.calculator_results = atoms.calc.results

        self.moveset = moveset
        self.max_steps = None
        self.dft_calc = dft_calc
        self.trajectory = trajectory
        self.loginterval = loginterval
        self.wrap_atoms = wrap_atoms
        self.gcmc_energy_only = gcmc_energy_only

        # Results cannot be none to write to the traj file, to be consistent, define an attribute that just contains 0 values
        self.results_none = {**self.calculator_results}
        tmp = {**self.calculator_results}
        for key, value in tmp.items():
            # Results are either numpy arrays or floats
            if type(value) is np.ndarray:
                self.results_none[key] = np.zeros(value.shape)
            else:
                self.results_none[key] = 0.0

        if communicator is None:
            communicator = DummyMPI()
        self.communicator = communicator
        if rng is None:
            self.rng = np.random
        else:
            self.rng = rng

        if self.gcmc_energy_only:
            self._assert_no_force_moves()
            self._install_force_tripwire()

        # Trajectory is attached here instead of in Dynamics.__init__
        # to respect the loginterval argument.

        # Cannot do trajectories in the usual way, because of when moves are rejected,
        # We don't want to have to repeat a calculation and we want the previous configuration saved to the file.

        """
        if trajectory is not None:
            if isinstance(trajectory, str):
                mode = "a" if append_trajectory else "w"
                trajectory = self.closelater(
                    Trajectory(trajectory, mode=mode, atoms=atoms)
                )
            self.attach(trajectory, interval=loginterval)
        """

        if logfile:
            logger = self.closelater(MCLogger(dyn=self, logfile=logfile))
            self.attach(logger, loginterval)

    def step(self, energy=None):
        atoms = self.atoms
        atoms.calc = self.dft_calc
        if len(atoms) == 0:
            energy = 0.0
        elif energy is None:
            energy = atoms.get_potential_energy()

        self.moveset.pick_move(atoms)
        accepted, results = self.moveset.execute_move(atoms, self.calculator_results)

        if results is None:
            energy = 0.0
            results = self.results_none
        else:
            energy = results["energy"]

        self.potential_energy = energy
        self.calculator_results = results
        self.natoms = len(atoms)

        if accepted:
            self.last_accepted_config = self.copy_with_properties(atoms, results)

        if self.wrap_atoms:
            atoms.wrap()

        if self.trajectory is not None:
            if (
                self.last_accepted_config is not None
                and self.nsteps % self.loginterval == 0
            ):
                self.save_to_traj(self.last_accepted_config, self.trajectory)

        return energy

    def todict(self):
        # return {'type': 'monte-carlo',
        #        'mc-type': self.__class__.__name__,
        #        'moveset': self.dt}
        return {"type": "monte-carlo"}

    def irun(self, steps=50):
        """MC-native generator: call self.step() and observers; never ask for gradients."""
        self.max_steps = self.nsteps + steps

        # Match ASE behavior: call observers at step 0 (e.g., logger)
        if self.nsteps == 0:
            self.call_observers()

        is_converged = self.converged()
        yield is_converged

        while not is_converged and self.nsteps < self.max_steps:
            self.step()
            self.nsteps += 1
            self.call_observers()
            is_converged = self.converged()
            yield is_converged

    def run(self, steps=50):
        """MC-native run loop built on irun()."""
        for converged in self.irun(steps=steps):
            pass
        return converged

    def get_nsteps(self):
        return self.nsteps

    def converged(self, *args, **kwargss):
        """MC is 'converged' when number of maximum steps is reached."""
        # print(self.nsteps,self.max_steps)
        return self.nsteps >= self.max_steps

    def get_current_move_stats(self):
        return self.moveset.get_current_move_stats()

    def copy_with_properties(self, atoms, results):
        atoms_copy = atoms.copy()
        # Filter results if the calculator is from outside ASE
        keys = list(results)
        for key in keys:
            if not(key in all_properties):
                _ = results.pop(key)
        atoms_copy.calc = SinglePointCalculator(atoms_copy, **results)
        return atoms_copy

    def save_to_traj(self, atoms, filename):
        with Trajectory(filename, mode="a") as traj:
            traj.write(atoms)

    def _assert_no_force_moves(self):
        for move in self.moveset.moves:
            if getattr(move, "name", None) == "HMC":
                raise ValueError(
                    "gcmc_energy_only=True prohibits HMC or force-based moves."
                )

    def _install_force_tripwire(self):
        def _raise_get_forces(*args, **kwargs):
            raise RuntimeError(
                "gcmc_energy_only=True prohibits atoms.get_forces() calls."
            )

        def _wrap_atoms(target_atoms):
            if not hasattr(target_atoms, "_gcmc_energy_only_get_forces"):
                target_atoms._gcmc_energy_only_get_forces = target_atoms.get_forces
                target_atoms.get_forces = _raise_get_forces

        if self.gibbs:
            for box_atoms in self.atoms:
                _wrap_atoms(box_atoms)
        else:
            _wrap_atoms(self.atoms)
