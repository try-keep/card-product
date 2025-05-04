import pytest
import datetime
from decimal import Decimal
from extension import ExtensionFactory


@pytest.fixture
def factory():
    """Create extension factory for testing"""
    return ExtensionFactory()


def test_single_extension_past_due(factory):
    """Test past due amount matches between factory and single extension"""
    # Create extension with 3 month term
    start_date = datetime.date(2025, 1, 15)
    extension = factory.create_extension(
        extension_id="TEST001",
        amount=Decimal('1000.00'),
        start_date=start_date,
        term_months=3
    )

    # Check date when first payment is past due
    check_date = datetime.date(2025, 3, 1)

    # Get past due amounts
    extension_past_due = extension.get_past_due_amount(check_date)
    factory_past_due = factory.get_past_due_amount(check_date)

    # Should match and equal first installment
    assert extension_past_due == factory_past_due
    assert factory_past_due == Decimal('363.33')


def test_multiple_extensions_past_due(factory):
    """Test past due calculation with multiple extensions"""
    # First extension - no past due
    ext1_start = datetime.date(2025, 3, 15)
    ext1 = factory.create_extension(
        extension_id="TEST001",
        amount=Decimal('1000.00'),
        start_date=ext1_start,
        term_months=3
    )

    # Second extension - 2 payments past due
    ext2_start = datetime.date(2025, 1, 15)
    ext2 = factory.create_extension(
        extension_id="TEST002",
        amount=Decimal('2000.00'),
        start_date=ext2_start,
        term_months=3
    )

    check_date = datetime.date(2025, 3, 20)

    # First extension should have no past due
    assert ext1.get_past_due_amount(check_date) == Decimal('0')

    # Second extension should have 2 payments past due
    assert ext2.get_past_due_amount(check_date) == Decimal('1453.34')

    # Factory total should match second extension past due
    assert factory.get_past_due_amount(check_date) == Decimal('1453.34')


def test_multiple_extensions_next_due(factory):
    """Test next due calculation with multiple extensions on different schedules"""
    # First extension - 2 month term
    ext1_start = datetime.date(2025, 1, 15)
    ext1 = factory.create_extension(
        extension_id="TEST001",
        amount=Decimal('1000.00'),
        start_date=ext1_start,
        term_months=2
    )

    # Second extension - 3 month term starting later
    ext2_start = datetime.date(2025, 2, 1)
    ext2 = factory.create_extension(
        extension_id="TEST002",
        amount=Decimal('2000.00'),
        start_date=ext2_start,
        term_months=3
    )

    check_date = datetime.date(2025, 2, 15)

    # First extension next payment
    assert ext1.get_next_due_amount(check_date) == Decimal('530.00')

    # Debugging
    # print(ext2.payment_schedule.to_markdown())

    # Second extension next payment
    assert ext2.get_next_due_amount(check_date) == Decimal('726.67')

    # Factory total should be sum of both next payments
    assert factory.get_next_due_amount(check_date) == Decimal('1256.67')


def test_make_past_due_payment_partial_coverage(factory):
    """Test payment that covers one installment from each extension"""
    # First extension - 2 month term
    ext1_start = datetime.date(2025, 1, 15)
    ext1 = factory.create_extension(
        extension_id="TEST001",
        amount=Decimal('1000.00'),
        start_date=ext1_start,
        term_months=2
    )

    # Second extension - 3 month term starting same time
    ext2_start = datetime.date(2025, 1, 15)
    ext2 = factory.create_extension(
        extension_id="TEST002",
        amount=Decimal('2000.00'),
        start_date=ext2_start,
        term_months=3
    )
    print(ext1.payment_schedule.to_markdown())
    print(ext2.payment_schedule.to_markdown())

    # Check date after first payments are due
    check_date = datetime.date(2025, 3, 15)

    # Make payment that should cover roughly one installment from each
    payment_result = factory._make_past_due_next_due_payment(
        check_date, Decimal('1200.00'))

    assert len(payment_result['payments']) == 2
    assert payment_result['total_amount'] == Decimal('1200.00')
    assert payment_result['remaining_amount'] == Decimal('0')
    assert ext1.get_past_due_amount(check_date) == Decimal('0')
    assert ext2.get_past_due_amount(check_date) == Decimal('56.67')


def test_make_past_due_payment_double_first_extension(factory):
    """Test payment that covers two installments for first extension"""
    # First extension - 2 month term
    ext1_start = datetime.date(2025, 1, 15)
    ext1 = factory.create_extension(
        extension_id="TEST001",
        amount=Decimal('1000.00'),
        start_date=ext1_start,
        term_months=2
    )

    # Second extension - 3 month term starting same time
    ext2_start = datetime.date(2025, 3, 15)
    ext2 = factory.create_extension(
        extension_id="TEST002",
        amount=Decimal('2000.00'),
        start_date=ext2_start,
        term_months=3
    )

    # Check date after all payments are due
    check_date = datetime.date(2025, 4, 15)

    # Make payment that should cover both installments of first extension
    payment_result = factory._make_past_due_next_due_payment(
        check_date, Decimal('1060.00'))

    print(ext1.payment_schedule.to_markdown())
    print(ext2.payment_schedule.to_markdown())

    assert len(payment_result['payments']) == 2
    assert payment_result['total_amount'] == Decimal('1060.00')

    assert ext1.status == "PAID"
    assert ext2.status == "ACTIVE"

    assert ext1.get_past_due_amount(check_date) == Decimal('0')


def test_make_past_due_payment_no_past_due(factory):
    """Test payment when no past due amounts exist"""
    # First extension - 2 month term
    ext1_start = datetime.date(2025, 1, 15)
    ext1 = factory.create_extension(
        extension_id="TEST001",
        amount=Decimal('1000.00'),
        start_date=ext1_start,
        term_months=2
    )

    # Second extension - 3 month term starting same time
    ext2_start = datetime.date(2025, 1, 15)
    ext2 = factory.create_extension(
        extension_id="TEST002",
        amount=Decimal('2000.00'),
        start_date=ext2_start,
        term_months=3
    )

    # Check date before any payments are due
    check_date = datetime.date(2025, 1, 20)

    # Make payment attempt
    payment_result = factory._make_past_due_next_due_payment(
        check_date, Decimal('500.00'))

    assert len(payment_result['payments']) == 1
    assert payment_result['total_amount'] == Decimal('500.00')
    assert payment_result['remaining_amount'] == Decimal('0')


def test_make_next_due_payment_before_due_date(factory):
    """Test next due payment before installment due date"""
    # Create extension with 2 month term
    start_date = datetime.date(2025, 1, 15)
    extension = factory.create_extension(
        extension_id="TEST001",
        amount=Decimal('1000.00'),
        start_date=start_date,
        term_months=2
    )

    # Check date before first payment is due
    check_date = datetime.date(2025, 2, 1)  # Payment due 2/15

    # Make payment for first installment
    payment_result = factory._make_past_due_next_due_payment(
        check_date, Decimal('530.00'))

    assert len(payment_result['payments']) == 1
    assert payment_result['total_amount'] == Decimal('530.00')
    assert payment_result['remaining_amount'] == Decimal('0.0')
    assert extension.payment_schedule.iloc[0]['paid'] == True
    assert extension.status == "ACTIVE"


def test_make_next_due_payment_on_due_date(factory):
    """Test next due payment on installment due date"""
    # Create extension with 2 month term
    start_date = datetime.date(2025, 1, 15)
    extension = factory.create_extension(
        extension_id="TEST001",
        amount=Decimal('1000.00'),
        start_date=start_date,
        term_months=2
    )

    # Check on first payment due date
    check_date = datetime.date(2025, 2, 15)

    # Make payment for first installment
    payment_result = factory._make_past_due_next_due_payment(
        check_date, Decimal('530.00'))

    assert len(payment_result['payments']) == 1
    assert payment_result['total_amount'] == Decimal('530.00')
    assert payment_result['remaining_amount'] == Decimal('0.0')
    assert extension.payment_schedule.iloc[0]['paid'] == True
    assert extension.status == "ACTIVE"


def test_make_next_due_payment_multiple_extensions(factory):
    """Test next due payment with multiple extensions"""
    # First extension - 2 month term
    ext1_start = datetime.date(2025, 1, 15)
    ext1 = factory.create_extension(
        extension_id="TEST001",
        amount=Decimal('1000.00'),
        start_date=ext1_start,
        term_months=2
    )

    # Second extension - 3 month term starting later
    ext2_start = datetime.date(2025, 1, 20)
    ext2 = factory.create_extension(
        extension_id="TEST002",
        amount=Decimal('2000.00'),
        start_date=ext2_start,
        term_months=3
    )

    # Check date before first payments are due
    check_date = datetime.date(2025, 2, 1)

    # Make payment that should cover first installment of both extensions
    payment_result = factory._make_past_due_next_due_payment(
        check_date, Decimal('1600.00'))

    assert len(payment_result['payments']) == 2
    assert payment_result['total_amount'] == Decimal('1600.00')
    assert payment_result['remaining_amount'] == Decimal('343.33')
    assert ext1.payment_schedule.iloc[0]['paid'] == True
    assert ext2.payment_schedule.iloc[0]['paid'] == True
    assert ext1.status == "ACTIVE"
    assert ext2.status == "ACTIVE"


def test_make_past_due_and_next_due_payment_multiple_extensions(factory):
    """Test next due payment with multiple extensions"""
    # First extension - 2 month term
    ext1_start = datetime.date(2025, 1, 15)
    ext1 = factory.create_extension(
        extension_id="TEST001",
        amount=Decimal('1000.00'),
        start_date=ext1_start,
        term_months=2
    )

    # Second extension - 3 month term starting later
    ext2_start = datetime.date(2025, 1, 20)
    ext2 = factory.create_extension(
        extension_id="TEST002",
        amount=Decimal('2000.00'),
        start_date=ext2_start,
        term_months=3
    )

    # Check date before first payments are due
    check_date = datetime.date(2026, 2, 1)

    # Make payment that should cover first installment of both extensions
    payment_result = factory._make_past_due_next_due_payment(
        check_date, Decimal('2513.34'))

    print(ext1.payment_schedule.to_markdown())
    print(ext2.payment_schedule.to_markdown())

    assert len(payment_result['payments']) == 4
    assert payment_result['total_amount'] == Decimal('2513.34')
    assert payment_result['remaining_amount'] == Decimal('0')
    assert ext1.payment_schedule.iloc[0]['paid'] == True
    assert ext2.payment_schedule.iloc[2]['paid'] == False
    assert ext1.status == "PAID"
    assert ext2.status == "ACTIVE"
