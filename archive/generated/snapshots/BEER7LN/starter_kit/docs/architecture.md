# Architecture

Implementation modules will live under `loomq/`; `adapter.py` remains the official thin entry point.

```text
adapter -> parser/AST -> transpilers -> target IR
                    -> simulator -> unified result schema
adapter -> L2 planner -> LLM client -> structured task plan
                   -> L1 parser/simulator -> validated QASM response
                   -> capability selector -> canonical backend response
                   -> local Web experience -> result visualization
adapter -> hybrid compiler -> quantum operations + RISC-V assembly
```

All cross-backend bit-order conversion belongs in one shared module, never in scattered backend-specific branches.

The L2 model never directly decides whether an answer is executable or whether a backend exists. QASM is parsed and simulated through the L1 implementation; backend recommendations are filtered from the official machine-readable capability table. The Web layer calls the same `adapter.agent_chat()` contract as the evaluator and adds no alternate scoring path.
