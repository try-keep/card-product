import pytest
import datetime
from decimal import Decimal
import pandas as pd
from extension import ExtensionProduct


@pytest.fixture
def base_extension():
    """Create a basic extension for testing"""
    start_date = datetime.date(2025, 1, 15)
    return ExtensionProduct(
        extension_id="TEST001",
        amount=Decimal('1000.00'),
        start_date=start_date,
        term_months=3,
        apr=Decimal('36.0')
    )


def test_extension_initialization(base_extension):
    """Test that extension is created with correct values"""
    # Check basic attributes
    assert base_extension.extension_id == "TEST001"
    assert base_extension.original_amount == Decimal('1000.00')
    assert base_extension.term_months == 3
    assert base_extension.apr == Decimal('36.0')
    assert base_extension.status == "ACTIVE"

    # Check calculated values
    assert base_extension.total_interest == Decimal(
        '90.00')  # (1000 * 0.36 * 3/12)
    assert base_extension.monthly_payment == pytest.approx(
        Decimal('363.33'), rel=Decimal('1e-2'))  # (1000 + 90) / 3

    # Check payment schedule
    assert len(base_extension.payment_schedule) == 3
    assert base_extension.payment_schedule['principal_amount'].sum() == pytest.approx(
        Decimal('1000.00'), rel=Decimal('1e-2'))
    assert base_extension.payment_schedule['interest_amount'].sum() == pytest.approx(
        Decimal('90.00'), rel=Decimal('1e-2'))

    # Check first payment date
    expected_first_payment = datetime.date(2025, 2, 15)
    assert base_extension.payment_schedule.iloc[0]['payment_date'] == expected_first_payment


def test_pay_past_due_amount(base_extension):
    """Test payment of past due amount only"""
    # Move to future date so first payment is past due
    payment_date = datetime.date(2025, 3, 1)

    # First installment should be past due
    past_due = base_extension.get_past_due_amount(payment_date)
    assert past_due == pytest.approx(Decimal('363.33'), rel=Decimal('1e-2'))

    # Make past due payment
    payment = base_extension.pay_past_due_amount(
        payment_date, Decimal('363.33'))

    # Verify payment was applied correctly
    assert payment['payment_amount'] == pytest.approx(
        Decimal('363.33'), rel=Decimal('1e-2'))
    assert payment['principal_paid'] == pytest.approx(
        Decimal('333.33'), rel=Decimal('1e-2'))
    assert payment['interest_paid'] == pytest.approx(
        Decimal('30.00'), rel=Decimal('1e-2'))

    print(base_extension.payment_schedule)
    # First installment should be marked paid
    assert base_extension.payment_schedule.iloc[0]['paid'] == True


def test_pay_next_due_amount(base_extension):
    """Test payment of next due amount"""
    payment_date = datetime.date(2025, 2, 15)

    # Get next due amount
    next_due = base_extension.get_next_due_amount(payment_date)
    assert next_due == pytest.approx(Decimal('363.33'), rel=Decimal('1e-2'))

    # Make payment
    payment = base_extension.make_payment(Decimal('363.33'), payment_date)

    # Verify payment was applied correctly
    assert payment['payment_amount'] == pytest.approx(
        Decimal('363.33'), rel=Decimal('1e-2'))
    assert payment['principal_paid'] == pytest.approx(
        Decimal('333.33'), rel=Decimal('1e-2'))
    assert payment['interest_paid'] == pytest.approx(
        Decimal('30.00'), rel=Decimal('1e-2'))

    # First installment should be marked paid
    assert base_extension.payment_schedule.iloc[0]['paid'] == True

    # Other installments should not be paid
    assert base_extension.payment_schedule.iloc[1]['paid'] == False
    assert base_extension.payment_schedule.iloc[2]['paid'] == False


def test_get_next_due_amount_on_due_date(base_extension):
    """Test getting next due amount when payment date is same as due date"""
    # First payment is due on Feb 15
    payment_date = datetime.date(2025, 2, 15)

    # Get next due amount on the due date
    next_due = base_extension.get_next_due_amount(payment_date)

    # Should return first payment amount since it's due today
    assert next_due == pytest.approx(Decimal('363.33'), rel=Decimal('1e-2'))


def test_get_past_due_amount_on_due_date(base_extension):
    """Test that past due amount is 0 when checking on the due date"""
    # First payment is due on Feb 15
    payment_date = datetime.date(2025, 2, 15)

    # Get past due amount on the due date
    past_due = base_extension.get_past_due_amount(payment_date)

    # Should return 0 since payment isn't past due yet
    assert past_due == Decimal('0.00')


def test_get_past_due_installments_with_paid_installment(base_extension):
    """Test getting past due installments after paying first installment"""
    # Pay first installment
    first_payment_date = datetime.date(2025, 2, 15)
    base_extension.make_payment(Decimal('363.33'), first_payment_date)

    # Move to future date where second payment is past due
    check_date = datetime.date(2025, 3, 20)

    # Get past due installments
    past_due = base_extension.get_past_due_installments(check_date)

    # Should only return second installment as past due
    assert len(past_due) == 1
    assert past_due.iloc[0]['payment_number'] == 2
    assert past_due.iloc[0]['payment_date'] == datetime.date(2025, 3, 15)
    assert past_due.iloc[0]['paid'] == False
    assert past_due.iloc[0]['remaining_principal'] == pytest.approx(
        Decimal('333.33'), rel=Decimal('1e-2'))
    assert past_due.iloc[0]['remaining_interest'] == pytest.approx(
        Decimal('30.00'), rel=Decimal('1e-2'))


def test_get_next_installment_no_next_installment(base_extension):
    """Test that get_next_installment returns None when there are no future installments"""
    # Pay all installments
    # Check after all payments are complete
    check_date = datetime.date(2025, 4, 16)

    # Should return None since all installments are paid
    next_installment = base_extension.get_next_installment(check_date)
    assert next_installment is None
