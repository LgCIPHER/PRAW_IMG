"""Progress persistence system for resumable operations"""

import json
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List, Set
from datetime import datetime
import logging
from dataclasses import dataclass, asdict
import aiofiles


@dataclass
class ProgressCheckpoint:
    """Represents a progress checkpoint"""
    operation_id: str
    subreddit: str
    processed_urls: Set[str]
    total_items: int
    processed_items: int
    timestamp: str
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "operation_id": self.operation_id,
            "subreddit": self.subreddit,
            "processed_urls": list(self.processed_urls),
            "total_items": self.total_items,
            "processed_items": self.processed_items,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProgressCheckpoint':
        """Create checkpoint from dictionary"""
        data['processed_urls'] = set(data['processed_urls'])
        return cls(**data)


class ProgressManager:
    """Manages progress persistence and recovery"""
    
    def __init__(self, checkpoint_dir: str = ".checkpoints"):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(exist_ok=True)
        self.logger = logging.getLogger(__name__)
        self.current_checkpoints: Dict[str, ProgressCheckpoint] = {}
    
    def _get_checkpoint_path(self, operation_id: str) -> Path:
        """Get file path for checkpoint"""
        return self.checkpoint_dir / f"{operation_id}.json"
    
    async def save_checkpoint(self, checkpoint: ProgressCheckpoint) -> bool:
        """Save checkpoint to disk
        
        Args:
            checkpoint: Checkpoint to save
        
        Returns:
            True if successful, False otherwise
        """
        try:
            checkpoint_path = self._get_checkpoint_path(checkpoint.operation_id)
            
            async with aiofiles.open(checkpoint_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(checkpoint.to_dict(), indent=2))
            
            self.current_checkpoints[checkpoint.operation_id] = checkpoint
            self.logger.debug(f"Saved checkpoint for {checkpoint.operation_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save checkpoint: {e}")
            return False
    
    async def load_checkpoint(self, operation_id: str) -> Optional[ProgressCheckpoint]:
        """Load checkpoint from disk
        
        Args:
            operation_id: ID of operation to load
        
        Returns:
            Checkpoint if found, None otherwise
        """
        try:
            checkpoint_path = self._get_checkpoint_path(operation_id)
            
            if not checkpoint_path.exists():
                return None
            
            async with aiofiles.open(checkpoint_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                data = json.loads(content)
            
            checkpoint = ProgressCheckpoint.from_dict(data)
            self.current_checkpoints[operation_id] = checkpoint
            
            self.logger.info(
                f"Loaded checkpoint for {operation_id}: "
                f"{checkpoint.processed_items}/{checkpoint.total_items} completed"
            )
            return checkpoint
            
        except Exception as e:
            self.logger.error(f"Failed to load checkpoint: {e}")
            return None
    
    async def delete_checkpoint(self, operation_id: str) -> bool:
        """Delete checkpoint file
        
        Args:
            operation_id: ID of operation checkpoint to delete
        
        Returns:
            True if successful, False otherwise
        """
        try:
            checkpoint_path = self._get_checkpoint_path(operation_id)
            
            if checkpoint_path.exists():
                checkpoint_path.unlink()
                self.logger.info(f"Deleted checkpoint for {operation_id}")
            
            if operation_id in self.current_checkpoints:
                del self.current_checkpoints[operation_id]
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to delete checkpoint: {e}")
            return False
    
    async def list_checkpoints(self) -> List[Dict[str, Any]]:
        """List all available checkpoints
        
        Returns:
            List of checkpoint summaries
        """
        checkpoints = []
        
        for checkpoint_file in self.checkpoint_dir.glob("*.json"):
            try:
                async with aiofiles.open(checkpoint_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    data = json.loads(content)
                
                checkpoints.append({
                    "operation_id": data["operation_id"],
                    "subreddit": data["subreddit"],
                    "progress": f"{data['processed_items']}/{data['total_items']}",
                    "timestamp": data["timestamp"]
                })
            except Exception as e:
                self.logger.warning(f"Failed to read {checkpoint_file}: {e}")
        
        return checkpoints


class ResumableOperation:
    """Base class for operations that support resume functionality"""
    
    def __init__(self, operation_id: str, progress_manager: ProgressManager):
        self.operation_id = operation_id
        self.progress_manager = progress_manager
        self.checkpoint: Optional[ProgressCheckpoint] = None
        self.logger = logging.getLogger(__name__)
        self.save_interval = 10  # Save checkpoint every N items
        self.items_since_save = 0
    
    async def initialize(self, subreddit: str, total_items: int) -> bool:
        """Initialize operation, loading checkpoint if exists
        
        Args:
            subreddit: Subreddit being processed
            total_items: Total number of items to process
        
        Returns:
            True if initialized successfully
        """
        # Try to load existing checkpoint
        self.checkpoint = await self.progress_manager.load_checkpoint(self.operation_id)
        
        if self.checkpoint:
            # Ask user if they want to resume
            if await self._ask_resume():
                self.logger.info(
                    f"Resuming from checkpoint: "
                    f"{self.checkpoint.processed_items}/{total_items} items processed"
                )
                return True
            else:
                # Start fresh
                await self.progress_manager.delete_checkpoint(self.operation_id)
                self.checkpoint = None
        
        # Create new checkpoint
        self.checkpoint = ProgressCheckpoint(
            operation_id=self.operation_id,
            subreddit=subreddit,
            processed_urls=set(),
            total_items=total_items,
            processed_items=0,
            timestamp=datetime.now().isoformat(),
            metadata={}
        )
        
        return True
    
    async def _ask_resume(self) -> bool:
        """Ask user if they want to resume from checkpoint"""
        # In a real application, you might use input() or a GUI
        print(f"\nFound existing progress for {self.checkpoint.subreddit}")
        print(f"Completed: {self.checkpoint.processed_items}/{self.checkpoint.total_items}")
        print(f"Last saved: {self.checkpoint.timestamp}")
        
        response = input("Resume from checkpoint? (y/n): ").lower().strip()
        return response == 'y'
    
    async def mark_processed(self, url: str, metadata: Optional[Dict] = None):
        """Mark an item as processed
        
        Args:
            url: URL of processed item
            metadata: Optional metadata to store
        """
        self.checkpoint.processed_urls.add(url)
        self.checkpoint.processed_items += 1
        self.checkpoint.timestamp = datetime.now().isoformat()
        
        if metadata:
            self.checkpoint.metadata.update(metadata)
        
        # Save checkpoint periodically
        self.items_since_save += 1
        if self.items_since_save >= self.save_interval:
            await self.progress_manager.save_checkpoint(self.checkpoint)
            self.items_since_save = 0
    
    def is_processed(self, url: str) -> bool:
        """Check if URL has already been processed
        
        Args:
            url: URL to check
        
        Returns:
            True if already processed
        """
        return url in self.checkpoint.processed_urls
    
    async def finalize(self):
        """Finalize operation and clean up checkpoint"""
        # Save final checkpoint
        await self.progress_manager.save_checkpoint(self.checkpoint)
        
        # Delete checkpoint if operation completed successfully
        if self.checkpoint.processed_items >= self.checkpoint.total_items:
            await self.progress_manager.delete_checkpoint(self.operation_id)
            self.logger.info(f"Operation {self.operation_id} completed successfully")


# Example usage in RedditImageScraper
class ResumableRedditScraper:
    """Reddit scraper with resume capability"""
    
    def __init__(self):
        self.progress_manager = ProgressManager()
        self.logger = logging.getLogger(__name__)
    
    async def process_subreddit(self, subreddit: str, submissions: List[Any]):
        """Process subreddit with resume support"""
        operation_id = f"scrape_{subreddit}_{datetime.now():%Y%m%d}"
        operation = ResumableOperation(operation_id, self.progress_manager)
        
        # Initialize operation
        await operation.initialize(subreddit, len(submissions))
        
        try:
            processed_count = 0
            
            for submission in submissions:
                url = submission.url
                
                # Skip if already processed
                if operation.is_processed(url):
                    self.logger.debug(f"Skipping already processed: {url}")
                    continue
                
                # Process submission
                result = await self._process_submission(submission)
                
                if result:
                    # Mark as processed with metadata
                    await operation.mark_processed(
                        url,
                        metadata={
                            "title": submission.title,
                            "processed_at": datetime.now().isoformat()
                        }
                    )
                    processed_count += 1
            
            # Finalize operation
            await operation.finalize()
            
            self.logger.info(
                f"Completed processing r/{subreddit}: "
                f"{processed_count} new items processed"
            )
            
        except Exception as e:
            # Save checkpoint on error for recovery
            await self.progress_manager.save_checkpoint(operation.checkpoint)
            self.logger.error(f"Operation interrupted: {e}")
            raise
    
    async def _process_submission(self, submission) -> bool:
        """Process a single submission (example)"""
        # Your processing logic here
        await asyncio.sleep(0.1)  # Simulate work
        return True
    
    async def list_pending_operations(self):
        """List all pending operations that can be resumed"""
        checkpoints = await self.progress_manager.list_checkpoints()
        
        if not checkpoints:
            print("No pending operations found")
            return
        
        print("\nPending Operations:")
        print("="*60)
        for cp in checkpoints:
            print(f"Operation: {cp['operation_id']}")
            print(f"Subreddit: r/{cp['subreddit']}")
            print(f"Progress: {cp['progress']}")
            print(f"Timestamp: {cp['timestamp']}")
            print("-"*60)