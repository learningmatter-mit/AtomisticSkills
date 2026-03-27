import numpy as np
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class MDStopIteration(Exception):
    """Exception raised to stop MD simulation from a callback."""
    pass

class ExplosionMonitor:
    """
    Monitor for unphysical instabilities in MD simulations.
    Stops the simulation if temperature exceeds a threshold or becomes NaN.
    """
    def __init__(self, atoms=None, temp_threshold: float = 10000.0):
        self.atoms = atoms
        self.temp_threshold = temp_threshold

    def __call__(self, *args, **kwargs):
        dyn = kwargs.get("dyn")
        atoms = self.atoms
        for arg in args:
            if hasattr(arg, "get_temperature"):
                if hasattr(arg, "atoms"):
                    dyn = arg
                    atoms = arg.atoms
                else:
                    atoms = arg
                break
        
        if atoms is None and dyn is not None and hasattr(dyn, "atoms"):
            atoms = dyn.atoms
            
        if atoms is None:
            return
            
        temp = atoms.get_temperature()
        if np.isnan(temp) or temp > self.temp_threshold:
            msg = f"Explosion detected: Temperature = {temp:.1f}K"
            logger.error(msg)
            raise MDStopIteration(msg)

class EquilibrationMonitor:
    """
    Monitor for simulation equilibration/stability.
    Detects when temperature and potential energy have converged.
    """
    def __init__(
        self, 
        atoms=None, 
        window_ps: float = 1.0, 
        stability_ps: float = 5.0, 
        temp_std_threshold: float = 50.0,
        **kwargs
    ):
        self.atoms = atoms
        self.timestep_fs = None
        self.log_interval = None
        self.window_ps = window_ps
        self.stability_ps = stability_ps
        self.temp_std_threshold = temp_std_threshold
        
        self.window_entries = None
        self.stability_entries = None
        self.history = {"temps": [], "epots": [], "stds": []}

    def _resolve_params(self, atoms, dyn=None, md_runner=None):
        """Resolve simulation parameters from atoms, dynamics, or md_runner object."""
        if self.atoms is None:
            self.atoms = atoms
            
        if md_runner is not None:
            if self.timestep_fs is None and hasattr(md_runner, "timestep"):
                self.timestep_fs = md_runner.timestep
            if self.log_interval is None and hasattr(md_runner, "loginterval"):
                self.log_interval = md_runner.loginterval
                
        if dyn is not None:
            # Try to get timestep from Dynamics object (ASE units)
            if self.timestep_fs is None:
                from ase import units
                # ASE Dynamics object has dt or get_time_step()
                if hasattr(dyn, "dt"):
                    self.timestep_fs = dyn.dt / units.fs
                elif hasattr(dyn, "get_time_step"):
                    self.timestep_fs = dyn.get_time_step() / units.fs
            
            # Log interval is usually not in dyn directly for the callback,
            # but we pass it during attach if we want.
            # However, matcalc uses its own loginterval.
            # We can try to guess it or pass it.
            if self.log_interval is None and hasattr(dyn, "observers"):
                for obs in dyn.observers:
                    try:
                        func = obs[0]
                        if func is self or (hasattr(func, "__self__") and func.__self__ is self):
                            self.log_interval = obs[1]
                            break
                    except Exception:
                        pass
        
        if self.timestep_fs is None:
            raise ValueError("timestep_fs must be provided or auto-detected from dynamics object.")
        if self.log_interval is None:
            raise ValueError("log_interval must be provided to correctly evaluate simulation time.")
            
        ts = self.timestep_fs
        li = self.log_interval
        
        if self.window_entries is None:
            self.window_entries = max(2, int(self.window_ps * 1000 / ts / li))
        if self.stability_entries is None:
            self.stability_entries = max(2, int(self.stability_ps * 1000 / ts / li))

    def __call__(self, *args, **kwargs):
        dyn = kwargs.get("dyn")
        md_runner = kwargs.get("md_runner")
        atoms = dyn.atoms if dyn is not None and hasattr(dyn, "atoms") else self.atoms
        
        if atoms is None:
            return

        # Resolve parameters on the first call
        self._resolve_params(atoms, dyn, md_runner)
        
        curr_temp = atoms.get_temperature()
        curr_epot = atoms.get_potential_energy() / len(atoms)
        
        self.history["temps"].append(curr_temp)
        self.history["epots"].append(curr_epot)
        
        if len(self.history["temps"]) >= self.window_entries:
            # We check the standard deviation of the most recent window
            recent_temps = self.history["temps"][-self.window_entries:]
            std_t = np.std(recent_temps)
            self.history["stds"].append(std_t)
            
            # Condition 1: Absolute threshold
            if std_t < self.temp_std_threshold:
                # Still check minimal duration? Original code checked stability_entries against history length
                # User said: "alternatively ... smaller than threshold"
                # Let's keep a sanity check that we have at least one window
                msg = f"Equilibration reached: std(T)={std_t:.2f} < {self.temp_std_threshold}"
                logger.info(msg)
                raise MDStopIteration(msg)

            # Condition 2: Fluctuation stability (plateau)
            # Check if stds have been recorded for stability_ps duration
            # "if it doesn't decrease (or remain at similar value) for stability_ps time"
            
            # We need enough std history to cover stability_ps
            # stability_entries is count of points (assuming 1 point per call effectively?)
            # Wait, stability_entries is calculated as (time / ts / li)
            # self.history["stds"] grows by 1 every call.
            # So looking back `stability_entries` in `stds` corresponds to `stability_ps`.
            
            if len(self.history["stds"]) >= self.stability_entries:
                recent_stds = self.history["stds"][-self.stability_entries:]
                
                # Check trend. Simple linear regression slope.
                x = np.arange(len(recent_stds))
                slope, _ = np.polyfit(x, recent_stds, 1)
                
                # If slope >= -epsilon (it is not decreasing significantly)
                # We assume decreasing is negative slope. 
                # "doesn't decrease" -> slope >= ~0
                # "remain at similar value" -> slope ~ 0
                
                # Let's say if slope > -0.005 (very slightly decreasing or flat/increasing)
                # It means we are not improving much anymore.
                
                # Also check relative change?
                # Let's stick to slope.
                
                if slope > -0.01: # Threshold for "not decreasing"
                    avg_std = np.mean(recent_stds)
                    msg = f"Equilibration reached (stable fluctuation): slope={slope:.4f}, mean_std={avg_std:.2f}"
                    logger.info(msg)
                    raise MDStopIteration(msg)

class OvershootMonitor:
    """
    Monitor for temperature overshoot or thermostat failure.
    Stops if temperature deviates too far from target.
    """
    def __init__(self, atoms=None, target_temp: float = 300.0, tolerance: float = 500.0, delay_steps: int = 100):
        self.atoms = atoms
        self.target_temp = target_temp
        self.tolerance = tolerance
        self.delay_steps = delay_steps  # Allow some steps for initial ramp
        self.step_count = 0

    def __call__(self, *args, **kwargs):
        self.step_count += 1
        if self.step_count < self.delay_steps:
            return
            
        dyn = kwargs.get("dyn")
        atoms = dyn.atoms if dyn is not None and hasattr(dyn, "atoms") else self.atoms
        
        if atoms is None:
            return
            
        temp = atoms.get_temperature()
        if abs(temp - self.target_temp) > self.tolerance:
            msg = f"Temperature overshoot detected: T={temp:.1f}K, Target={self.target_temp}K, Tolerance={self.tolerance}K"
            logger.error(msg)
            raise MDStopIteration(msg)

class VolumeMonitor:
    """
    Monitor for volume expansion/contraction in NPT simulations.
    Stops if volume exceeds upper or lower limit ratios.
    """
    def __init__(self, atoms=None, lower_limit_ratio: float = 0.2, upper_limit_ratio: float = 2.0):
        self.atoms = atoms
        self.initial_volume = atoms.get_volume() if atoms else None
        self.lower_limit_ratio = lower_limit_ratio
        self.upper_limit_ratio = upper_limit_ratio

    def __call__(self, *args, **kwargs):
        dyn = kwargs.get("dyn")
        atoms = dyn.atoms if dyn is not None and hasattr(dyn, "atoms") else self.atoms
        
        if atoms is None:
            return
        
        if self.initial_volume is None:
            self.initial_volume = atoms.get_volume()
            
        current_volume = atoms.get_volume()
        if current_volume > self.initial_volume * self.upper_limit_ratio:
            msg = f"Volume expansion detected: Volume {current_volume:.1f} A^3 > {self.upper_limit_ratio}x initial ({self.initial_volume:.1f} A^3)"
            logger.error(msg)
            raise MDStopIteration(msg)
        
        if current_volume < self.initial_volume * self.lower_limit_ratio:
            msg = f"Volume contraction detected: Volume {current_volume:.1f} A^3 < {self.lower_limit_ratio}x initial ({self.initial_volume:.1f} A^3)"
            logger.error(msg)
            raise MDStopIteration(msg)

class DiffusionMonitor:
    """
    Monitor for ionic diffusivity convergence.
    Stops the simulation if the relative error of diffusivity (std_dev/D)
    falls below a specified threshold.
    """
    def __init__(
        self, 
        atoms=None, 
        specie: str = "Li", 
        threshold: float = 0.1, 
        check_interval_ps: float = 5.0,
        ignore_ps: float = 5.0,
        min_msd: float = 5.0,
        output_dir: str | None = None,
        **kwargs
    ):
        """
        Initialize the Diffusion Monitor.

        Args:
            atoms (ase.Atoms, optional): ASE Atoms object to monitor.
            specie (str): The atomic species to analyze for diffusion (e.g., "Li"). 
                Defaults to "Li".
            threshold (float): Convergence threshold for the relative error of 
                diffusivity (diffusivity_std_dev / diffusivity). Simulation stops 
                if error < threshold. Defaults to 0.1 (10% error).
            check_interval_ps (float): Simulation time interval between successive 
                diffusivity evaluations in picoseconds. Defaults to 5.0 ps.
            ignore_ps (float): Initial simulation time to ignore for equilibration 
                before starting convergence checks. Defaults to 5.0 ps.
            output_dir (str, optional): Directory to save diffusion results.
            timestep_fs (float, optional): Simulation time step in fs. 
            log_interval (int, optional): Steps between logs.
            temperature (float, optional): Temperature of the simulation.
            **kwargs: Additional parameters.
        """
        self.atoms = atoms
        self.specie = specie
        self.threshold = threshold
        self.check_interval_ps = check_interval_ps
        self.ignore_ps = ignore_ps
        self.min_msd = min_msd
        self.output_dir = output_dir
        
        self.timestep_fs = None
        self.log_interval = None
        self.temperature = None
        
        self.structures = []
        self.check_interval_steps = None
        self.ignore_entries = None
        
    def _resolve_params(self, atoms, dyn=None, md_runner=None):
        if self.atoms is None:
            self.atoms = atoms
            
        if md_runner is not None:
            if self.timestep_fs is None and hasattr(md_runner, "timestep"):
                self.timestep_fs = md_runner.timestep
            if self.log_interval is None and hasattr(md_runner, "loginterval"):
                self.log_interval = md_runner.loginterval
            if self.temperature is None and hasattr(md_runner, "temperature"):
                self.temperature = md_runner.temperature
                
        if dyn is not None:
            if self.timestep_fs is None:
                from ase import units
                if hasattr(dyn, "dt"):
                    self.timestep_fs = dyn.dt / units.fs
                elif hasattr(dyn, "get_time_step"):
                    self.timestep_fs = dyn.get_time_step() / units.fs
                    
            if self.log_interval is None and hasattr(dyn, "observers"):
                for obs in dyn.observers:
                    try:
                        func = obs[0]
                        if func is self or (hasattr(func, "__self__") and func.__self__ is self):
                            self.log_interval = obs[1]
                            break
                    except Exception:
                        pass
                        
            if self.temperature is None:
                from ase import units
                if hasattr(dyn, "temperature"):
                    if dyn.temperature < 10.0:
                        self.temperature = dyn.temperature / units.kB
                    else:
                        self.temperature = dyn.temperature
                elif hasattr(dyn, "temperature_K"):
                    self.temperature = dyn.temperature_K
                    
        if self.timestep_fs is None:
            raise ValueError("timestep_fs must be provided or auto-detected from dynamics object.")
        if self.log_interval is None:
            raise ValueError("log_interval must be provided to evaluate diffusion correctly.")
        if self.temperature is None:
            raise ValueError("temperature must be explicitly provided or auto-detected.")
            
        ts = self.timestep_fs
        li = self.log_interval
        
        if self.check_interval_steps is None:
            # How many callback calls per check
            self.check_interval_steps = max(1, int(self.check_interval_ps * 1000 / ts / li))
        if self.ignore_entries is None:
            self.ignore_entries = max(0, int(self.ignore_ps * 1000 / ts / li))

    def finalize(self):
        """Force evaluate and plot diffusion at the end of the simulation."""
        if not self.output_dir or len(self.structures) < self.ignore_entries + 2:
            return
            
        from pymatgen.analysis.diffusion.analyzer import DiffusionAnalyzer
        import os, json
        
        analysis_structs = self.structures[self.ignore_entries:]
        if self.temperature is not None:
            temp = float(self.temperature)
        else:
            raise ValueError("temperature must be explicitly provided to DiffusionMonitor.")
        
        if self.timestep_fs is None:
            raise ValueError("timestep_fs must be explicitly provided to DiffusionMonitor.")
        if self.log_interval is None:
            raise ValueError("log_interval must be explicitly provided to DiffusionMonitor.")
            
        ts = self.timestep_fs
        li = self.log_interval
        
        try:
            # Fit analyzer on equilibrated segment
            analyzer = DiffusionAnalyzer.from_structures(
                structures=analysis_structs,
                specie=self.specie,
                temperature=temp,
                time_step=ts * li,
                step_skip=1,
                smoothed="max"
            )
            
            D = analyzer.diffusivity
            D_std = analyzer.diffusivity_std_dev
            rel_err = D_std / D if D > 1e-8 else float('inf')
            
            os.makedirs(self.output_dir, exist_ok=True)
            summary = {
                "diffusivity": float(D),
                "diffusivity_std_dev": float(D_std),
                "rel_err": float(rel_err),
                "temperature": float(temp),
                "species": self.specie,
                "time_ps": float(len(self.structures) * ts * li / 1000)
            }
            with open(os.path.join(self.output_dir, "diffusion_results.json"), "w") as f:
                import json
                json.dump(summary, f, indent=4)
            
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            
            plt.figure(figsize=(8, 6))
            
            # For smoothed MSD, the x-axis is the delay time (dt), not absolute time.
            # We use the analyzer fitted on the equilibrated segment.
            times_ps = analyzer.dt / 1000.0
            msd = analyzer.msd
            
            plt.plot(times_ps, msd, 'k-', label=f"{self.specie} MSD")
            
            # The fit line for time-averaged MSD passes through the origin
            slope_ps = 6 * D * 1e4
            y_fit = slope_ps * times_ps
            
            plt.plot(times_ps, y_fit, 'r--', label=f"Fit (D={D:.2e} $\\pm$ {D_std:.2e} cm$^2$/s)")
            
            plt.xlabel("Delay Time $\Delta t$ (ps)", fontsize=18)
            plt.ylabel(r"MSD ($\AA^2$)", fontsize=18)
            plt.xticks(fontsize=18)
            plt.yticks(fontsize=18)
            plt.title(f"{analyzer.temperature}K (skip={self.ignore_ps}ps)", fontsize=18)
            plt.legend(fontsize=16)
            
            plt.savefig(os.path.join(self.output_dir, f"msd_{self.specie}.png"), dpi=300, bbox_inches="tight")
            plt.close()
            logger.info(f"Saved finalized diffusion analysis to {self.output_dir}")
        except Exception as e:
            logger.warning(f"Failed to export diffusion results during finalization: {e}")

    def __call__(self, *args, **kwargs):
        dyn = kwargs.get("dyn")
        md_runner = kwargs.get("md_runner")
        atoms = dyn.atoms if dyn is not None and hasattr(dyn, "atoms") else self.atoms
        
        if atoms is None:
            return

        self._resolve_params(atoms, dyn, md_runner)
        
        # Collect current structure
        from pymatgen.io.ase import AseAtomsAdaptor
        adaptor = AseAtomsAdaptor()
        # Copy atoms to avoid issues if dyn modifies it in place
        self.structures.append(adaptor.get_structure(atoms.copy()))
        
        # Check convergence periodically
        n_total = len(self.structures)
        if n_total > self.ignore_entries + 2:
            # We check only every 'check_interval_steps' after equilibration
            if (n_total - self.ignore_entries) % self.check_interval_steps == 0:
                from pymatgen.analysis.diffusion.analyzer import DiffusionAnalyzer
                
                analysis_structs = self.structures[self.ignore_entries:]
                if self.temperature is not None:
                    temp = float(self.temperature)
                else:
                    raise ValueError("temperature must be explicitly provided to DiffusionMonitor.")
                
                if self.timestep_fs is None:
                    raise ValueError("timestep_fs must be explicitly provided to DiffusionMonitor.")
                if self.log_interval is None:
                    raise ValueError("log_interval must be explicitly provided to DiffusionMonitor.")
                    
                ts = self.timestep_fs
                li = self.log_interval
                
                try:
                    analyzer = DiffusionAnalyzer.from_structures(
                        structures=analysis_structs,
                        specie=self.specie,
                        temperature=temp,
                        time_step=ts * li,
                        step_skip=1,
                        smoothed="max"
                    )
                    
                    D = analyzer.diffusivity
                    D_std = analyzer.diffusivity_std_dev
                    # analyzer.msd is already the ensemble average over all diffusing species
                    # and averaged over different time origins.
                    # The last element corresponds to the longest time interval.
                    mean_msd = float(analyzer.msd[-1])
                    
                    if D > 1e-8 and D_std > 0:
                        rel_err = D_std / D
                        logger.info(f"Diffusion Monitor [{self.specie}]: D={D:.2e}, rel_err={rel_err:.3f} (target < {self.threshold}), mean_msd={mean_msd:.2f} (target >= {self.min_msd})")
                        
                        if rel_err < self.threshold and mean_msd >= self.min_msd:
                            msg = f"Diffusion converged for {self.specie}: rel_err={rel_err:.4f} < {self.threshold}, mean_msd={mean_msd:.2f} >= {self.min_msd}"
                            logger.info(msg)
                            self.finalize()
                            raise MDStopIteration(msg)
                        elif rel_err < self.threshold:
                            logger.info(f"Diffusion Monitor [{self.specie}]: rel_err met ({rel_err:.3f} < {self.threshold}), but mean_msd ({mean_msd:.2f}) < {self.min_msd}")
                    else:
                        logger.info(f"Diffusion Monitor [{self.specie}]: D={D:.2e}, D_std={D_std:.2e} (ignored due to insufficient diffusion or zero variance)")
                except MDStopIteration:
                    # Propagate the stop signal
                    raise
                except Exception as e:
                    # Might fail if not enough diffusion or specie not found
                    logger.warning(f"Diffusion Monitor calculation failed: {e}")

class QuenchingControl:
    """
    Callback to perform linear temperature quenching/ramping during MD.
    """
    def __init__(self, start_temp: float, end_temp: float, total_steps: int):
        self.start_temp = start_temp
        self.end_temp = end_temp
        self.total_steps = total_steps

    def __call__(self, *args, **kwargs):
        dyn = kwargs.get("dyn")
        if dyn is None:
            # Try to find Dynamics object in args
            for arg in args:
                if hasattr(arg, "get_number_of_steps"):
                    dyn = arg
                    break
        
        if dyn is None:
            return

        step = dyn.get_number_of_steps()
        fraction = min(1.0, step / self.total_steps)
        temp_k = self.start_temp + fraction * (self.end_temp - self.start_temp)
        
        from ase import units
        # Set temperature for various ASE thermostats
        # 1. Standard set_temperature (Langevin, NPT, etc.)
        # This updates the target temperature attribute used in the integration step.
        if hasattr(dyn, "set_temperature"):
            try:
                dyn.set_temperature(temperature_K=temp_k)
            except TypeError:
                # Some old versions or different signatures might use 'temperature'
                dyn.set_temperature(temp_k * units.kB)
        
        # 2. Bussi Thermostat (CSVR)
        # The Bussi thermostat lacks a set_temperature method in ASE.
        # We must manually update 'target_kinetic_energy', which determines the rescaling target.
        # target_KE = 0.5 * N_dof * k_B * T
        if hasattr(dyn, "target_kinetic_energy") and hasattr(dyn, "ndof"):
             dyn.target_kinetic_energy = 0.5 * temp_k * units.kB * dyn.ndof
        
        # 3. Langevin Thermostat (Backup)
        # Langevin noise (sigma) depends on T: sigma = sqrt(2 * T * friction / dt).
        # While set_temperature() usually handles this, we double check here to ensure noise balance is correct.
        if hasattr(dyn, "sigma") and hasattr(dyn, "temp") and hasattr(dyn, "friction") and hasattr(dyn, "dt"):
             import numpy as np
             dyn.sigma = np.sqrt(2 * dyn.friction * dyn.temp / dyn.dt)
        
        # 4. Nose-Hoover / MTK / NPT (Legacy/Manual Update)
        # These complex integrators often lack a cleaner set_temperature API in older ASE versions.
        # We must manually scale the thermostat reservoir energy (kT) and chain masses (Q/W/R).
        # This ensures the thermostat oscillates around the NEW temperature, not the old one.
        if not hasattr(dyn, "set_temperature"):
            # Thermostat kT and masses
            thermo = getattr(dyn, "_thermostat", None)
            if thermo and hasattr(thermo, "_kT"):
                thermo._kT = temp_k * units.kB
                if hasattr(thermo, "_Q") and hasattr(thermo, "_tdamp") and hasattr(thermo, "_num_atoms_global"):
                    # Q[0] scales with N_atoms, others scale with 1. Both scale with T.
                    thermo._Q[0] = 3 * thermo._num_atoms_global * thermo._kT * thermo._tdamp**2
                    thermo._Q[1:] = thermo._kT * thermo._tdamp**2
            
            # Barostat kT and masses (for NPT)
            baro = getattr(dyn, "_barostat", None)
            if baro and hasattr(baro, "_kT"):
                baro._kT = temp_k * units.kB
                if hasattr(baro, "_W") and hasattr(baro, "_pdamp") and hasattr(baro, "_num_atoms_global"):
                    baro._W = (baro._num_atoms_global + 1) * baro._kT * baro._pdamp**2
                if hasattr(baro, "_R") and hasattr(baro, "_pdamp"):
                    cell_dof = 9
                    baro._R[0] = cell_dof * baro._kT * baro._pdamp**2
                    baro._R[1:] = baro._kT * baro._pdamp**2
            
            # Top-level attributes
            if hasattr(dyn, "_temperature_K"):
                dyn._temperature_K = temp_k
            if hasattr(dyn, "_kT"):
                dyn._kT = temp_k * units.kB
            if hasattr(dyn, "temp"):
                dyn.temp = temp_k * units.kB
            if hasattr(dyn, "temperature_K"):
                dyn.temperature_K = temp_k

def get_md_callback(
    monitor_type: str, 
    atoms=None, 
    **kwargs
):
    """Factory function to create MD callbacks."""
    # Note: timestep_fs and log_interval can now be None for auto-detection in Monitors
    
    if monitor_type == "explosion":
        threshold = kwargs.get("temp_threshold", 10000.0)
        return ExplosionMonitor(atoms, threshold)
    elif monitor_type == "equilibration":
        return EquilibrationMonitor(
            atoms=atoms, 
            **kwargs
        )
    elif monitor_type == "overshoot":
        target_temp = kwargs.get("temperature", 300.0)
        tolerance = kwargs.get("tolerance", 500.0)
        return OvershootMonitor(atoms, target_temp, tolerance)
    elif monitor_type == "volume":
        lower = kwargs.get("lower_limit_ratio", 0.2)
        upper = kwargs.get("upper_limit_ratio", 2.0)
        return VolumeMonitor(atoms, lower, upper)
    elif monitor_type == "quenching":
        start_temp = kwargs.get("temperature", 3000.0)
        end_temp = kwargs.get("temperature_end", 300.0)
        steps = kwargs.get("steps", 20000)
        return QuenchingControl(start_temp, end_temp, steps), 1 # Apply every step
    elif monitor_type == "diffusion":
        specie = kwargs.get("specie", "Li")
        threshold = kwargs.get("threshold", 0.1)
        check_interval = kwargs.get("check_interval_ps", 5.0)
        ignore_ps = kwargs.get("ignore_ps", 5.0)
        output_dir = kwargs.get("output_dir", None)
        return DiffusionMonitor(
            atoms=atoms,
            specie=specie,
            threshold=threshold,
            check_interval_ps=check_interval,
            ignore_ps=ignore_ps,
            output_dir=output_dir
        )
    
    return None
