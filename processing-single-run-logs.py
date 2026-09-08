
import sys
import os
from functions_processing_logs_single_run import *
import csv
import pprint

# =============================================================================
# Processing script for LoRaWAN scheduler experiment logs only (no raw traffic)
# Compares three schedulers: Optimal, TTS Normal, and TTS Custom
# =============================================================================

# --- Directory paths for each experiment ---
BASE = "Optimal-Scheduler-Vs-The-Things-Stack"
DIR_OPTIMAL = f"{BASE}/OPTIMAL_TEST_DIFFERENT_END_DEVICE_GATEWAY"
DIR_TTS_NORMAL = f"{BASE}/TTS_NORMAL_ALTERNATIVE_RUN_DELL"
DIR_TTS_CUSTOM = f"{BASE}/TTS_CUSTOM_ALTERNATIVE_RUN_DELL"

# =============================================================================
# Data Extraction
# =============================================================================

# Extract non-scheduled (lost) downlinks for each scheduler
OPTIMAL_lost_DL   = extract_non_scheduled_downlinks(DIR_OPTIMAL,     DIR_OPTIMAL,     desired_headers_UL2, 1)
TTS_NORMAL_lost_DL = extract_non_scheduled_downlinks(DIR_TTS_NORMAL, DIR_TTS_NORMAL,  desired_headers_UL,  0)
TTS_CUSTOM_lost_DL = extract_non_scheduled_downlinks(DIR_TTS_CUSTOM, DIR_TTS_CUSTOM,  desired_headers_UL,  0)

# Compute Frame Delivery Ratio (FDR) for uplinks across all experiments
FDR_EXPERIMENTS, FDR_EXPERIMENTS_CONF, FDR_EXPERIMENTS_UNCONF = computation_FDR_UPLINKS(
    DIR_OPTIMAL, DIR_TTS_NORMAL, DIR_TTS_CUSTOM
)

# =============================================================================
# Directory Processing — extract SF data, ACK matrices, RX window matrices
# =============================================================================

# Optimal scheduler
sf_data_all_1, sf_values, gw_ed_combinations, ack_matrix, rx_matrix_1, rx_matrix_2, blocked_rx1_matrix, blocked_rx2_matrix = \
    process_directory(DIR_OPTIMAL, desired_headers2, desired_headers_UL2, 3, 4)
ack_percentages_ch = calculate_ack_percentages(sf_data_all_1)
print(desired_headers)

# TTS Normal scheduler
sf_data_all_2, sf_values_2, gw_ed_combinations_2, ack_matrix_2, rx_matrix_1_2, rx_matrix_2_2, blocked_rx1_matrix_2, blocked_rx2_matrix_2 = \
    process_directory(DIR_TTS_NORMAL, desired_headers2, desired_headers_UL, 3, 4)
ack_percentages_c = calculate_ack_percentages(sf_data_all_2)

# TTS Custom scheduler
sf_data_all_3, sf_values_3, gw_ed_combinations_3, ack_matrix_3, rx_matrix_1_3, rx_matrix_2_3, blocked_rx1_matrix_3, blocked_rx2_matrix_3 = \
    process_directory(DIR_TTS_CUSTOM, desired_headers2, desired_headers_UL)
ack_percentages_c_cs = calculate_ack_percentages(sf_data_all_3)

# =============================================================================
# Heatmap Matrix Creation
# =============================================================================

ack_matrix_ch,    rx1_matrix_ch,    rx2_matrix_ch,    HD_matrix_ch,    dc_rx1_ack_matrix_ch,    dc_rx2_ack_matrix_ch    = create_ack_heatmap_matrices(ack_percentages_ch)
ack_matrix_c,     rx1_matrix_c,     rx2_matrix_c,     HD_matrix_c,     dc_rx1_ack_matrix_c,     dc_rx2_ack_matrix_c     = create_ack_heatmap_matrices(ack_percentages_c)
ack_matrix_c_cs,  rx1_matrix_c_cs,  rx2_matrix_c_cs,  HD_matrix_c_cs,  dc_rx1_ack_matrix_c_cs,  dc_rx2_ack_matrix_c_cs  = create_ack_heatmap_matrices(ack_percentages_c_cs)

# Extract sorted end-device and gateway numbers from the Optimal experiment
ed_numbers = sorted(set(extract_gateway_and_end_devices(file)[1] for file in ack_percentages_ch))
gw_numbers = sorted(set(extract_gateway_and_end_devices(file)[0] for file in ack_percentages_ch))

# =============================================================================
# Plotting
# =============================================================================

# FDR plots (all, confirmed, unconfirmed)
plot_fdr_tout(FDR_EXPERIMENTS,        "ALL")
plot_fdr_tout(FDR_EXPERIMENTS_CONF,   "CONF")
plot_fdr_tout(FDR_EXPERIMENTS_UNCONF, "UNCONF")

# Downlink loss comparison
plot_downlink_info(OPTIMAL_lost_DL, TTS_NORMAL_lost_DL, TTS_CUSTOM_lost_DL)

# Vertical matrix plots (ACK + RX windows)
plot_matrices_vertical(sf_values,   gw_ed_combinations,   ack_matrix,   rx_matrix_1,   rx_matrix_2,   blocked_rx1_matrix,   blocked_rx2_matrix,   "Optimal with priority", False, False)
plot_matrices_vertical(sf_values_2, gw_ed_combinations_2, ack_matrix_2, rx_matrix_1_2, rx_matrix_2_2, blocked_rx1_matrix_2, blocked_rx2_matrix_2, "TTS",                   False, True)
plot_matrices_vertical(sf_values_3, gw_ed_combinations_3, ack_matrix_3, rx_matrix_1_3, rx_matrix_2_3, blocked_rx1_matrix_3, blocked_rx2_matrix_3, "SFTS",                  False, True)

# Standard matrix plots
plot_matrices(sf_values,   gw_ed_combinations,   ack_matrix,   rx_matrix_1,   rx_matrix_2,   blocked_rx1_matrix,   blocked_rx2_matrix,   "Optimal")
plot_matrices(sf_values_2, gw_ed_combinations_2, ack_matrix_2, rx_matrix_1_2, rx_matrix_2_2, blocked_rx1_matrix_2, blocked_rx2_matrix_2, "TTS")
plot_matrices(sf_values_3, gw_ed_combinations_3, ack_matrix_3, rx_matrix_1_3, rx_matrix_2_3, blocked_rx1_matrix_3, blocked_rx2_matrix_3, "SFTS")

# Blocked RX window matrix plots
plot_matrices_blocked(sf_values,   gw_ed_combinations,   ack_matrix,   rx_matrix_1,   rx_matrix_2,   blocked_rx1_matrix,   blocked_rx2_matrix,   "Optimal with priority")
plot_matrices_blocked(sf_values_2, gw_ed_combinations_2, ack_matrix_2, rx_matrix_1_2, rx_matrix_2_2, blocked_rx1_matrix_2, blocked_rx2_matrix_2, "TTS",  1000000)
plot_matrices_blocked(sf_values_3, gw_ed_combinations_3, ack_matrix_3, rx_matrix_1_3, rx_matrix_2_3, blocked_rx1_matrix_3, blocked_rx2_matrix_3, "SFTS", 1000000)

# ACK percentage heatmaps (single metric)
plot_ack_matrices([ack_matrix_ch],    ["ACK%"], ed_numbers, gw_numbers, "OPTIMAL_WITH_THRES")
plot_ack_matrices([ack_matrix_c],     ["ACK%"], ed_numbers, gw_numbers, "NORMAL_TTS")
plot_ack_matrices([ack_matrix_c_cs],  ["ACK%"], ed_numbers, gw_numbers, "CUSTOM_TTS")

# ACK percentage heatmaps split by duty-cycle RX window
plot_ack_matrices([dc_rx1_ack_matrix_c_cs, dc_rx2_ack_matrix_c_cs], ["dcRx1", "dcRx2"], ed_numbers, gw_numbers, "CUSTOM_TTS")
plot_ack_matrices([dc_rx1_ack_matrix_c,    dc_rx2_ack_matrix_c],    ["dcRx1", "dcRx2"], ed_numbers, gw_numbers, "NORMAL_TTS")
plot_ack_matrices([dc_rx1_ack_matrix_ch,   dc_rx2_ack_matrix_ch],   ["dcRx1", "dcRx2"], ed_numbers, gw_numbers, "OPTIMAL_WITH_THRES")

# ACK difference and bar plots across schedulers
plot_ack_differences(ack_matrix_ch, ack_matrix_c, ack_matrix_c_cs, ed_numbers, gw_numbers)
plot_ack_bars(ack_matrix_ch, ack_matrix_c, ack_matrix_c_cs, ed_numbers, gw_numbers)
plot_ack_bars(HD_matrix_ch,  HD_matrix_c,  HD_matrix_c_cs,  ed_numbers, gw_numbers, 'HD Loss', 20)

# =============================================================================
# Report & Debug Output
# =============================================================================

create_report(sf_data_all_1, sf_data_all_2, sf_data_all_3, "report.csv")

# Debug: pretty-print RX window 1 matrix for TTS Custom
pp = pprint.PrettyPrinter(indent=4)
pp.pprint(rx_matrix_1_3)

plt.show()





     






