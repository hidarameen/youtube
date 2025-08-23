"""
Rate limiting middleware for the Telegram bot
Prevents spam and ensures fair usage across users
"""

import asyncio
import json
import logging
import time
from typing import Dict, Optional, Tuple, Any
from collections import defaultdict, deque
from dataclasses import dataclass

from telegram import Update
from telegram.ext import ContextTypes

from config.settings import settings
from services.cache_manager import CacheManager

logger = logging.getLogger(__name__)

@dataclass
class RateLimit:
    """Rate limit configuration"""
    max_requests: int
    time_window: int  # seconds
    penalty_duration: int = 0  # seconds to wait after limit exceeded

class RateLimitMiddleware:
    """Advanced rate limiting middleware with multiple strategies"""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager
        
        # Rate limits configuration
        self.rate_limits = {
            'global': RateLimit(
                max_requests=settings.MAX_USERS_PER_MINUTE,
                time_window=60,  # 1 minute
                penalty_duration=30  # 30 seconds penalty
            ),
            'user': RateLimit(
                max_requests=settings.MAX_DOWNLOADS_PER_USER,
                time_window=3600,  # 1 hour
                penalty_duration=300  # 5 minutes penalty
            ),
            'download': RateLimit(
                max_requests=3,
                time_window=60,  # 1 minute for downloads
                penalty_duration=60  # 1 minute penalty
            ),
            'command': RateLimit(
                max_requests=10,
                time_window=60,  # 1 minute for commands
                penalty_duration=30  # 30 seconds penalty
            )
        }
        
        # In-memory tracking for fast access
        self.user_requests: Dict[int, deque] = defaultdict(deque)
        self.global_requests: deque = deque()
        self.user_penalties: Dict[int, float] = {}
        
        # Statistics
        self.stats = {
            'total_requests': 0,
            'blocked_requests': 0,
            'penalty_imposed': 0
        }
        
        logger.info("✅ Rate limit middleware initialized")
    
    async def check_rate_limit(
        self, 
        update: Update, 
        action_type: str = 'command'
    ) -> bool:
        """
        Check if request is within rate limits
        
        Args:
            update: Telegram update object
            action_type: Type of action ('command', 'download', 'upload')
            
        Returns:
            bool: True if request is allowed, False if rate limited
        """
        try:
            user = update.effective_user
            if not user:
                return False
            
            user_id = user.id
            current_time = time.time()
            
            self.stats['total_requests'] += 1
            
            # Check if user is currently under penalty
            if await self._is_user_penalized(user_id, current_time):
                logger.warning(f"🚫 User {user_id} is under penalty, request blocked")
                self.stats['blocked_requests'] += 1
                return False
            
            # Check global rate limit
            if not await self._check_global_limit(current_time):
                logger.warning(f"🌐 Global rate limit exceeded, blocking user {user_id}")
                self.stats['blocked_requests'] += 1
                return False
            
            # Check user-specific rate limit
            if not await self._check_user_limit(user_id, current_time, action_type):
                logger.warning(f"👤 User {user_id} rate limit exceeded for action: {action_type}")
                await self._impose_penalty(user_id, action_type, current_time)
                self.stats['blocked_requests'] += 1
                self.stats['penalty_imposed'] += 1
                return False
            
            # Request is allowed, record it
            await self._record_request(user_id, current_time, action_type)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Rate limit check error: {e}", exc_info=True)
            # Allow request on error to prevent breaking the bot
            return True
    
    async def _is_user_penalized(self, user_id: int, current_time: float) -> bool:
        """Check if user is currently under penalty"""
        try:
            # Check in-memory cache first
            if user_id in self.user_penalties:
                penalty_end = self.user_penalties[user_id]
                if current_time < penalty_end:
                    return True
                else:
                    # Penalty expired, remove it
                    del self.user_penalties[user_id]
            
            # Check Redis cache for persistent penalties
            penalty_key = f"rate_limit:penalty:{user_id}"
            penalty_end = await self.cache_manager.get(penalty_key)
            
            if penalty_end:
                penalty_end_time = float(penalty_end)
                if current_time < penalty_end_time:
                    # Update in-memory cache
                    self.user_penalties[user_id] = penalty_end_time
                    return True
                else:
                    # Penalty expired, remove it
                    await self.cache_manager.delete(penalty_key)
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking user penalty: {e}")
            return False
    
    async def _check_global_limit(self, current_time: float) -> bool:
        """Check global rate limit"""
        try:
            rate_limit = self.rate_limits['global']
            
            # Clean old requests from in-memory deque
            while (self.global_requests and 
                   current_time - self.global_requests[0] > rate_limit.time_window):
                self.global_requests.popleft()
            
            # Check if we're within limit
            if len(self.global_requests) >= rate_limit.max_requests:
                return False
            
            # Add current request
            self.global_requests.append(current_time)
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking global limit: {e}")
            return True  # Allow on error
    
    async def _check_user_limit(
        self, 
        user_id: int, 
        current_time: float, 
        action_type: str
    ) -> bool:
        """Check user-specific rate limit"""
        try:
            # Determine which rate limit to use
            if action_type == 'download':
                rate_limit = self.rate_limits['download']
            else:
                rate_limit = self.rate_limits['user']
            
            # Get user's request history from cache
            requests_key = f"rate_limit:user:{user_id}:{action_type}"
            cached_requests = await self.cache_manager.get(requests_key)
            
            if cached_requests:
                import json
                request_times = json.loads(cached_requests)
            else:
                request_times = []
            
            # Filter out old requests
            cutoff_time = current_time - rate_limit.time_window
            recent_requests = [t for t in request_times if t > cutoff_time]
            
            # Check if within limit
            if len(recent_requests) >= rate_limit.max_requests:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking user limit: {e}")
            return True  # Allow on error
    
    async def _record_request(
        self, 
        user_id: int, 
        current_time: float, 
        action_type: str
    ):
        """Record a request for rate limiting tracking"""
        try:
            # Update in-memory tracking
            if user_id not in self.user_requests:
                self.user_requests[user_id] = deque()
            
            self.user_requests[user_id].append(current_time)
            
            # Keep only recent requests in memory
            rate_limit = self.rate_limits.get(action_type, self.rate_limits['user'])
            cutoff_time = current_time - rate_limit.time_window
            
            while (self.user_requests[user_id] and 
                   self.user_requests[user_id][0] < cutoff_time):
                self.user_requests[user_id].popleft()
            
            # Update Redis cache
            requests_key = f"rate_limit:user:{user_id}:{action_type}"
            cached_requests = await self.cache_manager.get(requests_key)
            
            if cached_requests:
                import json
                request_times = json.loads(cached_requests)
            else:
                request_times = []
            
            # Add current request and filter old ones
            request_times.append(current_time)
            request_times = [t for t in request_times if t > cutoff_time]
            
            # Save back to cache
            await self.cache_manager.set(
                requests_key,
                json.dumps(request_times),
                expire=rate_limit.time_window
            )
            
        except Exception as e:
            logger.error(f"Error recording request: {e}")
    
    async def _impose_penalty(
        self, 
        user_id: int, 
        action_type: str, 
        current_time: float
    ):
        """Impose penalty on user for exceeding rate limit"""
        try:
            rate_limit = self.rate_limits.get(action_type, self.rate_limits['user'])
            penalty_end = current_time + rate_limit.penalty_duration
            
            # Store in memory for fast access
            self.user_penalties[user_id] = penalty_end
            
            # Store in Redis for persistence
            penalty_key = f"rate_limit:penalty:{user_id}"
            await self.cache_manager.set(
                penalty_key,
                str(penalty_end),
                expire=rate_limit.penalty_duration
            )
            
            logger.info(f"⏰ Imposed {rate_limit.penalty_duration}s penalty on user {user_id}")
            
        except Exception as e:
            logger.error(f"Error imposing penalty: {e}")
    
    async def get_user_rate_limit_info(self, user_id: int) -> Dict[str, Any]:
        """Get rate limit information for a user"""
        try:
            current_time = time.time()
            info = {}
            
            # Check penalty status
            penalty_key = f"rate_limit:penalty:{user_id}"
            penalty_end = await self.cache_manager.get(penalty_key)
            
            if penalty_end:
                penalty_end_time = float(penalty_end)
                if current_time < penalty_end_time:
                    info['penalized'] = True
                    info['penalty_remaining'] = int(penalty_end_time - current_time)
                else:
                    info['penalized'] = False
            else:
                info['penalized'] = False
            
            # Get request counts for different actions
            for action_type, rate_limit in self.rate_limits.items():
                if action_type == 'global':
                    continue
                
                requests_key = f"rate_limit:user:{user_id}:{action_type}"
                cached_requests = await self.cache_manager.get(requests_key)
                
                if cached_requests:
                    import json
                    request_times = json.loads(cached_requests)
                    cutoff_time = current_time - rate_limit.time_window
                    recent_requests = [t for t in request_times if t > cutoff_time]
                    
                    info[f'{action_type}_requests'] = len(recent_requests)
                    info[f'{action_type}_limit'] = rate_limit.max_requests
                    info[f'{action_type}_remaining'] = max(0, rate_limit.max_requests - len(recent_requests))
                else:
                    info[f'{action_type}_requests'] = 0
                    info[f'{action_type}_limit'] = rate_limit.max_requests
                    info[f'{action_type}_remaining'] = rate_limit.max_requests
            
            return info
            
        except Exception as e:
            logger.error(f"Error getting rate limit info: {e}")
            return {}
    
    async def reset_user_limits(self, user_id: int):
        """Reset all rate limits for a user (admin function)"""
        try:
            # Remove penalty
            penalty_key = f"rate_limit:penalty:{user_id}"
            await self.cache_manager.delete(penalty_key)
            
            if user_id in self.user_penalties:
                del self.user_penalties[user_id]
            
            # Clear request history
            for action_type in self.rate_limits.keys():
                if action_type == 'global':
                    continue
                
                requests_key = f"rate_limit:user:{user_id}:{action_type}"
                await self.cache_manager.delete(requests_key)
            
            # Clear in-memory tracking
            if user_id in self.user_requests:
                del self.user_requests[user_id]
            
            logger.info(f"🔄 Reset all rate limits for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error resetting user limits: {e}")
    
    def get_global_stats(self) -> Dict[str, Any]:
        """Get global rate limiting statistics"""
        try:
            current_time = time.time()
            
            # Count active penalties
            active_penalties = sum(
                1 for penalty_end in self.user_penalties.values()
                if current_time < penalty_end
            )
            
            # Calculate rate limit efficiency
            total_requests = self.stats['total_requests']
            blocked_requests = self.stats['blocked_requests']
            
            if total_requests > 0:
                success_rate = ((total_requests - blocked_requests) / total_requests) * 100
            else:
                success_rate = 100
            
            return {
                'total_requests': total_requests,
                'blocked_requests': blocked_requests,
                'success_rate': success_rate,
                'active_penalties': active_penalties,
                'penalties_imposed': self.stats['penalty_imposed'],
                'tracked_users': len(self.user_requests),
                'global_requests_1m': len(self.global_requests)
            }
            
        except Exception as e:
            logger.error(f"Error getting global stats: {e}")
            return {}
    
    async def cleanup_expired_data(self):
        """Clean up expired rate limiting data"""
        try:
            current_time = time.time()
            cleaned_count = 0
            
            # Clean expired penalties from memory
            expired_penalties = [
                user_id for user_id, penalty_end in self.user_penalties.items()
                if current_time >= penalty_end
            ]
            
            for user_id in expired_penalties:
                del self.user_penalties[user_id]
                cleaned_count += 1
            
            # Clean old requests from memory
            for user_id in list(self.user_requests.keys()):
                user_requests = self.user_requests[user_id]
                
                # Remove requests older than the longest time window
                max_window = max(limit.time_window for limit in self.rate_limits.values())
                cutoff_time = current_time - max_window
                
                while user_requests and user_requests[0] < cutoff_time:
                    user_requests.popleft()
                
                # Remove empty deques
                if not user_requests:
                    del self.user_requests[user_id]
                    cleaned_count += 1
            
            # Clean global requests
            global_limit = self.rate_limits['global']
            cutoff_time = current_time - global_limit.time_window
            
            while self.global_requests and self.global_requests[0] < cutoff_time:
                self.global_requests.popleft()
            
            if cleaned_count > 0:
                logger.info(f"🗑️ Cleaned up {cleaned_count} expired rate limit records")
            
        except Exception as e:
            logger.error(f"Error cleaning up expired data: {e}")
    
    async def is_action_allowed(
        self, 
        user_id: int, 
        action_type: str = 'command'
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if an action is allowed for a user
        
        Args:
            user_id: User ID to check
            action_type: Type of action
            
        Returns:
            Tuple of (allowed, reason if not allowed)
        """
        try:
            current_time = time.time()
            
            # Check penalty
            if await self._is_user_penalized(user_id, current_time):
                penalty_key = f"rate_limit:penalty:{user_id}"
                penalty_end = await self.cache_manager.get(penalty_key)
                
                if penalty_end:
                    remaining = int(float(penalty_end) - current_time)
                    return False, f"Rate limit penalty active. Try again in {remaining} seconds."
            
            # Check limits
            rate_limit = self.rate_limits.get(action_type, self.rate_limits['user'])
            
            requests_key = f"rate_limit:user:{user_id}:{action_type}"
            cached_requests = await self.cache_manager.get(requests_key)
            
            if cached_requests:
                import json
                request_times = json.loads(cached_requests)
                cutoff_time = current_time - rate_limit.time_window
                recent_requests = [t for t in request_times if t > cutoff_time]
                
                if len(recent_requests) >= rate_limit.max_requests:
                    return False, f"Rate limit exceeded. Maximum {rate_limit.max_requests} {action_type}s per {rate_limit.time_window} seconds."
            
            return True, None
            
        except Exception as e:
            logger.error(f"Error checking action allowance: {e}")
            return True, None  # Allow on error
