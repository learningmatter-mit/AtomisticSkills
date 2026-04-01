"""
Generates a simulated XRD .xy data file from a list of manually extracted peaks.

This is useful for digitizing plot screenshots or literature graphics
by visually extracting the major peak positions and intensities.

Usage:
    python digitize_plot.py peaks.json --output digitized.xy --min-x 5 --max-x 80 --points 4000

Requirements:
    - Conda environment: base-agent
    - Required packages: numpy
"""

import argparse
import json
import numpy as np
import sys
import os
import matplotlib.pyplot as plt

def pseudo_voigt(x, xc, A, w, eta=0.5):
    """
    Pseudo-Voigt profile generator.
    x: independent variable
    xc: peak center
    A: area/intensity
    w: FWHM
    eta: Lorentzian fraction (0 to 1)
    """
    w_g = w / np.sqrt(2 * np.log(2))
    w_l = w
    
    gaussian = (2 / w_g) * np.sqrt(np.log(2) / np.pi) * np.exp(-4 * np.log(2) * ((x - xc) / w_g)**2)
    lorentzian = (2 / np.pi) * (w_l / (4 * (x - xc)**2 + w_l**2))
    
    return A * (eta * lorentzian + (1 - eta) * gaussian) * 1.5

def main():
    parser = argparse.ArgumentParser(description="Digitize XRD peaks to an .xy file")
    parser.add_argument("input", help="JSON file containing list of peaks [{'2theta': 10.5, 'intensity': 1.0, 'fwhm': 0.3}, ...]")
    parser.add_argument("--output", default="digitized.xy", help="Output .xy file path")
    parser.add_argument("--min-x", type=float, default=5.0, help="Minimum 2-theta value")
    parser.add_argument("--max-x", type=float, default=90.0, help="Maximum 2-theta value")
    parser.add_argument("--points", type=int, default=4000, help="Number of data points")
    parser.add_argument("--noise", type=float, default=0.01, help="Amplitude of experimental noise to add")
    parser.add_argument("--background", type=float, default=0.05, help="Amplitude of exponential background to add")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"Error: Input file not found {args.input}")
        sys.exit(1)
        
    try:
        with open(args.input, 'r') as f:
            peaks = json.load(f)
    except Exception as e:
        print(f"Error reading JSON file {args.input}: {e}")
        sys.exit(1)
        
    x = np.linspace(args.min_x, args.max_x, args.points)
    y = np.zeros_like(x)
    
    for peak in peaks:
        xc = peak.get("2theta")
        A = peak.get("intensity")
        w = peak.get("fwhm", 0.3)  # default FWHM
        eta = peak.get("eta", 0.5) # default Lorentzian fraction
        
        if xc is None or A is None:
            print(f"Warning: Skipping invalid peak entry {peak}. Missing '2theta' or 'intensity'.")
            continue
            
        y += pseudo_voigt(x, xc, A, w, eta)
        
    # Add a realistic baseline/background
    if args.background > 0.0:
        background_curve = args.background * np.exp(-(x - args.min_x) / 10) + (args.background * 0.4)
        y += background_curve
        
    # Add some experimental noise
    if args.noise > 0.0:
        np.random.seed(42)  # for reproducibility
        noise_curve = np.random.normal(0, args.noise, len(x))
        y += noise_curve
        
    # Ensure non-negative
    y = np.clip(y, 0, None)
    
    # Scale to experimental-like counts (max ~ 1000)
    if np.max(y) > 0:
        y = y * (1000.0 / np.max(y))
        
    # Save to .xy file
    np.savetxt(args.output, np.column_stack((x, y)), fmt='%.3f %.3f')
    print(f"Successfully generated digitized XY data at: {args.output}")
    
    # Generate and save a plot of the digitized data
    plot_output = os.path.splitext(args.output)[0] + ".png"
    plt.figure(figsize=(10, 5))
    plt.plot(x, y, color='red', linewidth=1.5)
    
    # Add labels for the extracted peaks
    for peak in peaks:
        xc = peak.get("2theta")
        name = peak.get("name")
        if xc is not None and name is not None:
             # Find the approximate y-value at this peak to place the text nicely
             idx = np.abs(x - xc).argmin()
             peak_y = y[idx]
             plt.text(xc, peak_y + 20, name, rotation=90, verticalalignment='bottom', horizontalalignment='center', fontsize=9)
             
    plt.xlabel("2 theta (deg)")
    plt.ylabel("Intensity (counts)")
    plt.title("Digitized XRD Pattern")
    plt.xlim(args.min_x, args.max_x)
    plt.ylim(0, np.max(y) * 1.2) # Give room for labels
    plt.tight_layout()
    plt.savefig(plot_output, dpi=300)
    plt.close()
    
    print(f"Saved digitized plot image to: {plot_output}")

if __name__ == "__main__":
    main()
