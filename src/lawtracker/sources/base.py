"""Source adapter framework.

Every concrete source (DOJ FCPA actions list, FCPA Blog RSS, AFP media releases,
etc.) is a subclass of `SourceAdapter`. The base class handles the boilerplate
of HTTP fetching and converts errors into a `PollResult`; subclasses implement
only the source-specific extraction in `parse()`.
"""

from abc import ABC, abstractmethod
from datetime import date
from typing import Any, ClassVar, Literal

import httpx
from pydantic import BaseModel, Field

PollStatus = Literal["ok", "transient_failure", "permanent_failure"]


class EventRecord(BaseModel):
    """One observation an event_list adapter emits.

    The universal fields are populated by every adapter (None where the source
    genuinely lacks the data). Source-specific structured data goes in `metadata`,
    which the storage layer maps to a JSON column.
    """

    dedup_key: str
    source_id: str
    event_date: date | None
    title: str
    primary_actor: str | None
    summary: str | None
    url: str
    country: str | None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PollResult(BaseModel):
    """Result of a single poll cycle.

    `status` is the fetch outcome, not a change-detection outcome — the storage
    layer set-reconciles `events` against persisted state to decide what is new.
    """

    status: PollStatus
    events: list[EventRecord] = Field(default_factory=list)
    error: str | None = None


class SourceAdapter(ABC):
    """Per-source scraper.

    Subclasses declare class-level `source_id`, `kind`, and `url`, and implement
    `parse(html, client)`. The base class handles HTTP and error classification:

    - Transport errors and 5xx → `transient_failure` (poll loop retries on
      next cadence).
    - 4xx and parse errors → `permanent_failure` (loud log; surfaces in
      dashboard once that lands).

    Subclasses that need to fetch multiple URLs per poll (e.g. paginated
    archives, year-bucketed lists) override the `urls` property; the base
    iterates them and concatenates events. The first non-ok status across
    URLs becomes the result's status.

    Subclasses that need to make extra HTTP requests during parsing (e.g.
    DOJ FCPA actions following a link from each list-page entry to the
    matching press release for richer metadata) accept the `client` argument
    in `parse()`. Adapters that don't need it ignore it.

    Recommended dedup-key pattern for event_list subclasses: use the canonical
    detail URL when stable; otherwise hash a stable subset of fields (typically
    title + listed date).
    """

    source_id: ClassVar[str]
    kind: ClassVar[Literal["document", "event_list", "both"]]
    url: ClassVar[str]

    timeout_seconds: ClassVar[float] = 30.0
    user_agent: ClassVar[str] = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    @property
    def urls(self) -> tuple[str, ...]:
        """URLs to fetch per poll. Override for paginated / multi-page sources."""
        return (self.url,)

    def poll(self, *, client: httpx.Client | None = None) -> PollResult:
        """Fetch the source and return a PollResult.

        `client` is for test injection. Production callers pass None and the
        base class manages a default client with the configured timeout.
        """
        if client is None:
            with httpx.Client(
                timeout=self.timeout_seconds,
                follow_redirects=True,
                headers={"User-Agent": self.user_agent},
            ) as owned:
                return self._do_poll(owned)
        return self._do_poll(client)

    def _do_poll(self, client: httpx.Client) -> PollResult:
        all_events: list[EventRecord] = []
        worst_status: PollStatus = "ok"
        first_error: str | None = None

        for url in self.urls:
            single = self._fetch_one(client, url)
            if single.status != "ok":
                if worst_status == "ok":
                    worst_status = single.status
                    first_error = single.error
                continue
            all_events.extend(single.events)

        return PollResult(status=worst_status, events=all_events, error=first_error)

    def _fetch_one(self, client: httpx.Client, url: str) -> PollResult:
        try:
            response = client.get(url)
        except httpx.RequestError as exc:
            return PollResult(
                status="transient_failure", error=f"request error: {exc}"
            )

        if 500 <= response.status_code < 600:
            return PollResult(
                status="transient_failure",
                error=f"HTTP {response.status_code}",
            )
        if response.status_code >= 400:
            return PollResult(
                status="permanent_failure",
                error=f"HTTP {response.status_code}",
            )

        try:
            events = self.parse(response.text, client)
        except Exception as exc:
            return PollResult(
                status="permanent_failure",
                error=f"parse error: {type(exc).__name__}: {exc}",
            )
        return PollResult(status="ok", events=events)

    @abstractmethod
    def parse(self, html: str, client: httpx.Client) -> list[EventRecord]:
        """Extract EventRecords from the source's raw page content.

        `client` is provided for adapters that need to follow links during
        parsing (e.g. fetching a press release per list-page entry for
        richer metadata). Adapters that don't need it ignore it.
        """
