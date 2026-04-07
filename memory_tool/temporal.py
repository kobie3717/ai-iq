"""Temporal-aware search: natural language date parsing for memory queries."""

import re
from datetime import datetime, timedelta
from typing import Optional, Tuple

try:
    import dateparser
    _DATEPARSER_AVAILABLE = True
except ImportError:
    _DATEPARSER_AVAILABLE = False


def extract_temporal_constraint(query: str) -> Optional[Tuple[datetime, datetime]]:
    """Extract temporal constraints from natural language query.

    Examples:
        "errors last week" -> (7 days ago, now)
        "what happened in March" -> (March 1, March 31)
        "bugs yesterday" -> (yesterday 00:00, yesterday 23:59)

    Args:
        query: Search query string with potential temporal expressions

    Returns:
        Tuple of (start_date, end_date) if temporal constraint found, None otherwise
    """
    if not _DATEPARSER_AVAILABLE:
        return None

    query_lower = query.lower()
    now = datetime.now()

    # Fast-path common expressions without full dateparser

    # Week-based
    if 'last week' in query_lower or 'past week' in query_lower:
        return (now - timedelta(days=7), now)
    elif 'this week' in query_lower:
        # Monday to now
        days_since_monday = now.weekday()
        return (now - timedelta(days=days_since_monday), now)

    # Month-based
    elif 'last month' in query_lower or 'past month' in query_lower:
        return (now - timedelta(days=30), now)
    elif 'this month' in query_lower:
        return (now.replace(day=1, hour=0, minute=0, second=0, microsecond=0), now)

    # Year-based
    elif 'last year' in query_lower or 'past year' in query_lower:
        return (now - timedelta(days=365), now)
    elif 'this year' in query_lower:
        return (now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0), now)

    # Day-based
    elif 'yesterday' in query_lower:
        yesterday_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_end = (now - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
        return (yesterday_start, yesterday_end)
    elif 'today' in query_lower:
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return (today_start, now)

    # Last N days pattern
    last_n_match = re.search(r'last (\d+) days?', query_lower)
    if last_n_match:
        days = int(last_n_match.group(1))
        return (now - timedelta(days=days), now)

    # Try dateparser for month names and complex expressions
    try:
        # Check for month name patterns
        month_match = re.search(
            r'\bin (january|february|march|april|may|june|july|august|september|october|november|december)\b',
            query_lower
        )
        if month_match:
            month_name = month_match.group(1)
            # Parse "in [month]" as the month in current year
            parsed = dateparser.parse(f"{month_name} 1, {now.year}")
            if parsed:
                month_start = parsed.replace(hour=0, minute=0, second=0, microsecond=0)
                # Calculate last day of month
                if month_start.month == 12:
                    month_end = month_start.replace(year=month_start.year + 1, month=1, day=1) - timedelta(microseconds=1)
                else:
                    month_end = month_start.replace(month=month_start.month + 1, day=1) - timedelta(microseconds=1)
                return (month_start, month_end)
    except Exception:
        pass

    # No temporal constraint found
    return None


def strip_temporal_expressions(query: str) -> str:
    """Remove temporal expressions from query to improve content matching.

    Args:
        query: Original query string

    Returns:
        Query with temporal expressions removed
    """
    # Common temporal phrases to strip
    temporal_phrases = [
        r'\blast week\b',
        r'\bthis week\b',
        r'\blast month\b',
        r'\bthis month\b',
        r'\byesterday\b',
        r'\btoday\b',
        r'\blast year\b',
        r'\bthis year\b',
        r'\bpast week\b',
        r'\bpast month\b',
        r'\bpast year\b',
        r'\blast \d+ days?\b',
        r'\bin (january|february|march|april|may|june|july|august|september|october|november|december)\b',
    ]

    cleaned = query
    for phrase in temporal_phrases:
        cleaned = re.sub(phrase, '', cleaned, flags=re.IGNORECASE)

    # Remove extra whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    return cleaned
