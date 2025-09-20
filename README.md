# Training
# Energy-Efficient Cloud Systems: Virtual Machine Consolidation with Γ-Robustness Optimization

> **DOI:** [https://doi.org/10.1016/j.isci.2025.111897](https://doi.org/10.1016/j.isci.2025.111897)

## 📌 Overview

This repository provides a summary and implementation details for the paper **"Energy-efficient cloud systems: Virtual machine consolidation with Γ-robustness optimization"** by Han et al. (2025). The paper addresses the critical challenge of optimizing **Virtual Machine (VM) consolidation** in cloud data centers to improve energy efficiency while handling the uncertainty of VM resource usage through **Γ-robustness optimization**.

## 🎯 Key Contributions

1.  **Γ-Robustness Integration:** First application of Γ-robustness theory to VM consolidation, providing a less conservative and more efficient resource management strategy.
2.  **MILP Model:** A Mixed Integer Linear Programming model for optimal VM placement in small-scale scenarios.
3.  **GammaFF Algorithm:** A scalable heuristic algorithm for large-scale VM consolidation, combining First-Fit strategy with Γ-robustness constraints.
4.  **Real-Data Validation:** Comprehensive evaluation using real-world data from Huawei Cloud, demonstrating superior performance over state-of-the-art algorithms.

## 🧠 Core Concept: Γ-Robustness

Traditional consolidation methods use fixed values for VM CPU demand, leading to either over-provisioning (wasteful) or under-provisioning (risk of overload). This paper models CPU demand for each VM `i` as an uncertain parameter within a symmetric interval:

`u_i ∈ [uc_i - ur_i, uc_i + ur_i]`

Where:
- `uc_i`: Central (nominal) value (e.g., median usage).
- `ur_i`: Radius (maximum possible deviation).

The **Γ-robustness** constraint for a Physical Machine (PM) `j` ensures it can handle worst-case scenarios without being overly pessimistic:

`∑(uc_i of all VMs on PM j) + ∑(Γ largest ur_i on PM j) ≤ Capacity_j`

This ensures protection against up to `Γ` VMs simultaneously spiking to their maximum usage.

## ⚙️ Methodology

### 1. MILP Model (For Small Scale)
**Objective:**
Minimize the number of active PMs and the number of VM migrations.
`Minimize: ∑(y_j) + β * ∑(w_i)`

**Subject to:**
- Each VM is assigned to exactly one PM.
- The Γ-robust CPU and memory constraints for each PM.
- Binary constraints for decision variables.

### 2. GammaFF Algorithm (For Large Scale)
A heuristic algorithm designed for scalability and efficiency.

**Main Steps:**
1.  **Select a PM to empty.**
2.  **Form a VM Queue:** Take all VMs from the target PM and a **15%** sample of VMs from other PMs.
3.  **Sort and Reallocate:** Sort VMs by their upper bound usage (`uc_i + ur_i`). Use a **First-Fit** strategy to reallocate them to other PMs, strictly checking the Γ-robustness constraint.
4.  **Iterate:** Repeat until no more PMs can be emptied or a maximum iteration count is reached.

## 📊 Experimental Results & Findings

### Parameter Tuning
- **Best Percentiles for `uc_i` & `ur_i`:** **90th/10th percentile** of historical data provided the optimal balance between efficiency and avoiding overloads.
- **Best VM Sampling Ratio in GammaFF:** Sampling **15%** of VMs from other PMs was optimal, effectively reducing active PMs without causing excessive migrations.

### Performance Evaluation
- **Small-Scale (5-13 PMs):** The MILP model found the optimal solution. The GammaFF heuristic achieved **at least a 20% reduction** in active PMs.
- **Large-Scale (85-100 PMs):** GammaFF was compared against other algorithms (FirstFit, BestFit, HLEM-VMP, GMPR, GammaBF).
    - **GammaFF consistently achieved the LOWEST (or equal) number of active PMs.**
    - **GammaFF maintained a stable and acceptable migration count,** significantly lower than energy-focused algorithms like GMPR.

**Conclusion:** GammaFF provides the best trade-off between energy savings (minimizing active PMs) and migration costs.

## 🚧 Limitations & Future Work

- **Current Focus:** Primarily on CPU optimization with fixed memory.
- **Live Migration:** The cost of live migration (downtime, network latency) is not explicitly modeled.
- **Containerization:** The model is designed for VMs, not containers.
- **Future Directions:** Extend the model to multi-resource management, integrate live migration costs, and adapt the principles for container consolidation.

## 📚 Repository Contents (Expected)

This summary accompanies the theoretical framework. A full implementation would typically include:

- `src/`: Directory containing source code.
    - `milp_model.py`: Implementation of the MILP model (using a solver like Gurobi or CPLEX).
    - `gammaff_algorithm.py`: Implementation of the GammaFF heuristic algorithm.
- `data/`: Directory for sample datasets (format: JSON, as per Huawei Cloud data).
- `results/`: Output files and plots from experiments.
- `README.md`: This file.
