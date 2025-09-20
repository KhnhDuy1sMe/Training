# VM Placement Optimization Algorithm

This flowchart describes a heuristic algorithm for optimizing the placement of Virtual Machines (VMs) on Physical Machines (PMs) to consolidate workload and free up servers.

## Flowchart

```mermaid
flowchart TD
    A["Start"] --> B["Initialize:\nIter_count = 0\nSuccess = False\nQ = ∅"]
    B --> C{"Iter_count < Imax\nand Success = False?"}
    C -- "Yes" --> D["Select and mark an empty PM (PM_empty)"]
    D --> E["Initialize Queue Q:\nQ = All VMs from PM_empty"]
    E --> F["For each PM ≠ PM_empty\nand not empty: Sample k VMs\nand add to Q"]
    F --> G["Sort Q by U_max_i\nin descending order"]
    G --> H["For each VM in Q"]
    H --> I["Set Placed = False"]
    I --> J["For each PM in PM_list"]
    J --> K["Calculate total resource usage"]
    K --> L{"Usage ≤ Cj * yj?"}
    L -- "Yes" --> M["Place VM on this PM\nSet Placed = True"]
    M --> N["Break out of PM loop"]
    L -- "No" --> J
    N --> O{"VM Placed?"}
    O -- "Yes" --> H
    O -- "No" --> P["Break out of VM loop"]
    P --> R{"Is Q empty?\n(All VMs placed)?"}
    R -- "Yes" --> T["Commit changes\nSuccess = True"]
    R -- "No" --> U["Iter_count += 1\nReset all PM & VM states"]
    U --> C
    T --> C
    C -- "No" --> V{"Success = True?"}
    V -- "Yes" --> W["Return Optimized Placement"]
    V -- "No" --> X["Return 'No valid placement found'"]
```
## Explanation
This algorithm attempts to find a new VM arrangement to free up at least one target physical server (`PM_empty`).

- **Imax:** Maximum number of iterations to attempt.
- **k:** The number of VMs to randomly sample from each non-empty PM.
- **U_max_i:** The maximum resource utilization of VM *i* (e.g., CPU usage).
- **Cj * yj:** The total resource capacity of PM *j*.
- **Queue Q:** A collection of VMs that need to be re-placed.
- The inner loops try to find a new home for each VM in the sorted queue `Q`.
- If all VMs in `Q` can be placed, the algorithm succeeds.
- If any VM cannot be placed, the algorithm resets and tries again.
