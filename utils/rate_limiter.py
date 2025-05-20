from tortoise import fields, Model
from datetime import datetime, timedelta
from typing import Optional
import logging
import sys
from pathlib import Path

# Add the project root to Python path to allow imports
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)

from models import User

logger = logging.getLogger("rate_limiter")

class UserRequestLimit(Model):
    user = fields.ForeignKeyField('models.User', related_name='request_limits')
    daily_request_count = fields.IntField(default=0)
    last_request_time = fields.DatetimeField(auto_now=True)
    last_count_reset = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "user_request_limits"

class RateLimiter:
    # Default limits
    MAX_REQUESTS_PER_DAY = 50  # Maximum requests per day
    MIN_REQUEST_INTERVAL = 10  # Minimum seconds between requests
    
    @classmethod
    async def check_rate_limit(cls, user: User) -> tuple[bool, Optional[str]]:
        """
        Check if the user has exceeded their rate limits.
        Returns (allowed: bool, error_message: Optional[str])
        """
        try:
            # Get or create user limit record
            limit_record, created = await UserRequestLimit.get_or_create(user=user)
            
            now = datetime.utcnow()
            
            # Check if we need to reset daily count
            if (now - limit_record.last_count_reset).days >= 1:
                limit_record.daily_request_count = 0
                limit_record.last_count_reset = now
                await limit_record.save()
            
            # Check daily limit
            if limit_record.daily_request_count >= cls.MAX_REQUESTS_PER_DAY:
                return False, f"Daily request limit of {cls.MAX_REQUESTS_PER_DAY} exceeded. Please try again tomorrow."
            
            # Check request interval
            if not created and (now - limit_record.last_request_time).total_seconds() < cls.MIN_REQUEST_INTERVAL:
                return False, f"Please wait {cls.MIN_REQUEST_INTERVAL} seconds between requests."
            
            # Update counters
            limit_record.daily_request_count += 1
            limit_record.last_request_time = now
            await limit_record.save()
            
            return True, None
            
        except Exception as e:
            logger.error(f"Error checking rate limit: {str(e)}")
            # If there's an error checking limits, we'll allow the request but log the error
            return True, None
    
    @classmethod
    async def get_user_limits(cls, user: User) -> dict:
        """
        Get current limit status for a user
        """
        limit_record, _ = await UserRequestLimit.get_or_create(user=user)
        
        now = datetime.utcnow()
        reset_time = limit_record.last_count_reset + timedelta(days=1)
        
        return {
            "daily_requests_used": limit_record.daily_request_count,
            "daily_requests_limit": cls.MAX_REQUESTS_PER_DAY,
            "reset_time": reset_time.isoformat(),
            "requests_remaining": max(0, cls.MAX_REQUESTS_PER_DAY - limit_record.daily_request_count)
        } 