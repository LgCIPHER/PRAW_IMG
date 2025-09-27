"""Memory-efficient batch processing for large datasets"""

import asyncio
from typing import AsyncIterator, List, Callable, Any, TypeVar
import psutil
import logging
from dataclasses import dataclass
import gc

T = TypeVar('T')


@dataclass
class MemoryStats:
    """Memory usage statistics"""
    used_mb: float
    available_mb: float
    percent_used: float
    
    def __str__(self) -> str:
        return (
            f"Memory: {self.used_mb:.1f}MB used, "
            f"{self.available_mb:.1f}MB available ({self.percent_used:.1f}% used)"
        )


class MemoryMonitor:
    """Monitor and manage memory usage"""
    
    def __init__(self, max_memory_mb: float = 500.0, warning_threshold: float = 0.8):
        self.max_memory_mb = max_memory_mb
        self.warning_threshold = warning_threshold
        self.logger = logging.getLogger(__name__)
        self.process = psutil.Process()
    
    def get_current_usage(self) -> MemoryStats:
        """Get current memory usage statistics"""
        mem_info = self.process.memory_info()
        used_mb = mem_info.rss / (1024 * 1024)
        
        virtual_mem = psutil.virtual_memory()
        available_mb = virtual_mem.available / (1024 * 1024)
        percent_used = virtual_mem.percent / 100.0
        
        return MemoryStats(used_mb, available_mb, percent_used)
    
    def check_memory_pressure(self) -> bool:
        """Check if memory usage is approaching limits
        
        Returns:
            True if memory pressure is high
        """
        stats = self.get_current_usage()
        
        if stats.used_mb > self.max_memory_mb * self.warning_threshold:
            self.logger.warning(
                f"High memory usage detected: {stats}"
            )
            return True
        
        return False
    
    def force_cleanup(self):
        """Force garbage collection and cleanup"""
        gc.collect()
        self.logger.debug("Forced garbage collection completed")


class StreamProcessor:
    """Process items in streaming fashion to minimize memory usage"""
    
    def __init__(self, batch_size: int = 100, max_memory_mb: float = 500.0):
        self.batch_size = batch_size
        self.memory_monitor = MemoryMonitor(max_memory_mb)
        self.logger = logging.getLogger(__name__)
    
    async def stream_csv_lines(self, file_path: str) -> AsyncIterator[str]:
        """Stream CSV lines without loading entire file
        
        Args:
            file_path: Path to CSV file
        
        Yields:
            Individual CSV lines
        """
        import aiofiles
        
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8-sig') as f:
                # Skip header
                await f.readline()
                
                async for line in f:
                    if line.strip():
                        yield line.strip()
                        
                        # Check memory periodically
                        if self.memory_monitor.check_memory_pressure():
                            self.memory_monitor.force_cleanup()
                            await asyncio.sleep(0.1)  # Allow cleanup to complete
                            
        except Exception as e:
            self.logger.error(f"Error streaming file {file_path}: {e}")
            raise
    
    async def process_in_batches(
        self,
        items: AsyncIterator[T],
        processor: Callable[[List[T]], Any],
        progress_callback: Callable[[int], None] = None
    ):
        """Process items in batches to control memory usage
        
        Args:
            items: Async iterator of items to process
            processor: Function to process each batch
            progress_callback: Optional callback for progress updates
        """
        batch = []
        processed_count = 0
        
        async for item in items:
            batch.append(item)
            
            if len(batch) >= self.batch_size:
                # Process batch
                await processor(batch)
                processed_count += len(batch)
                
                if progress_callback:
                    progress_callback(processed_count)
                
                # Clear batch and check memory
                batch.clear()
                
                if self.memory_monitor.check_memory_pressure():
                    self.memory_monitor.force_cleanup()
                    await asyncio.sleep(0.1)
        
        # Process remaining items
        if batch:
            await processor(batch)
            processed_count += len(batch)
            
            if progress_callback:
                progress_callback(processed_count)


class ChunkedFileReader:
    """Read files in chunks to minimize memory footprint"""
    
    def __init__(self, chunk_size: int = 1024 * 1024):  # 1MB chunks
        self.chunk_size = chunk_size
        self.logger = logging.getLogger(__name__)
    
    async def read_in_chunks(self, file_path: str) -> AsyncIterator[bytes]:
        """Read file in chunks
        
        Args:
            file_path: Path to file
        
        Yields:
            Chunks of file data
        """
        import aiofiles
        
        try:
            async with aiofiles.open(file_path, 'rb') as f:
                while True:
                    chunk = await f.read(self.chunk_size)
                    if not chunk:
                        break
                    yield chunk
                    
        except Exception as e:
            self.logger.error(f"Error reading file {file_path}: {e}")
            raise


class MemoryEfficientCSVCleaner:
    """CSV cleaner optimized for low memory usage"""
    
    def __init__(self, max_memory_mb: float = 500.0):
        self.stream_processor = StreamProcessor(
            batch_size=50,
            max_memory_mb=max_memory_mb
        )
        self.logger = logging.getLogger(__name__)
    
    async def clean_large_csv(
        self,
        input_path: str,
        output_path: str,
        validator: Callable[[str], bool]
    ) -> int:
        """Clean CSV file without loading entire file into memory
        
        Args:
            input_path: Path to input CSV
            output_path: Path to output CSV
            validator: Function to validate each URL
        
        Returns:
            Number of valid lines written
        """
        import aiofiles
        
        valid_count = 0
        removed_count = 0
        
        async with aiofiles.open(output_path, 'w', encoding='utf-8-sig') as out_file:
            # Write header
            async with aiofiles.open(input_path, 'r', encoding='utf-8-sig') as in_file:
                header = await in_file.readline()
                await out_file.write(header)
            
            # Process lines in streaming fashion
            async for line in self.stream_processor.stream_csv_lines(input_path):
                try:
                    # Extract URL from line (assuming CSV format: id,subreddit,title,url)
                    parts = line.split(',')
                    if len(parts) >= 4:
                        url = parts[3].strip()
                        
                        if await validator(url):
                            # Write valid line
                            valid_count += 1
                            new_id = valid_count
                            parts[0] = str(new_id)
                            await out_file.write(','.join(parts) + '\n')
                        else:
                            removed_count += 1
                    
                except Exception as e:
                    self.logger.warning(f"Error processing line: {e}")
                    removed_count += 1
        
        self.logger.info(
            f"Cleaning complete: {valid_count} valid, {removed_count} removed"
        )
        return valid_count
    
    async def process_csv_batches(
        self,
        file_path: str,
        batch_processor: Callable[[List[dict]], Any]
    ):
        """Process CSV in batches
        
        Args:
            file_path: Path to CSV file
            batch_processor: Async function to process each batch
        """
        import aiofiles
        
        batch = []
        headers = []
        
        async with aiofiles.open(file_path, 'r', encoding='utf-8-sig') as f:
            # Read header
            header_line = await f.readline()
            headers = header_line.strip().split(',')
            
            async for line in f:
                if line.strip():
                    values = line.strip().split(',')
                    row = {h: v for h, v in zip(headers, values)}
                    batch.append(row)
                    
                    if len(batch) >= self.stream_processor.batch_size:
                        await batch_processor(batch)
                        batch.clear()
                        
                        # Memory check
                        if self.stream_processor.memory_monitor.check_memory_pressure():
                            self.stream_processor.memory_monitor.force_cleanup()
                            await asyncio.sleep(0.1)
            
            # Process remaining items
            if batch:
                await batch_processor(batch)


# Example usage
async def example_usage():
    """Demonstrate memory-efficient processing"""
    
    cleaner = MemoryEfficientCSVCleaner(max_memory_mb=200)
    
    # Define URL validator
    async def validate_url(url: str) -> bool:
        # Your validation logic
        return url.startswith('http')
    
    # Clean large CSV file
    await cleaner.clean_large_csv(
        input_path='large_file.csv',
        output_path='cleaned_file.csv',
        validator=validate_url
    )
    
    # Or process in batches
    async def process_batch(batch: List[dict]):
        # Process batch of rows
        print(f"Processing batch of {len(batch)} items")
    
    await cleaner.process_csv_batches(
        file_path='large_file.csv',
        batch_processor=process_batch
    )