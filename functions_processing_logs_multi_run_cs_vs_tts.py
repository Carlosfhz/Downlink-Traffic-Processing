#This is for processing the logs only 
import sys
import pandas as pd
import os
import glob
import matplotlib
import re
import numpy as np
import seaborn as sns
import json
import csv

#matplotlib.use('TkAgg')  # Use 'MacOSX' if you're on macOS
import matplotlib.pyplot as plt




desired_headers = ["senderId", "receiverID", "sendTime", "receivedTime", "SF", "SNR", "Ftype", "Freq", "RX"]
desired_headers_UL = ["senderId", "receiverID", "sendTime", "receivedTime", "SF", "SNR", "Ftype", "Freq","received","code",""]

desired_headers_UL2 = ["senderId", "receiverID", "sendTime", "receivedTime", "SF", "SNR", "Ftype", "Freq","received","code"]
headers_lost = ["HDsenderId", "HDreceiverID", "HDsendTime", "receivedTime", "SF", "SNR", "Ftype"]

def extract_parameters(filename,withSeed = False):
    gateway_match = re.search(r'gateway_(\d+)', filename)
    period_match = re.search(r'period_(\d+)', filename)
    percentage_match = re.search(r'percentage_(\d+)', filename)
    end_device_match = re.search(r'N_ED_(\d+)', filename)
    seed_match = re.search(r'seed_(\d+)', filename) if withSeed else None
    
    if gateway_match and end_device_match:
        gateway = int(gateway_match.group(1))
        end_devices = int(end_device_match.group(1))
        period = int(period_match.group(1))
        percentage = int(percentage_match.group(1))
        if withSeed and seed_match:
            seed = int(seed_match.group(1))
            return gateway, end_devices,period,percentage,seed
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
    dataframe["Blocked Time"] = dataframe["ToA"] * dataframe["RX"].map({1: 99, 2: 90}).fillna(0)


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

    #columns_to_drop = ["SNR"]
    #df.drop(columns=[col for col in columns_to_drop if col in df], inplace=True)
    if "RX" in headers:
        df = add_calculated_columns_DL(df,type)



    return df
def process_Tables(tabUL, tabDL):
    ED_stats = {}
    SF_stats = {}
    summary_stats = {"count_all_UL":0,"ACK": 0, "CUL": 0,"HD":0, "Rx1": 0, "Rx2": 0,"Blocked_Rx1": 0, "Blocked_Rx2": 0,"unusedTime_Rx1_sub_1": 0,"unusedTime_Rx1_sub_2": 0, "unusedTime_Rx2": 0,"ULTX":0,"UCRx":0}
    suband_1 = ["8.681e+08", "8.683e+08", "8.685e+08"]
    suband_2 = ["8.671e+08", "8.673e+08", "8.675e+08", "8.677e+08", "8.679e+08"]
    max_gw = int(tabUL["receiverID"].max())
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
        
            Rx1_Tab = receiver_rows[(receiver_rows['RX'] == 1) & (receiver_rows['SNR'] != '0')]
            Rx2_Tab = receiver_rows[(receiver_rows['RX'] == 2) & (receiver_rows['SNR'] != '0')]
            #Rx1_Tab = receiver_rows[(receiver_rows['RX'] == 1) & (receiver_rows['SNR'] != 0)]
            #Rx2_Tab = receiver_rows[(receiver_rows['RX'] == 2) & (receiver_rows['SNR'] != 0)]
            Rx_1_sub1 = Rx1_Tab[Rx1_Tab['Freq'].isin(suband_1)]
            Rx_1_sub2 = Rx1_Tab[Rx1_Tab['Freq'].isin(suband_2)]
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
            summary_stats["Blocked_Rx1"] += Rx1_Tab["Blocked Time"].sum()
            summary_stats["Blocked_Rx2"] += Rx2_Tab["Blocked Time"].sum()
            summary_stats["unusedTime_Rx1_sub_1"] += Rx_1_sub1["ToA"].sum()
            summary_stats["unusedTime_Rx1_sub_2"] += Rx_1_sub2["ToA"].sum()
            summary_stats["unusedTime_Rx2"] += Rx2_Tab["ToA"].sum()


    print(max_gw )
    if max_gw > 0:
        summary_stats["unusedTime_Rx1_sub_1"] /= max_gw 
        summary_stats["unusedTime_Rx1_sub_2"] /= max_gw 
        summary_stats["unusedTime_Rx2"] /= max_gw    
    else:
        print("Warning: max_gw is 0, division skipped to avoid ZeroDivisionError.")

    SF_stats = dict(sorted(SF_stats.items(), key=lambda item: int(item[0])))
    return ED_stats, SF_stats, summary_stats



def plot_matrices(sf_values, gw_ed_combinations, ack_matrix, rx_matrix_1,rx_matrix_2,Title):
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
            "Rx1%": np.mean([data["Rx1"] / data["ACK"]  * 100 for data in data_list]),
            "Rx2%": np.mean([data["Rx2"] /data["ACK"]  * 100 for data in data_list]),
            "Rx1_t%": np.mean([data["Rx1"] / data["CUL"]  * 100 for data in data_list]),
            "Rx2_t%": np.mean([data["Rx2"] /data["CUL"]  * 100 for data in data_list]),
            "ACK%_max": np.max([data["ACK"] / data["CUL"] * 100 for data in data_list]),
            "HD%_max": np.max([data["HD"] / data["count_all_UL"] * 100 for data in data_list]),
            "Rx1%_max": np.max([data["Rx1"] / data["ACK"]  * 100 for data in data_list]),
            "Rx2%_max": np.max([data["Rx2"] / data["ACK"]  * 100 for data in data_list]),
            "Rx1_t%_max": np.max([data["Rx1"] / data["CUL"]  * 100 for data in data_list]),
            "Rx2_t%_max": np.max([data["Rx2"] / data["CUL"]  * 100 for data in data_list]),
            "Blocked_Rx1": np.mean([data["Blocked_Rx1"] for data in data_list]),
            "ACK%_min": np.min([data["ACK"] / data["CUL"] * 100 for data in data_list]),
            "HD%_min": np.min([data["HD"] / data["count_all_UL"] * 100 for data in data_list]),
            "Rx1%_min": np.min([data["Rx1"] / data["ACK"]  * 100 for data in data_list]),
            "Rx2%_min": np.min([data["Rx2"] / data["ACK"]  * 100 for data in data_list]),
            "Rx1_t%_min": np.min([data["Rx1"] / data["CUL"]  * 100 for data in data_list]),
            "Rx2_t%_min": np.min([data["Rx2"] / data["CUL"]  * 100 for data in data_list]),
            "unusedTime_Rx1_sub1": np.mean([100*(1-data["unusedTime_Rx1_sub_1"]/36) for data in data_list]),
            "unusedTime_Rx1_sub2": np.mean([100*(1-data["unusedTime_Rx1_sub_2"]/36) for data in data_list]),
            "unusedTime_Rx1_sub1_max": np.max([100*(1-data["unusedTime_Rx1_sub_1"]/36) for data in data_list]),
            "unusedTime_Rx1_sub2_max": np.max([100*(1-data["unusedTime_Rx1_sub_2"]/36) for data in data_list]),
            "unusedTime_Rx1_sub1_min": np.min([100*(1-data["unusedTime_Rx1_sub_1"]/36) for data in data_list]),
            "unusedTime_Rx1_sub2_min": np.min([100*(1-data["unusedTime_Rx1_sub_2"]/36) for data in data_list]),
            "unusedTime_Rx2": np.mean([100*(1-data["unusedTime_Rx2"]/360) for data in data_list]),
            "unusedTime_Rx2_max": np.max([100*(1-data["unusedTime_Rx2"]/360) for data in data_list]),
            "unusedTime_Rx2_min": np.min([100*(1-data["unusedTime_Rx2"]/360) for data in data_list]),

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
                avg_scenario_data_per_SF[key][sf]["Rx1%"].append(metrics["Rx1"] /metrics["ACK"] * 100)
                avg_scenario_data_per_SF[key][sf]["Rx2%"].append(metrics["Rx2"] / metrics["ACK"] * 100)
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

def scenario_sort_key(x):
    tup = eval(x) if isinstance(x, str) else x
    # tup: (gw, ed, T, CT)
    return (tup[0], tup[3], tup[2])
def plot_ack_heatmap_per_sf(avg_scenario_data_per_SF,server):
    # Get all scenario keys and SFs
    scenario_keys = list(avg_scenario_data_per_SF.keys())
    # Sort scenario keys: first by gw, then by CT, then by T

    scenario_keys = sorted(scenario_keys, key=scenario_sort_key)
    # Get all SFs (as strings)
    all_sfs = set()
    for v in avg_scenario_data_per_SF.values():
        all_sfs.update(str(sf) for sf in v.keys())
    sf_list = sorted(all_sfs, key=int)
    # Build the heatmap matrix
    heatmap_data = []
    for sf in sf_list:
        row = []
        for scenario in scenario_keys:
            sf_dict = avg_scenario_data_per_SF[scenario]
            if sf in sf_dict and "ACK%" in sf_dict[sf]:
                row.append(sf_dict[sf]["ACK%"])
            else:
                row.append(float('nan'))
        heatmap_data.append(row)
    # Plot
    plt.figure(figsize=(8, 4))
    ax = sns.heatmap(heatmap_data,  annot=True, fmt=".0f",cmap="coolwarm",xticklabels=[str(k) for k in scenario_keys],yticklabels=sf_list,vmin=0, vmax=100, cbar_kws={'label': 'ACK%'} )
    ax.set_xlabel("Scenario (GW, ED, T, CT)")
    ax.set_ylabel("Spreading Factor")
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    filename = f'Figures/heatmaps_{server}_per_SF.pdf'
    plt.savefig(filename)

    plt.title("ACK% per SF and Scenario")
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
def plot_ack_bars(av_scenarios, metric, scenario_labels, title, shades,lim=100):
    # Extract unique values for percentages, end devices, periods, and gateways
    percentages = sorted(set(key[3] for scenario in av_scenarios for key in scenario.keys()))
    end_devices = sorted(set(key[1] for scenario in av_scenarios for key in scenario.keys()))
    periods = sorted(set(key[2] for scenario in av_scenarios for key in scenario.keys()))
    gateways = sorted(set(key[0] for scenario in av_scenarios for key in scenario.keys()))

    width = 0.2  # Width of each bar
    spacing = width / 4  # Spacing between bars of the same category
    colors = ['skyblue', 'lightgreen', 'salmon', 'orange', 'violet']

    for gateway in gateways:
        fig, ax = plt.subplots(figsize=(5, 4))  # Reduced figure size
        x_labels = []  # Labels for the x-axis
        x_positions = []  # Positions for the x-axis labels
        avg_values = {label: [] for label in scenario_labels}
        min_values = {label: [] for label in scenario_labels}
        max_values = {label: [] for label in scenario_labels}

        for percentage in percentages:
            for end_device in end_devices:
                for period in periods:
                    x_labels.append(f'({gateway},{percentage},{end_device},{period})')
                    x_positions.append(len(x_labels) - 1)
                    for av_scenario, label in zip(av_scenarios, scenario_labels):
                        key = (gateway, end_device, period, percentage)
                        if key in av_scenario:
                            avg_values[label].append(av_scenario[key][metric])
                            min_values[label].append(av_scenario[key][f"{metric}_min"])
                            max_values[label].append(av_scenario[key][f"{metric}_max"])
                        else:
                            avg_values[label].append(0)
                            min_values[label].append(0)
                            max_values[label].append(0)

        # Plot bars for each scenario
        for scenario_idx, label in enumerate(scenario_labels):
            ax.bar(
                np.array(x_positions) + (scenario_idx - (len(scenario_labels) - 1) / 2) * (width + spacing),
                avg_values[label],
                width,
                label=label,
                color=colors[scenario_idx % len(colors)],
                #edgecolor='black',
                yerr=[
                    np.array(avg_values[label]) - np.array(min_values[label]),
                    np.array(max_values[label]) - np.array(avg_values[label]),
                ],
                capsize=3,
                hatch=shades[scenario_idx % len(shades)]
            )


        ax.set_xticks(x_positions)
        # Exclude GW from x_labels in x-tick labels (show only (CT,ED,T))
        ax.set_xticklabels(
            [f"({','.join(lbl.split(',')[1:]).replace(')', '')})" if lbl.startswith('(') else lbl for lbl in x_labels],
            rotation=45, ha="right", fontsize=8
        )
        ax.set_ylabel(title.replace('_', ' '), fontsize=12)  # Increased y-axis label font size
        ax.set_xlabel('(CT,ED,T)', fontsize=12)  # Changed x-axis label as requested
        ax.grid(True, which='both', linestyle='--', linewidth=0.5)
        ax.legend(loc='upper left', fontsize='small')  # Adjusted legend font size
        ax.set_ylim(0, lim)
        if lim < 100 and lim !=1:
            multiple = 5   
        elif lim ==1:
            multiple = 0.1 
        else:
            multiple = 10
        ax.yaxis.set_major_locator(plt.MultipleLocator(multiple))  # Increase the number of ticks on the y-axis
        ax.tick_params(axis='y', labelsize=10)  # Increased y-axis tick label size
        ax.tick_params(axis='x', labelsize= 10)  # Increased x-axis tick label size
        plt.tight_layout()
        last_part = title.split('/')[-1]
        filename = f'Figures/ordered_{metric}_GW{gateway}_{last_part.replace(" ", "_").replace("%", "")}.pdf'
        plt.savefig(filename)
        ax.set_title(f'{metric} Comparison for Gateway {gateway}', fontsize=10)  # Reduced title font size


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


def extract_files_and_parameters(directories, labels):
    results = {}
    stats_per_ED = {} 

    for directory, label in zip(directories, labels):
        # Get all files ending with '_EndDevicesOut.csv' in the directory
        print(f"Processing directory: {directory}")
        files = glob.glob(os.path.join(directory, "*_EndDevicesOut.csv"))
        results[label] = {}
        stats_per_ED[label] = {}
        jains_index = {}
        jains_index_toa = {}
        gini_index = {}
        median_per_SF = {}
        # Initialize dictionaries to store computed indices
        unfairness = {}
        median_ratio = {}
        ack_coverage = {}
        ack_variance = {}
        FDR = {}
        FDR_cul = {}
        FDR_UUL = {}
        FDR_UUL_total = {}
        FDR_cul_total = {}
        ack_percentage_by_dr = {}
        for file in files:
             # Extract parameters from the file name
            gw, ed, period, percentage = extract_parameters(file)
            # Read the CSV file
            extracted_table = pd.read_csv(file, sep=',')
            print(f"Processing file: {file} with parameters GW: {gw}, ED: {ed}, Period: {period}, Percentage: {percentage}")
            #print(extracted_table)
            # Filter rows where Ftype is equal to 4
            # Remove spaces from all column names in the extracted_table
            extracted_table.columns = extracted_table.columns.str.replace(' ', '')
            extracted_table = extracted_table.apply(pd.to_numeric, errors='coerce').fillna(0).astype(int)
            extrated_table_copy = extracted_table.copy()

            extracted_table = extracted_table[extracted_table["FType"] == 4]
            extracted_table = extracted_table[extracted_table["CRx"] > 0]
            extracted_table["ACK_Percentage"] = extracted_table["Rxdl"] / (extracted_table["CRx"])
            #extracted_table["ACK_Percentage"] = extracted_table["Rxdl"] / extracted_table["CRx"]
            

            # Add ToA computation to the extracted table
            extracted_table["ToA"] = extracted_table.apply(lambda row: compute_time_on_air(12 - row["DataRate"]), axis=1)
            # Calculate ToA for RX1 and RX2 windows
            extracted_table["ToA_RX1"] = extracted_table.apply(lambda row: compute_time_on_air(12 - row["DataRate"]) if row["Rx1"] > 0 else 0, axis=1)
            extracted_table["ToA_RX2"] = extracted_table.apply(lambda row: compute_time_on_air(10) if row["Rx2"] > 0 else 0, axis=1)  # RX2 typically uses SF12 (DR0)
            # Calculate total access time per end device
            extracted_table["Total_Access_Time"] = ((extracted_table["Rx1"] * extracted_table["ToA_RX1"]) + (extracted_table["Rx2"] * extracted_table["ToA_RX2"]))
            
            # Compute Jain's Index for ACK_Percentage
            if (gw, ed, period, percentage) not in jains_index:
                jains_index[(gw, ed, period, percentage)] = []
                jains_index_toa[(gw, ed, period, percentage)] = []
                gini_index[(gw, ed, period, percentage)] = []
                unfairness[(gw, ed, period, percentage)] = []
                median_ratio[(gw, ed, period, percentage)] = []
                ack_coverage[(gw, ed, period, percentage)] = []
                ack_variance[(gw, ed, period, percentage)] = []
                FDR[(gw, ed, period, percentage)] = []
                FDR_cul[(gw, ed, period, percentage)] = []
                FDR_UUL[(gw, ed, period, percentage)] = []
                FDR_cul_total[(gw, ed, period, percentage)] = []
                FDR_UUL_total[(gw, ed, period, percentage)] = []
                median_per_SF[(gw, ed, period, percentage)]= {7:[],8:[],9:[],10:[],11:[],12:[]}
            # Compute ACK percentage by data rate (SF)  
            
            for dr in range(6):  # Data rates 0 to 5
                dr_rows = extracted_table[extracted_table["DataRate"] == dr]
                if len(dr_rows) > 0:
                    median_per_SF[(gw, ed, period, percentage)][12-dr].append(dr_rows["ACK_Percentage"].median())

            
            # Calculate Jain's Index and Gini Index for ACK_Percentage
            #ack_percentages = extracted_table["Total_Access_Time"].values
            #ack_percentages = extrated_table_copy["UCRx"]+extrated_table_copy["Rxdl"] /extrated_table_copy["Tx"]
            ack_percentages = extracted_table["ACK_Percentage"].values
            jains_index[(gw, ed, period, percentage)].append((np.sum(ack_percentages) ** 2) / (len(ack_percentages) * np.sum(ack_percentages ** 2)) if len(ack_percentages) > 0 else 0)

            ack_percentages = extracted_table["Total_Access_Time"].values
            jains_index_toa[(gw, ed, period, percentage)].append((np.sum(ack_percentages) ** 2) / (len(ack_percentages) * np.sum(ack_percentages ** 2)) if len(ack_percentages) > 0 else 0)

            gini_index[(gw, ed, period, percentage)].append( 1 - np.sum((ack_percentages / np.sum(ack_percentages)) ** 2) if np.sum(ack_percentages) > 0 else 0   )  
            FDR[(gw, ed, period, percentage)].append((np.sum(extrated_table_copy["UCRx"])+np.sum(extrated_table_copy["Rxdl"])) / np.sum(extrated_table_copy["Tx"]) if np.sum(extrated_table_copy["Tx"]) > 0 else 0)
            FDR_UUL[(gw, ed, period, percentage)].append(np.sum(extrated_table_copy["UCRx"]) / np.sum(extrated_table_copy["UCTx"]) if np.sum(extrated_table_copy["Tx"]) > 0 else 0)
            FDR_cul[(gw, ed, period, percentage)].append(np.sum(extrated_table_copy["Rxdl"]) / np.sum(extrated_table_copy["CTx"]) if np.sum(extrated_table_copy["Tx"]) > 0 else 0)
            FDR_UUL_total[(gw, ed, period, percentage)].append(np.sum(extrated_table_copy["UCRx"]) / np.sum(extrated_table_copy["Tx"]) if np.sum(extrated_table_copy["Tx"]) > 0 else 0)
            FDR_cul_total[(gw, ed, period, percentage)].append(np.sum(extrated_table_copy["Rxdl"]) / np.sum(extrated_table_copy["Tx"]) if np.sum(extrated_table_copy["Tx"]) > 0 else 0)

            # Calculate the actual ratio of successfully acknowledged packets to uplink packets received by the NS
            # Compute the actual ratio for each ED: ratio of successfully acknowledged packets to uplink packets received by the NS
            if extracted_table["Rxdl"].sum() > 0:
                actual_ratios = extracted_table["Rxdl"] / extracted_table["CRx"]
            else:
                actual_ratios = np.zeros(len(extracted_table))

            # Unfairness: standard deviation of the actual ratio between the number of successfully acknowledged packets
            # and the number of uplink packets received by the NS (i.e., std of actual_ratios)
            unfairness[(gw, ed, period, percentage)].append(np.std(actual_ratios))
            ack_variance[(gw, ed, period, percentage)].append(np.var(actual_ratios))
            ack_coverage[(gw, ed, period, percentage)].append(sum(1 for ack in extracted_table["Rxdl"]  if ack > 0) / len(extracted_table["Rxdl"]))
            
            
            # Compute the median of the ratios
            median_ratio[(gw, ed, period, percentage)].append(np.median(actual_ratios))        

        for gw, ed, period, percentage in jains_index.keys():
            # Store the computed indices in the results dictionary
            if (gw, ed, period, percentage) not in results[label]:
                results[label][gw, ed, period, percentage] = {}
            results[label][gw, ed, period, percentage] = {
                "Jains_Index": np.average(jains_index[gw, ed, period, percentage]),
                "Jains_Index_max": np.max(jains_index[gw, ed, period, percentage]),
                "Jains_Index_min": np.min(jains_index[gw, ed, period, percentage]),
                "Jains_Index_toa": np.average(jains_index_toa[gw, ed, period, percentage]),
                "Jains_Index_toa_max": np.max(jains_index_toa[gw, ed, period, percentage]),
                "Jains_Index_toa_min": np.min(jains_index_toa[gw, ed, period, percentage]),
                "Gini_Index": np.average(gini_index[gw, ed, period, percentage]),
                "Gini_Index_max": np.max(gini_index[gw, ed, period, percentage]),
                "Gini_Index_min": np.min(gini_index[gw, ed, period, percentage]),
                "Std": np.average(unfairness[gw, ed, period, percentage]),
                "Std_max": np.max(unfairness[gw, ed, period, percentage]),
                "Std_min": np.min(unfairness[gw, ed, period, percentage]),
                "ACK_Coverage": np.average(ack_coverage[gw, ed, period, percentage]),
                "ACK_Coverage_max": np.max(ack_coverage[gw, ed, period, percentage]),
                "ACK_Coverage_min": np.min(ack_coverage[gw, ed, period, percentage]),
                "ACK_Variance": np.average(ack_variance[gw, ed, period, percentage]),
                "ACK_Variance_max": np.max(ack_variance[gw, ed, period, percentage]),
                "ACK_Variance_min": np.min(ack_variance[gw, ed, period, percentage]),
                "Median_Ratio": np.average(median_ratio[gw, ed, period, percentage]),
                "Median_Ratio_max": np.max(median_ratio[gw, ed, period, percentage]),
                "Median_Ratio_min": np.min(median_ratio[gw, ed, period, percentage]),
                "FDR": 100*np.average(FDR[gw, ed, period, percentage]),
                "FDR_max": 100*np.max(FDR[gw, ed, period, percentage]),
                "FDR_min": 100*np.min(FDR[gw, ed, period, percentage]),
                "FDR_UUL": 100*np.average(FDR_UUL[gw, ed, period, percentage]),
                "FDR_UUL_max": 100*np.max(FDR_UUL[gw, ed, period, percentage]),
                "FDR_UUL_min": 100*np.min(FDR_UUL[gw, ed, period, percentage]),
                "FDR_cul": 100*np.average(FDR_cul[gw, ed, period, percentage]),
                "FDR_cul_max": 100*np.max(FDR_cul[gw, ed, period, percentage]),
                "FDR_cul_min": 100*np.min(FDR_cul[gw, ed, period, percentage]),
                "FDR_UUL_total": 100*np.average(FDR_UUL_total[gw, ed, period, percentage]),
                "FDR_UUL_total_max": 100*np.max(FDR_UUL_total[gw, ed, period, percentage]),
                "FDR_UUL_total_min": 100*np.min(FDR_UUL_total[gw, ed, period, percentage]),
                "FDR_cul_total": 100*np.average(FDR_cul_total[gw, ed, period, percentage]),
                "FDR_cul_total_max": 100*np.max(FDR_cul_total[gw, ed, period, percentage]),
                "FDR_cul_total_min": 100*np.min(FDR_cul_total[gw, ed, period, percentage]),
                "mean_per_SF": {
                    7: np.average(median_per_SF[gw, ed, period, percentage][7]),
                    8: np.average(median_per_SF[gw, ed, period, percentage][8]),
                    9: np.average(median_per_SF[gw, ed, period, percentage][9]),
                    10: np.average(median_per_SF[gw, ed, period, percentage][10]),
                    11: np.average(median_per_SF[gw, ed, period, percentage][11]),
                    12: np.average(median_per_SF[gw, ed, period, percentage][12])
                },
                "mean_per_SF_max": {
                    7: np.max(median_per_SF[gw, ed, period, percentage][7]) if median_per_SF[gw, ed, period, percentage][7] else None,
                    8: np.max(median_per_SF[gw, ed, period, percentage][8]) if median_per_SF[gw, ed, period, percentage][8] else None,
                    9: np.max(median_per_SF[gw, ed, period, percentage][9]) if median_per_SF[gw, ed, period, percentage][9] else None,
                    10: np.max(median_per_SF[gw, ed, period, percentage][10]) if median_per_SF[gw, ed, period, percentage][10] else None,
                    11: np.max(median_per_SF[gw, ed, period, percentage][11]) if median_per_SF[gw, ed, period, percentage][11] else None,
                    12: np.max(median_per_SF[gw, ed, period, percentage][12]) if median_per_SF[gw, ed, period, percentage][12] else None
                },
                "mean_per_SF_min": {
                    7: np.min(median_per_SF[gw, ed, period, percentage][7]) if median_per_SF[gw, ed, period, percentage][7] else None,
                    8: np.min(median_per_SF[gw, ed, period, percentage][8]) if median_per_SF[gw, ed, period, percentage][8] else None,
                    9: np.min(median_per_SF[gw, ed, period, percentage][9]) if median_per_SF[gw, ed, period, percentage][9] else None,
                    10: np.min(median_per_SF[gw, ed, period, percentage][10]) if median_per_SF[gw, ed, period, percentage][10] else None,
                    11: np.min(median_per_SF[gw, ed, period, percentage][11]) if median_per_SF[gw, ed, period, percentage][11] else None,
                    12: np.min(median_per_SF[gw, ed, period, percentage][12]) if median_per_SF[gw, ed, period, percentage][12] else None
                },
                "ACK_Percentage": extracted_table
            }

            

            # Compute the average ACK percentage          

    print(results)
    return results, stats_per_ED
def Plot_process_per_ED(stats_per_ED):
    for label, scenarios in stats_per_ED.items():
        gateways = sorted(set(scenario[0] for scenario in scenarios.keys()))
        percentages_periods = sorted(set((scenario[3], scenario[2]) for scenario in scenarios.keys()))

        for gw in gateways:
            plt.figure(figsize=(10, 6))
            plt.title(f"ACK Percentage Distribution for Label: {label}, GW: {gw}", fontsize=14)

            ack_percentages_all = []
            x_labels = []

            for percentage, period in percentages_periods:
                ack_percentages = []
                for scenario, data in scenarios.items():
                    if scenario[0] == gw and scenario[3] == percentage and scenario[2] == period:
                        ack_percentages.extend(data["ACK_Percentage"])

                if ack_percentages:
                    ack_percentages_all.append(ack_percentages)
                    x_labels.append(f"CT%: {percentage}, T: {period}")

            if ack_percentages_all:
                plt.boxplot(ack_percentages_all, patch_artist=True, 
                            boxprops=dict(facecolor='skyblue', color='blue'),
                            medianprops=dict(color='red'), whiskerprops=dict(color='blue'), 
                            capprops=dict(color='blue'), showfliers=False)
                plt.xticks(range(1, len(x_labels) + 1), x_labels, rotation=45, ha="right")
                plt.xlabel("Scenarios")
                plt.ylabel("ACK Percentage")
                plt.grid(axis='y', linestyle='--', linewidth=0.5)

            plt.tight_layout()





def plot_Jains_index_combined(results, metric):
    # Extract unique labels from the results
    labels = results.keys()
    colors = ['skyblue', 'lightgreen', 'salmon', 'orange', 'violet', 'gold', 'gray']
    # Extract unique gateways, percentages, end devices, and periodicities across all labels
    gateways = sorted(set(key[0] for label in labels for key in results[label].keys()))
    percentages = sorted(set(key[3] for label in labels for key in results[label].keys()))
    end_devices = sorted(set(key[1] for label in labels for key in results[label].keys()))
    periodicities = sorted(set(key[2] for label in labels for key in results[label].keys()))

    # Group scenarios by the number of gateways
    scenarios_by_gw = {}
    for label in labels:
        for key in results[label].keys():
            gw = key[0]
            if gw not in scenarios_by_gw:
                scenarios_by_gw[gw] = []
            if key not in scenarios_by_gw[gw]:
                scenarios_by_gw[gw].append(key)

    for gw, scenarios in scenarios_by_gw.items():
        # Sort scenarios by percentage, then by periodicity in ascending order
        scenarios = sorted(scenarios, key=lambda x: (x[3], x[2]))

        x_labels = []
        jains_data_by_label = {label: [] for label in labels}
        mean_per_sf_data_by_label = {label: {sf: [] for sf in range(7, 13)} for label in labels}

        # Populate data for the current gateway
        for scenario in scenarios:
            percentage = scenario[3]
            period = scenario[2]
            ed = scenario[1]
            x_labels.append(f"({percentage},{ed},{period})")
            for label in labels:
                # Standard metric
                if scenario in results[label]:
                    if metric in results[label][scenario]:
                        value = results[label][scenario][metric]
                        # If value is a dict, skip or set None
                        if isinstance(value, dict):
                            jains_data_by_label[label].append(None)
                        else:
                            jains_data_by_label[label].append(value)
                    else:
                        jains_data_by_label[label].append(None)
                    # mean_per_SF metric
                    if "mean_per_SF" in results[label][scenario]:
                        for sf in range(7, 13):
                            sf_value = results[label][scenario]["mean_per_SF"].get(sf, None)
                            if isinstance(sf_value, dict):
                                mean_per_sf_data_by_label[label][sf].append(None)
                            else:
                                mean_per_sf_data_by_label[label][sf].append(sf_value)
                    else:
                        for sf in range(7, 13):
                            mean_per_sf_data_by_label[label][sf].append(None)
                else:
                    jains_data_by_label[label].append(None)
                    for sf in range(7, 13):
                        mean_per_sf_data_by_label[label][sf].append(None)


        # Plot all SFs in one plot if metric is "mean_per_SF"
        if metric == "mean_per_SF":
            for label in labels:
                fig_sf, ax_sf = plt.subplots(figsize=(6, 4))
                for sf in range(7, 13):
                    ax_sf.plot(x_labels, mean_per_sf_data_by_label[label][sf], marker='o', label=f'SF{sf}', color=colors[(sf-7) % len(colors)], linewidth=2, markeredgewidth=2, markeredgecolor='black', linestyle='-', alpha=0.8)
                ax_sf.set_xlabel("Scenario")
                ax_sf.set_ylabel(f"Median Ratio per SF")
                ax_sf.set_ylim(0, 1)
                ax_sf.set_xticks(range(len(x_labels)))
                ax_sf.set_xticklabels(x_labels, rotation=45, ha='center', fontsize=8)
                ax_sf.grid(True)
                ax_sf.legend(title="SF", fontsize='small')
                plt.tight_layout()
                filename_sf = f'Figures/FDR_mean_per_SF_ALLSF_GW{gw}_{label}.pdf'
                plt.savefig(filename_sf)
                ax_sf.set_title(f"Median Ratio for All SFs - GW{gw} - {label}")

        else:
            fig, ax = plt.subplots(figsize=(6, 4))
            for idx, (label, jains_data) in enumerate(jains_data_by_label.items()):
                # Group scenarios by CT (percentage)
                ct_groups = {}
                for i, scenario in enumerate(scenarios):
                    ct = scenario[3]
                    if ct not in ct_groups:
                        ct_groups[ct] = []
                    ct_groups[ct].append((i, jains_data[i]))

                # Plot each CT group separately, connecting only dots with the same CT
                for ct, points in ct_groups.items():
                    indices, values = zip(*[(idx, val) for idx, val in points if val is not None])
                    # Only add legend for the first label (scheduler), not for each CT group
                    legend_label = label if ct == min(ct_groups.keys()) else None
                    ax.plot([x_labels[i] for i in indices], values, marker='X', label=legend_label, color=colors[idx % len(colors)], linewidth=2, markeredgewidth=1, markeredgecolor='black', linestyle='--', alpha=0.8)
            ax.set_xlabel("(CT, ED, T)", fontsize=12)
            ax.set_ylabel(f"Average {metric.replace('_', ' ')}", fontsize=12)
            ax.set_ylim(0, 1)
            ax.set_xticks(range(len(x_labels)))
            ax.set_xticklabels(x_labels, rotation=45, ha='center', fontsize=10)
            ax.grid(True)
            ax.legend(fontsize=10)
            ax.tick_params(axis='y', labelsize=10)  # Make y-tick labels bigger
            plt.tight_layout()
            filename = f'Figures/FDR_{metric}_GW{gw}.pdf'
            plt.savefig(filename)
            ax.set_title(f"{metric} Index for {gw} Gateways")
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

def process_results_file_precise(file_path,file_path2, headers=["timestamp","results"]):
    print(file_path)
    with open(file_path, 'r') as file:
        lines = file.readlines()
        table_lines = [line.strip() for line in lines if line.strip()]
        data = [row.split(',', 1) for row in table_lines]
    headers2 = ["Time", "ID", "Address", "FType", "X", "Y", 
                "Z", "GWDist", "Data Rate", "Tx Power", "Tx",
                "CTx", "UCTx", "Rx", "CRx", "UCRx", "HD-CUL",
                "HD-UUL", "TXdl", "Rxdl", "Rx1", "Rx2", "Rx1_s",
                 "Rx2_s", "Rx1_dc", "Rx2_dc", "MaxOT", "OT"]

    with open(file_path2, 'r') as file:
        reader = csv.reader(file, delimiter=',', quotechar='"')
        data2 = [row for row in reader if row]  # Read and filter out empty rows

    df2 = pd.DataFrame(data2, columns=headers2)
    df2["CRx"] = pd.to_numeric(df2["CRx"], errors='coerce').fillna(0)
    df2["TXdl"] = pd.to_numeric(df2["TXdl"], errors='coerce').fillna(0)
    transmited_DL = df2["TXdl"].sum()
    received_CUL = df2["CRx"].sum()
    df = pd.DataFrame(data)
    df.columns = headers

    total_conflict = 0
    total_blocked = 0

    for index, row in df.iterrows():
        if index == 0:
            continue  # Skip header row if present in data

        cleaned_results = row["results"].strip().replace('""', '"')\
                                               .replace('"{', '{')\
                                               .replace('}"', '}')\
                                               .replace(',""', ',')\
                                               .replace('""}', '}')\
                                               .replace('"{', '{"')\
                                               .replace('}"', '"}')
        try:
            results = json.loads(cleaned_results)
        except json.JSONDecodeError:
            continue  # Skip invalid JSON rows
        blocked = 0
        conflict = 0
        for gw_data in results.values():
            for status in gw_data.values():
                if status == "blocked":
                    blocked += 1
                elif status == "conflict":
                    conflict += 1
        if blocked > conflict:
            total_blocked += 1
        else:   
            total_conflict += 1
        # Check if the status is "conflict" or "blocked"
        # Increment the respective counter
        # if status == "conflict":
    return total_conflict, total_blocked,received_CUL,transmited_DL
def process_results_file_UDP(file_path,file_path2, headers=["Timestamp", "Gateway", "Topic", "Traffic", "Message", "Decoded-Payload"]):
    print(file_path)
    with open(file_path, 'r') as file:
        reader = csv.reader(file, delimiter=',', quotechar='"')
        data = [row for row in reader if row]  # Read and filter out empty rows

    headers2 = ["Time", "ID", "Address", "FType", "X", "Y"
                                       , "Z", "GWDist", "Data Rate", "Tx Power", "Tx",
                                         "CTx", "UCTx", "Rx", "CRx", "UCRx", "HD-CUL",
                                           "HD-UUL", "TXdl", "Rxdl", "Rx1", "Rx2", "Rx1_s",
                                             "Rx2_s", "Rx1_dc", "Rx2_dc", "MaxOT", "OT"]

    with open(file_path2, 'r') as file:
        reader = csv.reader(file, delimiter=',', quotechar='"')
        data2 = [row for row in reader if row]  # Read and filter out empty rows



    # Create a DataFrame with the specified headers
    df = pd.DataFrame(data, columns=headers)
    df2 = pd.DataFrame(data2, columns=headers2)

    df = df[df["Traffic"] == 'ack']
    
    conflict_count = 0
    # Ensure Rx1_dc and Rx2_dc are numeric and handle missing values
    df2["Rx1_dc"] = pd.to_numeric(df2["Rx1_dc"], errors='coerce').fillna(0)
    df2["Rx2_dc"] = pd.to_numeric(df2["Rx2_dc"], errors='coerce').fillna(0)
    df2["CRx"] = pd.to_numeric(df2["CRx"], errors='coerce').fillna(0)
    df2["TXdl"] = pd.to_numeric(df2["TXdl"], errors='coerce').fillna(0)
    blocked_count = df2["Rx1_dc"].sum() + df2["Rx2_dc"].sum()
    received_CUL = df2["CRx"].sum()
    transmited_DL = df2["TXdl"].sum()
    # Extract the "Message" column from the DataFrame
    # Convert the string representation of the dictionary to an actual dictionary
    # Extract the "Message" column from the DataFrame
    # Convert the string representation of the dictionary to an actual dictionary
    # Extract the "Message" column from the DataFrame
    messages = df["Message"].tolist()  # Extract the "Message" column as a list
    for ack in messages:
        #print(ack)
        ack_data = json.loads(ack.replace("'", '"'))  # Convert the string to a dictionary
        items = ack_data.get("items", [])
        if any(item.get("status") == "NO" for item in items) and any(item.get("status") == "COLLISION_PACKET" for item in items):
            conflict_count += 1
    transmited_DL -=blocked_count
    return conflict_count, blocked_count,received_CUL,transmited_DL

    
def extract_non_scheduled_downlinks(file_path, file_path2,type):
    result_files_results = glob.glob(os.path.join(file_path2, "*_results.csv"))
    result_files_udp = glob.glob(os.path.join(file_path2, "*_UDP.csv"))

    stadistics_loss_packets = {}
    print(f"Processing files in directory: {file_path}")
    headers_DL = desired_headers
    headers_DL.append("")
    if type == "UDP":
        result_files = result_files_udp

    else:
        result_files = result_files_results

    for file in result_files:
        print(f"Processing result file: {file}")

    for file in result_files:
        gw, ed, period, percentage, seed = extract_parameters(file, True)
        if gw is None or ed is None or percentage is None:
            print(f"Skipping file: {file} (missing required information in filename)")
            continue
        matching_files = [
            f for f in glob.glob(os.path.join(file_path, "*_EndDevicesOut.csv"))
            if extract_parameters(f, True) == (gw,ed,period,percentage,seed)
        ]
        file2 = matching_files[0] if matching_files else None
        if type == "UDP":
            conflict_count, blocked_count,received_CUL,transmited_DL = process_results_file_UDP(file,file2)
        else:
            conflict_count, blocked_count,received_CUL,transmited_DL = process_results_file_precise(file,file2)
        print(f"Conflicts by receive window: {conflict_count}")
        print(f"Blocked by receive window: {blocked_count}")
        print(f"Received CUL: {received_CUL}")
        print(f"Transmitted DL: {transmited_DL}")

        datas = {
            "conflict": conflict_count,
            "blocked": blocked_count,
            "received_CUL": received_CUL,
            "transmited_DL": transmited_DL,
            "norm_alized_conflict": 100*conflict_count / (received_CUL) if received_CUL > 0 else 0,
            "norm_alized_blocked": 100*blocked_count / (received_CUL) if received_CUL > 0 else 0,
        }

        if (gw, ed, period, percentage) not in stadistics_loss_packets:
            stadistics_loss_packets[(gw, ed, period, percentage)] = []
        stadistics_loss_packets[(gw, ed, period, percentage)].append(datas)
    # Process the collected data to create a summary

    average_stadistics_loss_packets = {}
    for key, data_list in stadistics_loss_packets.items():
        # Extract lists of each metric
        conflicts = [d["conflict"] for d in data_list]
        blockeds = [d["blocked"] for d in data_list]
        received_CULs = [d["received_CUL"] for d in data_list]
        transmited_DLs = [d["transmited_DL"] for d in data_list]
        norm_alized_conflicts = [d["norm_alized_conflict"] for d in data_list]
        norm_alized_blockeds = [d["norm_alized_blocked"] for d in data_list]
        print("##Key##:",key)
        print("Conflicts:",conflicts)
        print("Blockeds:",blockeds)
        print("Received CULs:",received_CULs)
        print("Transmited DLs:",transmited_DLs)
        # Calculate averages, mins, and maxs
        average_stadistics_loss_packets[key] = {
            "conflict_avg": np.average(conflicts),
            "conflict_max": np.max(conflicts),
            "conflict_min": np.min(conflicts),
            "blocked_avg": np.average(blockeds),
            "blocked_max": np.max(blockeds),
            "blocked_min": np.min(blockeds),
            "received_CUL_avg": np.average(received_CULs),
            "received_CUL_max": np.max(received_CULs),
            "received_CUL_min": np.min(received_CULs),
            "transmited_DL_avg": np.average(transmited_DLs),
            "transmited_DL_max": np.max(transmited_DLs),
            "transmited_DL_min": np.min(transmited_DLs),
            "norm_alized_conflict_avg": np.average(norm_alized_conflicts),
            "norm_alized_conflict_max": np.max(norm_alized_conflicts),
            "norm_alized_conflict_min": np.min(norm_alized_conflicts),
            "norm_alized_blocked_avg": np.average(norm_alized_blockeds),
            "norm_alized_blocked_max": np.max(norm_alized_blockeds),
            "norm_alized_blocked_min": np.min(norm_alized_blockeds),
        }
    return average_stadistics_loss_packets
def plot_lost_causes(lost_Causes, normalized=False):
    scenarios = sorted({s for sch in lost_Causes for s in lost_Causes[sch]}, key=lambda x: (x[0], x[3], x[1], x[2]))
    schedulers = list(lost_Causes.keys())
    metric_conf = 'norm_alized_conflict_avg' if normalized else 'conflict_avg'
    metric_blocked = 'norm_alized_blocked_avg' if normalized else 'blocked_avg'
    lim = 100 if normalized else 10000
    scenarios_by_gw = {}
    colors = ['skyblue', 'lightgreen']
    for s in scenarios: scenarios_by_gw.setdefault(s[0], []).append(s)
    for gw, gw_scenarios in scenarios_by_gw.items():
        x = np.arange(len(gw_scenarios))
        width = 0.35
        fig1, ax1 = plt.subplots(figsize=(5, 4))
        fig2, ax2 = plt.subplots(figsize=(5, 4))
        for i, sch in enumerate(schedulers):
            get = lambda m: [lost_Causes[sch].get(s, {}).get(m, 0) for s in gw_scenarios]
            bar_pos = x + i * width * 2
            rx, rx_min, rx_max = get('received_CUL_avg'), get('received_CUL_min'), get('received_CUL_max')
            tx, tx_min, tx_max = get('transmited_DL_avg'), get('transmited_DL_min'), get('transmited_DL_max')
            ax1.bar(bar_pos, rx, width, label=f'{sch} - Rx CUL', edgecolor='black', alpha=0.4, color=f'C{i*2}', yerr=[np.abs(np.array(rx)-np.array(rx_min)), np.abs(np.array(rx_max)-np.array(rx))], capsize=3)
            ax1.bar(bar_pos+width, tx, width, label=f'{sch} - Tx DL', edgecolor='black', alpha=0.7, color=f'C{i*2}', yerr=[np.abs(np.array(tx)-np.array(tx_min)), np.abs(np.array(tx_max)-np.array(tx))], capsize=3)
            conf, block = get(metric_conf), get(metric_blocked)
            # Plot Conflict bars with error bars (min/max)
            conf_min = get(metric_conf.replace('avg', 'min'))
            conf_max = get(metric_conf.replace('avg', 'max'))
            block_min = get(metric_blocked.replace('avg', 'min'))
            block_max = get(metric_blocked.replace('avg', 'max'))
            
            # Add conflict and blocked values together for combined error bars
            combined_vals = np.array(conf) + np.array(block)
            combined_min = np.array(conf_min) + np.array(block_min)
            combined_max = np.array(conf_max) + np.array(block_max)

            # Plot Conflict and Blocked bars (stacked) with combined error bars
            spacing = width / 6  # Spacing between bars of the same category
            ax2.bar(x + i * width + i * spacing, conf, width, label=f'{sch} - Conflict', 
                   alpha=0.5, edgecolor='black', color=colors[i])
            ax2.bar(x + i * width + i * spacing, block, width, bottom=np.array(conf),
                   label=f'{sch} - Blocked', alpha=1, edgecolor='black', color=colors[i],
                   yerr=[np.abs(combined_vals - combined_min), np.abs(combined_max - combined_vals)],
                   capsize=3)
            for ax in [ax1, ax2]:
                ax.set_xlabel('(CT,ED,T)',fontsize=12)
                ax2.set_ylabel('Scheduling Failure (%)' if normalized else 'Counts', fontsize=12)

                ax.set_xticks(x + width * (len(schedulers) - 1) / 2)
                # Remove GW from x-tick labels: show only (CT,ED,T)
                ax.set_xticklabels([f'({s[3]},{s[1]},{s[2]})' for s in gw_scenarios], rotation=45, ha='right', fontsize=10)
                #ax.set_xticklabels([f'({s[0]},{s[3]},{s[1]},{s[2]})' for s in gw_scenarios], rotation=45, ha='right', fontsize=8)
                ax.grid(True, linestyle='--', alpha=0.7)
                ax.set_ylim(0, lim)
        ax1.legend(loc='upper right', fontsize='small', frameon=True)
        ax2.legend(loc='upper center', bbox_to_anchor=(0.5, 1.3), ncol=2, fontsize='small', frameon=True)
        fig1.tight_layout()
        fig2.tight_layout()
        fig1.savefig(f'Figures/lost_causes_tx_rx_GW{gw}_{"normalized" if normalized else "raw"}.pdf')
        fig2.savefig(f'Figures/lost_causes_conflict_blocked_GW{gw}_{"normalized" if normalized else "raw"}.pdf')
def compute_time_on_air(sf, payload_size=13):
                """
                Compute Time on Air (ToA) in milliseconds based on spreading factor and payload size.
                
                Args:
                    sf: Spreading Factor (7-12)
                    payload_size: Payload size in bytes (default 13 bytes for LoRaWAN)
                
                Returns:
                    Time on Air in milliseconds
                """
                # LoRaWAN parameters
                bw = 125000  # Bandwidth in Hz (125 kHz for EU868)
                cr = 4/5     # Code rate 4/5
                h = 0        # Header disabled
                de = 0       # Low data rate optimization disabled for SF7-11
                
                if sf >= 11:
                    de = 1   # Enable low data rate optimization for SF11-12
                
                # Symbol time
                ts = (2 ** sf) / bw * 1000  # in milliseconds
                
                # Preamble time
                t_preamble = (8 + 4.25) * ts
                
                # Payload symbol number
                payload_nb = 8 + max(0, np.ceil((8 * payload_size - 4 * sf + 28 + 16 - 20 * h) / (4 * (sf - 2 * de))) * (cr))
                
                # Payload time
                t_payload = payload_nb * ts
                
                # Total time on air
                toa = t_preamble + t_payload
                
                return toa