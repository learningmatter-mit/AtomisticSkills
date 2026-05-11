# Li-O Phase Diagram Retrieval

This example retrieves and renders the complete Lithium-Oxygen (Li-O) temperature-composition phase diagram from the Materials Project API.

### Workflow

We run the provided script that interacts with the `mat-phase-diagram` MCP logic under the hood:

```bash
bash li_o_example.sh
```

### Outputs
- Extracts the stable binary hull into local JSON for analysis
- Automates fetching the thermodynamic limits of the Li-O system
- Explores Li2O's thermodynamic stability metrics computationally

### Literature Comparison
Our script queried the Materials Project database and isolated `Li2O` as the fully stable compound at the thermodynamic limit on the binary hull (`energy_above_hull = 0.0`). In experimental literature, both Lithium oxide (Li2O) and Lithium peroxide (Li2O2) are well-known stable solid phases in the Li-O phase diagram depending on oxygen partial pressure, with Li2O representing the fully reduced thermodynamic endpoint in air-free batteries. The Materials Project data correctly aligns with this 0K computational ground-state observation, where Li2O2 is typically very slightly above the theoretical 0K convex hull but stable at finite temperatures and pressures.
