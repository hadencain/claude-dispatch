from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class UsageEvent:
    session_id: str
    project: str
    model: str
    timestamp: datetime
    request_id: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_5m_tokens: int
    cache_write_1h_tokens: int
    web_search_requests: int
    web_fetch_requests: int

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["timestamp"] = self.timestamp.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "UsageEvent":
        d = dict(d)
        d["timestamp"] = datetime.fromisoformat(d["timestamp"])
        return cls(**d)


@dataclass(frozen=True)
class CostBreakdown:
    input: float = 0.0
    output: float = 0.0
    cache_read: float = 0.0
    cache_write_5m: float = 0.0
    cache_write_1h: float = 0.0
    web: float = 0.0
    unpriced: bool = False

    @property
    def total(self) -> float:
        return (self.input + self.output + self.cache_read
                + self.cache_write_5m + self.cache_write_1h + self.web)
