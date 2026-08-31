# OriginQ Bell Phi+ tomography (supplemental science evidence)

This package is supplemental to, and does not replace, the canonical two-platform hardware evidence.

## Attempts

- Attempt 1 `EE7D22A38D5A9F246A2031BC7A31C3AD` failed because the client omitted measurement instructions (`errCode=41`, `measured qubit is zero`). It is debugging provenance, not a provider or hardware failure.
- Attempt 2 `F7287E16E8478E4DB5051105468DB638` completed on real Origin Wukong 180-2 (`WK_C180_2`), requested 1000 shots and physical block `[49,58]`. Its corrected input is `H(0); CNOT(0,1); measure(0,0); measure(1,1)`.

## Result and boundary

The provider reconstructed a 4x4 density matrix and reported Phi+ fidelity `0.952449`. Independent calculation gives `0.952448944997` (absolute difference `5.50e-08`). The partial transpose has minimum eigenvalue `-0.456096768` and negativity `0.456096768`.

At the level of the provider-reconstructed density-matrix point estimate, the two-qubit state is entangled under the 2x2 PPT criterion. No statistical confidence interval is claimed because the archived provider result does not expose a sampling-level uncertainty model.

Raw provider responses, input program, OriginIR, independent audit, receipts and SHA-256 manifest are under `files/originq-tomography/`. No timestamps, counts or uncertainty values were fabricated.
