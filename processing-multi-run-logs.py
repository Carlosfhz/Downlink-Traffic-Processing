# This script processes multiple logs and plots metrics related to downlink scheduling
# for the comparison: Optimal vs TTS vs SFTS
import pandas as pd
import os
import glob
import re
import numpy as np
import seaborn as sns
import json
import matplotlib.pyplot as plt
from functions_processing_logs_multi_run import *


# --- Configuration ---

# Flag to switch between classic scenario directories and default (GlobeCom) directories
CLASSIC_SCENARIOS = True

# Default directories: experiments with varying proportion of confirmed uplink traffic (GlobeCom)
directory1 = "Optimal-Scheduler-Vs-The-Things-Stack/10_RUNS_NORMAL_LORAWAN_FOR_GLOBECOM_COMPARISON_FIXED_VERSION"
directory2 = "Optimal-Scheduler-Vs-The-Things-Stack/10_RUNS_CUSTOM_LORWAN_FOR_GLOBECOM_COMPARISON_FIXED_VERSION"
directory3 = "Optimal-Scheduler-Vs-The-Things-Stack/10_RUNS_OPTIMAL_LORWAN_FOR_GLOBECOM_COMPARISON_FIXED_VERSION"

# Override with classic scenario directories if flag is set
# Classic scenarios: fixed traffic profile, multiple seeds, used for journal review
if CLASSIC_SCENARIOS:
    directory1 = "Optimal-Scheduler-Vs-The-Things-Stack/10_CLASSIC_SCENARIO_NEW_RUN_MULTIPLE_SEEDS_REVEIW_TTS"      # The Things Stack (TTS)
    directory2 = "Optimal-Scheduler-Vs-The-Things-Stack/10_CLASSIC_SCENARIO_NEW_RUN_MULTIPLE_SEEDS_REVEIW_SFTS"     # Smart Flexible Traffic Scheduler (SFTS)
    directory3 = "Optimal-Scheduler-Vs-The-Things-Stack/10_CLASSIC_SCENARIO_NEW_RUN_MULTIPLE_SEEDS_REVEIW_OPTIMAL"  # Optimal Scheduler

# Colors assigned to each scheduler for consistent plot styling: TTS, SFTS, Optimal
colors_TTS_CUS_OP = ['orange', 'seagreen', 'salmon']

# --- CSV Column Headers ---
# Downlink frame headers
desired_headers     = ["senderId", "receiverID", "sendTime", "receivedTime", "SF", "SNR", "Ftype", "Freq", "RX"]
# Uplink frame headers (TTS/SFTS format — includes a trailing empty column)
desired_headers_UL  = ["senderId", "receiverID", "sendTime", "receivedTime", "SF", "SNR", "Ftype", "Freq", "received", "code", ""]
# Uplink frame headers (Optimal format — no trailing empty column)
desired_headers_UL2 = ["senderId", "receiverID", "sendTime", "receivedTime", "SF", "SNR", "Ftype", "Freq", "received", "code"]
# Half-duplex collision log headers
headers_lost        = ["HDsenderId", "HDreceiverID", "HDsendTime", "receivedTime", "SF", "SNR", "Ftype"]

# --- Initialize Matrices ---
sf_values           = None
gw_ed_combinations  = []
ack_matrix          = None
rx_matrix           = None
blocked_rx1_matrix  = None
blocked_rx2_matrix  = None


# --- Process Log Directories ---
# Each call aggregates metrics across all runs in the directory.
# Returns: averaged scenario metrics, per-SF data, and detected SF values.
av_scenario_2, sf_data_all_2, sf_values = process_directory(directory2, desired_headers, desired_headers_UL,  "Percentage", 3, 4)  # SFTS
av_scenario_1, sf_data_all_2, sf_values = process_directory(directory1, desired_headers, desired_headers_UL,  "Percentage", 3, 4)  # TTS
av_scenario_3, sf_data_all_2, sf_values = process_directory(directory3, desired_headers, desired_headers_UL2, "Percentage", 3, 4)  # Optimal

# Extract axis values for heatmap indexing
gw_numbers         = sorted(set(key[0] for key in av_scenario_2.keys()))   # Unique gateway counts
percentage_numbers = sorted(set(key[1] for key in av_scenario_2.keys()))   # Unique confirmed traffic percentages

# Reference scenario for ACK percentage analysis (SFTS)
ack_percentages_c = av_scenario_2

# --- Build Heatmap Matrices ---
# Each matrix contains ACK%, RX window 1%, and RX window 2% across GW/percentage combinations
ack_matrix_1,   rx_matrix_1,   rx_matrix_2   = create_ack_heatmap_matrices_2(av_scenario_1)  # TTS
ack_matrix_1_2, rx_matrix_1_2, rx_matrix_2_2 = create_ack_heatmap_matrices_2(av_scenario_2)  # SFTS
ack_matrix_1_3, rx_matrix_1_3, rx_matrix_2_3 = create_ack_heatmap_matrices_2(av_scenario_3)  # Optimal

# Re-process Optimal directory to ensure sf_data_all_3 is populated with the correct UL2 headers
av_scenario_3, sf_data_all_3, sf_values = process_directory(directory3, desired_headers, desired_headers_UL2, "Percentage", 3, 4)
ack_matrix_3, rx_matrix_13, rx_matrix_23    = create_ack_heatmap_matrices_2(av_scenario_3)


# --- Compute Frame Delivery Ratio (FDR) for Uplinks ---
# Returns FDR dicts for all frames, confirmed-only, and unconfirmed-only
FDR_EXPERIMENTS, FDR_EXPERIMENTS_CONF, FDR_EXPERIMENTS_UNCONF = computation_FDR_UPLINKS(directory3, directory1, directory2)

# --- Plotting ---
# Plot FDR across all uplink frame types
plot_fdr_tout(FDR_EXPERIMENTS, "ALL")

# Plot ACK delivery percentage per scheduler across GW/percentage configurations
plot_ack_bars([av_scenario_1, av_scenario_2, av_scenario_3], "ACK%", ["TTS", "SFTS", "Optimal"], 'ACK with DC")')

# Plot half-duplex collision percentage per scheduler
plot_ack_bars([av_scenario_1, av_scenario_2, av_scenario_3], "HD%",  ["TTS", "SFTS", "Optimal"], 'HD with DC")')


plt.show()

