from collections import deque
from datetime import datetime
import asyncio
from logging_config import logger

class ServerActionQueue:
    def __init__(self):
        self.queue = deque()
        self.processing = False
        self._lock = asyncio.Lock()
        
    async def add_action(self, action, guild_id, user_id):
        """Add a server action to the queue"""
        async with self._lock:
            action_item = {
                'action': action,
                'guild_id': guild_id,
                'user_id': user_id,
                'timestamp': datetime.now()
            }
            self.queue.append(action_item)
            logger.info(f"Added action to queue: {action_item}")
            
            if not self.processing:
                await self.process_queue()
    
    async def process_queue(self):
        """Process queued actions"""
        self.processing = True
        
        while self.queue:
            async with self._lock:
                action_item = self.queue.popleft()
                
            try:
                logger.info(f"Processing action: {action_item}")
                # Add more descriptive logging
                logger.info(f"Action '{action_item['action']}' from user {action_item['user_id']} in guild {action_item['guild_id']}")
                
                # Here we would actually process the action with the controller
                # but it's handled directly in the command functions
                
                # Add timestamp for completion
                action_item['completed_at'] = datetime.now()
                action_item['success'] = True
                
                # Calculate and log processing time
                start_time = action_item['timestamp']
                end_time = action_item['completed_at']
                processing_time = (end_time - start_time).total_seconds()
                logger.info(f"Action completed in {processing_time:.2f} seconds")
                
                # Cooldown between actions to avoid rate limiting
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"Error processing action: {e}")
                action_item['completed_at'] = datetime.now()
                action_item['success'] = False
                action_item['error'] = str(e)
                
        self.processing = False
        logger.info("Queue processing completed")

queue_manager = ServerActionQueue()
