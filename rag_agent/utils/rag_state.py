from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


RAG_SUCCESS = "success"
RAG_INSUFFICIENT_EVIDENCE = "insufficient_evidence"
RAG_INVALID_OUTPUT = "invalid_output"
RAG_TIMEOUT = "hard_fail_timeout"
RAG_CONNECTION_ERROR = "hard_fail_connection"
RAG_MODEL_SERVICE_ERROR = "hard_fail_model_service"
RAG_WORKER_ERROR = "hard_fail_worker"


@dataclass
class RetrievalResult:
    query: str
    used_filter: Optional[Dict[str, Any]]
    strategy: str
    results: List[Dict[str, Any]] = field(default_factory=list)
    relevant_results: List[Dict[str, Any]] = field(default_factory=list)
    strategy_diagnostics: List[Dict[str, Any]] = field(default_factory=list)
    query_embedding: Optional[List[float]] = None

    @property
    def returned_count(self) -> int:
        return len(self.results)

    @property
    def relevant_count(self) -> int:
        return len(self.relevant_results)

    def to_tool_dict(self) -> Dict[str, Any]:
        """Return the retrieval state exposed to the agent tool caller."""
        diagnostics = []
        for diagnostic in self.strategy_diagnostics:
            diagnostics.append({
                key: value
                for key, value in diagnostic.items()
                if key not in {"docs", "metadatas", "formatted_results", "relevant_results"}
            })
        return {
            "status": "success" if self.relevant_results else "error",
            "error_message": None if self.relevant_results else "No results found",
            "query": self.query,
            "used_filter": self.used_filter,
            "strategy": self.strategy,
            "results": self.relevant_results,
            "returned_count": self.returned_count,
            "relevant_count": self.relevant_count,
            "strategy_diagnostics": diagnostics,
        }


@dataclass
class RAGRequestState:
    latest_retrieval: Optional[RetrievalResult] = None
    latest_confidence: Optional[Dict[str, Any]] = None
    web_search_performed: bool = False
    web_content_ingested: int = 0
    agent_messages: List[str] = field(default_factory=list)
    embedding_cache: Dict[str, List[float]] = field(default_factory=dict)

    def reset(self) -> None:
        self.latest_retrieval = None
        self.latest_confidence = None
        self.web_search_performed = False
        self.web_content_ingested = 0
        self.agent_messages.clear()
        self.embedding_cache.clear()


@dataclass
class RAGResult:
    status: str
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    strategy: Optional[str] = None
    confidence: Optional[str] = None
    confidence_score: Optional[float] = None
    web_search_performed: bool = False
    web_content_ingested: int = 0
    agent_message: Optional[str] = None
    retrieval_state: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
