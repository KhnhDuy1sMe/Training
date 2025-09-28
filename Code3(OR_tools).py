#or_tool(google)
import numpy as np
import pandas as pd
import json
from typing import Dict, List
from ortools.sat.python import cp_model

# --- HELPER FUNCTIONS ---

def create_gamma_map(filepath: str, max_vms: int, p_sla: float) -> List[int]:
    """Creates a map from the number of VMs to the required Gamma value."""
    try:
        gamma_df = pd.read_csv(filepath)
    except FileNotFoundError:
        print(f"Error: File not found at '{filepath}'.")
        return None
        
    gamma_map = [0] * (max_vms + 1)
    grouped = gamma_df.groupby('n')
    
    for n in range(1, max_vms + 1):
        try:
            frame = grouped.get_group(n)
            # Find the smallest gamma where p_violate < p_sla
            suitable_rows = frame[frame['p_violate'] < p_sla]
            if not suitable_rows.empty:
                gamma_map[n] = int(suitable_rows['gamma'].min())
            else:
                # If no row satisfies, take the largest gamma available
                gamma_map[n] = int(frame['gamma'].max())
        except KeyError:
            # If no data for n, assume worst-case gamma = n
            gamma_map[n] = n
            
    return gamma_map

def load_data_from_json(filepath: str) -> Dict:
    """Loads and processes data from the JSON file."""
    try:
        with open(filepath) as f:
            raw_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Data file not found at '{filepath}'.")
        return None

    print(f"File Info: Found {len(raw_data)} PMs (hosts) in the source JSON file.")
    
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
                cpu_max = np.percentile(cpu_usage, 95)
                cpu_min = np.percentile(cpu_usage, 5)
            
            # Scale CPU values to integers for the CP-SAT solver
            data["uc"].append(int(((cpu_max + cpu_min) / 2) * 1000))
            data["ur"].append(int(((cpu_max - cpu_min) / 2) * 1000))
            data["mem"].append(int(vm.get("memory", 0)))
            data["initial_vm_placement"][vm_index] = pm_index
            vm_index += 1
            
    return data

# --- MAIN FUNCTION (OR-Tools Version) ---

def main():
    # --- CONFIGURATION PARAMETERS ---
    ROBUST_CSV_PATH = r'E:\VM 2025\robust_1000.csv'
    DATASET_JSON_PATH = r'E:\VM 2025\vm_offline_scheduling\dataset\10-0.json'
    P_SLA = 0.05
    ALPHA = 10**3
    TIME_LIMIT = 3600.0 # Time limit in seconds

    # --- LOAD DATA ---
    data = load_data_from_json(DATASET_JSON_PATH)
    if data is None: return
    N_Gamma_map = create_gamma_map(ROBUST_CSV_PATH, data["vm_num"], P_SLA)
    if N_Gamma_map is None: return

    # --- BUILD THE CP-SAT MODEL ---
    model = cp_model.CpModel()

    # (PHẦN 1, 2, 3: KHAI BÁO BIẾN, RÀNG BUỘC, MỤC TIÊU - GIỮ NGUYÊN)
    x = {(i, j): model.NewBoolVar(f'x_{i}_{j}') for i in range(data["vm_num"]) for j in range(data["host_num"])}
    x_hat = {(i, j): model.NewBoolVar(f'x_hat_{i}_{j}') for i in range(data["vm_num"]) for j in range(data["host_num"])}
    y = {j: model.NewBoolVar(f'y_{j}') for j in range(data["host_num"])}
    H = {(j, k): model.NewBoolVar(f'H_{j}_{k}') for j in range(data["host_num"]) for k in range(data["vm_num"] + 1)}

    # (Toàn bộ phần ràng buộc và mục tiêu giữ nguyên)
    for i in range(data["vm_num"]):
        model.AddExactlyOne(x[i, j] for j in range(data["host_num"]))
    for i in range(data["vm_num"]):
        for j in range(data["host_num"]):
            model.Add(x_hat[i, j] <= x[i, j])
    for j in range(data["host_num"]):
        model.Add(sum(x[i, j] for i in range(data["vm_num"])) == sum(H[j, k] * k for k in range(data["vm_num"] + 1)))
        model.AddExactlyOne(H[j, k] for k in range(data["vm_num"] + 1))
    for j in range(data["host_num"]):
        model.Add(sum(x_hat[i, j] for i in range(data["vm_num"])) == sum(H[j, k] * N_Gamma_map[k] for k in range(data["vm_num"] + 1)))
    for j in range(data["host_num"]):
        cpu_load = sum(data["uc"][i] * x[i, j] for i in range(data["vm_num"])) + \
                   sum(data["ur"][i] * x_hat[i, j] for i in range(data["vm_num"]))
        capacity = int(data["cpu_total"][j] * data["threshold"][j] * 1000)
        model.Add(cpu_load <= capacity).OnlyEnforceIf(y[j])
    for j in range(data["host_num"]):
        mem_load = sum(data["mem"][i] * x[i, j] for i in range(data["vm_num"]))
        capacity = data["mem_total"][j]
        model.Add(mem_load <= y[j] * capacity)

    active_hosts_cost = ALPHA * sum(y[j] for j in range(data["host_num"]))
    migration_cost = sum(1 - x[i, data["initial_vm_placement"][i]] for i in range(data["vm_num"]))
    model.Minimize(active_hosts_cost + migration_cost)

    # --- PHẦN 4: GIẢI BÀI TOÁN ---
    solver = cp_model.CpSolver()
    solver.parameters.log_search_progress = True
    solver.parameters.max_time_in_seconds = TIME_LIMIT
    
    print(f"\nSolving the problem with {data['host_num']} PMs and {data['vm_num']} VMs (Time limit: {TIME_LIMIT}s)...")
    
    status = solver.Solve(model)

    # --- PHẦN 5: IN KẾT QUẢ (ĐÃ CẬP NHẬT) ---
    print("\n" + "="*40)
    print("--- OPTIMIZATION RESULTS ---")
    
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        active_set = [j for j in range(data["host_num"]) if solver.Value(y[j]) > 0.5]
        total_migrations = sum(1 - solver.Value(x[i, data["initial_vm_placement"][i]]) for i in range(data["vm_num"]))
        
        print(f"Status: {solver.StatusName(status)}")
        print(f"Objective function value: {solver.ObjectiveValue():.2f}")
        print(f"Active hosts (Active set): {len(active_set)} - {active_set}")
        print(f"Total VM migrations: {total_migrations:.0f}")

        # Khôi phục lại logic tính toán min_set và max_set
        x_set = {j: [] for j in range(data["host_num"])}
        min_set = {j: [] for j in range(data["host_num"])}
        max_set = {j: [] for j in range(data["host_num"])}
        host_vm_num = []

        for j in active_set:
            for k in range(data["vm_num"] + 1):
                if solver.Value(H[j, k]) > 0.5:
                    host_vm_num.append((j, k))
                    break
            
            for i in range(data["vm_num"]):
                if solver.Value(x[i, j]) > 0.5:
                    x_set[j].append(i)
                    if solver.Value(x_hat[i, j]) > 0.5:
                        max_set[j].append(i)
                    else:
                        min_set[j].append(i)

        # In thông tin chi tiết với nhãn đã thay đổi
        print("\n--- DETAILED ANALYSIS ---")
        print(f"Number of VMs on each host: {host_vm_num}")
        
        print("\nPlacement details per host:")
        for j in active_set:
            print(f"\n[Host {j}]")
            print(f"  - Total VMs: {len(x_set[j])}")
            print(f"  - VM list: {x_set[j]}")
            print(f"  - Max set: {max_set[j]}")
            print(f"  - Min set: {min_set[j]}")
            
        print("="*40)
    else:
        print(f"\nOptimal solution not found. Status: {solver.StatusName(status)}")

if __name__ == "__main__":
    main()
