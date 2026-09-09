"""Semantic repository search tool backed by the repository indexer."""

from __future__ import annotations

from typing import Any

from pix.indexing.indexer import RepositoryIndexer
from pix.tools.base import Tool


class SemanticSearchTool(Tool):
    """Expose semantic repository search to an agent."""

    name = "semantic_search"
    description = (
        "Search the indexed repository by meaning. Returns related code and documentation chunks. "
        "Use this to locate implementations such as authentication, routing, persistence or tests."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Natural-language query or concept to find."},
            "limit": {"type": "integer", "description": "Maximum number of results.", "default": 10},
        },
        "required": ["query"],
        "additionalProperties": False,
    }

    def __init__(self, indexer: RepositoryIndexer) -> None:
        self.indexer = indexer

    def run(self, arguments: dict[str, Any]) -> Any:
        query = str(arguments["query"])
        limit = int(arguments.get("limit", 10))
        results = self.indexer.search_repository(query, limit=min(limit, 20))
        return {"query": query, "count": len(results), "results": [result.to_dict() for result in results]}


__all__ = ["SemanticSearchTool"]
