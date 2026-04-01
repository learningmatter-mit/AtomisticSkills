"""Logging for molecular dynamics."""

import weakref
import time
import ase.units as units
from ase.parallel import world
from ase.utils import IOContext


class MCLogger(IOContext):
    """Class for logging molecular dynamics simulations.

    Parameters:
    dyn:           The dynamics.  Only a weak reference is kept.

    logfile:       File name or open file, "-" meaning standard output.

    stress=False:  Include stress in log.

    peratom=False: Write energies per atom.

    mode="a":      How the file is opened if logfile is a filename.
    """

    def __init__(
        self, dyn, logfile, header=True, stress=False, peratom=False, mode="a"
    ):
        if hasattr(dyn, "get_nsteps"):
            self.dyn = weakref.proxy(dyn)
        else:
            self.dyn = None

        self.logfile = self.openfile(logfile, comm=world, mode=mode)
        self.stress = stress
        self.peratom = peratom
        if self.dyn is not None:
            self.hdr = "%-5s " % ("MC Step",)
            self.fmt = "%-6d "

        else:
            self.hdr = ""
            self.fmt = ""

        self.hdr += "%8s " % ("Time",)
        self.fmt += "%02d:%02d:%02d "

        if hasattr(dyn, "boxes"):
            self.hdr += "%6s" % ("Box",)
            self.fmt += "%6d"
            self.ge = True
        else:
            self.ge = False

        if self.peratom:
            self.hdr += "%12s" % ("Epot/N[eV]",)
            self.fmt += "%12.4f"
        else:
            self.hdr += "%12s" % ("Epot[eV]",)
            digits = 5
            self.fmt += 1 * ("%%12.%df " % (digits,))

        if self.dyn is not None:
            self.hdr += "%20s" % ("Move Statistics",)

        if header:
            self.logfile.write(self.hdr + "\n")

    def __del__(self):
        self.close()

    def __call__(self):
        epot = self.dyn.potential_energy
        global_natoms = self.dyn.natoms
        if self.peratom:
            epot /= global_natoms
        if self.dyn is not None:
            n = self.dyn.get_nsteps()
            dat = (n,)
        else:
            dat = ()

        t = time.localtime()

        dat += (t[3], t[4], t[5])

        if self.ge:
            dat += (self.dyn.box_idx,)

        dat += (epot,)

        if self.dyn is not None:
            s = self.dyn.get_current_move_stats().split("#")
            nstats = len(s)
            if nstats != 0:
                stats_format = nstats * ("%20s")
                dat += tuple(s)
                fmt = self.fmt + stats_format + "\n"
            else:
                fmt = self.fmt + "\n"
        else:
            fmt = self.fmt + "\n"

        self.logfile.write(fmt % dat)
        self.logfile.flush()
