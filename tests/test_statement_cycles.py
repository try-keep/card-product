import pytest
import datetime
from engine import Statement


@pytest.fixture
def base_start_date():
    return datetime.date(2025, 1, 15)


@pytest.fixture
def grace_period():
    return 21


def test_basic_cycle_generation(base_start_date, grace_period):
    """Test basic statement cycle generation with 3 cycles"""
    cycle_count = 3

    cycles = Statement.get_statement_cycles(
        base_start_date, grace_period, cycle_count)

    # Check number of cycles
    assert len(cycles) == cycle_count

    # Check first cycle
    assert cycles[0][0] == datetime.date(2025, 1, 15)  # start
    assert cycles[0][1] == datetime.date(2025, 2, 14)  # end
    # due (21 business days after end)
    assert cycles[0][2] == datetime.date(
        # 21 business days from Feb 14 (accounting for Family Day)
        2025, 3, 17)

    # Check second cycle
    assert cycles[1][0] == datetime.date(2025, 2, 15)  # start
    assert cycles[1][1] == datetime.date(2025, 3, 14)  # end
    assert cycles[1][2] == datetime.date(
        # 21 business days from Mar 14 (accounting for Good Friday Apr 18)
        2025, 4, 14)

    # Check third cycle
    assert cycles[2][0] == datetime.date(2025, 3, 15)  # start
    assert cycles[2][1] == datetime.date(2025, 4, 14)  # end
    assert cycles[2][2] == datetime.date(
        # 21 business days from Apr 14 (accounting for Victoria Day May 19)
        2025, 5, 14)


def test_invalid_start_date(grace_period):
    """Test that invalid start dates raise ValueError"""
    invalid_dates = [
        datetime.date(2025, 1, 1),   # 1st
        datetime.date(2025, 1, 28),  # 28th
        datetime.date(2025, 1, 29),  # 29th
        datetime.date(2025, 1, 30),  # 30th
        datetime.date(2025, 1, 31),  # 31st
    ]

    for date in invalid_dates:
        with pytest.raises(ValueError):
            Statement.get_statement_cycles(date, grace_period, 1)


def test_year_end_rollover():
    """Test statement cycles that cross year boundaries"""
    start_date = datetime.date(2025, 12, 15)
    grace_period = 21
    cycle_count = 2

    cycles = Statement.get_statement_cycles(
        start_date, grace_period, cycle_count)

    # Check first cycle (December)
    assert cycles[0][0] == datetime.date(2025, 12, 15)  # start
    assert cycles[0][1] == datetime.date(2026, 1, 14)   # end
    assert cycles[0][2] == datetime.date(2026, 2, 12)    # due

    # Check second cycle (January)
    assert cycles[1][0] == datetime.date(2026, 1, 15)   # start
    assert cycles[1][1] == datetime.date(2026, 2, 14)   # end
    assert cycles[1][2] == datetime.date(2026, 3, 16)    # due


def test_holiday_handling():
    """Test that due dates are adjusted for holidays"""
    start_date = datetime.date(2025, 3, 15)
    grace_period = 21
    cycle_count = 1

    cycles = Statement.get_statement_cycles(
        start_date, grace_period, cycle_count)

    # The end date should be April 14, 2025
    # 21 business days after that would normally be May 13, 2025
    # But need to account for Good Friday (Apr 18)
    # So due date should be May 14, 2025
    assert cycles[0][2] == datetime.date(2025, 5, 14)


def test_single_cycle():
    """Test generation of a single statement cycle"""
    start_date = datetime.date(2025, 6, 15)
    grace_period = 21
    cycle_count = 1

    cycles = Statement.get_statement_cycles(
        start_date, grace_period, cycle_count)

    assert len(cycles) == 1
    assert cycles[0][0] == datetime.date(2025, 6, 15)  # start
    assert cycles[0][1] == datetime.date(2025, 7, 14)  # end
    # Due date should be 21 business days after July 14
    # Need to account for Civic Holiday (Aug 4)
    # So due date should be Aug 13
    assert cycles[0][2] == datetime.date(2025, 8, 13)   # due
