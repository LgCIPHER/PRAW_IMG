"""Base components for the Reddit Image Scraper."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Callable, Dict, List, Optional

class ScraperState(Enum):
    """States for the scraping process."""
    INITIALIZING = "initializing"
    LOADING_CONFIG = "loading_config"
    CONNECTING = "connecting"
    SCRAPING = "scraping"
    CLEANING = "cleaning"
    ERROR = "error"
    COMPLETED = "completed"

@dataclass
class ScraperEvent:
    """Base class for scraper events."""
    type: str
    data: dict

class EventManager:
    """Manages event subscriptions and publishing."""
    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, callback: Callable) -> None:
        """Subscribe to an event type."""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable) -> None:
        """Unsubscribe from an event type."""
        if event_type in self.subscribers and callback in self.subscribers[event_type]:
            self.subscribers[event_type].remove(callback)

    async def publish(self, event: ScraperEvent) -> None:
        """Publish an event to all subscribers."""
        if event.type in self.subscribers:
            for callback in self.subscribers[event.type]:
                await callback(event)

@dataclass
class ProgressStats:
    """Detailed progress statistics."""
    total_subreddits: int
    processed_subreddits: int
    total_posts: int
    processed_posts: int
    start_time: datetime
    current_batch: int = 0
    total_batches: int = 0
    batch_size: int = 0
    estimated_completion_time: Optional[datetime] = None
    current_subreddit: str = ""
    
    def calculate_eta(self) -> None:
        """Calculate estimated completion time."""
        if self.processed_subreddits == 0:
            return None
        
        elapsed = (datetime.now() - self.start_time).total_seconds()
        rate = self.processed_subreddits / elapsed
        remaining = (self.total_subreddits - self.processed_subreddits) / rate
        self.estimated_completion_time = datetime.fromtimestamp(
            datetime.now().timestamp() + remaining
        )

class ScraperCommand(ABC):
    """Abstract base class for scraper commands."""
    @abstractmethod
    async def execute(self) -> None:
        """Execute the command."""
        pass