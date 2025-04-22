import datetime
from engine import KeepCardSimulator

# Create a simulator instance
# Statement cycle starts on 1st of each month
simulator = KeepCardSimulator(statement_cycle_start=3)

print("Generating transactions with FIXED payment impact on Balance Due...")

# Month 1: New card with purchases
simulator.add_transaction('PURCHASE', 200.00, '2025-01-05', '2025-01-05')
simulator.add_transaction('PURCHASE', 300.00, '2025-01-10', '2025-01-10')
simulator.add_transaction('PURCHASE', 100.00, '2025-01-20', '2025-01-20')
simulator.add_transaction('PURCHASE', 150.00, '2025-01-28', '2025-01-28')

# First statement period ends on Jan 31, due date is Feb 1
# Balance at this point is $750

# Month 2: A payment is made - this should affect both balance and balance due
print("\nAdding payment of $200 on Feb 10 - this should reduce both balance and balance due")
simulator.add_transaction('PAYMENT', 200.00, '2025-02-10', '2025-02-10')

# Add some more purchases
simulator.add_transaction('PURCHASE', 150.00, '2025-02-15', '2025-02-15')

# On the due date (Mar 1), customer can't pay the remaining balance, so creates an extension
# First, get the current balance due amount
calculated_balance_due = simulator.calculate_period_balance_due(
    datetime.date(2025, 3, 1))
print(f"\nBalance due on March 1, 2025: ${calculated_balance_due:.2f}")


simulator.add_transaction('PAYMENT', 200.00, '2025-03-01', '2025-03-01')

# Create extension for the full balance due amount on the due date
ext_id = simulator.create_statement_extension(
    calculated_balance_due, '2025-03-01', 6)
print(
    f"Created statement extension {ext_id} for ${calculated_balance_due:.2f} with 6-month term")

# Month 3: After extension, customer makes more purchases and payments
simulator.add_transaction('PURCHASE', 200.00, '2025-03-10', '2025-03-10')
simulator.add_transaction('PAYMENT', 150.00, '2025-03-20', '2025-03-20')


# Calculate the monthly extension payment amount
extension = [
    ext for ext in simulator.extensions if ext.extension_id == ext_id][0]
monthly_payment = extension.monthly_payment
print(f"\nMonthly extension payment amount: ${monthly_payment:.2f}")

# Make the first extension payment on the due date
simulator.make_extension_payment(ext_id, monthly_payment, '2025-04-01')

simulator.make_extension_payment(ext_id, 275, '2025-04-20')

# 1. Show the unified timeline with properly calculated Balance Due
print("\n===== UNIFIED TIMELINE WITH CORRECTED BALANCE DUE =====")
# Note: Now payments properly affect both balance and balance due
simulator.display_timeline()

# 2. Show the transaction ledger
print("\n===== TRANSACTION LEDGER =====")
simulator.show_transactions()

# 3. Show the statement summaries
print("\n===== STATEMENT SUMMARIES =====")
simulator.display_side_by_side()

# 4. Show the extension product details
print("\n===== EXTENSION PRODUCT DETAILS =====")
simulator.show_extensions()
