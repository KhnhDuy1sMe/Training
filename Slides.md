<!-- Slide 1 -->
# Energy-Efficient Cloud Systems: Virtual Machine Consolidation with Γ-Robustness Optimization

**Authors:** Xinming Han, Jianxiao Wang, Jiaxi Wu, Jie Song  
**Affiliation:** Peking University, China Mobile  
**Presenter:** [Your Name]  
**Date:** [Presentation Date]  

---

<!-- Slide 2 -->
## The Challenge of Cloud Efficiency

- ☁️ Cloud data centers have low average utilization (15-20%) → **Energy waste**
- 🔄 **Virtual Machine (VM) Consolidation:** Pack VMs onto fewer physical machines (PMs) to turn off idle servers and save energy
- ⚠️ **Problem:** VM CPU usage is unpredictable → Overloading PMs causes performance issues and SLA violations
- ⚖️ **Need a solution:** Balance between **energy savings** and **performance reliability**

---

<!-- Slide 3 -->
## Our Solution: Γ-Robustness Optimization

- Instead of fixed values, model VM CPU usage as uncertain within a range:  
  `[uc_i - ur_i, uc_i + ur_i]`  
  - `uc_i` = Central (nominal) value  
  - `ur_i` = Maximum deviation (radius)  
- **Γ-Robustness:** Allow **up to Γ VMs** on a PM to simultaneously reach their worst-case usage
- **Optimization constraint for each PM j:**  
  `∑(uc_i) + ∑(Γ largest ur_i) ≤ Capacity_j`  
- ✅ **Advantage:** Avoids overly conservative solutions, saves more energy

---

<!-- Slide 4 -->
## Mathematical Model (MILP)

**Objective:**  
`Minimize: ∑(Active PMs) + β * ∑(VM Migrations)`  

**Key Constraints:**  
1. Each VM is assigned to exactly one PM  
2. Total CPU (with Γ-robustness) and Memory resources of VMs on a PM ≤ PM capacity  
3. Binary constraints for decision variables  

- ✅ **Pros:** Finds optimal solution  
- ❌ **Cons:** Only feasible for **small-scale problems** (NP-Hard)

---

<!-- Slide 5 -->
## Scaling Up: The GammaFF Algorithm

To solve large-scale problems, we propose **GammaFF** - an efficient heuristic:

**Main Steps:**  
1.  **Select a PM to release**  
2.  **Form VM queue:** Take all VMs from target PM + **15%** VMs from other PMs  
3.  **Re-sort & Reallocate:** Sort VMs by `uc_i + ur_i` (descending). Use **First-Fit** strategy with **Γ-robustness check** to reallocate VMs to remaining PMs  
4.  **Iterate** until no more PMs can be released

---

<!-- Slide 6 -->
## Finding the Right Balance: Parameter Tuning (1)

**Determining uc_i and ur_i from historical data:**  

- **Results:**  
  - **80th/20th percentile:** Too aggressive → PMs exceed threshold  
  - **99th/1st percentile:** Too conservative → Resource waste  
  - **✅ 90th/10th percentile:** Best balance → Efficient resource use while ensuring safety  

**=> Chosen for the model**

---

<!-- Slide 7 -->
## Tuning the Algorithm: VM Sampling Ratio

**The proportion of VMs sampled from other PMs affects performance:**  

- **Results:**  
  - Selecting **15%** of VMs is the "sweet spot"  
  - Effectively reduces number of active PMs  
  - Increasing this ratio does not reduce more PMs but **significantly increases migrations** (causing overhead)  

**=> 15% ratio chosen for GammaFF**

---

<!-- Slide 8 -->
## Evaluation: Small-Scale Datasets (5-13 PMs)

- Compare **MILP** (optimal) vs. **GammaFF** (heuristic)  
- **Results:**  
  - **MILP:** Releases the most PMs (highest efficiency)  
  - **GammaFF:** Very good performance, reduces **at least 20%** of PMs compared to initial state  
  - **Trade-off:** GammaFF requires more migrations than MILP  
- **MILP cannot solve large problems** (>13 PMs)

---

<!-- Slide 9 -->
## Evaluation: Large-Scale Datasets (85-100 PMs)

Compare **GammaFF** with other algorithms:  
- **Simple:** FirstFit, BestFit  
- **Advanced:** HLEM-VMP, GMPR, GammaBF (variant of GammaFF)  

**Key Results:**  
- **GammaFF consistently achieves the LOWEST or equal number of active PMs**  
- **GammaFF's migration count is stable and acceptable,** much lower than GMPR  
- **=> GammaFF provides the best trade-off between energy savings and migration costs**

---

<!-- Slide 10 -->
## Why is GammaFF the Best?

- **FirstFit/BestFit:** Don't consider uncertainty → Low performance  
- **HLEM-VMP:** Conservative → High number of active PMs  
- **GMPR:** Optimizes energy but with very high migration cost  
- **GammaBF:** Sensitive to fluctuations, less stable than GammaFF  
- **✅ GammaFF:**  
  - **Integrates Γ-robustness** to handle uncertainty  
  - **Simple, stable, predictable** strategy  
  - **Excellent balance** between active PMs and migrations

---

<!-- Slide 11 -->
## Limitations and Future Directions

**Current study limitations:**  
1. Focuses mainly on **CPU**, assumes fixed memory  
2. Does not model **live migration costs** (downtime, network bandwidth)  
3. Model designed for **VMs**, not containers  

**Future directions:**  
- Extend to **multi-resource management** (CPU, RAM, Network)  
- Integrate **live migration costs** into optimization  
- Adapt principles for **container consolidation**

---

<!-- Slide 12 -->
## Conclusion

- Proposed a **novel method** for VM consolidation using **Γ-robustness optimization**  
- Method **effectively balances** energy savings and performance assurance  
- **GammaFF** is a **robust, efficient, and scalable** heuristic for large-scale data centers  
- Experimental results on **real Huawei Cloud data** show superior performance over state-of-the-art methods  

**Thank You!**  
**Q&A**
