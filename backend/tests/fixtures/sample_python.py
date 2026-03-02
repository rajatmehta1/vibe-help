"""Sample Python module for parser testing."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional, List

from .utils import helper_function
from ..models import User, Organization


MAX_RETRIES = 3
DEFAULT_TIMEOUT = 30.0
_internal_cache: dict = {}


def simple_function(x: int, y: int) -> int:
    """Add two numbers."""
    return x + y


async def fetch_data(url: str, timeout: float = 10.0) -> dict:
    """Fetch data from a URL asynchronously."""
    if not url.startswith("http"):
        raise ValueError("Invalid URL")
    for attempt in range(MAX_RETRIES):
        try:
            result = await _do_request(url, timeout)
            return result
        except ConnectionError:
            if attempt == MAX_RETRIES - 1:
                raise
    return {}


def _private_helper(data: list[str]) -> list[str]:
    return [item.strip() for item in data if item]


class BaseProcessor:
    """Base class for data processors."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._initialized = False

    def initialize(self) -> None:
        """Set up the processor."""
        self._initialized = True

    def process(self, data: dict) -> dict:
        """Process a single data item."""
        raise NotImplementedError


class DataProcessor(BaseProcessor):
    """Concrete data processor with validation and transformation."""

    def __init__(self, name: str, strict: bool = False) -> None:
        super().__init__(name)
        self.strict = strict
        self._errors: list[str] = []

    def process(self, data: dict) -> dict:
        """Process and validate data."""
        if self.strict and not self._validate(data):
            raise ValueError(f"Validation failed: {self._errors}")
        return self._transform(data)

    def _validate(self, data: dict) -> bool:
        self._errors = []
        if "id" not in data:
            self._errors.append("Missing id")
        if "value" not in data and self.strict:
            self._errors.append("Missing value in strict mode")
        return len(self._errors) == 0

    def _transform(self, data: dict) -> dict:
        return {
            "id": data.get("id"),
            "value": data.get("value", 0) * 2,
            "processed": True,
        }

    @property
    def error_count(self) -> int:
        return len(self._errors)


@staticmethod
def standalone_static():
    pass


class AsyncWorker:
    """Worker that processes items asynchronously."""

    async def run(self, items: list[dict]) -> list[dict]:
        results = []
        for item in items:
            result = await self._process_one(item)
            results.append(result)
        return results

    async def _process_one(self, item: dict) -> dict:
        return {"status": "done", **item}


def complex_function(
    data: list[dict],
    *,
    filter_fn: Optional[callable] = None,
    max_items: int = 100,
    **kwargs,
) -> list[dict]:
    """A function with complex parameters and high cyclomatic complexity."""
    results = []
    for item in data:
        if filter_fn and not filter_fn(item):
            continue
        if item.get("type") == "a":
            results.append({"category": "alpha", **item})
        elif item.get("type") == "b":
            results.append({"category": "beta", **item})
        else:
            results.append({"category": "other", **item})
        if len(results) >= max_items:
            break
    return results
