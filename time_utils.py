import datetime

holidays = [
    datetime.date(2025, 1, 1),   # New Year's Day
    datetime.date(2025, 4, 18),  # Good Friday
    datetime.date(2025, 5, 19),  # Victoria Day
    datetime.date(2025, 7, 1),   # Canada Day
    datetime.date(2025, 8, 4),   # Civic Holiday
    datetime.date(2025, 9, 1),   # Labour Day
    datetime.date(2025, 10, 13),  # Thanksgiving
    datetime.date(2025, 11, 11),  # Remembrance Day
    datetime.date(2025, 12, 25),  # Christmas Day
    datetime.date(2025, 12, 26),  # Boxing Day
]


def add_business_days(date, days):
    """
    Add specified number of business days to a date, accounting for weekends and holidays.

    Parameters:
    date (datetime): Starting date
    days (int): Number of business days to add
    holidays (list): List of holiday dates to exclude

    Returns:
    datetime: Date after adding specified business days
    """
    current_date = date
    remaining_days = days

    while remaining_days > 0:
        current_date += datetime.timedelta(days=1)
        # Skip weekends and holidays
        if current_date.weekday() < 5 and current_date not in holidays:
            remaining_days -= 1

    return current_date
