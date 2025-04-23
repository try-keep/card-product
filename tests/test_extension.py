import pytest
import datetime
import pandas as pd
from extension import ExtensionProduct


@pytest.fixture
def base_extension():
    """Create a basic extension for testing"""
    start_date = datetime.date(2025, 1, 15)
    return ExtensionProduct(
        extension_id="TEST001",
        amount=1000.00,
        start_date=start_date,
        term_months=3,
        apr=36.0
    )


def test_extension_initialization(base_extension):
    """Test that extension is created with correct values"""
    # Check basic attributes
    assert base_extension.extension_id == "TEST001"
    assert base_extension.original_amount == 1000.00
    assert base_extension.term_months == 3
    assert base_extension.apr == 36.0
    assert base_extension.status == "ACTIVE"

    # Check calculated values
    assert base_extension.total_interest == 90.00  # (1000 * 0.36 * 3/12)
    assert base_extension.monthly_payment == pytest.approx(
        363.33, rel=1e-2)  # (1000 + 90) / 3

    # Check payment schedule
    assert len(base_extension.payment_schedule) == 3
    assert base_extension.payment_schedule['principal_amount'].sum(
    ) == pytest.approx(1000.00)
    assert base_extension.payment_schedule['interest_amount'].sum(
    ) == pytest.approx(90.00)

    # Check first payment date
    expected_first_payment = datetime.date(2025, 2, 15)
    assert base_extension.payment_schedule.iloc[0]['payment_date'] == expected_first_payment


def test_pay_past_due_amount(base_extension):
    """Test payment of past due amount only"""
    # Move to future date so first payment is past due
    payment_date = datetime.date(2025, 3, 1)

    # First installment should be past due
    past_due = base_extension.get_past_due_amount(payment_date)
    assert past_due == pytest.approx(363.33, rel=1e-2)

    # Make past due payment
    payment = base_extension.pay_past_due_amount(payment_date, 363.33)

    # Verify payment was applied correctly
    assert payment['payment_amount'] == pytest.approx(363.33, rel=1e-2)
    assert payment['principal_paid'] == pytest.approx(333.33, rel=1e-2)
    assert payment['interest_paid'] == pytest.approx(30.00, rel=1e-2)

    print(base_extension.payment_schedule)
    # First installment should be marked paid
    assert base_extension.payment_schedule.iloc[0]['paid'] == True


def test_pay_next_due_amount(base_extension):
    """Test payment of next due amount"""
    payment_date = datetime.date(2025, 2, 15)

    # Get next due amount
    next_due = base_extension.get_next_due_amount(payment_date)
    assert next_due == pytest.approx(363.33, rel=1e-2)

    # Make payment
    payment = base_extension.make_payment(363.33, payment_date)

    # Verify payment was applied correctly
    assert payment['payment_amount'] == pytest.approx(363.33, rel=1e-2)
    assert payment['principal_paid'] == pytest.approx(333.33, rel=1e-2)
    assert payment['interest_paid'] == pytest.approx(30.00, rel=1e-2)

    # First installment should be marked paid
    assert base_extension.payment_schedule.iloc[0]['paid'] == True

    # Other installments should not be paid
    assert base_extension.payment_schedule.iloc[1]['paid'] == False
    assert base_extension.payment_schedule.iloc[2]['paid'] == False
