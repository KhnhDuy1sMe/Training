import numpy as np
import pandas as pd
import json
from typing import Dict, List
from ortools.sat.python import cp_model

# --- HÀM HỖ TRỢ ---
def create_gamma_map(filepath: str, max_vms: int, p_sla: float) -> List[int]:
    try:
        gamma_df = pd.read_csv(filepath)
    except FileNotFoundError:
        print(f"Lỗi: Không tìm thấy file '{filepath}'.")
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
            full_raw_data = json.load(f)
    except FileNotFoundError:
        print(f"Lỗi: Không tìm thấy file dữ liệu tại '{filepath}'.")
        return None

    initial_pm_count = len(full_raw_data)
    print(f"Thông tin file: Tìm thấy {initial_pm_count} PM (host) trong file JSON gốc.")
    
    raw_data = full_raw_data

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
            
            data["uc"].append(int(((cpu_max + cpu_min) / 2) * 1000))
            data["ur"].append(int(((cpu_max - cpu_min) / 2) * 1000))
            data["mem"].append(int(vm.get("memory", 0)))
            data["initial_vm_placement"][vm_index] = pm_index
            vm_index += 1
    return data

# --- HÀM CHÍNH (Phiên bản OR-Tools) ---

def main():
    # --- THAM SỐ CẤU HÌNH ---
    ROBUST_CSV_PATH = r'E:\VM 2025\robust_1000.csv'
    DATASET_JSON_PATH = r'E:\VM 2025\vm_offline_scheduling\dataset\40-2.json'
    P_SLA = 0.05
    ALPHA = 10**3
    TIME_LIMIT = 3600.0 # Đặt giới hạn thời gian ở đây (tính bằng giây)

    # --- TẢI DỮ LIỆU ---
    data = load_data_from_json(DATASET_JSON_PATH)
    if data is None: return
    N_Gamma_map = create_gamma_map(ROBUST_CSV_PATH, data["vm_num"], P_SLA)
    if N_Gamma_map is None: return

    # --- XÂY DỰNG MÔ HÌNH CP-SAT ---
    model = cp_model.CpModel()

    # 1. ĐỊNH NGHĨA BIẾN
    x = {(i, j): model.NewBoolVar(f'x_{i}_{j}') for i in range(data["vm_num"]) for j in range(data["host_num"])}
    x_hat = {(i, j): model.NewBoolVar(f'x_hat_{i}_{j}') for i in range(data["vm_num"]) for j in range(data["host_num"])}
    y = {j: model.NewBoolVar(f'y_{j}') for j in range(data["host_num"])}
    H = {(j, k): model.NewBoolVar(f'H_{j}_{k}') for j in range(data["host_num"]) for k in range(data["vm_num"] + 1)}

    # 2. THÊM RÀNG BUỘC
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
        model.Add(cpu_load == 0).OnlyEnforceIf(y[j].Not())

    for j in range(data["host_num"]):
        mem_load = sum(data["mem"][i] * x[i, j] for i in range(data["vm_num"]))
        capacity = data["mem_total"][j]
        model.Add(mem_load <= y[j] * capacity)

    # 3. ĐỊNH NGHĨA HÀM MỤC TIÊU
    active_hosts_cost = ALPHA * sum(y[j] for j in range(data["host_num"]))
    migration_cost = sum(1 - x[i, data["initial_vm_placement"][i]] for i in range(data["vm_num"]))
    model.Minimize(active_hosts_cost + migration_cost)

    # 4. GIẢI BÀI TOÁN
    solver = cp_model.CpSolver()
    solver.parameters.log_search_progress = True
    solver.parameters.max_time_in_seconds = TIME_LIMIT
    
    print(f"Bắt đầu giải bài toán với {data['host_num']} PM và {data['vm_num']} VM (giới hạn thời gian: {TIME_LIMIT} giây)...")
    
    status = solver.Solve(model)

    # 5. IN KẾT QUẢ
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        print("\n--- KẾT QUẢ TỐI ƯU HÓA ---")
        print(f"Giá trị hàm mục tiêu: {solver.ObjectiveValue():.2f}")
        
        active_hosts = [j for j in range(data["host_num"]) if solver.Value(y[j]) > 0.5]
        print(f"Số host hoạt động: {len(active_hosts)} (IDs: {active_hosts})")

        total_migrations = sum(1 - solver.Value(x[i, data["initial_vm_placement"][i]]) for i in range(data["vm_num"]))
        print(f"Tổng số di chuyển VM: {total_migrations:.0f}")
        
        for j in active_hosts:
            vms_on_host = [i for i in range(data["vm_num"]) if solver.Value(x[i, j]) > 0.5]
            print(f"Host {j} chứa các VM: {vms_on_host}")
    else:
        print("\nKhông tìm thấy lời giải tối ưu.")

if __name__ == "__main__":
    main()
