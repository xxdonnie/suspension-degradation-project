# Cycle Counting

## Overview

Fatigue damage accumulates cycle by cycle. Before a damage estimate can be made, the variable-amplitude load history recorded during driving must be decomposed into a set of discrete cycles, each characterised by a stress (or strain) amplitude and a mean value. This is done using the **rainflow counting algorithm**, which is the standard method in both automotive and structural engineering fatigue analysis.

Cycle counting is implemented in `scripts/process_pipeline.py` (function `count_cycles`).

## Why Rainflow Counting?

A real suspension load history is not a simple sinusoid — it is a complex, irregular waveform with superimposed large and small excursions. Simple peak counting or range counting underestimates damage because they fail to correctly pair up load reversals. Rainflow counting correctly identifies closed hysteresis loops in the stress-strain response, each of which corresponds to one cycle of fatigue damage. It is recommended by ASTM E1049 and is the standard method in automotive durability testing.

The method takes its name from a visual analogy: imagining rainwater flowing down a pagoda roof, dripping off overhanging edges to form nested loops.

## Algorithm

The implementation uses the `rainflow` Python library (Björk, 2021), which implements the ASTM E1049-85 three-point algorithm. The algorithm operates on a filtered, detrended time series of stress or strain values.

**Inputs:**
- Cleaned, detrended strain signal in microstrain (με) or acceleration signal in m/s² from `filter_signal.py`
- Residue handling: residues (unclosed half-cycles at the start and end of the record) are treated using the ASTM repeated block method — the sequence is duplicated and the residue cycles are extracted from the combined record

**Outputs for each counted cycle:**
- Range (peak-to-valley amplitude, in signal units)
- Mean value (midpoint of the cycle)
- Count (always 0.5 for half-cycles, summed to integer cycles in the histogram)
- Start index in the original time series (for traceability)

## From Strain to Stress

If strain gauge data is used as the primary channel, cycles are counted in microstrain (με) and then converted to stress amplitude:

```
σ_amplitude = E × ε_amplitude
```

where `E` is the elastic modulus of the strut material (assumed 210 GPa for low-carbon steel). This is a uniaxial assumption — the strain gauge measures strain in one direction only. See `06_fem_model/material_model.md` for the material assumptions.

If the accelerometer is used as the primary channel (when strain gauge data is unavailable or noisy), acceleration cycles are counted directly and used as a proxy for loading severity rather than a direct stress measure.

## Cycle Histogram (Rainflow Matrix)

The counted cycles are binned into a 2D rainflow matrix with:
- X-axis: mean stress (or strain) — divided into `n_mean = 16` bins
- Y-axis: stress amplitude (half-range) — divided into `n_amp = 32` bins

The bin edges are set symmetrically around zero for the mean axis, and from zero to the maximum observed amplitude for the amplitude axis.

The rainflow matrix is saved as a NumPy `.npy` file and also exported as a CSV for use in the FEM comparison. A 1D amplitude histogram (summed across all mean values) is also saved for quick visualisation.

## Damage Summation (Miner's Rule)

As a first-pass damage estimate, linear damage accumulation is applied using Miner's rule:

```
D = Σ (n_i / N_i)
```

where `n_i` is the number of counted cycles at amplitude `σ_i` and `N_i` is the number of cycles to failure at that amplitude, read from the S-N curve.

The S-N curve used is a simplified curve for structural steel (BS 7608 Class B weld, or plain material as applicable — see `06_fem_model/material_model.md`). This gives a conservative but tractable estimate.

A damage fraction `D ≥ 1.0` nominally indicates failure. In practice, Miner's rule scatter means the actual failure can occur anywhere between `D = 0.3` and `D = 3.0`, so the absolute value is less important than the relative comparison between drive routes or loading conditions.

## Output Files

| File | Description |
|---|---|
| `rainflow_cycles.csv` | Full list of counted cycles (range, mean, count) |
| `rainflow_matrix.npy` | 2D histogram (mean × amplitude) |
| `amplitude_histogram.csv` | 1D amplitude distribution (summed across means) |
| `damage_summary.txt` | Miner's rule damage estimate, S-N curve used, total cycle count |

## Known Limitations

- The rainflow implementation assumes that the signal is stationary over the analysis window. Long drives with varying road surfaces should be split into segments (e.g. smooth road vs. cobblestones) before counting.
- Miner's rule is linear and does not account for load sequence effects (high-amplitude cycles early in the sequence cause more damage than the same cycles late — this is the sequence effect, which Miner ignores).
- The S-N curve for the Space Star strut material is not known from manufacturer data. Literature values for structural steel are used as a proxy. This is a significant source of uncertainty and is discussed in `07_comparison/mismatch_analysis.md`.
- Multiaxial loading (the strut sees both axial and bending loads) is not fully captured by a single uniaxial gauge or a single accelerometer axis. Multiaxial fatigue criteria (e.g. von Mises equivalent stress cycles) would require additional measurement channels.
