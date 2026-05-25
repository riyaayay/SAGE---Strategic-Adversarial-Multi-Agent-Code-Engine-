---
axes:
  - id: 1
    label: oop_vs_functional
    description: Bias towards Class-based encapsulation vs Pure-function composition.
  - id: 2
    label: iteration_vs_recursion
    description: Bias towards imperative loops vs recursive divide-and-conquer.
  - id: 3
    label: async_vs_sync
    description: Force non-blocking concurrency vs strict sequential execution.
  - id: 4
    label: generic_vs_specialized
    description: Use abstract generics vs concrete, highly optimized types.
  - id: 5
    label: performance_vs_readability
    description: Sacrifice developer experience for raw cycle efficiency.
  - id: 6
    label: memory_vs_cpu
    description: Bias towards caching/lookup-tables vs on-the-fly recomputation.
  - id: 7
    label: defensive_vs_optimistic
    description: Extensive validation vs assuming clean inputs.
---

# TORSION SUFFIXES

When implementing this solution, you MUST adhere to the following architectural nudge to explore an orthogonal solution manifold:

- **OOP vs Functional**: Favor Object-Oriented patterns, inheritance, and state encapsulation.
- **Iteration vs Recursion**: Use iterative loops (for/while) and avoid all recursive calls.
- **Async vs Sync**: Implement using `asyncio` and non-blocking I/O.
- **Generic vs Specialized**: Use `typing.TypeVar` and generic classes to maximize reuse.
- **Performance vs Readability**: Use bitwise operators, localized optimizations, and minimize allocations.
- **Memory vs CPU**: Use `functools.lru_cache` and pre-computed tables to minimize CPU cycles.
- **Defensive vs Optimistic**: Implement exhaustive input validation and `try/except` blocks.
