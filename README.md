# LoRaWAN Traffic-Processing Plots

Python utilities for processing LoRaWAN emulation logs and producing the PDF
figures in [`Figures/`](Figures/). The repository contains two independent
comparison studies:

1. **ChirpStack vs. The Things Stack (TTS)** - compares the two network
   servers for a fixed 500-end-device deployment. The scenarios vary the
   topology (one or three gateways), the confirmed-uplink proportion, and the
   uplink periodicity.
2. **Optimal Scheduler vs. TTS** - compares the Optimal scheduler, standard
   TTS, and TTS with the threshold-based scheduler (labelled **SFTS** in the
   scripts). It contains:
   - **Classic scenarios**, which vary the numbers of end devices and gateways
     with a fixed traffic profile.
   - **Confirmed-traffic scenarios**, which vary the confirmed-uplink
     proportion and gateway count.

## Repository layout

```text
Chirpstack-vs-The-Things-Stack/
  TTS_TEST_10_REPETITION_COPY/       # TTS logs for the server comparison
  CS_TEST_10_REPETITION_COPY/        # ChirpStack logs for the server comparison

Optimal-Scheduler-Vs-The-Things-Stack/
  10_CLASSIC_SCENARIO_..._TTS/       # classic TTS runs
  10_CLASSIC_SCENARIO_..._SFTS/      # classic threshold-scheduler runs
  10_CLASSIC_SCENARIO_..._OPTIMAL/   # classic Optimal-scheduler runs
  10_RUNS_NORMAL_.../                # confirmed-traffic TTS runs
  10_RUNS_CUSTOM_.../                # confirmed-traffic SFTS runs
  10_RUNS_OPTIMAL_.../               # confirmed-traffic Optimal runs
  OPTIMAL_TEST_DIFFERENT_END_DEVICE_GATEWAY/
  TTS_NORMAL_ALTERNATIVE_RUN_DELL/
  TTS_CUSTOM_ALTERNATIVE_RUN_DELL/   # single-run scheduler-comparison inputs

functions_processing_logs_*.py       # reusable parsers, aggregators, and plotters
processing-*.py                      # configured analysis entry points
Figures/                             # generated PDF figures
```

The directory names are used directly by the entry-point scripts. Keep them,
or update the corresponding path constants before running an analysis.

## Requirements

Use Python 3 and install the plotting/data dependencies:

```bash
python3 -m pip install pandas numpy matplotlib seaborn
```

Run every command below from the repository root. The scripts use relative
paths and save plots to `Figures/`.

## Run the analyses

### ChirpStack vs. TTS

```bash
python3 processing-multi-run-logs-cs-vs-tts.py
```

This script reads the two `*_TEST_10_REPETITION_COPY` directories and averages
the repeated runs for each `(gateways, end devices, periodicity, confirmed
traffic percentage)` scenario. It produces comparison plots for:

- frame delivery ratio (FDR), confirmed-uplink FDR, and unconfirmed-uplink
  FDR;
- Jain's fairness index, including the time-on-air variant;
- ACK delivery, RX1/RX2 utilization, RX1/RX2 share of all confirmed uplinks,
  half-duplex loss, and unused receive-window time;
- loss causes, separated by gateway and RX window.

The helper module is
[`functions_processing_logs_multi_run_cs_vs_tts.py`](functions_processing_logs_multi_run_cs_vs_tts.py).
Besides the PDFs, its directory processor writes scenario-level and
average-scenario JSON and CSV summaries next to the processed log directory.

### Optimal Scheduler vs. TTS: multi-run scenarios

```bash
python3 processing-multi-run-logs.py
```

[`processing-multi-run-logs.py`](processing-multi-run-logs.py) controls which
experiment family is used through `CLASSIC_SCENARIOS`:

- `True` (the checked-in default) selects the three classic directories and
  compares TTS, SFTS, and Optimal as end-device and gateway counts change.
- `False` selects the three `10_RUNS_*_GLOBECOM_COMPARISON_FIXED_VERSION`
  directories and compares the same schedulers as confirmed traffic percentage
  and gateway count change.

For the selected family, the script averages repeated runs, calculates ACK,
half-duplex, RX-window, and uplink FDR metrics, then creates the FDR plot and
per-confirmed-traffic bar charts. It also writes raw and averaged scenario
data as JSON and CSV files using the processed directory name as a prefix.
Its reusable implementation is
[`functions_processing_logs_multi_run.py`](functions_processing_logs_multi_run.py).

### Optimal Scheduler vs. TTS: single-run topology matrices

```bash
python3 processing-single-run-logs.py
```

This entry point uses the three `*_ALTERNATIVE_RUN_DELL`/`OPTIMAL_TEST_*`
directories. It processes each scenario individually and generates:

- all/confirmed/unconfirmed FDR comparisons;
- scheduled-downlink loss comparisons;
- ACK, RX1, and RX2 matrices by spreading factor and `(gateway, end-device)`
  configuration, in horizontal and vertical layouts;
- blocked receive-window-time matrices;
- ACK heatmaps, receive-window-specific ACK heatmaps, ACK differences, and
  side-by-side ACK/half-duplex-loss bars;
- `report.csv`, a cross-scheduler summary.

[`functions_processing_logs_single_run.py`](functions_processing_logs_single_run.py)
contains the shared parsing, metric, and plotting functions for this mode.

## Log contract

The processors discover `*_uplinks.csv` files. They extract scenario
parameters from the filename, so filenames must retain these fields:

```text
...period_<period>_gateway_<gateways>_seed_<seed>_percentage_<0-100>_log_N_ED_<end-devices>_..._uplinks.csv
```

For example, the included logs use names such as
`...period_1440_gateway_1_seed_120_percentage_50_log_N_ED_500_log_uplinks.csv`.
The embedded CSV-style sections are located by their header rows rather than
by a fixed line number. Expected tables include downlink records with `RX` and
uplink records with `received` and `code`; Optimal logs use the variant without
the trailing empty uplink column. The analyses also use the associated
`*_GlobalPerf.csv`/`*_GlobalPerf.txt`, `*_EndDevicesOut.csv`, and, where
applicable, `*_results.csv` files to calculate FDR and scheduling-failure
causes.

Do not rename only one scheduler's files: cross-scheduler FDR calculations
match logs by gateway, end-device count, confirmed-traffic percentage, and
seed.

## Processing details

The functions modules perform the common workflow:

1. find the log files and parse their scenario parameters;
2. read the embedded downlink and uplink tables;
3. deduplicate repeated uplink receptions by send time, prioritizing a
   successful reception;
4. calculate per-end-device and per-spreading-factor counts, ACKs, RX1/RX2
   use, time on air, blocked time, half-duplex loss, FDR, and fairness;
5. average repeated runs per scenario and render the requested comparisons.

The scripts call `plt.show()` after saving PDFs. In a headless environment,
use a non-interactive Matplotlib backend:

```bash
MPLBACKEND=Agg python3 processing-multi-run-logs-cs-vs-tts.py
```

Existing files in `Figures/`, generated summaries, and `report.csv` are
overwritten when a run produces the same output name.
