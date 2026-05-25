# SAGE-PRO Prompting Guide

SAGE-PRO is not a simple chatbot; it is an adversarial reasoning engine. To get the best results, you should provide tasks that define high-level interfaces rather than low-level implementation details.

## Best Practices

1.  **Define Interfaces**: Clearly state expected inputs, outputs, and side effects.
2.  **State Constraints**: Use keywords like "thread-safe", "non-blocking", or "memory-efficient" to trigger the Torsion operators.
3.  **Provide Context**: Include relevant files using the `context_files` parameter to help the Router find topological voids.

## Examples

### ✅ Good: Task with Interface and Constraints
> "Implement a thread-safe LRU cache with TTL. The cache should support async eviction via a background worker. Key eviction should be O(1)."

### ❌ Bad: Task that is too vague
> "Write a cache script."

### ✅ Good: Complex System Refactoring
> "Refactor the existing database connection pool to use the Circuit Breaker pattern. Ensure it is robust against network timeouts."

## v3.0 Multi-Modal Workflows

SAGE-PRO v3.0 is no longer text-only. Leverage the new IDE features for complex workflows:

1.  **Vision Debugging ("Look at This")**: If your UI is misaligned or a plot looks wrong, do not try to describe it in text. Take a screenshot, navigate to the `Vision Debugger` tab, and upload it along with the source code. The VLM will pinpoint the exact CSS/Matplotlib lines to change.
2.  **Time-Travel Architecting**: When designing complex systems, allow SAGE to generate the first pass. Then, use the `Time-Travel Branching` tab to fork the AI's execution before the `Implementer` node, allowing you to explore an alternate architectural pattern without re-running the entire pipeline.
3.  **LSP-Aware Prompting**: You can now ask SAGE to perform surgical codebase refactors (e.g., "Rename the `UserAuth` class to `IdentityManager` globally"). The engine will automatically use Jedi LSP to find all references safely.
