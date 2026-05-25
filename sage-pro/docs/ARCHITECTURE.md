# SAGE-PRO Architecture

SAGE-PRO (Adversarial Orthogonal Divergence Engine) is a multi-agent coding assistant optimized for the AMD MI300X. It uses a non-abelian synthesis approach to explore divergent solution manifolds and refine them via a Nash equilibrium loop.

## The AODE Ensemble

The system consists of four specialist agents co-resident in 192GB HBM3 memory:

1.  **Architect**: (`Qwen/Qwen2.5-Coder-32B-Instruct-AWQ`) High-level structural design and topological void routing.
2.  **Implementer**: (`deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct`) Turning specs into code with Torsion-warped nudges.
3.  **Red-Team**: (Ensemble: `DeepSeek-V2-Lite` + `StarCoder2-15B`) Adversarial test generation and vulnerability scanning.
4.  **Synthesizer**: (`Qwen/Qwen2.5-Coder-72B-Instruct-AWQ`) Merging divergent branches and hardening the final solution.

## Data Flow & Operators

```mermaid
sequence_graph
    participant U as User
    participant R as Router (Persistent Homology)
    participant A as Architect
    participant I as Implementer (Torsion)
    participant RT as Red-Team Ensemble
    participant S as Synthesizer (Lie Bracket)
    participant C as Crucible (Nash Loop)

    U->>R: Coding Task
    R->>A: Routed Task + Topological Voids
    A->>I: Architectural Spec
    I-->>I: Branch ABC || Branch ACB (Parallel)
    I->>S: Divergent Code Paths
    S->>RT: Initial Merge Proposal
    loop Nash Equilibrium
        RT->>C: Adversarial Tests + Flaws
        C->>S: Refinement Request
        S->>C: Hardened Code
    end
    C->>U: Final Hardened Artifact
```

## Mathematical Operators
- **Persistent Homology**: Identifies structural gaps in the repository's semantic space.
- **Torsion**: Programmatically nudges the Implementer along orthogonal axes (e.g., Sync vs Async).
- **Lie Bracket**: Measures the semantic distance between divergent branches.
- **Nash Damage**: Quantitative grounding for the refinement loop.

*See [SAGE_PRO_v3_MATHEMATICAL_SPEC.md](SAGE_PRO_v3_MATHEMATICAL_SPEC.md) for full formalisms.*
