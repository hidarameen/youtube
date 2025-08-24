"""
Authentication middleware for the Telegram bot
Handles access control based on allowed chat IDs and user permissions
"""

import logging
from typing import List, Set, Optional
from telegram import Update
from telegram.ext import ContextTypes

from config.settings import settings

logger = logging.getLogger(__name__)

class AuthMiddleware:
    """Authentication and authorization middleware"""
    
    def __init__(self):
        # Convert allowed chat IDs to set for faster lookups
        self.allowed_chat_ids: Set[int] = set(settings.ALLOWED_CHAT_IDS)
        self.admin_user_ids: Set[int] = set(settings.ADMIN_USER_IDS)
        
        # Cache for authorized users to reduce database lookups
        self.authorized_users_cache: Set[int] = set()
        self.unauthorized_users_cache: Set[int] = set()
        
        # Track access attempts for security monitoring
        self.access_attempts = {}
        
        # Brute force protection
        self.max_failed_attempts = 5
        self.lockout_duration = 300  # 5 minutes
        self.failed_attempts: Dict[int, List[float]] = {}
        
        # Audit logging
        self.enable_audit_log = True
        self.audit_log_file = 'logs/security_audit.log'
        
        logger.info(f"✅ Auth middleware initialized with {len(self.allowed_chat_ids)} allowed chats")
    
    async def check_access(self, update: Update) -> bool:
        """
        Check if user has access to the bot
        
        Args:
            update: Telegram update object
            
        Returns:
            bool: True if access granted, False otherwise
        """
        try:
            user = update.effective_user
            chat = update.effective_chat
            
            if not user or not chat:
                logger.warning("❌ Access denied: No user or chat information")
                return False
            
            user_id = user.id
            chat_id = chat.id
            
            # Check cache first for performance
            if user_id in self.authorized_users_cache:
                return True
            
            if user_id in self.unauthorized_users_cache:
                logger.debug(f"❌ Access denied for cached unauthorized user {user_id}")
                return False
            
            # Admin users always have access
            if user_id in self.admin_user_ids:
                logger.info(f"✅ Admin access granted to user {user_id}")
                self.authorized_users_cache.add(user_id)
                return True
            
            # Check if chat is allowed
            if chat_id not in self.allowed_chat_ids:
                logger.warning(f"❌ Access denied: Chat {chat_id} not in allowed list")
                self._log_access_attempt(user_id, chat_id, False, "Chat not allowed")
                self.unauthorized_users_cache.add(user_id)
                return False
            
            # For group chats, check if user is a member
            if chat.type in ['group', 'supergroup']:
                try:
                    member = await chat.get_member(user_id)
                    if member.status in ['kicked', 'left']:
                        logger.warning(f"❌ Access denied: User {user_id} not a member of chat {chat_id}")
                        self._log_access_attempt(user_id, chat_id, False, "Not a group member")
                        return False
                except Exception as e:
                    logger.error(f"❌ Error checking group membership: {e}")
                    return False
            
            # Access granted
            logger.info(f"✅ Access granted to user {user_id} in chat {chat_id}")
            self._log_access_attempt(user_id, chat_id, True, "Access granted")
            self.authorized_users_cache.add(user_id)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Auth middleware error: {e}", exc_info=True)
            return False
    
    def is_admin(self, user_id: int) -> bool:
        """
        Check if user is an admin
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            bool: True if user is admin
        """
        return user_id in self.admin_user_ids
    
    def add_allowed_chat(self, chat_id: int):
        """
        Add a chat ID to allowed list
        
        Args:
            chat_id: Chat ID to add
        """
        self.allowed_chat_ids.add(chat_id)
        logger.info(f"✅ Added chat {chat_id} to allowed list")
    
    def remove_allowed_chat(self, chat_id: int):
        """
        Remove a chat ID from allowed list
        
        Args:
            chat_id: Chat ID to remove
        """
        self.allowed_chat_ids.discard(chat_id)
        logger.info(f"🗑️ Removed chat {chat_id} from allowed list")
    
    def add_admin_user(self, user_id: int):
        """
        Add a user to admin list
        
        Args:
            user_id: User ID to add as admin
        """
        self.admin_user_ids.add(user_id)
        self.authorized_users_cache.add(user_id)
        logger.info(f"✅ Added user {user_id} as admin")
    
    def remove_admin_user(self, user_id: int):
        """
        Remove a user from admin list
        
        Args:
            user_id: User ID to remove from admin
        """
        self.admin_user_ids.discard(user_id)
        self.authorized_users_cache.discard(user_id)
        logger.info(f"🗑️ Removed user {user_id} from admin list")
    
    def clear_user_cache(self, user_id: Optional[int] = None):
        """
        Clear user authorization cache
        
        Args:
            user_id: Specific user ID to clear, or None to clear all
        """
        if user_id:
            self.authorized_users_cache.discard(user_id)
            self.unauthorized_users_cache.discard(user_id)
            logger.debug(f"🗑️ Cleared cache for user {user_id}")
        else:
            self.authorized_users_cache.clear()
            self.unauthorized_users_cache.clear()
            logger.info("🗑️ Cleared all user authorization cache")
    
    def _log_access_attempt(self, user_id: int, chat_id: int, success: bool, reason: str):
        """
        Log access attempt for security monitoring
        
        Args:
            user_id: User ID attempting access
            chat_id: Chat ID where access was attempted
            success: Whether access was granted
            reason: Reason for access decision
        """
        try:
            import time
            
            attempt_key = f"{user_id}_{chat_id}"
            current_time = time.time()
            
            if attempt_key not in self.access_attempts:
                self.access_attempts[attempt_key] = []
            
            # Add current attempt
            self.access_attempts[attempt_key].append({
                'timestamp': current_time,
                'success': success,
                'reason': reason
            })
            
            # Keep only last 10 attempts per user-chat combination
            self.access_attempts[attempt_key] = self.access_attempts[attempt_key][-10:]
            
            # Log failed attempts for security monitoring
            if not success:
                recent_failures = [
                    attempt for attempt in self.access_attempts[attempt_key]
                    if not attempt['success'] and current_time - attempt['timestamp'] < 300  # 5 minutes
                ]
                
                if len(recent_failures) >= 3:
                    logger.warning(f"🚨 Multiple failed access attempts from user {user_id} in chat {chat_id}")
            
        except Exception as e:
            logger.error(f"Error logging access attempt: {e}")
    
    def get_access_stats(self) -> dict:
        """
        Get access statistics for monitoring
        
        Returns:
            dict: Access statistics
        """
        try:
            import time
            
            current_time = time.time()
            total_attempts = 0
            successful_attempts = 0
            recent_attempts = 0
            
            for attempts in self.access_attempts.values():
                for attempt in attempts:
                    total_attempts += 1
                    if attempt['success']:
                        successful_attempts += 1
                    
                    # Count recent attempts (last hour)
                    if current_time - attempt['timestamp'] < 3600:
                        recent_attempts += 1
            
            success_rate = (successful_attempts / total_attempts * 100) if total_attempts > 0 else 0
            
            return {
                'total_attempts': total_attempts,
                'successful_attempts': successful_attempts,
                'success_rate': success_rate,
                'recent_attempts_1h': recent_attempts,
                'allowed_chats_count': len(self.allowed_chat_ids),
                'admin_users_count': len(self.admin_user_ids),
                'cached_authorized_users': len(self.authorized_users_cache),
                'cached_unauthorized_users': len(self.unauthorized_users_cache)
            }
            
        except Exception as e:
            logger.error(f"Error getting access stats: {e}")
            return {}
    
    def is_chat_allowed(self, chat_id: int) -> bool:
        """
        Check if a chat is in the allowed list
        
        Args:
            chat_id: Chat ID to check
            
        Returns:
            bool: True if chat is allowed
        """
        return chat_id in self.allowed_chat_ids
    
    def get_allowed_chats(self) -> List[int]:
        """
        Get list of allowed chat IDs
        
        Returns:
            List[int]: List of allowed chat IDs
        """
        return list(self.allowed_chat_ids)
    
    def get_admin_users(self) -> List[int]:
        """
        Get list of admin user IDs
        
        Returns:
            List[int]: List of admin user IDs
        """
        return list(self.admin_user_ids)
    
    async def check_admin_access(self, update: Update) -> bool:
        """
        Check if user has admin access
        
        Args:
            update: Telegram update object
            
        Returns:
            bool: True if user is admin and has access
        """
        if not await self.check_access(update):
            return False
        
        user = update.effective_user
        if not user:
            return False
        
        return self.is_admin(user.id)
    
    def require_admin(self, func):
        """
        Decorator to require admin access for a function
        
        Args:
            func: Function to decorate
            
        Returns:
            Decorated function
        """
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            if not await self.check_admin_access(update):
                await update.effective_message.reply_text(
                    "❌ Access denied. Administrator privileges required."
                )
                return
            
            return await func(update, context)
        
        return wrapper
    
    def cleanup_old_attempts(self, max_age_hours: int = 24):
        """
        Clean up old access attempts to prevent memory buildup
        
        Args:
            max_age_hours: Maximum age of attempts to keep in hours
        """
        try:
            import time
            
            current_time = time.time()
            cutoff_time = current_time - (max_age_hours * 3600)
            
            cleaned_count = 0
            for key in list(self.access_attempts.keys()):
                # Filter out old attempts
                self.access_attempts[key] = [
                    attempt for attempt in self.access_attempts[key]
                    if attempt['timestamp'] > cutoff_time
                ]
                
                # Remove empty entries
                if not self.access_attempts[key]:
                    del self.access_attempts[key]
                    cleaned_count += 1
            
            if cleaned_count > 0:
                logger.info(f"🗑️ Cleaned up {cleaned_count} old access attempt records")
            
        except Exception as e:
            logger.error(f"Error cleaning up access attempts: {e}")
