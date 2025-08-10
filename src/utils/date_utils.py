"""
Date and time utilities for the application.
Provides date calculations, formatting, and timezone handling.
"""

from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional
import pytz
from dateutil.relativedelta import relativedelta


class DateUtils:
    """Date and time utility functions."""

    def __init__(
        self, default_timezone: str = "UTC", date_format: str = "%Y-%m-%d %H:%M:%S"
    ):
        self.default_timezone = default_timezone
        self.date_format = date_format
        self.tz = pytz.timezone(default_timezone)

    def calculate_age(self, birth_date: date) -> int:
        """Calculate age from birth date."""
        today = date.today()
        age = today.year - birth_date.year

        # Adjust if birthday hasn't occurred this year
        if today.month < birth_date.month or (
            today.month == birth_date.month and today.day < birth_date.day
        ):
            age -= 1

        return age

    def validate_coppa_age(self, birth_date: date) -> Dict[str, Any]:
        """Validate age for COPPA compliance."""
        age = self.calculate_age(birth_date)

        return {
            "age": age,
            "is_coppa_age": 3 <= age <= 13,
            "birth_date": birth_date.isoformat(),
            "calculated_on": date.today().isoformat(),
        }

    def calculate_session_expiry(
        self, session_start: datetime, hours: int = 24
    ) -> datetime:
        """Calculate session expiry time."""
        return session_start + timedelta(hours=hours)

    def format_iso(self, dt: datetime) -> str:
        """Format datetime as ISO string."""
        return dt.isoformat()

    def format_human_readable(self, dt: datetime) -> str:
        """Format datetime in human-readable format."""
        return dt.strftime("%B %d, %Y at %I:%M %p")

    def format_for_child(self, dt: datetime) -> str:
        """Format datetime in child-friendly format."""
        now = datetime.now()
        diff = now - dt

        if diff.days == 0:
            if diff.seconds < 3600:  # Less than 1 hour
                minutes = diff.seconds // 60
                return f"{minutes} minutes ago"
            else:
                hours = diff.seconds // 3600
                return f"{hours} hours ago"
        elif diff.days == 1:
            return "yesterday"
        elif diff.days < 7:
            return f"{diff.days} days ago"
        else:
            return dt.strftime("%B %d")

    def calculate_duration(
        self, start_time: datetime, end_time: datetime
    ) -> Dict[str, Any]:
        """Calculate duration between two datetime objects."""
        duration = end_time - start_time

        total_seconds = int(duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        return {
            "total_seconds": total_seconds,
            "hours": hours,
            "minutes": minutes,
            "seconds": seconds,
            "human_readable": self._format_duration_human(hours, minutes, seconds),
        }

    def is_business_hours(
        self, dt: datetime, start_hour: int = 9, end_hour: int = 17
    ) -> bool:
        """Check if datetime falls within business hours."""
        return start_hour <= dt.hour < end_hour and dt.weekday() < 5

    def get_age_group(self, birth_date: date) -> str:
        """Get age group classification."""
        age = self.calculate_age(birth_date)

        if age < 3:
            return "toddler"
        elif age <= 5:
            return "preschool"
        elif age <= 8:
            return "elementary"
        elif age <= 13:
            return "preteen"
        else:
            return "teen_or_adult"

    def next_birthday(self, birth_date: date) -> Dict[str, Any]:
        """Calculate next birthday information."""
        today = date.today()
        this_year_birthday = birth_date.replace(year=today.year)

        if this_year_birthday < today:
            next_birthday = birth_date.replace(year=today.year + 1)
        else:
            next_birthday = this_year_birthday

        days_until = (next_birthday - today).days

        return {
            "next_birthday": next_birthday.isoformat(),
            "days_until": days_until,
            "turning_age": self.calculate_age(birth_date)
            + (1 if this_year_birthday < today else 0),
        }

    def consent_expiry_date(
        self, consent_date: datetime, validity_months: int = 12
    ) -> datetime:
        """Calculate when parental consent expires."""
        return consent_date + relativedelta(months=validity_months)

    def is_consent_valid(
        self, consent_date: datetime, validity_months: int = 12
    ) -> bool:
        """Check if parental consent is still valid."""
        expiry_date = self.consent_expiry_date(consent_date, validity_months)
        return datetime.now() < expiry_date

    def safe_date_range(
        self, child_birth_date: date, days_back: int = 30
    ) -> Dict[str, str]:
        """Generate safe date range for child data queries."""
        end_date = date.today()
        start_date = end_date - timedelta(days=days_back)

        # Ensure we don't go before child's birth
        if start_date < child_birth_date:
            start_date = child_birth_date

        return {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "days_covered": (end_date - start_date).days,
        }

    def _format_duration_human(self, hours: int, minutes: int, seconds: int) -> str:
        """Format duration in human-readable format."""
        parts = []

        if hours > 0:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")

        if minutes > 0:
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")

        if seconds > 0 and hours == 0:  # Only show seconds if less than an hour
            parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")

        if not parts:
            return "0 seconds"

        return ", ".join(parts)


class TimeFormatter:
    """Specialized time formatting for different contexts."""

    def __init__(self, date_utils: Optional[DateUtils] = None):
        self.date_utils = date_utils or DateUtils()

    def format_for_audit_log(self, dt: datetime) -> str:
        """Format datetime for audit logging."""
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")

    def format_for_parent_report(self, dt: datetime) -> str:
        """Format datetime for parent activity reports."""
        return dt.strftime("%B %d, %Y at %I:%M %p")

    def format_session_time(self, start: datetime, end: datetime) -> str:
        """Format session duration for display."""
        duration = self.date_utils.calculate_duration(start, end)

        if duration["hours"] > 0:
            return f"{duration['hours']}h {duration['minutes']}m"
        elif duration["minutes"] > 0:
            return f"{duration['minutes']} minutes"
        else:
            return f"{duration['seconds']} seconds"

    def format_child_friendly_time(self, dt: datetime) -> str:
        """Format time in a way children can understand."""
        hour = dt.hour

        if 5 <= hour < 12:
            time_of_day = "morning"
        elif 12 <= hour < 17:
            time_of_day = "afternoon"
        elif 17 <= hour < 20:
            time_of_day = "evening"
        else:
            time_of_day = "night"

        return f"this {time_of_day}"

    def relative_time_child_friendly(self, dt: datetime) -> str:
        """Format relative time in child-friendly terms."""
        now = datetime.now()
        diff = now - dt

        if diff.seconds < 300:  # Less than 5 minutes
            return "just now"
        elif diff.seconds < 3600:  # Less than 1 hour
            minutes = diff.seconds // 60
            return f"{minutes} minutes ago"
        elif diff.days == 0:
            return "earlier today"
        elif diff.days == 1:
            return "yesterday"
        elif diff.days < 7:
            return f"{diff.days} days ago"
        else:
            return "a while ago"


# Global utility functions
def get_current_timestamp() -> int:
    """Get current timestamp as integer."""
    return int(datetime.now().timestamp())


def get_current_datetime() -> datetime:
    """Get current datetime."""
    return datetime.now()


def get_utc_now() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(pytz.UTC)
