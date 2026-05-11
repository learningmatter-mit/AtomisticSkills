import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import os

with open('raman_modes.json') as f:
    data = json.load(f)

freqs = [m["frequency_cm"] for m in data["modes"] if m["raman_active"] and not m["is_acoustic"]]
intensities = [float(m["raman_intensity"]) for m in data["modes"] if m["raman_active"] and not m["is_acoustic"]]

x_points = np.linspace(0, 1000, 2000)
y_points = np.zeros_like(x_points)

broadening = 8.0
for f, i in zip(freqs, intensities):
    y_points += i * (broadening / 2.0) ** 2 / ((x_points - f) ** 2 + (broadening / 2.0) ** 2)

if y_points.max() > 0:
    y_points /= y_points.max()

plt.figure(figsize=(6, 5))
plt.plot(x_points, y_points, linewidth=2.5, color="#2874A6", label="Simulated (equal int.)")

for i, f in enumerate(set(freqs)):
    plt.axvline(f, color="#E74C3C", linewidth=0.8, alpha=0.6, linestyle="--")

plt.xlim(0, 1000)
plt.ylim(0, 1.1)
plt.xlabel("Raman Shift (cm$^{-1}$)", fontsize=14)
plt.ylabel("Intensity (a.u.)", fontsize=14)
plt.title("Raman Spectrum — TiO2", fontsize=15)
plt.legend(frameon=True, edgecolor="black")
plt.tight_layout()
plt.savefig('raman_spectrum.png', dpi=300)
print('Re-generated raman_spectrum.png')
print('Frequencies plotted:', sorted(list(set(freqs))))
