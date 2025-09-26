import numpy as np
import pandas as pd
import json
from typing import Dict, List
from gurobipy import Model, GRB, quicksum

# --- HÀM HỖ TRỢ ---

def create_gamma_map(filepath: str, max_vms: int, p_sla: float) -> List[int]:
    """
    Tạo một danh sách tra cứu (map) từ đường dẫn file CSV.
    """
    try:
        # Sử dụng đường dẫn file được truyền vào
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
    """Tải dữ liệu máy ảo và máy chủ từ file JSON."""
    try:
        with open(filepath) as f:
            raw_data = json.load(f)
            raw_data = raw_data[:12]
    except FileNotFoundError:
        print(f"Lỗi: Không tìm thấy file dữ liệu tại '{filepath}'.")
        return None

    data = {
        "vm_num": sum(len(pm.get("vms", [])) for pm in raw_data),
        "host_num": len(raw_data),
        "cpu_total": [pm.get("total_cpu", 0) for pm in raw_data],
        "mem_total": [pm.get("total_memory", 0) for pm in raw_data],
        "threshold": [pm.get("threshold", 0.8) for pm in raw_data],
        "uc": [], "ur": [], "mem": [],
        "initial_vm_placement": {},
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
            
            data["uc"].append((cpu_max + cpu_min) / 2)
            data["ur"].append((cpu_max - cpu_min) / 2)
            data["mem"].append(vm.get("memory", 0))
            data["initial_vm_placement"][vm_index] = pm_index
            vm_index += 1

    return data

# --- HÀM CHÍNH ---

def main():
    # --- ĐỊNH NGHĨA ĐƯỜNG DẪN VÀ THAM SỐ ---
    ROBUST_CSV_PATH = r'E:\VM 2025\robust_1000.csv'
    DATASET_JSON_PATH = r'E:\VM 2025\vm_offline_scheduling\dataset\15-2_small.json'
    
    P_SLA = 0.05
    ALPHA = 10**3
    TIME_LIMIT_SECONDS = 3600

    # --- TẢI DỮ LIỆU VÀ TẠO GAMMA MAP ---
    data = load_data_from_json(DATASET_JSON_PATH)
    if data is None: return

    N_Gamma_map = create_gamma_map(ROBUST_CSV_PATH, data["vm_num"], P_SLA)
    if N_Gamma_map is None: return

    # --- XÂY DỰNG MÔ HÌNH GUROBI ---
    model = Model("Robust_VM_Placement")

    # 1. ĐỊNH NGHĨA BIẾN
    x = model.addVars(data["vm_num"], data["host_num"], vtype=GRB.BINARY, name="x")
    x_hat = model.addVars(data["vm_num"], data["host_num"], vtype=GRB.BINARY, name="x_hat")
    y = model.addVars(data["host_num"], vtype=GRB.BINARY, name="y")
    H = model.addVars(data["host_num"], data["vm_num"] + 1, vtype=GRB.BINARY, name="H")

    # 2. THÊM RÀNG BUỘC
    model.addConstrs((x.sum(i, '*') == 1 for i in range(data["vm_num"])), name="VM_Assignment")
    model.addConstrs((x_hat[i, j] <= x[i, j] for i in range(data["vm_num"]) for j in range(data["host_num"])), name="x_hat_link")
    model.addConstrs((x.sum('*', j) == quicksum(H[j, k] * k for k in range(data["vm_num"] + 1)) for j in range(data["host_num"])), name="VM_Count")
    model.addConstrs((H.sum(j, '*') == 1 for j in range(data["host_num"])), name="Host_VM_Count_Unique")
    model.addConstrs((x_hat.sum('*', j) == quicksum(H[j, k] * N_Gamma_map[k] for k in range(data["vm_num"] + 1)) for j in range(data["host_num"])), name="Gamma_Constraint")
    
    for j in range(data["host_num"]):
        cpu_load = quicksum(data["uc"][i] * x[i, j] for i in range(data["vm_num"])) + \
                   quicksum(data["ur"][i] * x_hat[i, j] for i in range(data["vm_num"]))
        capacity = data["cpu_total"][j] * data["threshold"][j]
        model.addConstr(cpu_load <= y[j] * capacity, name=f"CPU_Capacity_{j}")

    for j in range(data["host_num"]):
        mem_load = quicksum(data["mem"][i] * x[i, j] for i in range(data["vm_num"]))
        capacity = data["mem_total"][j]
        model.addConstr(mem_load <= y[j] * capacity, name=f"Memory_Capacity_{j}")

    # 3. ĐỊNH NGHĨA HÀM MỤC TIÊU
    active_hosts_cost = ALPHA * y.sum()
    migration_cost = quicksum(1 - x[i, data["initial_vm_placement"][i]] for i in range(data["vm_num"]))
    
    model.setObjective(active_hosts_cost + migration_cost, GRB.MINIMIZE)

    # 4. CẤU HÌNH VÀ GIẢI BÀI TOÁN
    model.setParam("TimeLimit", TIME_LIMIT_SECONDS)
    model.optimize()

    # 5. IN KẾT QUẢ
    if model.status == GRB.OPTIMAL or model.status == GRB.FEASIBLE:
        print("\n--- KẾT QUẢ TỐI ƯU HÓA ---")
        print(f"Giá trị hàm mục tiêu: {model.ObjVal:.2f}")
        
        active_hosts = [j for j in range(data["host_num"]) if y[j].X > 0.5]
        print(f"Số host hoạt động: {len(active_hosts)} (IDs: {active_hosts})")

        total_migrations = sum(1 - x[i, data["initial_vm_placement"][i]].X for i in range(data["vm_num"]))
        print(f"Tổng số di chuyển VM: {total_migrations:.0f}")

        for j in active_hosts:
            vms_on_host = [i for i in range(data["vm_num"]) if x[i, j].X > 0.5]
            print(f"Host {j} chứa các VM: {vms_on_host}")
    else:
        print("\nKhông tìm thấy lời giải tối ưu.")

if __name__ == "__main__":
    main()
