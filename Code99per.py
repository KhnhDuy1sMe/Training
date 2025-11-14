from __future__ import annotations

import json
import copy
import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Iterable, Tuple

import numpy as np


# ==============================
# 1. Data model: VM & PM
# ==============================

@dataclass
class VM:
    id: str          # dùng string cho hợp với vm_id kiểu UUID
    u_c: float       # center (nominal CPU utilization)
    u_r: float       # radius (deviation)
    mem: float       # memory usage
    pm_id: Optional[int] = None  # PM hiện tại

    @property
    def u_max(self) -> float:
        """Worst-case CPU dùng để sort: u_c + u_r."""
        return self.u_c + self.u_r


@dataclass
class PM:
    id: int
    cpu_cap: float   # capacity CPU đã nhân threshold
    mem_cap: float   # capacity memory
    vms: List[str] = field(default_factory=list)  # list ID VM
    active: bool = True

    def __repr__(self) -> str:
        return f"PM(id={self.id}, active={self.active}, vms={self.vms})"


# ==============================
# 2. Hàm robust CPU (G-robust)
# ==============================

def robust_cpu_usage(vms_on_pm: Iterable[VM], G: int) -> float:
    """
    Tính CPU usage G-robust trên 1 PM:
        sum(u_c) + sum(G bán kính lớn nhất u_r).
    """
    vms_list = list(vms_on_pm)
    if not vms_list:
        return 0.0

    centers = [vm.u_c for vm in vms_list]
    radii = sorted((vm.u_r for vm in vms_list), reverse=True)

    return sum(centers) + sum(radii[:G])


def can_place_vm_on_pm(
    vm: VM,
    pm: PM,
    all_vms: Dict[str, VM],
    G: int,
) -> bool:
    """
    Kiểm tra xem có thể đặt thêm vm lên pm hay không
    dưới ràng buộc G-robustness và memory.
    """
    current_vms = [all_vms[vid] for vid in pm.vms]
    current_vms.append(vm)

    # CPU G-robust
    cpu = robust_cpu_usage(current_vms, G)
    if cpu > pm.cpu_cap + 1e-9:
        return False

    # Memory
    mem = sum(v.mem for v in current_vms)
    if mem > pm.mem_cap + 1e-9:
        return False

    return True


# ==============================
# 3. GammaFF heuristic solver
# ==============================

class GammaFFSolver:
    """
    Heuristic GammaFF (Gamma robust First-Fit).

    Ý tưởng (đơn giản hóa):
        - Chọn 1 PM "empty" (ít VM nhất).
        - Lấy tất cả VM trên PM đó + sample 1 phần VM từ PM khác → queue.
        - Sort queue theo u_max giảm dần.
        - First-Fit + G-robustness để đặt lại.
        - Nếu đặt được hết thì commit, không thì rollback.
    """

    def __init__(
        self,
        pms: List[PM],
        vms: List[VM],
        G: int,
        sample_ratio: float = 0.15,
        max_iter: int = 100,
        rng: Optional[random.Random] = None,
    ):
        self.G = G
        self.sample_ratio = sample_ratio
        self.max_iter = max_iter

        self._vms: Dict[str, VM] = {vm.id: copy.deepcopy(vm) for vm in vms}
        self._pms: Dict[int, PM] = {pm.id: copy.deepcopy(pm) for pm in pms}

        self.rng = rng or random.Random()

        # Tổng số lần migration của tất cả VM trong toàn bộ quá trình
        self.migration_count: int = 0

        self._sync_vm_pm_lists()

    # --------- public API ---------

    @property
    def pms(self) -> List[PM]:
        return list(self._pms.values())

    @property
    def vms(self) -> List[VM]:
        return list(self._vms.values())

    def run(self) -> bool:
        """
        Chạy heuristic GammaFF.
        Trả về True nếu có ít nhất 1 iteration consolidate thành công.
        """
        iter_count = 0
        improved_anything = False

        while iter_count < self.max_iter:
            iter_count += 1

            success = self._single_iteration()
            if success:
                improved_anything = True
            else:
                # không cải thiện được nữa, dừng
                break

        return improved_anything

    def active_pms(self) -> List[PM]:
        return [pm for pm in self._pms.values() if pm.vms]

    def inactive_pms(self) -> List[PM]:
        return [pm for pm in self._pms.values() if not pm.vms]

    def count_active_pms(self) -> int:
        return len(self.active_pms())

    def total_robust_cpu_per_pm(self) -> Dict[int, float]:
        result: Dict[int, float] = {}
        for pm in self._pms.values():
            vms_on_pm = [self._vms[vid] for vid in pm.vms]
            result[pm.id] = robust_cpu_usage(vms_on_pm, self.G)
        return result

    def check_feasibility(self) -> Tuple[bool, List[str]]:
        """
        Check tất cả PM có thoả CPU G-robust & memory không.
        """
        errors: List[str] = []

        for pm in self._pms.values():
            vms_on_pm = [self._vms[vid] for vid in pm.vms]
            cpu = robust_cpu_usage(vms_on_pm, self.G)
            mem = sum(vm.mem for vm in vms_on_pm)

            if cpu > pm.cpu_cap + 1e-9:
                errors.append(
                    f"PM {pm.id}: CPU robust {cpu:.3f} > cap {pm.cpu_cap:.3f}"
                )
            if mem > pm.mem_cap + 1e-9:
                errors.append(
                    f"PM {pm.id}: MEM {mem:.3f} > cap {pm.mem_cap:.3f}"
                )

        return (len(errors) == 0, errors)

    # --------- internal helpers ---------

    def _sync_vm_pm_lists(self) -> None:
        """
        Đồng bộ: từ vm.pm_id → pm.vms.
        """
        for pm in self._pms.values():
            pm.vms = []

        for vm in self._vms.values():
            if vm.pm_id is None:
                continue
            if vm.pm_id not in self._pms:
                raise ValueError(f"VM {vm.id} refers to non-existent PM {vm.pm_id}")
            self._pms[vm.pm_id].vms.append(vm.id)

        for pm in self._pms.values():
            pm.active = bool(pm.vms)

    def _single_iteration(self) -> bool:
        """
        Một vòng lặp GammaFF.
        """
        snapshot_pms = copy.deepcopy(self._pms)
        snapshot_vms = copy.deepcopy(self._vms)

        # 1) chọn PM để empty
        candidate_pms = [pm for pm in self._pms.values() if pm.vms]
        if not candidate_pms:
            return False

        pm_empty = min(candidate_pms, key=lambda pm: len(pm.vms))

        # 2) tạo queue Q
        queue_vm_ids: List[str] = []

        # 2.1) tất cả VM trên pm_empty
        queue_vm_ids.extend(pm_empty.vms)
        pm_empty.vms = []  # tạm remove

        # 2.2) sample một phần VM từ các PM khác
        for pm in self._pms.values():
            if pm.id == pm_empty.id or not pm.vms:
                continue
            k = max(1, int(len(pm.vms) * self.sample_ratio))
            sampled = self.rng.sample(pm.vms, k)
            queue_vm_ids.extend(sampled)
            pm.vms = [vid for vid in pm.vms if vid not in sampled]

        # 3) sort Q theo u_max giảm dần
        queue_vm_ids = list(set(queue_vm_ids))
        queue_vm_ids.sort(
            key=lambda vid: self._vms[vid].u_max,
            reverse=True,
        )

        # 4) First-Fit + G-robust
        placed_all = True
        for vid in queue_vm_ids:
            vm = self._vms[vid]
            placed = False

            for pm in self._pms.values():
                if can_place_vm_on_pm(vm, pm, self._vms, self.G):
                    pm.vms.append(vm.id)
                    vm.pm_id = pm.id
                    pm.active = True
                    placed = True
                    break

            if not placed:
                placed_all = False
                break

        if placed_all:
            # update active flag
            for pm in self._pms.values():
                pm.active = bool(pm.vms)

            # -------- ĐẾM MIGRATION CHO ITERATION NÀY --------
            for vid, vm_new in self._vms.items():
                old_pm = snapshot_vms[vid].pm_id
                new_pm = vm_new.pm_id
                if old_pm != new_pm:
                    # mỗi lần một VM đổi PM trong iteration thành công → +1 migration
                    self.migration_count += 1

            return True

        # rollback
        self._pms = snapshot_pms
        self._vms = snapshot_vms
        return False


# ==============================
# 4. Loader: giống Gurobi, không limit PM
# ==============================

def load_huawei_percentile(path: str, G: int):
    """
    Lấy data giống code Gurobi:

        cpu_usage_scaled = cpu_usage * vcpus / 100
        cpu_max = percentile(95)
        cpu_min = percentile(5)
        u_c = (cpu_max + cpu_min) / 2
        u_r = (cpu_max - cpu_min) / 2

    Ánh xạ:
        PM.cpu_cap  = threshold * total_cpu
        PM.mem_cap  = total_memory
        VM.mem      = vm["memory"]
        VM.pm_id    = pm["pm_id"]

    KHÔNG GIỚI HẠN SỐ LƯỢNG PM.
    """
    with open(path) as f:
        raw_data = json.load(f)

    pms: List[PM] = []
    vms: List[VM] = []

    for pm_entry in raw_data:
        pm_id = int(pm_entry["pm_id"])
        threshold = float(pm_entry["threshold"])
        total_cpu = float(pm_entry["total_cpu"])
        total_mem = float(pm_entry["total_memory"])

        cpu_cap = threshold * total_cpu
        mem_cap = total_mem

        pms.append(
            PM(
                id=pm_id,
                cpu_cap=cpu_cap,
                mem_cap=mem_cap,
            )
        )

        for vm_entry in pm_entry["vms"]:
            vm_id = str(vm_entry["vm_id"])
            vcpus = float(vm_entry["vcpus"])
            mem = float(vm_entry["memory"])

            cpu_usage_raw = np.array(vm_entry["cpu_usage"], dtype=float)
            cpu_usage = cpu_usage_raw * vcpus / 100.0

            cpu_max = np.percentile(cpu_usage, 95)
            cpu_min = np.percentile(cpu_usage, 5)

            u_c = (cpu_max + cpu_min) / 2.0
            u_r = (cpu_max - cpu_min) / 2.0

            vms.append(
                VM(
                    id=vm_id,
                    u_c=u_c,
                    u_r=u_r,
                    mem=mem,
                    pm_id=pm_id,
                )
            )

    return pms, vms, G


# ==============================
# 5. Main: chạy thử + migration count
# ==============================

def main():
    # ---- Config để bạn đổi nhanh ----
    JSON_PATH = r"E:\VM 2025\Data\dataset\90-1.json"   # sửa đường dẫn/filename ở đây
    G = 2                     # lấy G = 2 (2 VM tệ nhất trên mỗi host)

    print(f"Đọc dữ liệu từ: {JSON_PATH}")
    pms, vms, G = load_huawei_percentile(JSON_PATH, G)

    print(f"Số PM ban đầu: {len(pms)}")
    print(f"Số VM ban đầu: {len(vms)}")

    # Lưu placement ban đầu (để so sánh cuối cùng)
    initial_pm_of_vm: Dict[str, Optional[int]] = {vm.id: vm.pm_id for vm in vms}

    rng = random.Random(42)

    solver = GammaFFSolver(
        pms=pms,
        vms=vms,
        G=G,
        sample_ratio=0.15,
        max_iter=100,
        rng=rng,
    )

    print("\n--- Trước khi chạy GammaFF ---")
    print("Số PM active:", solver.count_active_pms())

    improved = solver.run()

    print("\n--- Sau khi chạy GammaFF ---")
    print("Số PM active:", solver.count_active_pms())
    print("Có consolidate được không:", improved)

    ok, errors = solver.check_feasibility()
    print(f"Thoả G-robustness & memory (G={G}):", ok)
    if not ok:
        print("Vi phạm:")
        for e in errors:
            print("  -", e)

    # ===== Migration metrics =====
    # 1) Tổng số lần migration (count theo từng bước di chuyển trong các iteration thành công)
    print(f"\nTổng số lần migration (tất cả bước di chuyển VM trong GammaFF): {solver.migration_count}")

    # 2) Số VM có PM cuối khác PM ban đầu
    migrated_vms = 0
    for vm in solver.vms:
        old_pm = initial_pm_of_vm.get(vm.id, None)
        new_pm = vm.pm_id
        if old_pm is not None and new_pm is not None and old_pm != new_pm:
            migrated_vms += 1

    print(f"Số VM có host cuối khác ban đầu: {migrated_vms} / {len(vms)} "
          f"({migrated_vms / len(vms) * 100:.1f}%)")

    # ==============================
    #  In kết quả gọn gàng dạng bảng
    # ==============================

    robust_cpu = solver.total_robust_cpu_per_pm()

    print("\nTóm tắt theo PM (chỉ hiển thị gọn):")
    header = f"{'PM':>4} {'Active':>7} {'#VMs':>6} {'CPU_robust':>12} {'Cap':>10} {'Load%':>8}"
    print(header)
    print("-" * len(header))

    active_count = 0
    inactive_count = 0

    # Sắp xếp theo id PM cho dễ nhìn
    for pm in sorted(solver.pms, key=lambda x: x.id):
        cpu_r = robust_cpu[pm.id]
        cap = pm.cpu_cap
        load_pct = (cpu_r / cap * 100) if cap > 0 else 0.0
        n_vms = len(pm.vms)

        if n_vms > 0:
            active_count += 1
        else:
            inactive_count += 1

        print(
            f"{pm.id:>4} "
            f"{str(pm.active):>7} "
            f"{n_vms:>6} "
            f"{cpu_r:>12.2f} "
            f"{cap:>10.2f} "
            f"{load_pct:>7.1f}%"
        )

    print("-" * len(header))
    print(f"Tổng PM active : {active_count}")
    print(f"Tổng PM inactive: {inactive_count}")

    # Nếu THỬ muốn xem một ít VM_id cho debug, bật flag này
    SHOW_SOME_VM_IDS = False
    MAX_VM_IDS = 5

    if SHOW_SOME_VM_IDS:
        print("\nMột vài VM_id trên mỗi PM (tối đa", MAX_VM_IDS, "VM/PM):")
        for pm in sorted(solver.pms, key=lambda x: x.id):
            if not pm.vms:
                continue
            sample_ids = pm.vms[:MAX_VM_IDS]
            more = "" if len(pm.vms) <= MAX_VM_IDS else f"... (+{len(pm.vms) - MAX_VM_IDS} VM nữa)"
            print(f"PM {pm.id}: {sample_ids} {more}")


if __name__ == "__main__":
    main()
