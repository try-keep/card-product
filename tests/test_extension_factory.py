import pytest
import datetime
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
        amount=1000.00,
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
    assert factory_past_due == pytest.approx(363.33, rel=1e-2)


def test_multiple_extensions_past_due(factory):
    """Test past due calculation with multiple extensions"""
    # First extension - no past due
    ext1_start = datetime.date(2025, 3, 15)
    ext1 = factory.create_extension(
        extension_id="TEST001",
        amount=1000.00,
        start_date=ext1_start,
        term_months=3
    )

    # Second extension - 2 payments past due
    ext2_start = datetime.date(2025, 1, 15)
    ext2 = factory.create_extension(
        extension_id="TEST002",
        amount=2000.00,
        start_date=ext2_start,
        term_months=3
    )

    check_date = datetime.date(2025, 3, 20)

    # First extension should have no past due
    assert ext1.get_past_due_amount(check_date) == 0

    # Second extension should have 2 payments past due
    assert ext2.get_past_due_amount(
        check_date) == pytest.approx(1453.34, rel=1e-2)

    # Factory total should match second extension past due
    assert factory.get_past_due_amount(
        check_date) == pytest.approx(1453.34, rel=1e-2)


def test_multiple_extensions_next_due(factory):
    """Test next due calculation with multiple extensions on different schedules"""
    # First extension - 2 month term
    ext1_start = datetime.date(2025, 1, 15)
    ext1 = factory.create_extension(
        extension_id="TEST001",
        amount=1000.00,
        start_date=ext1_start,
        term_months=2
    )

    # Second extension - 3 month term starting later
    ext2_start = datetime.date(2025, 2, 1)
    ext2 = factory.create_extension(
        extension_id="TEST002",
        amount=2000.00,
        start_date=ext2_start,
        term_months=3
    )

    check_date = datetime.date(2025, 2, 15)

    # First extension next payment
    assert ext1.get_next_due_amount(
        check_date) == pytest.approx(530.00, rel=1e-2)

    # Debugging
    # print(ext2.payment_schedule.to_markdown())

    # Second extension next payment
    assert ext2.get_next_due_amount(
        check_date) == pytest.approx(726.67, rel=1e-2)

    # Factory total should be sum of both next payments
    assert factory.get_next_due_amount(
        check_date) == pytest.approx(1256.67, rel=1e-2)
