# V7.2.1 pedagogy references

This patch borrows teaching patterns—not product branding—from the following
Microsoft Quantum learning materials:

- [QDK Circuit Editor](https://learn.microsoft.com/en-us/azure/quantum/qdk-circuit-editor): circuit and state changes kept visible together.
- [QDK VS Code reference](https://learn.microsoft.com/en-us/azure/quantum/vscode-qdk-reference): run, show the circuit, and inspect the histogram as one workflow.
- [Quantum Katas / QDK learning](https://learn.microsoft.com/en-us/azure/quantum/katas-qdk-learning): short explanation followed by a small hands-on check.
- [Quantum circuit concepts](https://learn.microsoft.com/en-us/azure/quantum/concepts-circuits): left-to-right time, horizontal qubit rails, CNOT control/target symbols, and measurement conventions.
- [Explore superposition](https://learn.microsoft.com/en-us/training/modules/explore-superposition/): the optional one-qubit Bloch-sphere view.
- [Bell-pair quickstart](https://learn.microsoft.com/en-us/azure/quantum/qsharp-quickstart): the minimal H + CNOT Bell preparation.

LoomQ implements original HTML/CSS/SVG visuals. It does not ship Microsoft
logos, screenshots, or branded UI. No Microsoft source code was copied into
the product; therefore this patch adds no third-party source license beyond
this reference note.

## V7.2.2 judge-aligned information architecture references

The V7.2.2 flow also uses the following public products and explainers as
interaction and misconception-correction inspiration:

- [IBM Quantum Composer](https://quantum.cloud.ibm.com/docs/en/guides/composer): keep circuit and result views together.
- [Quirk](https://github.com/Strilanc/Quirk): immediate visual feedback as a circuit changes.
- [Quantum Flytrap](https://lab.quantumflytrap.com/) and [Quantum Game](https://quantumgame.io/): small direct-manipulation experiments.
- [Quantum Odyssey](https://store.steampowered.com/app/2802710/Quantum_Odyssey/): guided no-code progression with advanced material behind optional paths.
- [3Blue1Brown Grover explanation](https://www.youtube.com/watch?v=RQWpF2Gb-gU) and [Looking Glass Universe](https://www.youtube.com/watch?v=kgSVkVNxXyU): visual intuition with careful limits on common quantum shortcuts.
- [NVIDIA quantum-computing overview](https://www.nvidia.com/en-us/solutions/quantum-computing/): later hybrid classical/quantum and hardware context, not first-run pedagogy.

These are research references only. LoomQ does not copy their branding,
screenshots, logos, UI, or source code, and the beginner path does not add
Grover, new algorithms, new hardware capabilities, or extra backends.
