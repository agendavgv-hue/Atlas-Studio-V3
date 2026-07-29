"""Pipeline registry for ProductionEngine and future Job Queue."""

from __future__ import annotations

from collections.abc import Callable

from app.pipelines.base import Pipeline


class PipelineRegistry:
    """Maps pipeline ids to factory callables."""

    def __init__(self) -> None:
        self._factories: dict[str, Callable[[], Pipeline]] = {}

    def register(self, pipeline_id: str, factory: Callable[[], Pipeline]) -> None:
        self._factories[pipeline_id] = factory

    def create(self, pipeline_id: str) -> Pipeline:
        factory = self._factories.get(pipeline_id)
        if factory is None:
            raise KeyError(f"Unknown pipeline: {pipeline_id}")
        return factory()

    def has(self, pipeline_id: str) -> bool:
        return pipeline_id in self._factories

    def ids(self) -> list[str]:
        return sorted(self._factories)
