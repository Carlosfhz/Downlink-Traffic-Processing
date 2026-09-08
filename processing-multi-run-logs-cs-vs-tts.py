
from functions_processing_logs_multi_run_cs_vs_tts import *
import numpy as np

# Directories for TTS and CS test data
Directory_TTS = "Chirpstack-vs-The-Things-Stack/TTS_TEST_10_REPETITION_COPY"
Directory_CS  = "Chirpstack-vs-The-Things-Stack/CS_TEST_10_REPETITION_COPY"

labels = ["TTS", "CS"]
hatch  = ['', '']

# --- FDR & Jain's Index ---
results, stats_per_ED = extract_files_and_parameters([Directory_TTS, Directory_CS], labels)

plot_ack_bars([results["TTS"], results["CS"]], "FDR",            labels, 'Average FDR (%)',       hatch)
plot_ack_bars([results["TTS"], results["CS"]], "FDR_cul",        labels, 'Average FDR CUL (%)',   hatch)
plot_ack_bars([results["TTS"], results["CS"]], "FDR_UUL",        labels, 'Average FDR UUL (%)',   hatch)
plot_ack_bars([results["TTS"], results["CS"]], "Jains_Index",    labels, 'Average Jains Index',   hatch, 1)
plot_ack_bars([results["TTS"], results["CS"]], "Jains_Index_toa",labels, 'Average Jains Index',   hatch, 1)

plot_Jains_index_combined(results, "Jains_Index")

# --- ACK & Window Utilization ---
av_scenario_TTS, sf_data_all_TTS, sf_values_TTS = process_directory(Directory_TTS, desired_headers, desired_headers_UL, "Period", 3, 4)
av_scenario_CS,  sf_data_all_CS,  sf_values_CS  = process_directory(Directory_CS,  desired_headers, desired_headers_UL, "Period", 3, 4)

plot_ack_bars([av_scenario_TTS, av_scenario_CS], "ACK%",               labels, 'ACK (%)',                  hatch)
plot_ack_bars([av_scenario_TTS, av_scenario_CS], "Rx1%",               labels, 'Utilization Rx1 (%)',      hatch)
plot_ack_bars([av_scenario_TTS, av_scenario_CS], "Rx2%",               labels, 'Utilization Rx2 (%)',      hatch)
plot_ack_bars([av_scenario_TTS, av_scenario_CS], "Rx1_t%",             labels, 'Rx1 Percentage Total (%)', hatch)
plot_ack_bars([av_scenario_TTS, av_scenario_CS], "Rx2_t%",             labels, 'Rx2 Percentage Total (%)', hatch)
plot_ack_bars([av_scenario_TTS, av_scenario_CS], "HD%",                labels, 'Half Duplex Loss (%)',     hatch, 30)
plot_ack_bars([av_scenario_TTS, av_scenario_CS], "unusedTime_Rx1_sub1",labels, 'Unused Rx1 (%) Sub 1',    hatch)
plot_ack_bars([av_scenario_TTS, av_scenario_CS], "unusedTime_Rx1_sub2",labels, 'Unused Rx1 (%) Sub 2',    hatch)
plot_ack_bars([av_scenario_TTS, av_scenario_CS], "unusedTime_Rx2",     labels, 'Unused Rx2 (%)',           hatch)

# --- Lost Downlinks ---
TTS_lost_DL = extract_non_scheduled_downlinks(Directory_TTS, Directory_TTS, 0)
CS_lost_DL  = extract_non_scheduled_downlinks(Directory_CS,  Directory_CS,  "UDP")

lost_Causes = {"TTS": TTS_lost_DL, "CS": CS_lost_DL}
plot_lost_causes(lost_Causes, True)

plt.show()