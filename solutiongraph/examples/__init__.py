"""Executable, dependency-free domain examples for the universal runtime."""

# Import order is intentional: showcase_tasks reuses the task dataclasses and
# tasks attaches the showcase tuple after those dataclasses are defined.
# ruff: noqa: I001
from solutiongraph.examples.tasks import (
    EXAMPLE_TASKS,
    ExampleRoute,
    ExecutableExample,
    all_examples,
    get_example,
    run_example,
)
from solutiongraph.examples.showcase_tasks import (
    DUECARE_HARNESS_BUNDLE,
    SHOWCASE_EXAMPLE_TASKS,
    SHOWCASE_REGISTRY,
)

__all__ = [
    "EXAMPLE_TASKS",
    "ExecutableExample",
    "ExampleRoute",
    "all_examples",
    "get_example",
    "run_example",
    "DUECARE_HARNESS_BUNDLE",
    "SHOWCASE_EXAMPLE_TASKS",
    "SHOWCASE_REGISTRY",
]
