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
