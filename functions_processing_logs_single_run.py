import math
import sys
import pandas as pd
import os
import glob
import matplotlib
import re
import numpy as np
import seaborn as sns
import pprint
import json
from matplotlib.patches import Patch
import matplotlib.pyplot as plt

colors_TTS_CUS_OP = ['orange','seagreen','salmon']
desired_headers = ["senderId", "receiverID", "sendTime", "receivedTime", "SF", "SNR", "Ftype","Freq", "RX"]
desired_headers_UL = ["senderId", "receiverID", "sendTime", "receivedTime", "SF", "SNR", "Ftype", "Freq","received","code",""]
desired_headers_UL2 = ["senderId", "receiverID", "sendTime", "receivedTime", "SF", "SNR", "Ftype", "Freq","received","code"]
desired_headers2 = ["senderId", "receiverID", "sendTime", "receivedTime", "SF", "SNR", "Ftype", "Freq", "RX"]
headers_lost = ["HDsenderId", "HDreceiverID", "HDsendTime", "receivedTime", "SF", "SNR", "Ftype", "fcnt"]

def extract_gateway_and_end_devices(filename):
    gateway_match = re.search(r'gateway_(\d+)', filename)
    end_device_match = re.search(r'N_ED_(\d+)', filename)
    
    if gateway_match and end_device_match:
        gateway = int(gateway_match.group(1))
        end_devices = int(end_device_match.group(1))
        return gateway, end_devices
    return None, None
def add_calculated_columns_DL(dataframe,type):
    dataframe["sendTime"] = pd.to_numeric(dataframe["sendTime"], errors='coerce').fillna(0)
    dataframe["receivedTime"] = pd.to_numeric(dataframe["receivedTime"], errors='coerce').fillna(0)
    dataframe["RX"] = pd.to_numeric(dataframe["RX"], errors='coerce').fillna(0)
    dataframe["SF"] = pd.to_numeric(dataframe["SF"], errors='coerce').fillna(0)
    if type == 3:
        dataframe["sendTime"] /= 1e3  # Convert milliseconds to seconds
        dataframe["receivedTime"] /= 1e3  # Convert milliseconds to seconds
    else:
        dataframe["sendTime"] /= 1e3  # Convert nanoseconds to milliseconds
        dataframe["receivedTime"] /= 1e3  # Convert nanoseconds to milliseconds

    dataframe["ToA"] = dataframe["receivedTime"] - dataframe["sendTime"]
    dataframe["Blocked Time"] = dataframe["ToA"] * dataframe["RX"].map({1: 99, 2: 9}).fillna(0)


    return dataframe

def extract_table_with_headers(file_path, headers, type, with_duplicated=False, table_index=0):
    print(f"Reading file: {file_path}")
    with open(file_path, 'r') as file:
        lines = file.readlines()

    # Find all starting indices of tables by matching headers
    table_start_indices = [
        idx + 1 for idx, line in enumerate(lines) if all(header in line for header in headers)
    ]

    if not table_start_indices or table_index >= len(table_start_indices):
        raise ValueError(f"Table with specified headers not found or table_index {table_index} out of range.")

    start_idx = table_start_indices[table_index]
    end_idx = next(
        (idx for idx in range(start_idx, len(lines)) if lines[idx].strip() == "" or not lines[idx][0].isdigit()),
        len(lines)
    )

    # Extract table lines
    table_lines = [line.strip() for line in lines[start_idx:end_idx]]

    # Create DataFrame
    data = [row.split(',') for row in table_lines]
    df = pd.DataFrame(data, columns=headers)


    # Filter rows where Ftype == 4
    df = df[df['Ftype'] == str(type)]  # Assuming 'Ftype' is stored as a string in the file

    # Filter out repeated uplinks with the same sendTime
    if not with_duplicated and "received" in headers:
        # Prioritize rows with received == 1
        df = df.sort_values(by=["sendTime", "received"], ascending=[True, False])
        # Drop duplicates, keeping the first occurrence (which will have received == 1 if it exists)
        df = df.drop_duplicates(subset=["sendTime"])

    columns_to_drop = ["SNR"]
    df.drop(columns=[col for col in columns_to_drop if col in df], inplace=True)

    if "RX" in headers:
        df = add_calculated_columns_DL(df, type)

    return df

def _get_hd_lost_packets(uplinks_file, headers):
    """Return (hd_lost_set, hd_lost_count) for packets lost due to half-duplex.

    A packet is considered HD-lost when ALL received copies have code == '1'.
    """
    uplinks = extract_table_with_headers(uplinks_file, headers, 4, True)
    uplinks = uplinks[uplinks["Ftype"] == "4"]

    grouped = uplinks.groupby(["senderId", "sendTime"])
    hd_lost = grouped.filter(lambda g: (g["code"] == "1").all())

    hd_lost_set = set(zip(hd_lost["senderId"], hd_lost["sendTime"]))
    hd_lost_count = hd_lost.groupby(["senderId", "sendTime"]).ngroups
    total_uplinks = uplinks.shape[0]
    return hd_lost_set, hd_lost_count, total_uplinks


def _remove_hd_caused_downlinks(downlinks, hd_lost_set):
    """Filter out downlinks that were triggered by HD-lost uplinks.

    The logs can record the same HD loss with two different time offsets
    (1000 ms or 2000 ms), so both are checked.
    """
    def is_hd_caused(row):
        time_match = (
            row["sendTime"] - 1000 in hd_lost_set or
            row["sendTime"] - 2000 in hd_lost_set
        )
        return row["receiverID"] in hd_lost_set and time_match

    return downlinks[~downlinks.apply(is_hd_caused, axis=1).astype(bool)]


def _count_failures_by_rx(downlinks, failure_type):
    """Count rows matching failure_type split by receive window (RX1 / RX2)."""
    subset = downlinks[downlinks["Failure Type"] == failure_type]
    return {
        "1": subset[subset["RX"] == 1].shape[0],
        "2": subset[subset["RX"] == 2].shape[0],
    }


def extract_non_scheduled_downlinks(file_path, file_path2, headers, type_file):
    result_files  = glob.glob(os.path.join(file_path2, "*_results.csv"))
    uplinks_files = glob.glob(os.path.join(file_path,  "*_uplinks.csv"))

    print(f"Processing files in: {file_path}")
    print(f"Found {len(result_files)} result files and {len(uplinks_files)} uplinks files.")

    file_set   = result_files if type_file == 0 else uplinks_files
    statistics = {}
    headers_DL = desired_headers
    headers_DL.append("")
    for file in file_set:
        gw, ed, percentage = extract_gateway_and_ed_percentage(file)
        if None in (gw, ed, percentage):
            print(f"Skipping {file} (could not parse gw / ed / percentage)")
            continue

        print(f"Processing: {file} | GW={gw}, ED={ed}, %={percentage}")

        # --- Half-duplex loss analysis ---
        uplinks_file = find_matching_uplinks_file(uplinks_files, gw, ed, percentage)
        hd_lost_set, hd_lost_count, total_uplinks = _get_hd_lost_packets(uplinks_file, headers)
        print(f"  HD-lost packets: {hd_lost_count}")

        # --- Conflict / blocked counts ---
        if type_file == 0:
            conflict_count, blocked_count = process_results_file(file)

        elif type_file == 1:
            downlinks = extract_table_with_headers(file, headers_DL, 3, True, 1)
            downlinks.rename(columns={downlinks.columns[8]: "Failure Type"}, inplace=True)
            downlinks["Failure Type"] = downlinks["Failure Type"].map({"b": "Blocked", "c": "Conflict"})

            downlinks = _remove_hd_caused_downlinks(downlinks, hd_lost_set)

            conflict_count = _count_failures_by_rx(downlinks, "Conflict")
            blocked_count  = _count_failures_by_rx(downlinks, "Blocked")

        statistics[(gw, ed, percentage)] = {
            "conflict": {k: v / gw for k, v in conflict_count.items()},
            "blocked":  {k: v / gw for k, v in blocked_count.items()},
            "hd_lost":  hd_lost_count / gw,
        }

    return statistics
def computation_FDR_UPLINKS(optimal, tts, custom_tts):
    # Get all files in the directory that end with 'GlobalPerf.csv'
    global_perf_files = glob.glob(os.path.join(tts, "*_GlobalPerf.csv"))
    print(f"Found {len(global_perf_files)} files ending with 'GlobalPerf.csv':")
    FDR_EXPERIMENTS = {}
    FDR_EXPERIMENTS_CONF = {}
    FDR_EXPERIMENTS_UNCONF = {}

    for file in global_perf_files:
        for global_perf_file in global_perf_files:
            # Extract gateway, end device, percentage, and seed from the file name
            gw_match = re.search(r'_gateway_(\d+)_', global_perf_file)
            ed_match = re.search(r'log_N_ED_(\d+)_', global_perf_file)
            percentage_match = re.search(r'percentage_(\d+)_', global_perf_file)
            seed_match = re.search(r'seed_(\d+)_', global_perf_file)

            if gw_match and ed_match and percentage_match and seed_match:
                gw = int(gw_match.group(1))
                ed = int(ed_match.group(1))
                percentage = int(percentage_match.group(1))
                seed = int(seed_match.group(1))

                # Extract the corresponding GlobalPerf.csv file from the custom_tts directory
                template_headers = [
                    "Time", "ID", "Address", "FType", "X", "Y", "Z", "GWDist", "Data Rate", 
                    "Tx Power", "Tx", "CTx", "UCTx", "Rx", "CRx", "UCRx", "HD-CUL", "HD-UUL", 
                    "TXdl", "Rxdl", "Rx1", "Rx2", "Rx1_s", "Rx2_s", "Rx1_dc", "Rx2_dc", 
                    "MaxOT", "OT"
                ]
                
                template_tts = f"*_gateway_{gw}_seed_{seed}_percentage_{percentage}_log_N_ED_{ed}_GlobalPerf.csv"
                template_custom = f"*_gateway_{gw}_percentage_{percentage}_log_N_ED_{ed}_log_downlinks_{seed}_uplinks.csv"
                template_custom2 = f"*_gateway_{gw}_seed_{seed}_percentage_{percentage}_log_N_ED_{ed}_EndDevicesOut.csv"
                custom_tts_file = glob.glob(os.path.join(custom_tts, template_tts))[0]
                optimal_uplinks_file = glob.glob(os.path.join(optimal, template_custom))[0]

                custom_uplinks_file = glob.glob(os.path.join(custom_tts, template_custom2))[0]
                tts_uplinks_file = glob.glob(os.path.join(tts, template_custom2))[0]

                if os.path.exists(optimal_uplinks_file) and os.path.exists(custom_tts_file):
                    # Read the table from custom_tts_file
                    custom_tts_df = pd.read_csv(custom_tts_file, delimiter=',', usecols=["Time", "Sent", "Received", "Interfered", "No Receivers", "Busy", "Under"], skipinitialspace=True)

                    # Read the table from global_perf_file
                    global_perf_df = pd.read_csv(global_perf_file, delimiter=',', usecols=["Time", "Sent", "Received", "Interfered", "No Receivers", "Busy", "Under"], skipinitialspace=True)

                    custom_end_device = pd.read_csv(custom_uplinks_file, delimiter=',', usecols=template_headers, skipinitialspace=True)
                    TTS_end_device = pd.read_csv(tts_uplinks_file, delimiter=',', usecols=template_headers, skipinitialspace=True)


                    # Extract the values of Sent, Received, and Busy from both files
                    custom_tts_sent = custom_tts_df["Sent"].sum()
                    custom_tts_received = custom_tts_df["Received"].sum()
                    custom_tts_busy = custom_tts_df["Busy"].sum()

                    total_CONF_sent = TTS_end_device["CTx"].sum()
                    total_UNCONF_sent = TTS_end_device["UCTx"].sum()

                    global_perf_sent = TTS_end_device["Tx"].sum()
                    global_perf_received = global_perf_df["Received"].sum()
                    global_perf_busy = global_perf_df["Busy"].sum()

                    print(f"Custom TTS - Sent: {custom_tts_sent}, Received: {custom_tts_received}, Busy: {custom_tts_busy}")
                    print(f"Normal TTS - Sent: {global_perf_sent}, Received: {global_perf_received}, Busy: {global_perf_busy}")
                    optimal_uplinks_received = 0
                    # Process the optimal uplinks file
                    if os.path.exists(optimal_uplinks_file):
                        optimal_uplinks_df_conf = extract_table_with_headers(optimal_uplinks_file, desired_headers_UL2, 4)
                        optimal_uplinks_df_unconf = extract_table_with_headers(optimal_uplinks_file, desired_headers_UL2, 2)
                        optimal_downlinks_df = extract_table_with_headers(optimal_uplinks_file, desired_headers2, 3)
                        optimal_uplinks_received_conf = optimal_downlinks_df.shape[0]
                        optimal_uplinks_received_unconf = optimal_uplinks_df_unconf[optimal_uplinks_df_unconf["received"] == "1"].shape[0]
                        optimal_uplinks_received = (optimal_uplinks_received_conf + optimal_uplinks_received_unconf)
                        print(f"Optimal - Sent: {global_perf_sent}, Received: {optimal_uplinks_received}")
                    else:
                        print(f"Optimal uplinks file not found: {optimal_uplinks_file}")

                    FDR_NO_DL = (custom_tts_received+custom_tts_busy) / global_perf_sent * 100 if global_perf_sent > 0 else 0
                    FDR_CUSTOM = (custom_end_device["TXdl"].sum()  + custom_end_device["UCRx"].sum()) / global_perf_sent * 100 if global_perf_sent > 0 else 0
                    FDR_TTS = (TTS_end_device["TXdl"].sum() + TTS_end_device["UCRx"].sum()) / global_perf_sent * 100 if global_perf_sent > 0 else 0
                    FDR_OPTIMAL = (optimal_uplinks_received) / global_perf_sent * 100 if global_perf_sent > 0 else 0

                    FDR_CONF_CUSTOM = custom_end_device["TXdl"].sum()/ total_CONF_sent * 100 if total_CONF_sent > 0 else 0
                    FDR_CONF_TTS = TTS_end_device["TXdl"].sum() / total_CONF_sent * 100 if total_CONF_sent > 0 else 0 
                    FDR_CONF_OPTIMAL= optimal_uplinks_received_conf/ total_CONF_sent * 100 if total_CONF_sent > 0 else 0

                    FDR_UNCONF_CUSTOM = custom_end_device["UCRx"].sum() / total_UNCONF_sent * 100 if total_UNCONF_sent  > 0 else 0 
                    FDR_UNCONF_TTS =  TTS_end_device["UCRx"].sum()/ total_UNCONF_sent * 100 if total_UNCONF_sent  > 0 else 0
                    FDR_UNCONF_OPTIMAL = optimal_uplinks_df_unconf[optimal_uplinks_df_unconf["received"] == "1"].shape[0] / total_UNCONF_sent * 100 if total_UNCONF_sent  > 0 else 0

                    FDR_EXPERIMENTS[(gw, ed, percentage,seed)] = {
                        "FDR_NO_DL": FDR_NO_DL,
                        "FDR_CUSTOM": FDR_CUSTOM,
                        "FDR_TTS": FDR_TTS,
                        "FDR_OPTIMAL": FDR_OPTIMAL
                    }

                    FDR_EXPERIMENTS_CONF[(gw, ed, percentage,seed)] = {
                        "FDR_NO_DL": FDR_NO_DL,
                        "FDR_CUSTOM": FDR_CONF_CUSTOM,
                        "FDR_TTS": FDR_CONF_TTS,
                        "FDR_OPTIMAL": FDR_CONF_OPTIMAL
                    }
                    FDR_EXPERIMENTS_UNCONF[(gw, ed, percentage,seed)] = {
                        "FDR_NO_DL": FDR_NO_DL,
                        "FDR_CUSTOM": FDR_UNCONF_CUSTOM,
                        "FDR_TTS": FDR_UNCONF_TTS,
                        "FDR_OPTIMAL": FDR_UNCONF_OPTIMAL
                    }
                else:
                    print(f"Optimal uplinks file not found for gw: {gw}, ed: {ed}, percentage: {percentage}, seed: {seed}")

    FDR_EXPERIMENTS = dict(sorted(FDR_EXPERIMENTS.items(), key=lambda x: (x[0][1], x[0][0])))
    FDR_EXPERIMENTS_CONF = dict(sorted(FDR_EXPERIMENTS_CONF.items(), key=lambda x: (x[0][1], x[0][0])))
    FDR_EXPERIMENTS_UNCONF = dict(sorted(FDR_EXPERIMENTS_UNCONF.items(), key=lambda x: (x[0][1], x[0][0])))
    return FDR_EXPERIMENTS, FDR_EXPERIMENTS_CONF, FDR_EXPERIMENTS_UNCONF


def extract_gateway_and_ed_percentage(file):
    gw_match = re.search(r'_gateway_(\d+)_', file)
    ed_match = re.search(r'log_N_ED_(\d+)_', file)
    percentage_match = re.search(r'percentage_(\d+)_', file)
    if gw_match and ed_match and percentage_match:
        return int(gw_match.group(1)), int(ed_match.group(1)), int(percentage_match.group(1))
    return None, None, None


def find_matching_uplinks_file(uplinks_files, gw, ed, percentage):
    for uplink in uplinks_files:
        uplink_gw, uplink_ed, uplink_percentage = extract_gateway_and_ed_percentage(uplink)
        if uplink_gw == gw and uplink_ed == ed and uplink_percentage == percentage:
            return uplink
    return None


def process_results_file(file_path, headers=["timestamp","results"]):

    print(file_path)
    with open(file_path, 'r') as file:
        lines = file.readlines()
        # Skip empty lines and strip whitespace
        table_lines = [line.strip() for line in lines if line.strip()]

        # Split the lines into two columns: timestamp and results using a comma as the delimiter
        data = [row.split(',', 1) for row in table_lines]

    # Create a DataFrame without specifying headers
    df = pd.DataFrame(data)
    df.columns = ["timestamp", "results"]
    
    conflict_count = {"1": 0, "2": 0}
    blocked_count = {"1": 0, "2": 0}
    print(df)
    for index, row in df.iterrows():
        print(row["timestamp"], index)
        # Clean and parse the JSON string in the 'results' column
        if index > 0:
            cleaned_results = row["results"].strip().replace('""', '"').replace('"{', '{').replace('}"', '}').replace(',""', ',').replace('""}', '}').replace('"{', '{"').replace('}"', '"}')
            results = json.loads(cleaned_results)
            for _, windows in results.items():
                for window, status in windows.items():
                    if status == "conflict":
                        conflict_count[window] += 1
                    elif status == "blocked":
                        blocked_count[window] += 1

    return conflict_count, blocked_count
        
def process_Tables(tabUL,tabDL):
    ED_stats = {}
    SF_stats = {}
    for index, row in tabUL.iterrows():
        sender_id = row['senderId']
        if sender_id not in ED_stats:
            SF = row['SF']
            ED_stats[sender_id] = {"SF": SF, "RX": 0,"ACK":0,"HD":0,"Rx1":0,"Rx2":0, "ToA": 0, "Blocked_Rx1": 0, "Blocked_Rx2": 0}
            # Get all lines with the same sender_id in tabUL
            sender_rows = tabUL[tabUL['senderId'] == sender_id]
            lost_due_HD = sender_rows[sender_rows['received'] == "0"]
            # Get all lines in tabDL with receiverID equal to sender_id
            receiver_rows = tabDL[tabDL['receiverID'] == sender_id]
            Rx1_Tab = receiver_rows[receiver_rows['RX'] == 1]
            Rx2_Tab = receiver_rows[receiver_rows['RX'] == 2]
            ED_stats[sender_id]["HD"] = len(lost_due_HD)
            ED_stats[sender_id]["RX"] = len(sender_rows)
            ED_stats[sender_id]["HD"] = len(sender_rows)
            ED_stats[sender_id]["Rx1"] = len(Rx1_Tab)
            ED_stats[sender_id]["Rx2"] = len(Rx2_Tab)
            ED_stats[sender_id]["ACK"] = len(receiver_rows)
            ED_stats[sender_id]["ToA"] = receiver_rows["ToA"].sum()
            ED_stats[sender_id]["Blocked_Rx1"] = Rx1_Tab["Blocked Time"].sum()
            ED_stats[sender_id]["Blocked_Rx2"] = Rx2_Tab["Blocked Time"].sum()
            if SF not in SF_stats:
                SF_stats[SF] = {"count":0,"Rx":0,"ACK":0,"HD":0,"Rx1":0,"Rx2":0, "Blocked_Rx1": 0, "Blocked_Rx2": 0}            
            SF_stats[SF]["count"] += len(sender_rows)
            SF_stats[SF]["Rx"] += len(receiver_rows)
            SF_stats[SF]["HD"] += len(lost_due_HD)
            SF_stats[SF]["Rx1"] += len(Rx1_Tab)
            SF_stats[SF]["Rx2"] += len(Rx2_Tab)
            SF_stats[SF]["ACK"] += len(receiver_rows)
            SF_stats[SF]["Blocked_Rx1"] += Rx1_Tab["Blocked Time"].sum()
            SF_stats[SF]["Blocked_Rx2"] += Rx2_Tab["Blocked Time"].sum()

    #print(ED_stats)
    SF_stats = dict(sorted(SF_stats.items(), key=lambda item: int(item[0])))
    return ED_stats, SF_stats


def plot_matrices_vertical(sf_values, gw_ed_combinations, ack_matrix, rx_matrix_1, rx_matrix_2, blocked_rx1_matrix, blocked_rx2_matrix, Title, include_colorbar=True, include_y_axis=True):
    # Adjust figure size to prevent label overlap
    print("Plotting matrices vertically")
    print("ACK Matrix: ", ack_matrix)
    fig1, axes1 = plt.subplots(3, 1, figsize=(4, 8), gridspec_kw={'hspace': 0.2}, sharex=True, facecolor='none')  # Reduced hspace for less vertical difference

    cbar_ax = None
    if include_colorbar:
        cbar_ax = fig1.add_axes([.86, .3, .02, .4])  # Adjusted position and size for the colorbar
        cbar_ax.tick_params(labelsize=8)  # Set smaller font size for colorbar numbers

    sns.heatmap(ack_matrix.T, ax=axes1[0], xticklabels=gw_ed_combinations, yticklabels=sf_values if include_y_axis else [], cmap="coolwarm", annot=True, vmin=0, vmax=100, annot_kws={"size": 8}, fmt=".0f", cbar=False, linewidths=0.5, linecolor='gray')
    axes1[0].set_title('ACK%', fontsize=12)
    if include_y_axis:
        axes1[0].set_ylabel('SF', fontsize=10, rotation=0, labelpad=40, ha='center', va='center')
    axes1[0].tick_params(axis='both', which='major', labelsize=8)

    sns.heatmap(rx_matrix_1.T, ax=axes1[1], xticklabels=gw_ed_combinations, yticklabels=sf_values if include_y_axis else [], cmap="coolwarm", annot=True, vmin=0, vmax=100, annot_kws={"size": 8}, fmt=".0f", cbar=False, linewidths=0.5, linecolor='gray')
    axes1[1].set_title('Rx1%', fontsize=12)
    if include_y_axis:
        axes1[1].set_ylabel('SF', fontsize=10, rotation=0, labelpad=40, ha='center', va='center')
    axes1[1].tick_params(axis='both', which='major', labelsize=8)

    sns.heatmap(rx_matrix_2.T, ax=axes1[2], xticklabels=gw_ed_combinations, yticklabels=sf_values if include_y_axis else [], cmap="coolwarm", annot=True, vmin=0, vmax=100, annot_kws={"size": 8}, fmt=".0f", cbar=include_colorbar, cbar_ax=cbar_ax if include_colorbar else None, linewidths=0.5, linecolor='gray')
    axes1[2].set_title('Rx2%', fontsize=12)
    axes1[2].set_xticklabels(gw_ed_combinations, rotation=45, ha='right', fontsize=8)

    if include_y_axis:
        axes1[2].set_ylabel('SF', fontsize=10, rotation=0, labelpad=40, ha='center', va='center')
    axes1[2].set_xlabel('(gw,ed)', fontsize=10)
    axes1[2].tick_params(axis='both', which='major', labelsize=8)

    # Adjust y-axis label position to be below the last tick
    for ax in axes1:
        if include_y_axis:
            ax.yaxis.set_label_coords(-0.05, -0.1)  # Adjusted position for the y-axis label

    plt.tight_layout(rect=[0, 0, 0.95, 1] if include_colorbar else [0, 0, 1, 1])  # Adjusted layout to fit the colorbar

    fig1.subplots_adjust(
        top=0.9,
        bottom=0.1,
        left=0.07,  # Adjusted to provide space for the SF label
        right=0.93,
        hspace=0.15,  # Reduced hspace for less vertical difference
        wspace=0.2
    )
    fig1.savefig(f'Figures/ACK_and_RX_Percentages_{Title.replace(" ", "_")}_vertical.pdf')


def plot_matrices_blocked(sf_values, gw_ed_combinations, ack_matrix, rx_matrix_1, rx_matrix_2, blocked_rx1_matrix, blocked_rx2_matrix, Title,scaler=1):
    fig2, axes2 = plt.subplots(1, 2, figsize=(8, 3), gridspec_kw={'wspace': 0.1, 'width_ratios': [1, 1]}, facecolor='none')
    print(blocked_rx1_matrix)
    blocked_rx1_matrix_s = blocked_rx1_matrix / scaler
    blocked_rx2_matrix_s = blocked_rx2_matrix / scaler
    print(blocked_rx1_matrix_s)
    cbar_ax = fig2.add_axes([.82, .4, .02, 0.5])  # Adjusted to align the colorbar with the height of the heatmaps

    sns.heatmap(blocked_rx1_matrix_s.T, ax=axes2[0], yticklabels=sf_values, xticklabels=gw_ed_combinations, cmap="viridis", vmin=0, vmax=3000, annot=False, cbar=False)
    axes2[0].set_title('Blocked Rx1(s)', fontsize=12)
    axes2[0].set_xlabel('(gw,ed)', fontsize=12)
    axes2[0].set_ylabel('SF', fontsize=12)
    axes2[0].set_xticklabels(gw_ed_combinations, rotation=45, ha='right', fontsize=8)
    axes2[0].tick_params(axis='both', which='major', labelsize=8)

    sns.heatmap(blocked_rx2_matrix_s.T, ax=axes2[1], yticklabels=[], xticklabels=gw_ed_combinations, cmap="viridis", vmin=0, vmax=3000, annot=False, cbar=True, cbar_ax=cbar_ax)
    axes2[1].set_title('Blocked Rx2(s)', fontsize=12)
    axes2[1].set_xlabel('(gw,ed)', fontsize=12)
    #axes2[1].set_ylabel('SF', fontsize=10)
    axes2[1].set_xticklabels(gw_ed_combinations, rotation=45, ha='right', fontsize=8)
    axes2[1].tick_params(axis='both', which='major', labelsize=8)

    fig2.subplots_adjust(
        top=0.9,
        bottom=0.4,
        left=0.1,
        right=0.8
    )

    plt.tight_layout(rect=[0, 0, 0.9, 0.85])  # Adjust layout to account for the colorbar
    fig2.savefig(f'Figures/Blocked_RX_Times_modify_{Title.replace(" ", "_")}.pdf')

def plot_matrices(sf_values, gw_ed_combinations, ack_matrix, rx_matrix_1, rx_matrix_2, blocked_rx1_matrix, blocked_rx2_matrix, Title):
    # Plot for ack_matrix and rx_matrix
    fig1, axes1 = plt.subplots(1, 3, figsize=(14, 4), gridspec_kw={'wspace': 0.3})
    
    # Create a colorbar axis outside the subplots
    cbar_ax = fig1.add_axes([0.92, 0.15, 0.02, 0.7])

    sns.heatmap(ack_matrix.T, ax=axes1[0], xticklabels=gw_ed_combinations, yticklabels=sf_values, cmap="coolwarm", annot=True, vmin=0, vmax=100, annot_kws={"size": 7}, fmt=".0f", cbar=False)
    axes1[0].set_title('ACK%', fontsize=12)
    axes1[0].set_xlabel('(gw,ed)', fontsize=10)
    axes1[0].set_ylabel('SF', fontsize=10)
    axes1[0].set_xticklabels(gw_ed_combinations, rotation=45, ha='right', fontsize=8)
    axes1[0].set_yticklabels(sf_values, fontsize=8)
    axes1[0].tick_params(axis='both', which='major', labelsize=8)

    sns.heatmap(rx_matrix_1.T, ax=axes1[1], xticklabels=gw_ed_combinations, yticklabels=[], cmap="coolwarm", annot=True, vmin=0, vmax=100, annot_kws={"size": 7}, fmt=".0f", cbar=False)
    axes1[1].set_title('Rx1%', fontsize=12)
    axes1[1].set_xlabel('(gw,ed)', fontsize=10)
    axes1[1].set_xticklabels(gw_ed_combinations, rotation=45, ha='right', fontsize=8)
    axes1[1].tick_params(axis='both', which='major', labelsize=8)

    sns.heatmap(rx_matrix_2.T, ax=axes1[2], xticklabels=gw_ed_combinations, yticklabels=[], cmap="coolwarm", annot=True, vmin=0, vmax=100, annot_kws={"size": 7}, fmt=".0f", cbar=True, cbar_ax=cbar_ax)
    axes1[2].set_title('Rx2%', fontsize=12)
    axes1[2].set_xlabel('(gw,ed)', fontsize=10)
    axes1[2].set_xticklabels(gw_ed_combinations, rotation=45, ha='right', fontsize=8)
    axes1[2].tick_params(axis='both', which='major', labelsize=8)

    plt.tight_layout()
    fig1.subplots_adjust(right=0.9, bottom=0.25)

    fig1.savefig(f'Figures/ACK_and_RX_Percentages_{Title.replace(" ", "_")}.pdf', bbox_inches='tight')

def get_files(directory):
    # Get all files in the specified directory
    files = glob.glob(os.path.join(directory, "*_uplinks.csv"))

    return files

def plot_ack_percentages(ack_percentages_ch, ack_percentages_c, ack_percentages_c_cs):
    # Extract data for plotting
    labels = []
    ch_data = {"Rx1%": [], "Rx2%": [], "No_ACK%": []}
    c_data = {"Rx1%": [], "Rx2%": [], "No_ACK%": []}
    c_cs_data = {"Rx1%": [], "Rx2%": [], "No_ACK%": []}
    
    for file in ack_percentages_ch:
        gw, ed = extract_gateway_and_end_devices(file)
        if gw:
            label = f"GW{gw}_ED{ed}"
            labels.append(label)
            ch_data["Rx1%"].append(ack_percentages_ch[file]["Rx1%"])
            ch_data["Rx2%"].append(ack_percentages_ch[file]["Rx2%"])
            ch_data["No_ACK%"].append(ack_percentages_ch[file]["No_ACK%"])
    
    for file in ack_percentages_c:
        gw, ed = extract_gateway_and_end_devices(file)
        if gw:
            label = f"GW{gw}_ED{ed}"
            if label not in labels:
                labels.append(label)
                ch_data["Rx1%"].append(0)
                ch_data["Rx2%"].append(0)
                ch_data["No_ACK%"].append(0)
            c_data["Rx1%"].append(ack_percentages_c[file]["Rx1%"])
            c_data["Rx2%"].append(ack_percentages_c[file]["Rx2%"])
            c_data["No_ACK%"].append(ack_percentages_c[file]["No_ACK%"])
    
    for file in ack_percentages_c_cs:
        gw, ed = extract_gateway_and_end_devices(file)
        if gw:
            label = f"GW{gw}_ED{ed}"
            if label not in labels:
                labels.append(label)
                ch_data["Rx1%"].append(0)
                ch_data["Rx2%"].append(0)
                ch_data["No_ACK%"].append(0)
                c_data["Rx1%"].append(0)
                c_data["Rx2%"].append(0)
                c_data["No_ACK%"].append(0)
            c_cs_data["Rx1%"].append(ack_percentages_c_cs[file]["Rx1%"])
            c_cs_data["Rx2%"].append(ack_percentages_c_cs[file]["Rx2%"])
            c_cs_data["No_ACK%"].append(ack_percentages_c_cs[file]["No_ACK%"])
    
    x = np.arange(len(labels))  # the label locations
   
    width = 0.2  # the width of the bars
    spacing = width / 4 # spacing between bars of the same file

    fig, ax = plt.subplots(figsize=(10, 5))

    # Plot Christelle's data
    ax.bar(x - width - spacing, ch_data["Rx1%"], width, color='royalblue', hatch='/')
    ax.bar(x - width - spacing, ch_data["Rx2%"], width, color='seagreen', bottom=np.array(ch_data["Rx1%"]), hatch='/')
    ax.bar(x - width - spacing, ch_data["No_ACK%"], width, color='salmon', bottom=np.array(ch_data["Rx2%"]) + np.array(ch_data["Rx1%"]), hatch='/', label='Optimal')

    # Plot Carlos's data
    ax.bar(x, c_data["Rx1%"], width, color='royalblue', hatch='|')
    ax.bar(x, c_data["Rx2%"], width, color='seagreen', bottom=np.array(c_data["Rx1%"]), hatch='|')
    ax.bar(x, c_data["No_ACK%"], width, color='salmon', bottom=np.array(c_data["Rx2%"]) + np.array(c_data["Rx1%"]), hatch='|', label='TTS')

    # Plot Carlos_cs's data
    ax.bar(x + width + spacing, c_cs_data["Rx1%"], width, color='royalblue', hatch='\\')
    ax.bar(x + width + spacing, c_cs_data["Rx2%"], width, color='seagreen', bottom=np.array(c_cs_data["Rx1%"]), hatch='\\')
    ax.bar(x + width + spacing, c_cs_data["No_ACK%"], width, color='salmon', bottom=np.array(c_cs_data["Rx2%"]) + np.array(c_cs_data["Rx1%"]), hatch='\\', label='CS')

    # Add some text for labels, title and custom x-axis tick labels, etc.
    ax.set_xlabel('GW and ED Combinations')
    ax.set_ylabel('Percentages')
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    
    legend_labels = ['Rx1%', 'Rx2%', 'No_ACK%']

    handles = [ax.bar(0, 0.2, color=colors) for colors in ['royalblue', 'seagreen', 'salmon']]
    if legend_labels:
        leg0 = ax.legend(handles, legend_labels, bbox_to_anchor=(0.5, 1.15), loc='upper left', ncol=3)

        # Add custom hatch legend using inexistent bars
        handles = [ax.bar(0, 0, color='w', hatch=hatches) for hatches in ['/', '|', '\\']]
        labels_actualizado = ['Optimal', 'TTS', 'CS']
        leg1 = ax.legend(handles, labels_actualizado, bbox_to_anchor=(0.5, 1.15), loc='upper right', ncol=3)
    ax.add_artist(leg0)
    ax.add_artist(leg1)
    ax.grid(True)
    ax.set_axisbelow(True)

    fig.tight_layout(rect=[0, 0, 1, 0.9])  # Adjust the bottom and top of the plot
def TimeOnAir(spreading_factor,payload_size_bytes=12, bandwidth_khz=125, coding_rate=1, preamble_length=8, explicit_header=True, crc_enabled=True, low_dr_optimize='auto'):
    t_sym = (2 ** spreading_factor) / (bandwidth_khz * 1000) * 1000
    t_preamble = (preamble_length + 4.25) * t_sym
    h = 0 if explicit_header else 1
    if low_dr_optimize == 'auto':
        de = 1 if (bandwidth_khz == 125 and spreading_factor >= 11) else 0
    else:
        de = 1 if low_dr_optimize else 0
    cr = coding_rate + 4
    payload_symb_nb = 8 + max(
        math.ceil(
            (8 * payload_size_bytes - 4 * spreading_factor + 28 + (16 if crc_enabled else 0) - 20 * h) /
            (4 * (spreading_factor - 2 * de))
        ) * cr,
        0
    )
    t_payload = payload_symb_nb * t_sym
    return t_preamble + t_payload
    
def process_directory(directory, desired_headers, desired_headers_UL,typeDL=3,typeUL=4):
    files = get_files(directory)

    sf_values = None
    gw_ed_combinations = []
    ack_matrix = None
    rx_matrix_1 = None
    rx_matrix_2 = None
    blocked_rx1_matrix = None
    blocked_rx2_matrix = None
    sf_data_all = {}
    for file_idx, i in enumerate(get_files(directory)):
        gw, ed = extract_gateway_and_end_devices(i)
        print(i)
        tabDL = extract_table_with_headers(i, desired_headers, typeDL)
        tabUL = extract_table_with_headers(i, desired_headers_UL, typeUL)
        if "received" not in desired_headers_UL:
            tabUL["received"] = "1"
            tabUL_HD = extract_table_with_headers(i, headers_lost, 2)
            tabUL_HD["received"] = "0"
            tabUL_HD.columns = tabUL.columns
            tabUL.loc[tabUL["sendTime"].isin(tabUL_HD["sendTime"]), "received"] = "0"
            
        ed_data, sf_data = process_Tables(tabUL, tabDL)
        sf_data_all[i] = sf_data
        if sf_values is None:
            sf_values = list(sf_data.keys())
            ack_matrix = np.zeros((len(files), len(sf_values)))
            rx_matrix_1 = np.zeros((len(files), len(sf_values)))
            rx_matrix_2 = np.zeros((len(files), len(sf_values)))

            blocked_rx1_matrix = np.zeros((len(files), len(sf_values)))
            blocked_rx2_matrix = np.zeros((len(files), len(sf_values)))

        gw_ed_combinations.append((gw, ed))

        # Populate matrices
        for sf_idx, sf in enumerate(sf_values):
            ack_matrix[file_idx, sf_idx] = round(100 * sf_data[sf]["ACK"] / sf_data[sf]["count"], 2) if sf_data[sf]["count"] > 0 else 0
            rx_matrix_1[file_idx, sf_idx] = round(100 * sf_data[sf]["Rx1"] / sf_data[sf]["ACK"], 2) if sf_data[sf]["ACK"] > 0 else 0
            rx_matrix_2[file_idx, sf_idx] = round(100 * sf_data[sf]["Rx2"] / sf_data[sf]["ACK"], 2) if sf_data[sf]["ACK"] > 0 else 0
            blocked_rx1_matrix[file_idx, sf_idx] = sf_data[sf]["Blocked_Rx1"]
            blocked_rx2_matrix[file_idx, sf_idx] = sf_data[sf]["Blocked_Rx2"]

    # Sort gw_ed_combinations and matrices
    sorted_indices = sorted(range(len(gw_ed_combinations)), key=lambda idx: (gw_ed_combinations[idx][1], gw_ed_combinations[idx][0]))
    sorted_indices = sorted(range(len(gw_ed_combinations)), key=lambda idx: (gw_ed_combinations[idx][1], gw_ed_combinations[idx][0]))
    sorted_files = sorted(sf_data_all.keys(), key=lambda file: extract_gateway_and_end_devices(file))

    sf_data_all = {file: sf_data_all[file] for file in sorted_files}
    
    gw_ed_combinations = [gw_ed_combinations[idx] for idx in sorted_indices]
    ack_matrix = ack_matrix[sorted_indices, :]
    rx_matrix_1 = rx_matrix_1[sorted_indices, :]
    rx_matrix_2 = rx_matrix_2[sorted_indices, :]
    blocked_rx1_matrix = blocked_rx1_matrix[sorted_indices, :]
    blocked_rx2_matrix = blocked_rx2_matrix[sorted_indices, :]

    return sf_data_all,sf_values, gw_ed_combinations, ack_matrix, rx_matrix_1,rx_matrix_2, blocked_rx1_matrix, blocked_rx2_matrix

def calculate_ack_percentages(sf_data_all):
    ack_percentages = {}

    for file, sf_data in sf_data_all.items():
        ack_percentages[file] = {"count": 0, "ACK": 0,"HD":0, "Rx1": 0, "Rx2": 0, "No_ACK": 0, "dcRx1": 0, "dcRx2": 0}
        
        for sf, data in sf_data.items():
            total_count = data["count"]

            ack_percentages[file]["count"] += total_count
            ack_percentages[file]["ACK"] += data["ACK"]
            ack_percentages[file]["dcRx1"] += data["Rx1"]*TimeOnAir(int(sf))/1000
            ack_percentages[file]["dcRx2"] += data["Rx2"]*TimeOnAir(int(sf))/1000
            ack_percentages[file]["HD"] += data["HD"]
            ack_percentages[file]["Rx1"] += data["Rx1"]
            ack_percentages[file]["Rx2"] += data["Rx2"]
            ack_percentages[file]["No_ACK"] += total_count - data["ACK"]
        ack_percentages[file]["HD%"] = ack_percentages[file]["HD"] / ack_percentages[file]["count"] * 100 if ack_percentages[file]["count"] > 0 else 0
        ack_percentages[file]["ACK%"] = ack_percentages[file]["ACK"] / ack_percentages[file]["count"] * 100 if ack_percentages[file]["count"] > 0 else 0
        ack_percentages[file]["Rx1%"] = ack_percentages[file]["Rx1"] / ack_percentages[file]["ACK"] * 100 if ack_percentages[file]["ACK"] > 0 else 0
        ack_percentages[file]["Rx2%"] = ack_percentages[file]["Rx2"] / ack_percentages[file]["ACK"] * 100 if ack_percentages[file]["ACK"] > 0 else 0
        ack_percentages[file]["No_ACK%"] = ack_percentages[file]["No_ACK"] / ack_percentages[file]["count"] * 100 if ack_percentages[file]["count"] > 0 else 0
        gw, _ = extract_gateway_and_end_devices(file)
        if gw and gw > 0:
            ack_percentages[file]["dcRx1"] /= 36*gw/100
            ack_percentages[file]["dcRx2"] /= 360*gw/100

    # Sort ack_percentages by number of gateways and end devices
    sorted_ack_percentages = {}
    sorted_files = sorted(ack_percentages.keys(), key=lambda file: (extract_gateway_and_end_devices(file)[1], extract_gateway_and_end_devices(file)[0]))

    for file in sorted_files:
        sorted_ack_percentages[file] = ack_percentages[file]

    ack_percentages = sorted_ack_percentages
    return ack_percentages

def create_ack_heatmap_matrices(ack_percentages):
    # Extract unique gateway and end device numbers
    gw_numbers = sorted(set(extract_gateway_and_end_devices(file)[0] for file in ack_percentages))
    ed_numbers = sorted(set(extract_gateway_and_end_devices(file)[1] for file in ack_percentages))

    # Initialize matrices
    ack_matrix = np.zeros((len(gw_numbers), len(ed_numbers)))
    rx1_matrix = np.zeros((len(gw_numbers), len(ed_numbers)))
    rx2_matrix = np.zeros((len(gw_numbers), len(ed_numbers)))
    dc_rx1_ack_matrix = np.zeros((len(gw_numbers), len(ed_numbers)))
    dc_rx2_ack_matrix = np.zeros((len(gw_numbers), len(ed_numbers)))

    # Populate matrices
    for file, data in ack_percentages.items():
        gw, ed = extract_gateway_and_end_devices(file)
        gw_idx = gw_numbers.index(gw)
        ed_idx = ed_numbers.index(ed)
        ack_matrix[gw_idx, ed_idx] = data["ACK%"]
        dc_rx1_ack_matrix[gw_idx, ed_idx] = data["dcRx1"]
        dc_rx2_ack_matrix[gw_idx, ed_idx] = data["dcRx2"]
        rx1_matrix[gw_idx, ed_idx] = data["Rx1%"]
        rx2_matrix[gw_idx, ed_idx] = data["Rx2%"]

    return ack_matrix, rx1_matrix, rx2_matrix, dc_rx1_ack_matrix, dc_rx2_ack_matrix

# def plot_ack_matrices(matrices, titles, ed_numbers, gw_numbers):
#     for idx, (matrix, title) in enumerate(zip(matrices, titles)):
#         fig, ax = plt.subplots(figsize=(6, 4))
#         sns.heatmap(matrix, xticklabels=ed_numbers, yticklabels=gw_numbers, vmin=0, vmax=100, annot=True, fmt=".0f", annot_kws={"size": 8}, cmap="coolwarm", cbar_kws={'label': 'ACK%'}, ax=ax)
#         ax.set_title(title)
#         ax.set_xlabel('End Devices')
#         ax.set_ylabel('Gateways')
#         plt.tight_layout()
#         plt.savefig(f"{title.replace(' ', '_')}.pdf")
#         plt.show()
def create_ack_heatmap_matrices(ack_percentages):
    # Extract unique gateway and end device numbers
    gw_numbers = sorted(set(extract_gateway_and_end_devices(file)[0] for file in ack_percentages))
    ed_numbers = sorted(set(extract_gateway_and_end_devices(file)[1] for file in ack_percentages))

    # Initialize matrices
    ack_matrix = np.zeros((len(gw_numbers), len(ed_numbers)))
    rx1_matrix = np.zeros((len(gw_numbers), len(ed_numbers)))
    rx2_matrix = np.zeros((len(gw_numbers), len(ed_numbers)))
    HD_matrix = np.zeros((len(gw_numbers), len(ed_numbers)))
    dc_rx1_ack_matrix = np.zeros((len(gw_numbers), len(ed_numbers)))
    dc_rx2_ack_matrix = np.zeros((len(gw_numbers), len(ed_numbers)))

    # Populate matrices
    for file, data in ack_percentages.items():
        gw, ed = extract_gateway_and_end_devices(file)
        gw_idx = gw_numbers.index(gw)
        ed_idx = ed_numbers.index(ed)
        ack_matrix[gw_idx, ed_idx] = data["ACK%"]
        rx1_matrix[gw_idx, ed_idx] = data["Rx1%"]
        rx2_matrix[gw_idx, ed_idx] = data["Rx2%"]
        HD_matrix[gw_idx, ed_idx] = data["HD%"]
        dc_rx1_ack_matrix[gw_idx, ed_idx] = data["dcRx1"]
        dc_rx2_ack_matrix[gw_idx, ed_idx] = data["dcRx2"]

    return ack_matrix, rx1_matrix, rx2_matrix,HD_matrix, dc_rx1_ack_matrix, dc_rx2_ack_matrix

def plot_ack_matrices(matrices, titles, ed_numbers, gw_numbers, title_save):
    fig, axes = plt.subplots(1, len(matrices), figsize=(3.5 * len(matrices), 2.5),
                             sharey=True, constrained_layout=True)

    # Convert axes to array if there's only one subplot
    if len(matrices) == 1:
        axes = np.array([axes])

    for idx, (matrix, title) in enumerate(zip(matrices, titles)):
        sns.heatmap(matrix, xticklabels=ed_numbers, yticklabels=gw_numbers, vmin=0, vmax=100, annot=True, fmt=".0f", annot_kws={"size": 10}, cmap="coolwarm", ax=axes[idx],
                    cbar=False)
        axes[idx].set_title(title, fontsize=14)
        axes[idx].set_xlabel('End Devices', fontsize=12)
        if idx == 0:
            axes[idx].set_ylabel('Gateways', fontsize=12)
        axes[idx].tick_params(axis='both', which='major', labelsize=10)

    # Single shared colorbar — matplotlib places it inside the figure automatically
    sm = plt.cm.ScalarMappable(cmap="coolwarm", norm=plt.Normalize(vmin=0, vmax=100))
    cbar = fig.colorbar(sm, ax=axes.tolist(), shrink=1)
    cbar.outline.set_visible(False)
    #plt.tight_layout()
    plt.savefig(f"Figures/{title_save}_Combined_{'_'.join(titles).replace(' ', '_').replace('%', '')}.pdf",
                bbox_inches='tight')
def create_report(sf_data_all_1, sf_data_all_2, sf_data_all_3, output_file):
    # Combine all data into a single dictionary
    combined_data = {
        "Optimal": sf_data_all_1,
        "TTS": sf_data_all_2,
        "Custom TTS": sf_data_all_3
    }

    # Create a dictionary to store the aggregated data
    aggregated_data = {}

    # Iterate over the combined data
    for method, data in combined_data.items():
        for file, sf_data in data.items():
            gw, ed = extract_gateway_and_end_devices(file)
            key = (gw, ed)
            if key not in aggregated_data:
                aggregated_data[key] = {
                    "Gateway": gw,
                    "End Devices": ed,
                    "Optimal Total Count": 0,
                    "Optimal Total ACK": 0,
                    "Optimal Total Rx1": 0,
                    "Optimal Total Rx2": 0,
                    "Optimal Total HD": 0,
                    "TTS Total Count": 0,
                    "TTS Total ACK": 0,
                    "TTS Total Rx1": 0,
                    "TTS Total Rx2": 0,
                    "TTS Total HD": 0,
                    "Custom TTS Total Count": 0,
                    "Custom TTS Total ACK": 0,
                    "Custom TTS Total Rx1": 0,
                    "Custom TTS Total Rx2": 0,
                    "Custom TTS Total HD": 0
                }
            
            total_count = sum(stats["count"] for stats in sf_data.values())
            total_ack = sum(stats["ACK"] for stats in sf_data.values())
            total_rx1 = sum(stats["Rx1"] for stats in sf_data.values())
            total_rx2 = sum(stats["Rx2"] for stats in sf_data.values())
            total_hd = sum(stats["HD"] for stats in sf_data.values())

            aggregated_data[key][f"{method} Total Count"] += total_count
            aggregated_data[key][f"{method} Total ACK"] += total_ack
            aggregated_data[key][f"{method} Total Rx1"] += total_rx1
            aggregated_data[key][f"{method} Total Rx2"] += total_rx2
            aggregated_data[key][f"{method} Total HD"] += total_hd

    # Create a list to store the rows for the CSV
    rows = []

    # Iterate over the aggregated data
    for (gw, ed), data in aggregated_data.items():
        row = {
            "Gateway": gw,
            "End Devices": ed,
            "Optimal Total Count": data["Optimal Total Count"],
            "TTS Total Count": data["TTS Total Count"],
            "Custom TTS Total Count": data["Custom TTS Total Count"],
            "Optimal Total ACK": data["Optimal Total ACK"],
            "TTS Total ACK": data["TTS Total ACK"],
            "Custom TTS Total ACK": data["Custom TTS Total ACK"],
            "Optimal Total Rx1": data["Optimal Total Rx1"],
            "TTS Total Rx1": data["TTS Total Rx1"],
            "Custom TTS Total Rx1": data["Custom TTS Total Rx1"],
            "Optimal Total Rx2": data["Optimal Total Rx2"],
            "TTS Total Rx2": data["TTS Total Rx2"],
            "Custom TTS Total Rx2": data["Custom TTS Total Rx2"],
            "Optimal Total HD": data["Optimal Total HD"],
            "TTS Total HD": data["TTS Total HD"],
            "Custom TTS Total HD": data["Custom TTS Total HD"]
        }
        rows.append(row)

    # Create a DataFrame from the rows
    df = pd.DataFrame(rows)

    # Save the DataFrame to a CSV file
    df.to_csv(output_file, index=False)
    def create_sf_report(sf_data_all_1, sf_data_all_2, sf_data_all_3, output_file):
        # Combine all data into a single dictionary
        combined_data = {
            "Optimal": sf_data_all_1,
            "TTS": sf_data_all_2,
            "Custom TTS": sf_data_all_3
        }

        # Create a dictionary to store the aggregated data
        aggregated_data = {}

        # Iterate over the combined data
        for method, data in combined_data.items():
            for file, sf_data in data.items():
                gw, ed = extract_gateway_and_end_devices(file)
                for sf, stats in sf_data.items():
                    key = (gw, ed, sf)
                    if key not in aggregated_data:
                        aggregated_data[key] = {
                            "Gateway": gw,
                            "End Devices": ed,
                            "SF": sf,
                            "Optimal Count": 0,
                            "Optimal ACK": 0,
                            "Optimal Rx1": 0,
                            "Optimal Rx2": 0,
                            "Optimal HD": 0,
                            "TTS Count": 0,
                            "TTS ACK": 0,
                            "TTS Rx1": 0,
                            "TTS Rx2": 0,
                            "TTS HD": 0,
                            "Custom TTS Count": 0,
                            "Custom TTS ACK": 0,
                            "Custom TTS Rx1": 0,
                            "Custom TTS Rx2": 0,
                            "Custom TTS HD": 0
                        }

                    aggregated_data[key][f"{method} Count"] += stats["count"]
                    aggregated_data[key][f"{method} ACK"] += stats["ACK"]
                    aggregated_data[key][f"{method} Rx1"] += stats["Rx1"]
                    aggregated_data[key][f"{method} Rx2"] += stats["Rx2"]
                    aggregated_data[key][f"{method} HD"] += stats["HD"]

        # Create a list to store the rows for the CSV
        rows = []

        # Iterate over the aggregated data
        for (gw, ed, sf), data in aggregated_data.items():
            row = {
                "Gateway": gw,
                "End Devices": ed,
                "SF": sf,
                "Optimal Count": data["Optimal Count"],
                "TTS Count": data["TTS Count"],
                "Custom TTS Count": data["Custom TTS Count"],
                "Optimal ACK": data["Optimal ACK"],
                "TTS ACK": data["TTS ACK"],
                "Custom TTS ACK": data["Custom TTS ACK"],
                "Optimal Rx1": data["Optimal Rx1"],
                "TTS Rx1": data["TTS Rx1"],
                "Custom TTS Rx1": data["Custom TTS Rx1"],
                "Optimal Rx2": data["Optimal Rx2"],
                "TTS Rx2": data["TTS Rx2"],
                "Custom TTS Rx2": data["Custom TTS Rx2"],
                "Optimal HD": data["Optimal HD"],
                "TTS HD": data["TTS HD"],
                "Custom TTS HD": data["Custom TTS HD"]
            }
            rows.append(row)

        # Create a DataFrame from the rows
        df = pd.DataFrame(rows)

        # Save the DataFrame to a CSV file
        df.to_csv(output_file, index=False)

    # Call the function to create the SF report
    create_sf_report(sf_data_all_1, sf_data_all_2, sf_data_all_3, "sf_report.csv")
def plot_ack_bars(ack_matrix_ch, ack_matrix_c, ack_matrix_c_cs, ed_numbers, gw_numbers,label_in='ACK',xlim = 100):
    # Number of end devices and gateways
    num_ed = len(ed_numbers)
    num_gw = len(gw_numbers)

    # Create a figure and axis
    fig, ax = plt.subplots(figsize=(8, 4), facecolor='none')

    # Define bar width and positions
    bar_width = 0.25
    index = np.arange(num_ed * num_gw)

    # Flatten the matrices for plotting
    ack_ch_flat = ack_matrix_ch.T.flatten()
    ack_c_flat = ack_matrix_c.T.flatten()
    ack_c_cs_flat = ack_matrix_c_cs.T.flatten()

    # Plot the bars side by side with edge lines
    ax.bar(index- bar_width, ack_c_flat, bar_width, label='TTS', color=colors_TTS_CUS_OP[0], alpha=0.9, edgecolor='black', linewidth=0.8)  # Strong Green
    ax.bar(index , ack_c_cs_flat, bar_width, label='SFTS', color=colors_TTS_CUS_OP[1], alpha=0.9, edgecolor='black', linewidth=0.8)  # Strong Orange
    ax.bar(index + bar_width, ack_ch_flat, bar_width, label='Optimal', color=colors_TTS_CUS_OP[2], alpha=0.9, edgecolor='black', linewidth=0.8)  # Strong Blue

    # Set the x-ticks and labels
    ax.set_xticks(index)
    ax.set_xticklabels([f'({gw_numbers[i % num_gw]},{ed_numbers[i // num_gw]})' for i in range(len(index))], rotation=45, ha='center')

    # Set labels and title
    ax.set_xlabel('(gw,ed)', fontsize=14)
    ax.set_ylabel(f'{label_in} (%)', fontsize=14)

    # Set y-axis limits and ticks
    ax.set_ylim(0, xlim)
    ax.set_yticks(np.arange(0, xlim + 1, xlim/10))  # Add ticks at intervals of 10

    # Add legend outside the plot
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, 1.28), ncol=3, fontsize=12)

    # Add grid
    ax.grid(True)
    ax.set_axisbelow(True)

    # Show the plot
    plt.tight_layout()
    plt.savefig(f"Figures/{label_in}_Bars_Comparison_SideBySide.pdf")
def plot_ack_differences(ack_matrix_ch, ack_matrix_c, ack_matrix_c_cs, ed_numbers, gw_numbers):
    # Number of end devices and gateways
    num_ed = len(ed_numbers)
    num_gw = len(gw_numbers)

    # Compute the differences
    diff_ch_c = ack_matrix_ch - ack_matrix_c
    diff_c_cs_c = ack_matrix_c_cs - ack_matrix_c

    # Create a figure and axis
    fig, ax = plt.subplots(figsize=(8, 4))

    # Define bar width and positions
    bar_width = 0.4
    index = np.arange(num_ed * num_gw)

    # Flatten the matrices for plotting
    diff_ch_c_flat = diff_ch_c.T.flatten()
    diff_c_cs_c_flat = diff_c_cs_c.T.flatten()

    # Plot the differences for Optimal - TTS
    ax.bar(index - bar_width / 2, diff_ch_c_flat, bar_width, label='Optimal - TTS', color='lightblue', alpha=0.8)

    # Plot the differences for TTS threshold - TTS
    ax.bar(index + bar_width / 2, diff_c_cs_c_flat, bar_width, label='TTS threshold - TTS', color='lightcoral', alpha=0.8)

    # Set the x-ticks and labels
    ax.set_xticks(index)
    ax.set_xticklabels([f'(ED{ed_numbers[i // num_gw]}, GW{gw_numbers[i % num_gw]})' for i in range(len(index))], rotation=45, ha='right', fontsize=12)

    # Set labels and title
    ax.set_xlabel('End Devices and Gateways', fontsize=14)
    ax.set_ylabel('Difference in ACK Percentage', fontsize=14)
    # Add legend outside the plot
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, 1.2), ncol=2, fontsize=12)

    # Add grid
    ax.grid(True)
    ax.set_axisbelow(True)

    # Adjust layout and save the plot
    plt.tight_layout()
    plt.savefig("Figures/ACK_Differences_Comparison.pdf")


def extract_metric(labels, data_dict, key1, key2=None):
    return [data_dict[k][key1][key2] if key2 else data_dict[k][key1] for k in labels]
    
def plot_downlink_info(dict_optimal, dict_normal, dict_custom):
    labels = sorted(dict_optimal.keys(), key=lambda x: (x[1], x[0]))  # Sort by ED first, then by GW
    label_strs = [f"({k[0]},{k[1]})" for k in labels]
    bar_width = 0.25
    x = np.arange(len(labels))

    metrics = {
        "blocked": {
            
            "norm": (extract_metric(labels, dict_normal, 'blocked', '1'), extract_metric(labels, dict_normal, 'blocked', '2')),
            "cust": (extract_metric(labels, dict_custom, 'blocked', '1'), extract_metric(labels, dict_custom, 'blocked', '2')),
            "opt": (extract_metric(labels, dict_optimal, 'blocked', '1'), extract_metric(labels, dict_optimal, 'blocked', '2'))
        },
        "conflict": {
            "norm": (extract_metric(labels, dict_normal, 'conflict', '1'), extract_metric(labels, dict_normal, 'conflict', '2')),
            "cust": (extract_metric(labels, dict_custom, 'conflict', '1'), extract_metric(labels, dict_custom, 'conflict', '2')),
            "opt": (extract_metric(labels, dict_optimal, 'conflict', '1'), extract_metric(labels, dict_optimal, 'conflict', '2')),

        },
        "hd_lost": {
            "norm": extract_metric(labels, dict_normal, 'hd_lost'),
            "cust": extract_metric(labels, dict_custom, 'hd_lost'),
            "opt": extract_metric(labels, dict_optimal, 'hd_lost')
        }
    }
    

    for metric, data in metrics.items():
        fig, ax = plt.subplots(figsize=(8, 4), facecolor='none')
        
        if metric == "hd_lost":
            ax.bar(x- bar_width, data["norm"], width=bar_width, label='TTS', color=colors_TTS_CUS_OP[0], alpha=0.9, edgecolor='black', linewidth=0.8)
            ax.bar(x , data["cust"], width=bar_width, label='SFTS', color=colors_TTS_CUS_OP[1], alpha=0.9, edgecolor='black', linewidth=0.8)
            ax.bar(x + bar_width, data["opt"], width=bar_width, label='Optimal', color=colors_TTS_CUS_OP[2], alpha=0.9, edgecolor='black', linewidth=0.8)
            ax.set_ylabel("Number of HD Lost", fontsize=12)
            
            # Adaptive y-axis for hd_lost
            all_values = data["opt"] + data["norm"] + data["cust"]
            max_val = max(all_values) if all_values else 100
            y_tick_interval = max(1, int(max_val / 8))
            ax.set_yticks(range(0, int(max_val) + y_tick_interval + 1, y_tick_interval))
        else:

            ax.bar(x- bar_width, data["norm"][0], width=bar_width, color=colors_TTS_CUS_OP[0], alpha=0.9, edgecolor='black', linewidth=0.8, label='TTS Rx1' if metric == list(metrics.keys())[1] else '')
            ax.bar(x- bar_width, data["norm"][1], width=bar_width, bottom=data["norm"][0], color=colors_TTS_CUS_OP[0], alpha=0.5, edgecolor='black', linewidth=0.8, hatch='//', label='TTS Rx2' if metric == list(metrics.keys())[1] else '')
            ax.bar(x, data["cust"][0], width=bar_width, color=colors_TTS_CUS_OP[1], alpha=0.9, edgecolor='black', linewidth=0.8, label='SFTS Rx1' if metric == list(metrics.keys())[1] else '')
            ax.bar(x, data["cust"][1], width=bar_width, bottom=data["cust"][0], color=colors_TTS_CUS_OP[1], alpha=0.5, edgecolor='black', linewidth=0.8, hatch='//', label='SFTS Rx2' if metric == list(metrics.keys())[1] else '')
            ax.bar(x + bar_width , data["opt"][0], width=bar_width, color=colors_TTS_CUS_OP[2], alpha=0.9, edgecolor='black', linewidth=0.8, label='Optimal Rx1' if metric == list(metrics.keys())[1] else '')
            ax.bar(x + bar_width , data["opt"][1], width=bar_width, bottom=data["opt"][0], color=colors_TTS_CUS_OP[2], alpha=0.5, edgecolor='black', linewidth=0.8, hatch='//', label='Optimal Rx2' if metric == list(metrics.keys())[1] else '')
            
            ax.set_ylabel(f"Number of {metric.capitalize()}", fontsize=14)

            # Set ylim to 1200 for conflict and blocked
            #ax.set_yticks(range(0, 1201, 200))
            y_lim = 230 if metric == "conflict" else 1300
            ax.set_yticks(range(0, y_lim + 1, y_lim // 10))
            ax.set_ylim(0, y_lim)

        ax.set_xlabel("(gw,ed)", fontsize=14)
        ax.set_xticks(x)
        ax.set_xticklabels(label_strs, rotation=45, ha='right', fontsize=10)
        
        # Create custom legend for stacked bars
        if metric != "hd_lost":
            legend_elements = [
                Patch(facecolor=colors_TTS_CUS_OP[0], edgecolor='black', label='TTS Rx1'),
                Patch(facecolor=colors_TTS_CUS_OP[0], edgecolor='black', hatch='//', label='TTS Rx2'),
                Patch(facecolor=colors_TTS_CUS_OP[1], edgecolor='black', label='SFTS Rx1'),
                Patch(facecolor=colors_TTS_CUS_OP[1], edgecolor='black', hatch='//', label='SFTS Rx2'),
                Patch(facecolor=colors_TTS_CUS_OP[2], edgecolor='black', label='Optimal Rx1'),
                Patch(facecolor=colors_TTS_CUS_OP[2], edgecolor='black', hatch='//', label='Optimal Rx2'),
            ]
            ax.legend(handles=legend_elements,loc='upper center', bbox_to_anchor=(0.5, 1.32), ncol=3, fontsize=12)
        else:
            ax.legend(loc='upper center', bbox_to_anchor=(0.5, 1.28), ncol=3, fontsize=12)
        
        ax.grid(True)
        ax.set_axisbelow(True)
        plt.tight_layout()
        plt.savefig(f"Figures/Downlink_{metric.capitalize()}_Comparison.pdf")

def plot_fdr_tout(FDR_TOUT,title):
    # Extract data for plotting
    labels = []
    fdr_no_dl = []
    fdr_custom = []
    fdr_tts = []
    fdr_optimal = []

    prev_ed = None  # To track the previous number of end devices
    segment_indices = []  # To track the indices where segments should break

    for key, value in FDR_TOUT.items():
        gw, ed, percentage, seed = key
        label = f"({gw},{ed})"
        if label not in labels:
            labels.append(label)
            fdr_no_dl.append(value["FDR_NO_DL"])
            fdr_custom.append(value["FDR_CUSTOM"])
            fdr_tts.append(value["FDR_TTS"])
            fdr_optimal.append(value["FDR_OPTIMAL"])

            # Check if there's a transition in the number of end devices
            if prev_ed is not None and ed != prev_ed:
                segment_indices.append(len(labels) - 1)
            prev_ed = ed

    x = np.arange(len(labels))  # the label locations

    fig, ax = plt.subplots(figsize=(6, 3), facecolor='none')

    # Helper function to plot segments
    def plot_segments(x, y, label=None, **kwargs):
        start = 0
        for idx in segment_indices:
            ax.plot(x[start:idx], y[start:idx], label=label if start == 0 else None, **kwargs, markeredgecolor='black')
            start = idx
        ax.plot(x[start:], y[start:], label=label if start == 0 else None, **kwargs, markeredgecolor='black')

    # Plot the lines with breaks at segment indices 
    plot_segments(x, fdr_no_dl, marker='o', label='NO DL', color='royalblue', alpha=0.8, linestyle='-')
    plot_segments(x, fdr_tts, marker='^', label='TTS', color='orange', alpha=0.8, linestyle='-.')    
    plot_segments(x, fdr_custom, marker='s', label='SFTS', color='seagreen', alpha=0.8, linestyle='--')
    plot_segments(x, fdr_optimal, marker='d', label='Optimal', color='salmon', alpha=0.8, linestyle=':')

    # Add some text for labels, title and custom x-axis tick labels, etc.
    ax.set_xlabel('(gw,ed)', fontsize=12)
    ax.set_ylabel('UL FDR (%)', fontsize=12)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=10)

    # Set y-axis limits
    ax.set_ylim(25, 100)
    ax.set_yticks(np.arange(30, 101, 10))  # Set yticks in steps of 10

    # Add grid
    ax.grid(True)
    ax.set_axisbelow(True)

    # Add legend for only the first segments
    ax.legend(fontsize=9, loc='upper center', bbox_to_anchor=(0.5, 1.2), ncol=4, frameon=False, columnspacing=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=9)

    # Adjust layout and show the plot
    plt.tight_layout()
    plt.savefig(f"Figures/FDR_TOUT_Comparison_Line_{title}.pdf")


