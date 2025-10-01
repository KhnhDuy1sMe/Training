import numpy as np
import pandas as pd
import json
from typing import Dict, List

# Support_function 
def create_gamma_map(filepath: str, max_vms: int, p_sla: float) -> List[int]:
    try:
        gamma_df = pd.read_csv(filepath)
    except FileNotFoundError:
        print(f"Error:'{filepath}' not found.")
        return None
    gamma_map = [0] * (max_vms + 1)
    grouped = gamma_df.groupby('n')
    for n in range(1, max_vms + 1):
        try:
            frame = grouped.get_group(n)
            suitable_rows = frame[frame['p_violate'] < p_sla]
            if not suitable_rows.empty:
                gamma_map[n] = int(suitable_rows['gamma'].min())
            else:
                gamma_map[n] = int(frame['gamma'].max())
        except KeyError:
            gamma_map[n] = n
    return gamma_map

def load_data_from_json(filepath: str) -> Dict:
    try:
        with open(filepath) as f:
            raw_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Data file at '{filepath}' not found.")
        return None
    initial_pm_count = len(raw_data)
    print(f"File info: Found {initial_pm_count} PM (host) in original JSON file.")
    data = {
        "vm_num": sum(len(pm.get("vms", [])) for pm in raw_data),
        "host_num": len(raw_data),
        "cpu_total": [pm.get("total_cpu", 0) for pm in raw_data],
        "mem_total": [int(pm.get("total_memory", 0)) for pm in raw_data],
        "threshold": [pm.get("threshold", 0.8) for pm in raw_data],
        "uc": [], "ur": [], "mem": [], "initial_vm_placement": {},
    }
    vm_index = 0
    for pm_index, pm in enumerate(raw_data):
        for vm in pm.get("vms", []):
            vcpus = vm.get("vcpus", 1)
            cpu_usage = np.array(vm.get("cpu_usage", [0])) * vcpus / 100
            if len(cpu_usage) < 20:
                cpu_max, cpu_min = np.max(cpu_usage), np.min(cpu_usage)
            else:
                cpu_max = np.percentile(cpu_usage, 90)
                cpu_min = np.percentile(cpu_usage, 10)
            data["uc"].append(int(((cpu_max + cpu_min) / 2) * 1000))
            data["ur"].append(int(((cpu_max - cpu_min) / 2) * 1000))
            data["mem"].append(int(vm.get("memory", 0)))
            data["initial_vm_placement"][vm_index] = pm_index
            vm_index += 1
    return data

# Gamma_FF_algorithm
def gamma_first_fit(data, gamma_map):
    vm_num = data["vm_num"]
    host_num = data["host_num"]
    vm_cpu = data["uc"]
    vm_ur = data["ur"]
    vm_mem = data["mem"]
    cpu_total = data["cpu_total"]
    mem_total = data["mem_total"]
    threshold = data["threshold"]

    hosts_state = []
    for j in range(host_num):
        hosts_state.append({
            "cpu_used": 0,
            "mem_used": 0,
            "vms": [],
            "gamma": 0
        })

    vm_assignment = [-1] * vm_num
    for i in range(vm_num):
        placed = False
        for j in range(host_num):
            # Number_of_VMs_after_migration
            n = len(hosts_state[j]["vms"]) + 1
            gamma = gamma_map[n] if n < len(gamma_map) else n

            # Usage_after_migration
            cpu_load = hosts_state[j]["cpu_used"] + vm_cpu[i] + vm_ur[i] * gamma
            cpu_cap = int(cpu_total[j] * threshold[j] * 1000)
            mem_load = hosts_state[j]["mem_used"] + vm_mem[i]

            if cpu_load <= cpu_cap and mem_load <= mem_total[j]:
                # Replace_VM_to_PM[j]
                hosts_state[j]["cpu_used"] += vm_cpu[i]
                hosts_state[j]["mem_used"] += vm_mem[i]
                hosts_state[j]["gamma"] = gamma
                hosts_state[j]["vms"].append(i)
                vm_assignment[i] = j
                placed = True
                break
        if not placed:
            print(f"Unable to distribute VM {i}")
    return vm_assignment, hosts_state

def main():
    # Data_from_files
    ROBUST_CSV_PATH = r'E:\VM 2025\robust_1000.csv'
    DATASET_JSON_PATH = r'E:\VM 2025\vm_offline_scheduling\dataset\200-0.json'
    P_SLA = 0.05

    # Load_data
    data = load_data_from_json(DATASET_JSON_PATH)
    if data is None: return
    gamma_map = create_gamma_map(ROBUST_CSV_PATH, data["vm_num"], P_SLA)
    if gamma_map is None: return

    # Apply_algorthim
    print("Running Gamma First-Fit algorithm...")
    vm_assignment, hosts_state = gamma_first_fit(data, gamma_map)

    # Results
    used_hosts = [j for j, h in enumerate(hosts_state) if len(h["vms"]) > 0]
    print(f"The number of used PMs: {len(used_hosts)}")
    for j in used_hosts:
        print(f"Host {j} include: {hosts_state[j]['vms']}")

    migs = sum(1 for i, j in enumerate(vm_assignment) if j != data["initial_vm_placement"][i])
    print(f"The number of migrated VMs: {migs}")

if __name__ == "__main__":
    main()
