
import pandas as pd
import os
import glob
import re
import numpy as np
import seaborn as sns
import json
import matplotlib.pyplot as plt

# --- CSV Column Headers ---
desired_headers     = ["senderId", "receiverID", "sendTime", "receivedTime", "SF", "SNR", "Ftype", "Freq", "RX"]
desired_headers_UL  = ["senderId", "receiverID", "sendTime", "receivedTime", "SF", "SNR", "Ftype", "Freq", "received", "code", ""]
desired_headers_UL2 = ["senderId", "receiverID", "sendTime", "receivedTime", "SF", "SNR", "Ftype", "Freq", "received", "code"]
headers_lost        = ["HDsenderId", "HDreceiverID", "HDsendTime", "receivedTime", "SF", "SNR", "Ftype"]
colors_TTS_CUS_OP = ['orange', 'seagreen', 'salmon']

def extract_parameters(filename):
    gateway_match = re.search(r'gateway_(\d+)', filename)
    period_match = re.search(r'period_(\d+)', filename)
    percentage_match = re.search(r'percentage_(\d+)', filename)
    end_device_match = re.search(r'N_ED_(\d+)', filename)
    
    if gateway_match and end_device_match:
        gateway = int(gateway_match.group(1))
        end_devices = int(end_device_match.group(1))
        period = int(period_match.group(1))
        percentage = int(percentage_match.group(1))
        return gateway, end_devices,period,percentage
    return None, None





def extract_gateway_and_percentage(filename):
    gateway_match = re.search(r'gateway_(\d+)', filename)
    end_device_match = re.search(r'percentage_(\d+)', filename)
    
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
        dataframe["sendTime"] /= 1e9  # Convert nanoseconds to milliseconds
        dataframe["receivedTime"] /= 1e9  # Convert nanoseconds to milliseconds
    else:
        dataframe["sendTime"] /= 1e3  # Convert nanoseconds to milliseconds
        dataframe["receivedTime"] /= 1e3  # Convert nanoseconds to milliseconds

    dataframe["ToA"] = dataframe["receivedTime"] - dataframe["sendTime"]
    dataframe["Blocked Time"] = dataframe["ToA"] * dataframe["RX"].map({1: 100, 2: 10}).fillna(0)


    return dataframe

def extract_table_with_headers(file_path, headers,type):
    print(f"Reading file: {file_path}")
    with open(file_path, 'r') as file:
        lines = file.readlines() 
    
    # Find the starting index of the table by matching headers
    for idx, line in enumerate(lines):
        if all(header in line for header in headers):
            start_idx = idx + 1
            break
    else:
        raise ValueError("Table with specified headers not found.")
    
    # Extract table lines
    table_lines = []
    for line in lines[start_idx:]:
        if line.strip() == "" or not line[0].isdigit():
            break
        table_lines.append(line.strip())
    
    # Create DataFrame
    data = [row.split(',') for row in table_lines]
    df = pd.DataFrame(data, columns=headers)
    
    # Filter rows where Ftype == 4
    #df = df[df['Ftype'] == str(type)]  # Assuming 'Ftype' is stored as a string in the file
    # Filter out repeated uplinks with the same sendTime
    if type == 4:
        df = df.sort_values(by=["received", "receivedTime"], ascending=[False, True]).drop_duplicates(subset=["sendTime"])

    columns_to_drop = ["SNR"]
    df.drop(columns=[col for col in columns_to_drop if col in df], inplace=True)
    if "RX" in headers:
        df = add_calculated_columns_DL(df,type)



    return df
def process_Tables(tabUL, tabDL):
    ED_stats = {}
    SF_stats = {}
    summary_stats = {"count_all_UL":0,"ACK": 0, "CUL": 0,"HD":0, "Rx1": 0, "Rx2": 0}

    for index, row in tabUL.iterrows():
        sender_id = row['senderId']
        if sender_id not in ED_stats:
            SF = row['SF']
            ED_stats[sender_id] = {"SF": SF, "RX": 0, "ACK": 0, "Rx1": 0, "Rx2": 0, "ToA": 0, "Blocked_Rx1": 0, "Blocked_Rx2": 0}
            # Get all lines with the same sender_id in tabUL
            sender_rows_complete = tabUL[tabUL['senderId'] == sender_id]
            sender_rows = sender_rows_complete[sender_rows_complete['Ftype'] == str(4)]
            # Get all lines in tabDL with receiverID equal to sender_id
            receiver_rows = tabDL[tabDL['receiverID'] == sender_id]
            Rx1_Tab = receiver_rows[receiver_rows['RX'] == 1]
            Rx2_Tab = receiver_rows[receiver_rows['RX'] == 2]
            ED_stats[sender_id]["RX"] = len(sender_rows)
            ED_stats[sender_id]["Rx1"] = len(Rx1_Tab)
            ED_stats[sender_id]["Rx2"] = len(Rx2_Tab)
            ED_stats[sender_id]["ACK"] = len(receiver_rows)
            ED_stats[sender_id]["ToA"] = receiver_rows["ToA"].sum()
            ED_stats[sender_id]["Blocked_Rx1"] = Rx1_Tab["Blocked Time"].sum()
            ED_stats[sender_id]["Blocked_Rx2"] = Rx2_Tab["Blocked Time"].sum()
            if SF not in SF_stats:
                SF_stats[SF] = {"count": 0, "Rx": 0, "ACK": 0, "Rx1": 0, "Rx2": 0, "Blocked_Rx1": 0, "Blocked_Rx2": 0}
            SF_stats[SF]["count"] += len(sender_rows)
            SF_stats[SF]["Rx"] += len(receiver_rows)
            SF_stats[SF]["Rx1"] += len(Rx1_Tab)
            SF_stats[SF]["Rx2"] += len(Rx2_Tab)
            SF_stats[SF]["ACK"] += len(receiver_rows)
            SF_stats[SF]["Blocked_Rx1"] += Rx1_Tab["Blocked Time"].sum()
            SF_stats[SF]["Blocked_Rx2"] += Rx2_Tab["Blocked Time"].sum()

            # Update summary statistics
            summary_stats["ACK"] += len(receiver_rows)
            summary_stats["CUL"] += len(sender_rows)
            summary_stats["count_all_UL"] += len(sender_rows_complete)
            if "received" in sender_rows:
                summary_stats["HD"] += len(sender_rows_complete[sender_rows_complete['received'] == '0'])
            summary_stats["Rx1"] += len(Rx1_Tab)
            summary_stats["Rx2"] += len(Rx2_Tab)

    SF_stats = dict(sorted(SF_stats.items(), key=lambda item: int(item[0])))
    return ED_stats, SF_stats, summary_stats



def plot_matrices(sf_values, gw_ed_combinations, ack_matrix, rx_matrix_1,rx_matrix_2, blocked_rx1_matrix, blocked_rx2_matrix,Title):
    # Plot for ack_matrix and rx_matrix
    fig1, axes1 = plt.subplots(1, 3, figsize=(13, 4))

    sns.heatmap(ack_matrix, ax=axes1[0], xticklabels=sf_values, yticklabels=gw_ed_combinations, cmap="coolwarm", annot=True, vmin=0, vmax=100, annot_kws={"size": 8}, fmt=".0f")
    axes1[0].set_title('ACK%')
    axes1[0].set_xlabel('SF')
    axes1[0].set_ylabel('(gw, ed)')

    sns.heatmap(rx_matrix_1, ax=axes1[1], xticklabels=sf_values, yticklabels=gw_ed_combinations, cmap="coolwarm", annot=True, vmin=0, vmax=100, annot_kws={"size": 8}, fmt=".0f")
    axes1[1].set_title('Utilization Rx1%')
    axes1[1].set_xlabel('SF')
    axes1[1].set_ylabel('(gw, ed)')

    sns.heatmap(rx_matrix_2, ax=axes1[2], xticklabels=sf_values, yticklabels=gw_ed_combinations, cmap="coolwarm", annot=True, vmin=0, vmax=100, annot_kws={"size": 8}, fmt=".0f")
    axes1[2].set_title('Utilization Rx2%')
    axes1[2].set_xlabel('SF')
    axes1[2].set_ylabel('(gw, ed)')
    fig1.suptitle(f'ACK and RX Percentages by SF and (gw, ed) {Title}', fontsize=16)

    plt.tight_layout()



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
        gw, ed,_,_ = extract_parameters(file)
        if gw:
            label = f"GW{gw}_ED{ed}"
            labels.append(label)
            ch_data["Rx1%"].append(ack_percentages_ch[file]["Rx1%"])
            ch_data["Rx2%"].append(ack_percentages_ch[file]["Rx2%"])
            ch_data["No_ACK%"].append(ack_percentages_ch[file]["No_ACK%"])
    
    for file in ack_percentages_c:
        gw, ed = extract_parameters(file)
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
        gw, ed,_,_ = extract_parameters(file)
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


def process_directory(directory, desired_headers, desired_headers_UL,emulation_type, typeDL=3, typeUL=4):
    files = get_files(directory)
    #print(files)
    sf_values = None

    scenario_data_per_SF = {}
    scenario_data = {}

    for i in files:
        gw, ed,period,percentage= extract_parameters(i)


        tuple_param = (gw,ed,period,percentage)

        if tuple_param not in scenario_data_per_SF:
            scenario_data_per_SF[tuple_param] = []
        if tuple_param not in scenario_data:
            scenario_data[tuple_param] = []

        tabDL = extract_table_with_headers(i, desired_headers, typeDL)
        tabUL = extract_table_with_headers(i, desired_headers_UL, typeUL)
        if "received" not in desired_headers_UL:
            tabUL["received"] = "1"
            tabUL_HD = extract_table_with_headers(i, headers_lost, 2)
            tabUL_HD["received"] = "0"
            tabUL_HD.columns = tabUL.columns
            tabUL.loc[tabUL["sendTime"].isin(tabUL_HD["sendTime"]), "received"] = "0"


        
        # Save tabUL to a CSV file
        
        _, sf_data,summary_stats = process_Tables(tabUL, tabDL)
        scenario_data_per_SF[tuple_param].append(sf_data)
        scenario_data[tuple_param].append(summary_stats)

  
    # Calculate average values for each scenario
    avg_scenario_data = {}
    avg_scenario_data_per_SF = {}
    #print(scenario_data)
    for key, data_list in scenario_data.items():
        #print(data_list)
        total_cul = np.sum([data["CUL"] for data in data_list])
        avg_scenario_data[key] = {
            "ACK%": np.mean([data["ACK"] / data["CUL"] * 100 for data in data_list]),
            "HD%": np.mean([data["HD"]/ data["count_all_UL"] * 100 for data in data_list]),
            "Rx1%": np.mean([data["Rx1"] / data["CUL"]  * 100 for data in data_list]),
            "Rx2%": np.mean([data["Rx2"] /data["CUL"]  * 100 for data in data_list]),
            "ACK%_max": np.max([data["ACK"] / data["CUL"] * 100 for data in data_list]),
            "HD%_max": np.max([data["HD"] / data["count_all_UL"] * 100 for data in data_list]),
            "Rx1%_max": np.max([data["Rx1"] / data["CUL"]  * 100 for data in data_list]),
            "Rx2%_max": np.max([data["Rx2"] / data["CUL"]  * 100 for data in data_list]),
            "ACK%_min": np.min([data["ACK"] / data["CUL"] * 100 for data in data_list]),
            "HD%_min": np.min([data["HD"] / data["count_all_UL"] * 100 for data in data_list]),
            "Rx1%_min": np.min([data["Rx1"] / data["CUL"]  * 100 for data in data_list]),
            "Rx2%_min": np.min([data["Rx2"] / data["CUL"]  * 100 for data in data_list])
        }
    
    for key, sf_data_list in scenario_data_per_SF.items():
        avg_scenario_data_per_SF[key] = {}
        for sf_data in sf_data_list:
            for sf, metrics in sf_data.items():
                if sf not in avg_scenario_data_per_SF[key]:
                    avg_scenario_data_per_SF[key][sf] = {
                        "count": [],
                        "Rx%": [],
                        "ACK%": [],
                        "Rx1%": [],
                        "Rx2%": [],
                        "Blocked_Rx1": [],
                        "Blocked_Rx2": []
                    }
                avg_scenario_data_per_SF[key][sf]["count"].append(metrics["count"])
                avg_scenario_data_per_SF[key][sf]["Rx%"].append(metrics["Rx"] / metrics["count"] * 100)
                avg_scenario_data_per_SF[key][sf]["ACK%"].append(metrics["ACK"] / metrics["count"] * 100)
                avg_scenario_data_per_SF[key][sf]["Rx1%"].append(metrics["Rx1"] /metrics["count"] * 100)
                avg_scenario_data_per_SF[key][sf]["Rx2%"].append(metrics["Rx2"] / metrics["count"] * 100)
                avg_scenario_data_per_SF[key][sf]["Blocked_Rx1"].append(metrics["Blocked_Rx1"])
                avg_scenario_data_per_SF[key][sf]["Blocked_Rx2"].append(metrics["Blocked_Rx2"])

        for sf, metrics in avg_scenario_data_per_SF[key].items():
            avg_scenario_data_per_SF[key][sf] = {
                "count": np.mean(metrics["count"]),
                "Rx%": np.mean(metrics["Rx%"]),
                "ACK%": np.mean(metrics["ACK%"]),
                "Rx1%": np.mean(metrics["Rx1%"]),
                "Rx2%": np.mean(metrics["Rx2%"]),
                "Blocked_Rx1": np.mean(metrics["Blocked_Rx1"]),
                "Blocked_Rx2": np.mean(metrics["Blocked_Rx2"]),
                "count_max": np.max(metrics["count"]),
                "Rx%_max": np.max(metrics["Rx%"]),
                "ACK%_max": np.max(metrics["ACK%"]),
                "Rx1%_max": np.max(metrics["Rx1%"]),
                "Rx2%_max": np.max(metrics["Rx2%"]),
                "Blocked_Rx1_max": np.max(metrics["Blocked_Rx1"]),
                "Blocked_Rx2_max": np.max(metrics["Blocked_Rx2"]),
                "count_min": np.min(metrics["count"]),
                "Rx%_min": np.min(metrics["Rx%"]),
                "ACK%_min": np.min(metrics["ACK%"]),
                "Rx1%_min": np.min(metrics["Rx1%"]),
                "Rx2%_min": np.min(metrics["Rx2%"]),
                "Blocked_Rx1_min": np.min(metrics["Blocked_Rx1"]),
                "Blocked_Rx2_min": np.min(metrics["Blocked_Rx2"])
            }


    # Convert tuple keys to strings for JSON serialization
    def convert_numpy_int64(data):
        if isinstance(data, dict):
            return {k: convert_numpy_int64(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [convert_numpy_int64(v) for v in data]
        elif isinstance(data, np.int64):
            return int(data)
        else:
            return data

    scenario_data_str_keys = {str(k): convert_numpy_int64(v) for k, v in scenario_data.items()}
    scenario_data_per_SF_str_keys = {str(k): convert_numpy_int64(v) for k, v in scenario_data_per_SF.items()}
    avg_scenario_data_str_keys = {str(k): convert_numpy_int64(v) for k, v in avg_scenario_data.items()}
    avg_scenario_data_per_SF_str_keys = {str(k): convert_numpy_int64(v) for k, v in avg_scenario_data_per_SF.items()}

    # Save the average scenario data to a JSON file
    with open(directory+'_'+'scenario_data.json', 'w') as json_file:
        json.dump(scenario_data_str_keys, json_file, indent=4)

    # Save the average scenario data per SF to a JSON file
    with open(directory+'_'+'scenario_data_per_sf.json', 'w') as json_file:
        json.dump(scenario_data_per_SF_str_keys, json_file, indent=4)
    with open(directory+'_'+'average_scenario_data.json', 'w') as json_file:
        json.dump(avg_scenario_data_str_keys, json_file, indent=4)

    # Save the average scenario data per SF to a JSON file
    with open(directory+'_'+'average_scenario_data_per_sf.json', 'w') as json_file:
        json.dump(avg_scenario_data_per_SF_str_keys, json_file, indent=4)
    sf_values = avg_scenario_data_per_SF.keys()
    json_to_csv(scenario_data_str_keys, csv_file=directory+'_'+'scenario_data.csv')
    json_to_csv(avg_scenario_data_str_keys, csv_file=directory+'_'+'average_scenario_data.csv')

    return avg_scenario_data,avg_scenario_data_per_SF,sf_values

def json_to_csv(data, csv_file):
    # Convert dictionary data to a DataFrame
    df = pd.DataFrame.from_dict(data, orient='index')

    # Sort DataFrame by the tuple keys (GW, ED, periodicity, CT)
    df.index = pd.MultiIndex.from_tuples(df.index.map(eval), names=["GW", "ED", "Periodicity", "CT"])
    df = df.sort_index()

    # Save DataFrame to CSV
    df.to_csv(csv_file)

def plot_ack_matrices(matrices, titles, ed_numbers, gw_numbers):
    num_matrices = len(matrices)
    fig, axes = plt.subplots(1, num_matrices, figsize=(4 * num_matrices, 3))

    if num_matrices == 1:
        axes = [axes]

    for idx, (matrix, title) in enumerate(zip(matrices, titles)):
        sns.heatmap(matrix, xticklabels=ed_numbers, yticklabels=gw_numbers, vmin=0, vmax=100, annot=True, fmt=".0f", annot_kws={"size": 8}, cmap="coolwarm", cbar_kws={'label': 'ACK%'}, ax=axes[idx])
        axes[idx].set_title(title)
        axes[idx].set_xlabel('End Devices')
        axes[idx].set_ylabel('Gateways')

    plt.tight_layout()

def create_ack_heatmap_matrices_2(av_scenario):
    # Extract unique gateway and percentage numbers

    end_devices = sorted(set(key[1] for key in av_scenario.keys()))
    gw_numbers = sorted(set(key[0] for key in av_scenario.keys()))
    periods = sorted(set(key[2] for key in av_scenario.keys()))
    percentage_numbers = sorted(set(key[3] for key in av_scenario.keys()))


    # Initialize matrices
    ack_matrix = np.zeros((len(gw_numbers), len(percentage_numbers)))
    rx1_matrix = np.zeros((len(gw_numbers), len(percentage_numbers)))
    rx2_matrix = np.zeros((len(gw_numbers), len(percentage_numbers)))

    # Populate matrices
    for (gw, ed,period,percentage), data in av_scenario.items():
        gw_idx = gw_numbers.index(gw)
        percentage_idx = percentage_numbers.index(percentage)
        ack_matrix[gw_idx, percentage_idx] = data["ACK%"]
        rx1_matrix[gw_idx, percentage_idx] = data["Rx1%"]
        rx2_matrix[gw_idx, percentage_idx] = data["Rx2%"]

    return ack_matrix, rx1_matrix, rx2_matrix


def plot_ack_matrices(matrices, titles, ed_numbers, gw_numbers):
    num_matrices = len(matrices)
    fig, axes = plt.subplots(1, num_matrices, figsize=(4 * num_matrices, 3))

    if num_matrices == 1:
        axes = [axes]

    for idx, (matrix, title) in enumerate(zip(matrices, titles)):
        sns.heatmap(matrix, xticklabels=ed_numbers, yticklabels=gw_numbers, vmin=0, vmax=100, annot=True, fmt=".0f", annot_kws={"size": 8}, cmap="coolwarm", cbar_kws={'label': 'ACK%'}, ax=axes[idx])
        axes[idx].set_title(title)
        axes[idx].set_xlabel('Confirm Traffic %')
        axes[idx].set_ylabel('Gateways')

    plt.tight_layout()
def computation_FDR_UPLINKS(optimal, tts, custom_tts):
    # Get all files in the directory that end with 'GlobalPerf.csv'
    global_perf_files = glob.glob(os.path.join(tts, "*_GlobalPerf.csv"))
    print(f"Found {len(global_perf_files)} files ending with 'GlobalPerf.csv':")
    FDR_EXPERIMENTS_RAW = {}
    FDR_EXPERIMENTS_CONF_RAW = {}
    FDR_EXPERIMENTS_UNCONF_RAW = {}

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

                _m1 = glob.glob(os.path.join(custom_tts, template_tts))
                _m2 = glob.glob(os.path.join(optimal, template_custom))
                _m3 = glob.glob(os.path.join(custom_tts, template_custom2))
                _m4 = glob.glob(os.path.join(tts, template_custom2))

                if not _m1:
                    print(f"Warning: no match for {template_tts} in {optimal}, skipping.")
                    continue
                if not _m2:
                    print(f"Warning: no match for {template_custom} in {custom_tts}, skipping.")
                    continue
                if not _m3:
                    print(f"Warning: no match for {template_custom2} in {optimal}, skipping.")
                    continue
                if not _m4:
                    print(f"Warning: no match for {template_custom2} in {tts}, skipping.")
                    continue

                custom_tts_file = _m1[0]
                optimal_uplinks_file = _m2[0]
                custom_uplinks_file = _m3[0]
                tts_uplinks_file = _m4[0]

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
                        optimal_uplinks_df_all = extract_table_with_headers(optimal_uplinks_file, desired_headers_UL2, 4)
                        optimal_downlinks_df_all_dl_confirmed = extract_table_with_headers(optimal_uplinks_file, desired_headers, 3).shape[0]

                        # The UL section contains both Ftype=2 and Ftype=4 — split AFTER reading
                        optimal_uplinks_received_conf = optimal_uplinks_df_all[
                            (optimal_uplinks_df_all["Ftype"] == "4") &
                            (optimal_uplinks_df_all["received"] == "1")
                        ].shape[0]
                        optimal_uplinks_received_unconf = optimal_uplinks_df_all[
                            (optimal_uplinks_df_all["Ftype"] == "2") &
                            (optimal_uplinks_df_all["received"] == "1")
                        ].shape[0]
                        optimal_uplinks_received = optimal_downlinks_df_all_dl_confirmed + optimal_uplinks_received_unconf
                        print(f"Optimal - Sent: {global_perf_sent}, Received conf: {optimal_uplinks_received_conf}, unconf: {optimal_uplinks_received_unconf}, total: {optimal_uplinks_received}")
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
                    FDR_UNCONF_OPTIMAL = optimal_uplinks_received_unconf / total_UNCONF_sent * 100 if total_UNCONF_sent  > 0 else 0

                    scenario_key = (gw, ed, percentage)
                    
                    if scenario_key not in FDR_EXPERIMENTS_RAW:
                        FDR_EXPERIMENTS_RAW[scenario_key] = []
                        FDR_EXPERIMENTS_CONF_RAW[scenario_key] = []
                        FDR_EXPERIMENTS_UNCONF_RAW[scenario_key] = []
                    
                    FDR_EXPERIMENTS_RAW[scenario_key].append({
                        "FDR_NO_DL": FDR_NO_DL,
                        "FDR_CUSTOM": FDR_CUSTOM,
                        "FDR_TTS": FDR_TTS,
                        "FDR_OPTIMAL": FDR_OPTIMAL
                    })

                    FDR_EXPERIMENTS_CONF_RAW[scenario_key].append({
                        "FDR_NO_DL": FDR_NO_DL,
                        "FDR_CUSTOM": FDR_CONF_CUSTOM,
                        "FDR_TTS": FDR_CONF_TTS,
                        "FDR_OPTIMAL": FDR_CONF_OPTIMAL
                    })
                    
                    FDR_EXPERIMENTS_UNCONF_RAW[scenario_key].append({
                        "FDR_NO_DL": FDR_NO_DL,
                        "FDR_CUSTOM": FDR_UNCONF_CUSTOM,
                        "FDR_TTS": FDR_UNCONF_TTS,
                        "FDR_OPTIMAL": FDR_UNCONF_OPTIMAL
                    })
                else:
                    print(f"Optimal uplinks file not found for gw: {gw}, ed: {ed}, percentage: {percentage}, seed: {seed}")

    # Compute averages, mins, and maxs for each scenario
    FDR_EXPERIMENTS = {}
    FDR_EXPERIMENTS_CONF = {}
    FDR_EXPERIMENTS_UNCONF = {}
    
    for scenario_key in FDR_EXPERIMENTS_RAW.keys():
        metrics = ["FDR_NO_DL", "FDR_CUSTOM", "FDR_TTS", "FDR_OPTIMAL"]
        
        # Process overall FDR experiments
        FDR_EXPERIMENTS[scenario_key] = {
            "avg": {metric: np.mean([v[metric] for v in FDR_EXPERIMENTS_RAW[scenario_key]]) for metric in metrics},
            "min": {metric: np.min([v[metric] for v in FDR_EXPERIMENTS_RAW[scenario_key]]) for metric in metrics},
            "max": {metric: np.max([v[metric] for v in FDR_EXPERIMENTS_RAW[scenario_key]]) for metric in metrics}
        }
        
        # Process confirmed experiments
        FDR_EXPERIMENTS_CONF[scenario_key] = {
            "avg": {metric: np.mean([v[metric] for v in FDR_EXPERIMENTS_CONF_RAW[scenario_key]]) for metric in metrics},
            "min": {metric: np.min([v[metric] for v in FDR_EXPERIMENTS_CONF_RAW[scenario_key]]) for metric in metrics},
            "max": {metric: np.max([v[metric] for v in FDR_EXPERIMENTS_CONF_RAW[scenario_key]]) for metric in metrics}
        }
        
        # Process unconfirmed experiments
        FDR_EXPERIMENTS_UNCONF[scenario_key] = {
            "avg": {metric: np.mean([v[metric] for v in FDR_EXPERIMENTS_UNCONF_RAW[scenario_key]]) for metric in metrics},
            "min": {metric: np.min([v[metric] for v in FDR_EXPERIMENTS_UNCONF_RAW[scenario_key]]) for metric in metrics},
            "max": {metric: np.max([v[metric] for v in FDR_EXPERIMENTS_UNCONF_RAW[scenario_key]]) for metric in metrics}
        }

    FDR_EXPERIMENTS = dict(sorted(FDR_EXPERIMENTS.items(), key=lambda x: (x[0][1], x[0][0])))
    FDR_EXPERIMENTS_CONF = dict(sorted(FDR_EXPERIMENTS_CONF.items(), key=lambda x: (x[0][1], x[0][0])))
    FDR_EXPERIMENTS_UNCONF = dict(sorted(FDR_EXPERIMENTS_UNCONF.items(), key=lambda x: (x[0][1], x[0][0])))
    print(FDR_EXPERIMENTS)
    return FDR_EXPERIMENTS, FDR_EXPERIMENTS_CONF, FDR_EXPERIMENTS_UNCONF
def plot_fdr_tout(FDR_TOUT,title):
    # Extract data for plotting
    labels = []
    fdr_no_dl_avg = []
    fdr_no_dl_min = []
    fdr_no_dl_max = []
    fdr_custom_avg = []
    fdr_custom_min = []
    fdr_custom_max = []
    fdr_tts_avg = []
    fdr_tts_min = []
    fdr_tts_max = []
    fdr_optimal_avg = []
    fdr_optimal_min = []
    fdr_optimal_max = []

    prev_ed = None  # To track the previous number of end devices
    segment_indices = []  # To track the indices where segments should break

    for key, value in FDR_TOUT.items():
        gw, ed, percentage = key
        label = f"({gw},{ed})"
        if label not in labels:
            labels.append(label)
            fdr_no_dl_avg.append(value["avg"]["FDR_NO_DL"])
            fdr_no_dl_min.append(value["min"]["FDR_NO_DL"])
            fdr_no_dl_max.append(value["max"]["FDR_NO_DL"])
            fdr_custom_avg.append(value["avg"]["FDR_CUSTOM"])
            fdr_custom_min.append(value["min"]["FDR_CUSTOM"])
            fdr_custom_max.append(value["max"]["FDR_CUSTOM"])
            fdr_tts_avg.append(value["avg"]["FDR_TTS"])
            fdr_tts_min.append(value["min"]["FDR_TTS"])
            fdr_tts_max.append(value["max"]["FDR_TTS"])
            fdr_optimal_avg.append(value["avg"]["FDR_OPTIMAL"])
            fdr_optimal_min.append(value["min"]["FDR_OPTIMAL"])
            fdr_optimal_max.append(value["max"]["FDR_OPTIMAL"])

            # Check if there's a transition in the number of end devices
            if prev_ed is not None and ed != prev_ed:
                segment_indices.append(len(labels) - 1)
            prev_ed = ed

    x = np.arange(len(labels))  # the label locations

    fig, ax = plt.subplots(figsize=(6, 4), facecolor='none')

    # Helper function to plot segments with error bars
    def plot_segments_with_errorbars(x, y_avg, y_min, y_max, label=None, **kwargs):
        start = 0
        y_err_lower = [avg - min_val for avg, min_val in zip(y_avg, y_min)]
        y_err_upper = [max_val - avg for max_val, avg in zip(y_max, y_avg)]
        
        for idx in segment_indices:
            ax.errorbar(x[start:idx], y_avg[start:idx], 
                       yerr=[y_err_lower[start:idx], y_err_upper[start:idx]], 
                       label=label if start == 0 else None, **kwargs, markeredgecolor='black')
            start = idx
        ax.errorbar(x[start:], y_avg[start:], 
                   yerr=[y_err_lower[start:], y_err_upper[start:]], 
                   label=label if start == 0 else None, **kwargs, markeredgecolor='black')

    # Plot the lines with error bars
    plot_segments_with_errorbars(x, fdr_no_dl_avg, fdr_no_dl_min, fdr_no_dl_max, 
                                 marker='o', label='NO DL', color='royalblue', alpha=0.8, linestyle='-', capsize=5, markersize=4)
    plot_segments_with_errorbars(x, fdr_tts_avg, fdr_tts_min, fdr_tts_max, 
                                 marker='^', label='TTS', color='orange', alpha=0.8, linestyle='-.', capsize=5, markersize=4)    
    plot_segments_with_errorbars(x, fdr_custom_avg, fdr_custom_min, fdr_custom_max, 
                                 marker='s', label='SFTS', color='seagreen', alpha=0.8, linestyle='--', capsize=5, markersize=4)
    plot_segments_with_errorbars(x, fdr_optimal_avg, fdr_optimal_min, fdr_optimal_max, 
                                 marker='d', label='Optimal', color='salmon', alpha=0.8, linestyle=':', capsize=5, markersize=4)

    # Add some text for labels, title and custom x-axis tick labels, etc.
    ax.set_xlabel('(gw,ed)', fontsize=11)
    ax.set_ylabel('UL FDR (%)', fontsize=11)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=10)

    # Set y-axis limits
    ax.set_ylim(25, 100)
    ax.set_yticks(np.arange(30, 101, 10))  # Set yticks in steps of 10
    ax.tick_params(axis='y', labelsize=10)

    # Add grid
    ax.grid(True)
    ax.set_axisbelow(True)

    # Add legend for only the first segments
    ax.legend(fontsize=11, loc='upper center', bbox_to_anchor=(0.5, 1.28), ncol=4, frameon=False, columnspacing=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=10)

    # Adjust layout and show the plot
    plt.tight_layout()
    plt.savefig(f"Figures/FDR_TOUT_Comparison_Line_{title}.pdf")
def plot_ack_bars_ori(av_scenario, metrics,title):
    # Extract unique percentages and gateways
    end_devices = sorted(set(key[1] for key in av_scenario.keys()))
    gateways = sorted(set(key[0] for key in av_scenario.keys()))
    periods = sorted(set(key[2] for key in av_scenario.keys()))
    percentages = sorted(set(key[3] for key in av_scenario.keys()))

    for metric_group in metrics:
        labels = []
        avg_ack = {percentage: {metric: [] for metric in metric_group} for percentage in percentages}
        min_ack = {percentage: {metric: [] for metric in metric_group} for percentage in percentages}
        max_ack = {percentage: {metric: [] for metric in metric_group} for percentage in percentages}
        for end_device in end_devices:
            for gateway in gateways:
                labels.append(f"GW{gateway}")
                for period in periods:
                    for percentage in percentages:
                        key = (gateway,end_device,period, percentage)
                        for metric in metric_group:
                            if key in av_scenario:
                                avg_ack[percentage][metric].append(av_scenario[key][metric])
                                min_ack[percentage][metric].append(av_scenario[key][metric+"_min"])
                                max_ack[percentage][metric].append(av_scenario[key][metric+"_max"])
                            else:
                                avg_ack[percentage][metric].append(0)
                                min_ack[percentage][metric].append(0)
                                max_ack[percentage][metric].append(0)

        x = np.arange(len(labels))
        width = 0.2  # Adjusted width for thinner bars
        spacing = width / 4  # spacing between bars of the same gateway

        fig, axes = plt.subplots(1, len(metric_group), figsize=(5 * len(metric_group), 3))

        if len(metric_group) == 1:
            axes = [axes]

        colors = ['skyblue', 'lightgreen', 'salmon', 'orange', 'violet']
        for metric_idx, metric in enumerate(metric_group):
            for idx, percentage in enumerate(percentages):
                axes[metric_idx].bar(x + (idx - 1.5) * (width + spacing), avg_ack[percentage][metric], width, 
                                     label=f'{percentage}%', color=colors[idx], 
                                     yerr=[np.array(avg_ack[percentage][metric]) - np.array(min_ack[percentage][metric]), 
                                           np.array(max_ack[percentage][metric]) - np.array(avg_ack[percentage][metric])], capsize=3)

        for metric_idx, metric in enumerate(metric_group):
            axes[metric_idx].set_ylabel('Percentage')
            axes[metric_idx].set_title(f'{metric}')
            axes[metric_idx].set_xticks(x)
            axes[metric_idx].set_xticklabels(labels)
            axes[metric_idx].legend()
            axes[metric_idx].set_ylim(0, 100)  # Set the same ylim for all plots
            axes[metric_idx].grid(True, which='both', linestyle='--', linewidth=0.5)
            for metric_idx, metric in enumerate(metric_group):
                axes[metric_idx].set_ylabel('Percentage')
                axes[metric_idx].set_xlabel('Gateways')
                axes[metric_idx].set_title(f'{metric}')
                axes[metric_idx].set_xticks(x)
                axes[metric_idx].set_xticklabels(labels)
                axes[metric_idx].legend(ncol=4, loc='upper center', fontsize='small')
                axes[metric_idx].set_ylim(0, 120)  # Set the same ylim for all plots
                axes[metric_idx].grid(True, which='both', linestyle='--', linewidth=0.5)

        plt.suptitle(f'File: {title}', fontsize=16)
        plt.tight_layout()
def plot_ack_bars(av_scenarios, metric, scenario_labels, title):
    # Extract unique values for gateways, periods, and percentages
    gateways = sorted(set(key[0] for scenario in av_scenarios for key in scenario.keys()))
    percentages = sorted(set(key[3] for scenario in av_scenarios for key in scenario.keys()))

    width = 0.2  # Width of each bar
    spacing = width / 4  # Spacing between bars of the same gateway
    colors = colors_TTS_CUS_OP 


    for percentage in percentages:
        fig, ax = plt.subplots(figsize=(5, 3))  # Reduced figure size
        x = np.arange(len(gateways))  # Positions for gateways on the x-axis

        for scenario_idx, (av_scenario, label) in enumerate(zip(av_scenarios, scenario_labels)):
            avg_values = []
            min_values = []
            max_values = []

            for gateway in gateways:
                # Find the key corresponding to the current gateway and percentage
                key = next((k for k in av_scenario.keys() if k[0] == gateway and k[3] == percentage), None)
                if key:
                    avg_values.append(av_scenario[key][metric])
                    min_values.append(av_scenario[key][f"{metric}_min"])
                    max_values.append(av_scenario[key][f"{metric}_max"])
                else:
                    avg_values.append(0)
                    min_values.append(0)
                    max_values.append(0)

            # Plot bars for the current scenario
            ax.bar(x + (scenario_idx - len(av_scenarios) / 2) * (width + spacing), avg_values, width,
                   label=label, color=colors[scenario_idx % len(colors)],
                   yerr=[np.array(avg_values) - np.array(min_values),
                         np.array(max_values) - np.array(avg_values)], capsize=3)

        #ax.set_title(f'{percentage}% Confirm Traffic', fontsize=12)  # Reduced title font size
        ax.set_xticks(x)
        ax.set_xticklabels([f'GW{gateway}' for gateway in gateways], rotation=45, ha="right", fontsize=12)  # Reduced x-axis label font size
        ax.set_ylabel(f'{metric}', fontsize=12)  # Reduced y-axis label font size
        ax.set_xlabel('Gateways', fontsize=12)  # Reduced x-axis label font size
        ax.grid(True, which='both', linestyle='--', linewidth=0.5)
        ax.legend(loc='upper right', fontsize='small')  # Reduced legend font size
        ax.set_ylim(0, 100)
        ax.yaxis.set_major_locator(plt.MultipleLocator(5))  # Increase the number of ticks on the y-axis
        ax.tick_params(axis='y', labelsize=12)  # Reduced size of the y-axis tick labels
        ax.tick_params(axis='x', labelsize=12)  # Reduced size of the x-axis tick labels

        plt.tight_layout()
        last_part = title.split('/')[-1]
        filename = f'Figures/mod_{metric}_{percentage}_{last_part.replace(" ", "_").replace("%", "")}.pdf'
        filename = filename.replace("%", "")
        plt.savefig(filename)
def plot_ack_bars_ed(av_scenarios, metric, scenario_labels, title):
    # Extract unique values for end devices, gateways, and percentages
    end_devices = sorted(set(key[1] for scenario in av_scenarios for key in scenario.keys()))
    gateways = sorted(set(key[0] for scenario in av_scenarios for key in scenario.keys()))
    percentages = sorted(set(key[3] for scenario in av_scenarios for key in scenario.keys()))

    # Create (gw, ed) pairs sorted by end device then gateway
    gw_ed_pairs = sorted([(gw, ed) for gw in gateways for ed in end_devices], key=lambda x: (x[1], x[0]))

    # Adapt bar width and spacing based on number of scenarios
    num_scenarios = len(av_scenarios)
    total_bar_width = 0.4  # Total width allocated for all bars at each tick
    width = total_bar_width / num_scenarios  # Width of each bar
    spacing = width * 0.1  # Small spacing between bars
    colors = colors_TTS_CUS_OP 

    # Adjust figure size based on number of pairs
    fig_width = max(9, 2 + len(gw_ed_pairs) * 0.6)

    for percentage in percentages:
        fig, ax = plt.subplots(figsize=(fig_width, 4.5))
        x = np.arange(len(gw_ed_pairs))  # Positions for gw_ed pairs on the x-axis

        for scenario_idx, (av_scenario, label) in enumerate(zip(av_scenarios, scenario_labels)):
            avg_values = []
            min_values = []
            max_values = []

            for gw, ed in gw_ed_pairs:
                # Find the key corresponding to the current gw, ed pair and percentage
                key = next((k for k in av_scenario.keys() if k[0] == gw and k[1] == ed and k[3] == percentage), None)
                if key:
                    avg_values.append(av_scenario[key][metric])
                    min_values.append(av_scenario[key][f"{metric}_min"])
                    max_values.append(av_scenario[key][f"{metric}_max"])
                else:
                    avg_values.append(0)
                    min_values.append(0)
                    max_values.append(0)

            # Center bars around tick: offset = (scenario_idx - (num_scenarios - 1) / 2) * (width + spacing)
            offset = (scenario_idx - (num_scenarios - 1) / 2) * (width + spacing)
            ax.bar(x + offset, avg_values, width,
                   label=label, color=colors[scenario_idx % len(colors)],
                   yerr=[np.array(avg_values) - np.array(min_values),
                         np.array(max_values) - np.array(avg_values)], capsize=4)

        #ax.set_title(f'{percentage}% Confirm Traffic', fontsize=14)  # Reduced title font size
        ax.set_xticks(x)
        ax.set_xticklabels([f'({ed},{gw})' for gw, ed in gw_ed_pairs], rotation=45, ha="right", fontsize=14)
        ax.set_ylabel(f'{metric}', fontsize=14)
        ax.set_xlabel('(ed, gw)', fontsize=14)
        ax.grid(True, which='both', linestyle='--', linewidth=0.5)
        ax.legend(loc='upper center', bbox_to_anchor=(0.5, 1.22), fontsize=13, ncol=len(av_scenarios))  # Legend outside plot on top
        ax.set_ylim(0, 100)
        ax.set_xlim(-0.5, len(gw_ed_pairs) - 0.5)
        ax.yaxis.set_major_locator(plt.MultipleLocator(10))  # Increase the number of ticks on the y-axis
        ax.tick_params(axis='y', labelsize=14)
        ax.tick_params(axis='x', labelsize=14)

        plt.tight_layout()
        last_part = title.split('/')[-1]
        filename = f'Figures/mod_{metric}_{percentage}_{last_part.replace(" ", "_").replace("%", "")}.pdf'
        filename = filename.replace("%", "")
        plt.savefig(filename)

def plot_ack_bars_original(av_scenario, metrics, title):
    # Extract unique values for end devices, gateways, periods, and percentages
    end_devices = sorted(set(key[0] for key in av_scenario.keys()))
    gateways = sorted(set(key[1] for key in av_scenario.keys()))
    periods = sorted(set(key[2] for key in av_scenario.keys()))
    percentages = sorted(set(key[3] for key in av_scenario.keys()))

    # Create combinations of percentages and periods for x-axis labels
    x_labels = [(percentage, period) for percentage in percentages for period in periods]

    for metric_group in metrics:
        labels = []
        avg_ack = {key: {metric: [] for metric in metric_group} for key in av_scenario.keys()}
        min_ack = {key: {metric: [] for metric in metric_group} for key in av_scenario.keys()}
        max_ack = {key: {metric: [] for metric in metric_group} for key in av_scenario.keys()}

        for key in av_scenario.keys():
            end_device, gateway, period, percentage = key
            label = f"ED{end_device}_GW{gateway}"
            labels.append(label)
            for metric in metric_group:
                avg_ack[key][metric].append(av_scenario[key][metric])
                min_ack[key][metric].append(av_scenario[key][metric + "_min"])
                max_ack[key][metric].append(av_scenario[key][metric + "_max"])

        x = np.arange(len(x_labels))
        width = 0.2  # Adjusted width for thinner bars
        spacing = width / 4  # spacing between bars of the same key

        fig, axes = plt.subplots(1, len(metric_group), figsize=(5 * len(metric_group), 4))  # Slightly increased height

        if len(metric_group) == 1:
            axes = [axes]

        colors = ['skyblue', 'lightgreen', 'salmon', 'orange', 'violet']
        for metric_idx, metric in enumerate(metric_group):
            for idx, (percentage, period) in enumerate(x_labels):
                for key in av_scenario.keys():
                    if key[2] == period and key[3] == percentage:
                        axes[metric_idx].bar(x[idx] + (end_devices.index(key[0]) + gateways.index(key[1]) - 1.5) * (width + spacing),
                                             avg_ack[key][metric], width,
                                             label=f'GW:{key[0]}' if idx == 0 else "", color=colors[(end_devices.index(key[0]) + gateways.index(key[1])) % len(colors)],
                                             yerr=[np.array(avg_ack[key][metric]) - np.array(min_ack[key][metric]),
                                                   np.array(max_ack[key][metric]) - np.array(avg_ack[key][metric])], capsize=3)

        for metric_idx, metric in enumerate(metric_group):
            axes[metric_idx].set_ylabel(f'{metric}')
            axes[metric_idx].set_xticks(x)
            axes[metric_idx].set_xticklabels([f'({percentage},{period})' for percentage, period in x_labels], rotation=45, ha="right")
            axes[metric_idx].legend(loc='upper center', bbox_to_anchor=(0.5, 1.15), ncol=4, fontsize='small')
            axes[metric_idx].set_ylim(0, 100)  # Set the same ylim for all plots
            axes[metric_idx].set_yticks(np.arange(0, 101, 10))  # Add more ticks on the y-axis
            axes[metric_idx].grid(True, which='both', linestyle='--', linewidth=0.5)
        plt.tight_layout()
        last_part = title.split('/')[-1]
        print(metric_group)
        if len(metric_group) == 2:
            plt.savefig(f'Figures/Rx_windows_{last_part.replace(" ", "_")}.pdf')
        else:
            plt.savefig(f'Figures/ACK_{last_part.replace(" ", "_")}.pdf')

        plt.suptitle(f'File: {title}', fontsize=16)

def create_report(av_scenario_1, av_scenario_2, av_scenario_3, output_file):
    # Extract unique keys from all scenarios
    all_keys = set(av_scenario_1.keys()).union(av_scenario_2.keys()).union(av_scenario_3.keys())
    all_keys = sorted(all_keys, key=lambda x: (x[0], x[1], x[2], x[3]))  # Sort by GW, ED, Period, CT

    # Initialize the report data
    report_data = []

    # Iterate through all keys and collect data
    for key in all_keys:
        gw, ed, period, percentage = key
        row = {
            "GW": gw,
            "ED": ed,
            "Period": period,
            "CT%": percentage,
        }

        # Add average data for TTS Normal, Threshold, and Optimal
        row.update({
            "TTS Normal ACK% (Avg)": av_scenario_1[key]["ACK%"] if key in av_scenario_1 else None,
            "TTS Threshold ACK% (Avg)": av_scenario_2[key]["ACK%"] if key in av_scenario_2 else None,
            "Optimal ACK% (Avg)": av_scenario_3[key]["ACK%"] if key in av_scenario_3 else None,
            "TTS Normal Rx1% (Avg)": av_scenario_1[key]["Rx1%"] if key in av_scenario_1 else None,
            "TTS Threshold Rx1% (Avg)": av_scenario_2[key]["Rx1%"] if key in av_scenario_2 else None,
            "Optimal Rx1% (Avg)": av_scenario_3[key]["Rx1%"] if key in av_scenario_3 else None,
            "TTS Normal Rx2% (Avg)": av_scenario_1[key]["Rx2%"] if key in av_scenario_1 else None,
            "TTS Threshold Rx2% (Avg)": av_scenario_2[key]["Rx2%"] if key in av_scenario_2 else None,
            "Optimal Rx2% (Avg)": av_scenario_3[key]["Rx2%"] if key in av_scenario_3 else None,
        })

        # Add min data for TTS Normal, Threshold, and Optimal
        row.update({
            "TTS Normal ACK% (Min)": av_scenario_1[key]["ACK%_min"] if key in av_scenario_1 else None,
            "TTS Threshold ACK% (Min)": av_scenario_2[key]["ACK%_min"] if key in av_scenario_2 else None,
            "Optimal ACK% (Min)": av_scenario_3[key]["ACK%_min"] if key in av_scenario_3 else None,
            "TTS Normal Rx1% (Min)": av_scenario_1[key]["Rx1%_min"] if key in av_scenario_1 else None,
            "TTS Threshold Rx1% (Min)": av_scenario_2[key]["Rx1%_min"] if key in av_scenario_2 else None,
            "Optimal Rx1% (Min)": av_scenario_3[key]["Rx1%_min"] if key in av_scenario_3 else None,
            "TTS Normal Rx2% (Min)": av_scenario_1[key]["Rx2%_min"] if key in av_scenario_1 else None,
            "TTS Threshold Rx2% (Min)": av_scenario_2[key]["Rx2%_min"] if key in av_scenario_2 else None,
            "Optimal Rx2% (Min)": av_scenario_3[key]["Rx2%_min"] if key in av_scenario_3 else None,
        })

        # Add max data for TTS Normal, Threshold, and Optimal
        row.update({
            "TTS Normal ACK% (Max)": av_scenario_1[key]["ACK%_max"] if key in av_scenario_1 else None,
            "TTS Threshold ACK% (Max)": av_scenario_2[key]["ACK%_max"] if key in av_scenario_2 else None,
            "Optimal ACK% (Max)": av_scenario_3[key]["ACK%_max"] if key in av_scenario_3 else None,
            "TTS Normal Rx1% (Max)": av_scenario_1[key]["Rx1%_max"] if key in av_scenario_1 else None,
            "TTS Threshold Rx1% (Max)": av_scenario_2[key]["Rx1%_max"] if key in av_scenario_2 else None,
            "Optimal Rx1% (Max)": av_scenario_3[key]["Rx1%_max"] if key in av_scenario_3 else None,
            "TTS Normal Rx2% (Max)": av_scenario_1[key]["Rx2%_max"] if key in av_scenario_1 else None,
            "TTS Threshold Rx2% (Max)": av_scenario_2[key]["Rx2%_max"] if key in av_scenario_2 else None,
            "Optimal Rx2% (Max)": av_scenario_3[key]["Rx2%_max"] if key in av_scenario_3 else None,
        })

        report_data.append(row)

    # Convert the report data to a DataFrame
    report_df = pd.DataFrame(report_data)

    # Save the report to a CSV file
    report_df.to_csv(output_file, index=False)


def computation_FDR_UPLINKS_old(optimal, tts, custom_tts):
    """Compute Frame Delivery Rate (FDR) for uplinks.

    Each scenario (gw, ed, percentage) may contain multiple experiment seeds.
    Per-seed FDR values are collected and then averaged to produce the final result.

    Returns three dicts keyed by (gw, ed, percentage):
        FDR_EXPERIMENTS        – overall FDR (confirmed + unconfirmed)
        FDR_EXPERIMENTS_CONF   – confirmed traffic only
        FDR_EXPERIMENTS_UNCONF – unconfirmed traffic only
    """
    template_headers = [
        "Time", "ID", "Address", "FType", "X", "Y", "Z", "GWDist", "Data Rate",
        "Tx Power", "Tx", "CTx", "UCTx", "Rx", "CRx", "UCRx", "HD-CUL", "HD-UUL",
        "TXdl", "Rxdl", "Rx1", "Rx2", "Rx1_s", "Rx2_s", "Rx1_dc", "Rx2_dc",
        "MaxOT", "OT"
    ]

    def fdr(numerator, denominator):
        return numerator / denominator * 100 if denominator > 0 else 0.0

    global_perf_files = glob.glob(os.path.join(tts, "*_GlobalPerf.csv"))
    print(f"Found {len(global_perf_files)} GlobalPerf files.")

    # raw[(gw, ed, percentage)] = list of per-seed result dicts
    raw = {}

    for global_perf_file in global_perf_files:
        gw_m  = re.search(r'_gateway_(\d+)_',    global_perf_file)
        ed_m  = re.search(r'log_N_ED_(\d+)_',    global_perf_file)
        pct_m = re.search(r'percentage_(\d+)_',  global_perf_file)
        sd_m  = re.search(r'seed_(\d+)_',        global_perf_file)

        if not all([gw_m, ed_m, pct_m, sd_m]):
            print(f"Skipping {global_perf_file}: could not parse all parameters.")
            continue

        gw         = int(gw_m.group(1))
        ed         = int(ed_m.group(1))
        percentage = int(pct_m.group(1))
        seed       = int(sd_m.group(1))

        # Locate matching files for this seed
        t_gp  = f"*_gateway_{gw}_seed_{seed}_percentage_{percentage}_log_N_ED_{ed}_GlobalPerf.csv"
        t_opt = f"*_gateway_{gw}_percentage_{percentage}_log_N_ED_{ed}_log_downlinks_{seed}_uplinks.csv"
        t_ed  = f"*_gateway_{gw}_seed_{seed}_percentage_{percentage}_log_N_ED_{ed}_EndDevicesOut.csv"

        custom_gp_files  = glob.glob(os.path.join(custom_tts, t_gp))
        optimal_ul_files = glob.glob(os.path.join(optimal,    t_opt))
        custom_ed_files  = glob.glob(os.path.join(custom_tts, t_ed))
        tts_ed_files     = glob.glob(os.path.join(tts,        t_ed))

        if not all([custom_gp_files, optimal_ul_files, custom_ed_files, tts_ed_files]):
            print(f"Missing files for gw={gw}, ed={ed}, %={percentage}, seed={seed} — skipping.")
            continue

        custom_gp_file       = custom_gp_files[0]
        optimal_uplinks_file = optimal_ul_files[0]
        custom_uplinks_file  = custom_ed_files[0]
        tts_uplinks_file     = tts_ed_files[0]

        # Read summary CSVs
        custom_gp_df  = pd.read_csv(custom_gp_file,    delimiter=',', skipinitialspace=True,
                                     usecols=["Time", "Sent", "Received", "Busy"])
        global_perf_df = pd.read_csv(global_perf_file, delimiter=',', skipinitialspace=True,
                                     usecols=["Time", "Sent", "Received", "Busy"])

        # Read per-device CSVs
        custom_ed   = pd.read_csv(custom_uplinks_file, delimiter=',', usecols=template_headers, skipinitialspace=True)
        tts_ed      = pd.read_csv(tts_uplinks_file,    delimiter=',', usecols=template_headers, skipinitialspace=True)

        total_sent        = tts_ed["Tx"].sum()
        total_conf_sent   = tts_ed["CTx"].sum()
        total_unconf_sent = tts_ed["UCTx"].sum()

        # Parse optimal uplink log
        opt_ul_conf   = extract_table_with_headers(optimal_uplinks_file, desired_headers_UL2, 4)
        opt_ul_unconf = extract_table_with_headers(optimal_uplinks_file, desired_headers_UL2, 2)
        opt_dl        = extract_table_with_headers(optimal_uplinks_file, desired_headers,     3)

        opt_conf_rx   = opt_dl.shape[0]
        opt_unconf_rx = opt_ul_unconf[opt_ul_unconf["received"] == "1"].shape[0]
        opt_total_rx  = opt_conf_rx + opt_unconf_rx

        custom_gp_rx = custom_gp_df["Received"].sum() + custom_gp_df["Busy"].sum()

        seed_result = {
            "all": {
                "FDR_NO_DL":   fdr(custom_gp_rx,                                                    total_sent),
                "FDR_CUSTOM":  fdr(custom_ed["TXdl"].sum() + custom_ed["UCRx"].sum(),               total_sent),
                "FDR_TTS":     fdr(tts_ed["TXdl"].sum()    + tts_ed["UCRx"].sum(),                  total_sent),
                "FDR_OPTIMAL": fdr(opt_total_rx,                                                     total_sent),
            },
            "conf": {
                "FDR_NO_DL":   fdr(custom_gp_rx,                  total_sent),
                "FDR_CUSTOM":  fdr(custom_ed["TXdl"].sum(),        total_conf_sent),
                "FDR_TTS":     fdr(tts_ed["TXdl"].sum(),           total_conf_sent),
                "FDR_OPTIMAL": fdr(opt_conf_rx,                    total_conf_sent),
            },
            "unconf": {
                "FDR_NO_DL":   fdr(custom_gp_rx,                  total_sent),
                "FDR_CUSTOM":  fdr(custom_ed["UCRx"].sum(),        total_unconf_sent),
                "FDR_TTS":     fdr(tts_ed["UCRx"].sum(),           total_unconf_sent),
                "FDR_OPTIMAL": fdr(opt_unconf_rx,                  total_unconf_sent),
            },
        }

        scenario_key = (gw, ed, percentage)
        raw.setdefault(scenario_key, []).append(seed_result)
        print(f"  gw={gw}, ed={ed}, %={percentage}, seed={seed} — processed.")

    # Average all seeds for each scenario
    def average_sub(entries, sub_key):
        keys = entries[0][sub_key].keys()
        return {k: float(np.mean([e[sub_key][k] for e in entries])) for k in keys}

    FDR_EXPERIMENTS        = {}
    FDR_EXPERIMENTS_CONF   = {}
    FDR_EXPERIMENTS_UNCONF = {}

    for scenario_key, entries in sorted(raw.items(), key=lambda x: (x[0][1], x[0][0])):
        n = len(entries)
        print(f"Scenario {scenario_key}: averaging over {n} seed(s).")
        FDR_EXPERIMENTS[scenario_key]        = average_sub(entries, "all")
        FDR_EXPERIMENTS_CONF[scenario_key]   = average_sub(entries, "conf")
        FDR_EXPERIMENTS_UNCONF[scenario_key] = average_sub(entries, "unconf")

    return FDR_EXPERIMENTS, FDR_EXPERIMENTS_CONF, FDR_EXPERIMENTS_UNCONF


def plot_fdr_tout_old(FDR_TOUT, title):
    """Plot uplink Frame Delivery Rate comparison across scenarios.

    FDR_TOUT is keyed by (gw, ed, percentage) — the averaged output of
    computation_FDR_UPLINKS.  Segments are broken whenever the number of
    end devices changes, so the x-axis groups are visually separated.
    """
    labels         = []
    fdr_no_dl      = []
    fdr_custom     = []
    fdr_tts        = []
    fdr_optimal    = []
    segment_indices = []
    prev_ed        = None

    for (gw, ed, percentage), value in FDR_TOUT.items():
        label = f"({gw},{ed})"
        if label in labels:
            continue

        labels.append(label)
        fdr_no_dl.append(value["FDR_NO_DL"])
        fdr_custom.append(value["FDR_CUSTOM"])
        fdr_tts.append(value["FDR_TTS"])
        fdr_optimal.append(value["FDR_OPTIMAL"])

        if prev_ed is not None and ed != prev_ed:
            segment_indices.append(len(labels) - 1)
        prev_ed = ed

    x = np.arange(len(labels))

    fig, ax = plt.subplots(figsize=(6, 3), facecolor='none')

    def plot_segments(y_vals, label, marker, color, linestyle):
        """Draw a broken line whose gaps coincide with ED-group transitions."""
        start = 0
        for idx in segment_indices:
            ax.plot(x[start:idx], y_vals[start:idx],
                    label=label if start == 0 else None,
                    marker=marker, color=color, linestyle=linestyle,
                    alpha=0.8, markeredgecolor='black')
            start = idx
        ax.plot(x[start:], y_vals[start:],
                label=label if start == 0 else None,
                marker=marker, color=color, linestyle=linestyle,
                alpha=0.8, markeredgecolor='black')

    plot_segments(fdr_no_dl,   label='NO DL',             marker='o', color='royalblue', linestyle='-')
    plot_segments(fdr_tts,     label='TTS',               marker='^', color='orange',    linestyle='-.')
    plot_segments(fdr_custom,  label='TTS with threshold', marker='s', color='seagreen',  linestyle='--')
    plot_segments(fdr_optimal, label='OPTIMAL',           marker='d', color='salmon',    linestyle=':')

    ax.set_xlabel('(gw, ed)', fontsize=12)
    ax.set_ylabel('UL FDR (%)', fontsize=12)
    ax.set_ylim(25, 100)
    ax.set_yticks(np.arange(30, 101, 10))
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=9)
    ax.grid(True)
    ax.set_axisbelow(True)
    ax.legend(fontsize=9, loc='upper center', bbox_to_anchor=(0.5, 1.2),
              ncol=4, frameon=False, columnspacing=0.5)

    plt.tight_layout()
    os.makedirs("Figures", exist_ok=True)
    plt.savefig(f"Figures/FDR_TOUT_Comparison_Line_{title}.pdf")


