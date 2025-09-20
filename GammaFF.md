# VM Placement Optimization Algorithm

This flowchart describes a heuristic algorithm for optimizing the placement of Virtual Machines (VMs) on Physical Machines (PMs) to consolidate workload and free up servers.

## Flowchart

```mermaid
flowchart TD
    A([Start]) --> B[Initialize:<br>Iter_count = 0<br>Success = False<br>Q = ∅]
    B --> C{Iter_count < Imax<br>and Success = False?}
    C -- Yes --> D[Select and mark an empty PM (PM_empty)]
    D --> E[Initialize Queue Q:<br>Q = All VMs from PM_empty]
    E --> F[For each PM ≠ PM_empty<br>and not empty: Sample k VMs<br>and add to Q]
    F --> G[Sort Q by U_max_i<br>in descending order]
    G --> H[For each VM in Q]
    H --> I[Set Placed = False]
    I --> J[For each PM in PM_list]
    J --> K[Calculate total resource usage]
    K --> L{Usage ≤ Cj * yj?}
    L -- Yes --> M[Place VM on this PM<br>Set Placed = True]
    M --> N[Break out of PM loop]
    L -- No --> J
    N --> O{VM Placed?}
    O -- Yes --> H
    O -- No --> P[Break out of VM loop]
    P --> R{Is Q empty?<br>(All VMs placed)?}
    R -- Yes --> T[Commit changes<br>Success = True]
    R -- No --> U[Iter_count += 1<br>Reset all PM & VM states]
    U --> C
    T --> C
    C -- No --> V{Success = True?}
    V -- Yes --> W([Return Optimized Placement])
    V -- No --> X([Return &quot;No valid placement found&quot;])
```
## Explanation
This algorithm attempts to find a new VM arrangement to free up at least one target physical server (`PM_empty`).

- **Imax:** Maximum number of iterations to attempt.
- **k:** The number of VMs to randomly sample from each non-empty PM (to potentially re-place them and free up the target PM).
- **U_max_i:** The maximum resource utilization of VM *i* (e.g., CPU usage). Sorting by this in descending order prioritizes placing the most demanding VMs first, which is a common heuristic for avoiding resource fragmentation.
- **Cj * yj:** The total resource capacity of PM *j*. The condition `Usage ≤ Cj * yj` ensures a VM is only placed on a PM if it has sufficient remaining resources.
- **Queue Q:** A collection of VMs that need to be re-placed. It's initialized with all VMs from the target `PM_empty` and is then augmented with samples from other PMs.
- The inner loops try to find a new home for each VM in the sorted queue `Q`.
- If all VMs in `Q` can be placed elsewhere, the changes are committed, and the algorithm succeeds, freeing the target `PM_empty`.
- If any VM cannot be placed, the algorithm resets the state and tries again with a new iteration (up to `Imax` times).
