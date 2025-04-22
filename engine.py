import pandas as pd
import numpy as np
import datetime
import uuid
from datetime import timedelta


class ExtensionProduct:
    def __init__(self, extension_id, amount, start_date, term_months, apr=36.0):
        """
        Initialize a statement extension product.

        Parameters:
        extension_id (str): Unique identifier for this extension
        amount (float): Amount of the extension
        start_date (datetime): Date when the extension begins
        term_months (int): Number of months for repayment (1-12)
        apr (float): Annual Percentage Rate for the extension (default: 36.0%)
        """
        self.extension_id = extension_id
        self.original_amount = amount
        self.start_date = start_date
        # Ensure between 1-12 months
        self.term_months = min(max(1, term_months), 12)
        self.apr = apr
        self.status = "ACTIVE"

        # Calculate total interest as fixed fee
        total_interest = amount * (apr/100) * (term_months/12)

        # Calculate monthly payment (fixed payment including principal and interest)
        self.monthly_payment = (amount + total_interest) / term_months

        # Create payment schedule as a pandas DataFrame
        monthly_principal = amount / term_months
        monthly_interest = total_interest / term_months

        schedule_data = []
        for month in range(1, term_months + 1):
            payment_date = self._add_months(start_date, month)

            schedule_data.append({
                'payment_number': month,
                'payment_date': payment_date,
                'payment_amount': self.monthly_payment,
                'principal_amount': monthly_principal,
                'interest_amount': monthly_interest,
                'remaining_principal': monthly_principal,
                'remaining_interest': monthly_interest,
                'paid': False
            })

        self.payment_schedule = pd.DataFrame(schedule_data)

        # Track actual payments
        self.payments = []
        self.current_balance = amount

    def _add_months(self, date, months):
        """Add specified number of months to a date."""
        month = date.month - 1 + months
        year = date.year + month // 12
        month = month % 12 + 1
        day = min(date.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year %
                  400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month-1])
        return datetime.date(year, month, day)

    def make_payment(self, amount, payment_date):
        """
        Record a payment towards this extension with partial payment support.

        Parameters:
        amount (float): Payment amount
        payment_date (datetime): Date of payment

        Returns:
        dict: Payment details
        """
        remaining_payment = amount
        total_principal_paid = 0
        total_interest_paid = 0

        # First, pay past due installments (oldest to newest)
        past_due = self.payment_schedule[
            (self.payment_schedule['payment_date'] < payment_date) &
            (~self.payment_schedule['paid'])
        ]

        for idx, installment in past_due.iterrows():
            # Pay principal first
            principal_payment = min(
                remaining_payment, installment['remaining_principal'])
            self.payment_schedule.at[idx,
                                     'remaining_principal'] -= principal_payment
            remaining_payment -= principal_payment
            total_principal_paid += principal_payment

            # Then pay interest if there's money left
            if remaining_payment > 0:
                interest_payment = min(
                    remaining_payment, installment['remaining_interest'])
                self.payment_schedule.at[idx,
                                         'remaining_interest'] -= interest_payment
                remaining_payment -= interest_payment
                total_interest_paid += interest_payment

            if self.payment_schedule.at[idx, 'remaining_principal'] <= 0 and self.payment_schedule.at[idx, 'remaining_interest'] <= 0:
                self.payment_schedule.at[idx, 'paid'] = True

            if remaining_payment <= 0:
                break

        # Next, pay current period installment if there's money left
        current_installment = self.payment_schedule[
            (self.payment_schedule['payment_date'] >= payment_date) &
            (~self.payment_schedule['paid'])
        ].iloc[0] if not self.payment_schedule[
            (self.payment_schedule['payment_date'] >= payment_date) &
            (~self.payment_schedule['paid'])
        ].empty else None

        if current_installment is not None and remaining_payment > 0:
            idx = current_installment.name
            principal_payment = min(
                remaining_payment, current_installment['remaining_principal'])
            self.payment_schedule.at[idx,
                                     'remaining_principal'] -= principal_payment
            remaining_payment -= principal_payment
            total_principal_paid += principal_payment

            if remaining_payment > 0:
                interest_payment = min(
                    remaining_payment, current_installment['remaining_interest'])
                self.payment_schedule.at[idx,
                                         'remaining_interest'] -= interest_payment
                remaining_payment -= interest_payment
                total_interest_paid += interest_payment

            if self.payment_schedule.at[idx, 'remaining_principal'] <= 0 and self.payment_schedule.at[idx, 'remaining_interest'] <= 0:
                self.payment_schedule.at[idx, 'paid'] = True

        # Finally, distribute remaining amount across future installments
        if remaining_payment > 0:
            future_installments = self.payment_schedule[
                (self.payment_schedule['payment_date'] > payment_date) &
                (~self.payment_schedule['paid'])
            ]

            if not future_installments.empty:
                # Calculate how many full installments can be covered
                total_future_principal = future_installments['remaining_principal'].sum(
                )
                avg_installment_principal = total_future_principal / \
                    len(future_installments)
                installments_covered = int(
                    remaining_payment / avg_installment_principal)

                # Calculate fee to be waived based on covered installments
                total_future_interest = future_installments['remaining_interest'].sum(
                )
                avg_installment_interest = total_future_interest / \
                    len(future_installments)
                waived_interest = avg_installment_interest * installments_covered

                # Distribute remaining payment across all future installments principal
                per_installment_principal = remaining_payment / \
                    len(future_installments)
                per_installment_interest = waived_interest / \
                    len(future_installments)

                for idx, installment in future_installments.iterrows():
                    # Apply principal payment
                    principal_paid = min(
                        per_installment_principal, installment['remaining_principal'])
                    self.payment_schedule.at[idx,
                                             'remaining_principal'] -= principal_paid
                    total_principal_paid += principal_paid

                    # Apply waived interest
                    interest_waived = min(
                        per_installment_interest, installment['remaining_interest'])
                    self.payment_schedule.at[idx,
                                             'remaining_interest'] -= interest_waived
                    total_interest_paid += interest_waived

                    # Mark installment as paid if no principal or interest remains
                    if self.payment_schedule.at[idx, 'remaining_principal'] <= 0 and self.payment_schedule.at[idx, 'remaining_interest'] <= 0:
                        self.payment_schedule.at[idx, 'paid'] = True

        # Update current balance and record payment
        self.current_balance = max(
            0, self.current_balance - total_principal_paid)

        payment = {
            'payment_date': payment_date,
            'payment_amount': amount,
            'principal_paid': total_principal_paid,
            'interest_paid': total_interest_paid,
            'remaining_balance': self.current_balance
        }
        self.payments.append(payment)

        # Check if extension is fully paid
        if self.payment_schedule['paid'].all():
            self.status = "PAID"

        return payment


class KeepCardSimulator:
    def __init__(self, statement_cycle_start=1):
        """
        Initialize the Keep Card simulator.

        Parameters:
        statement_cycle_start (int): Day of month when statement cycle starts (1-28 recommended)
        """
        self.transactions = pd.DataFrame(columns=[
            'id', 'type', 'direction', 'amount', 'effective_date', 'created_at', 'balance'
        ])
        self.statements = pd.DataFrame(columns=[
            'start_date', 'end_date', 'due_date', 'beginning_balance',
            'ending_balance', 'purchases_amount', 'refunds_amount', 'payments_amount',
            'balance_due'
        ])
        self.statement_cycle_start = statement_cycle_start

        # Statement extensions
        self.extensions = []

        # Canadian holidays for 2025 (simplified list)
        self.holidays = [
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

    def is_business_day(self, date):
        """Check if the date is a business day."""
        return date.weekday() < 5 and date not in self.holidays

    def get_next_business_day(self, date):
        """Get the next business day after the given date."""
        next_day = date + timedelta(days=1)
        while not self.is_business_day(next_day):
            next_day += timedelta(days=1)
        return next_day

    def add_transaction(self, transaction_type, amount, effective_date=None, created_at=None):
        """
        Add a single transaction to the system.

        Parameters:
        transaction_type (str): Type of transaction ('PURCHASE', 'REFUND', 'PAYMENT', 'PAYMENT_REVERSAL', 'EXTENSION')
        amount (float): Amount of the transaction
        effective_date (str or datetime): Date when transaction is effective (default: today)
        created_at (str or datetime): Date when transaction is created (default: today)

        Returns:
        DataFrame: Updated transactions DataFrame
        """
        if effective_date is None:
            effective_date = datetime.date.today()
        else:
            if isinstance(effective_date, str):
                effective_date = datetime.datetime.strptime(
                    effective_date, '%Y-%m-%d').date()

        if created_at is None:
            created_at = datetime.date.today()
        else:
            if isinstance(created_at, str):
                created_at = datetime.datetime.strptime(
                    created_at, '%Y-%m-%d').date()

        # Determine direction based on transaction type
        if transaction_type in ['PAYMENT', 'REFUND', 'EXTENSION']:
            direction = 'CREDIT'
        else:
            direction = 'DEBIT'

        # Create new transaction
        new_transaction = pd.DataFrame({
            'id': [str(uuid.uuid4())],
            'type': [transaction_type],
            'direction': [direction],
            'amount': [float(amount)],
            'effective_date': [effective_date],
            'created_at': [created_at],
            'balance': [0.0]  # Placeholder, will be calculated
        })

        # Add to transactions and sort by effective date
        self.transactions = pd.concat(
            [self.transactions, new_transaction], ignore_index=True)
        self.transactions = self.transactions.sort_values(
            by=['effective_date', 'type'],
            ascending=[True, True],
            key=lambda x: pd.Categorical(x, categories=[
                                         'EXTENSION', 'PAYMENT', 'PURCHASE'], ordered=True) if x.name == 'type' else x
        )

        # Recalculate running balance
        self._recalculate_balance()

        # Generate statements
        self._generate_statements()

        return self.transactions

    def create_statement_extension(self, amount, effective_date=None, term_months=12, apr=36.0):
        """
        Create a statement extension to move balance due to the extension product.

        Parameters:
        amount (float): Amount to extend
        effective_date (str or datetime): Date of extension (default: today)
        term_months (int): Number of months for repayment (1-12)
        apr (float): Annual Percentage Rate for the extension (default: 36.0%)

        Returns:
        str: ID of the created extension
        """
        if effective_date is None:
            effective_date = datetime.date.today()
        else:
            if isinstance(effective_date, str):
                effective_date = datetime.datetime.strptime(
                    effective_date, '%Y-%m-%d').date()

        # Add an EXTENSION transaction to the card
        self.add_transaction('EXTENSION', amount,
                             effective_date, effective_date)

        # Create the extension product
        extension_id = f"EXT-{len(self.extensions) + 1:04d}"
        extension = ExtensionProduct(
            extension_id, amount, effective_date, term_months, apr)
        self.extensions.append(extension)

        return extension_id

    def make_extension_payment(self, extension_id, amount, payment_date=None):
        """
        Make a payment toward a statement extension.

        Parameters:
        extension_id (str): ID of the extension to pay
        amount (float): Payment amount
        payment_date (str or datetime): Date of payment (default: today)

        Returns:
        dict: Payment details or None if extension not found
        """
        if payment_date is None:
            payment_date = datetime.date.today()
        else:
            if isinstance(payment_date, str):
                payment_date = datetime.datetime.strptime(
                    payment_date, '%Y-%m-%d').date()

        # Find the extension
        extension = None
        for ext in self.extensions:
            if ext.extension_id == extension_id:
                extension = ext
                break

        if extension is None:
            print(f"Extension {extension_id} not found")
            return None

        # Make the payment
        return extension.make_payment(amount, payment_date)

    def generate_bulk_transactions(self, num_purchases=0, avg_purchase_amount=50,
                                   num_refunds=0, avg_refund_amount=25,
                                   num_payments=0, avg_payment_amount=100,
                                   start_date=None, end_date=None, randomize=True):
        """
        Generate multiple transactions in bulk.

        Parameters:
        num_purchases (int): Number of purchase transactions to generate
        avg_purchase_amount (float): Average amount for purchases
        num_refunds (int): Number of refund transactions to generate
        avg_refund_amount (float): Average amount for refunds
        num_payments (int): Number of payment transactions to generate
        avg_payment_amount (float): Average amount for payments
        start_date (str or datetime): Start date for transactions (default: beginning of current month)
        end_date (str or datetime): End date for transactions (default: end of current month)
        randomize (bool): Whether to randomize amounts and dates

        Returns:
        DataFrame: Updated transactions DataFrame
        """
        if start_date is None:
            start_date = datetime.date.today().replace(day=1)
        elif isinstance(start_date, str):
            start_date = datetime.datetime.strptime(
                start_date, '%Y-%m-%d').date()

        if end_date is None:
            # Last day of current month
            next_month = start_date.replace(day=28) + timedelta(days=4)
            end_date = next_month - timedelta(days=next_month.day)
        elif isinstance(end_date, str):
            end_date = datetime.datetime.strptime(end_date, '%Y-%m-%d').date()

        # Generate purchases
        for _ in range(num_purchases):
            if randomize:
                amount = np.random.uniform(0.1, avg_purchase_amount * 2)
                days_between = (end_date - start_date).days
                random_days = int(np.random.random() * days_between)
                date = start_date + timedelta(days=random_days)
            else:
                amount = avg_purchase_amount
                days_between = (end_date - start_date).days
                day_increment = max(1, days_between //
                                    num_purchases) if num_purchases > 0 else 1
                date = start_date + timedelta(days=_ * day_increment)

            self.add_transaction('PURCHASE', amount, date, date)

        # Generate refunds
        for _ in range(num_refunds):
            if randomize:
                amount = np.random.uniform(0.1, avg_refund_amount * 2)
                days_between = (end_date - start_date).days
                random_days = int(np.random.random() * days_between)
                date = start_date + timedelta(days=random_days)
            else:
                amount = avg_refund_amount
                days_between = (end_date - start_date).days
                day_increment = max(1, days_between //
                                    num_refunds) if num_refunds > 0 else 1
                date = start_date + timedelta(days=_ * day_increment)

            self.add_transaction('REFUND', amount, date, date)

        # Generate payments
        for _ in range(num_payments):
            if randomize:
                amount = np.random.uniform(0.1, avg_payment_amount * 2)
                days_between = (end_date - start_date).days
                random_days = int(np.random.random() * days_between)
                date = start_date + timedelta(days=random_days)
            else:
                amount = avg_payment_amount
                days_between = (end_date - start_date).days
                day_increment = max(1, days_between //
                                    num_payments) if num_payments > 0 else 1
                date = start_date + timedelta(days=_ * day_increment)

            self.add_transaction('PAYMENT', amount, date, date)

        return self.transactions

    def _recalculate_balance(self):
        """Recalculate the running balance for all transactions."""
        if self.transactions.empty:
            return

        balance = 0.0
        for idx in self.transactions.index:
            transaction = self.transactions.loc[idx]
            if transaction['direction'] == 'DEBIT':
                balance += transaction['amount']
            else:  # CREDIT
                balance -= transaction['amount']

            self.transactions.loc[idx, 'balance'] = balance

    def _calculate_balance_due(self, current_stmt_idx, prev_stmt_idx=None):
        """
        Calculate the balance due from previous statement.

        Parameters:
        current_stmt_idx (int): Index of current statement
        prev_stmt_idx (int): Index of previous statement

        Returns:
        float: Balance due amount
        """
        # If this is the first statement, there's no previous balance due
        if prev_stmt_idx is None or prev_stmt_idx < 0:
            return 0.0

        # Get previous statement details
        prev_stmt = self.statements.iloc[prev_stmt_idx]
        prev_end_balance = prev_stmt['ending_balance']
        prev_due_date = prev_stmt['due_date']

        # Get current statement details
        current_stmt = self.statements.iloc[current_stmt_idx]
        current_start_date = current_stmt['start_date']

        # Find all payments and extensions made between previous due date and current statement start
        credits_after_due_date = self.transactions[
            ((self.transactions['type'] == 'PAYMENT') | (self.transactions['type'] == 'EXTENSION')) &
            (self.transactions['effective_date'] <= current_start_date) &
            (self.transactions['effective_date'] > prev_due_date)
        ]['amount'].sum()

        # Subtract payments and extensions from previous balance
        balance_due = max(0, prev_end_balance - credits_after_due_date)

        return balance_due

    def _generate_statements(self):
        """Generate statements based on transactions."""
        if self.transactions.empty:
            self.statements = pd.DataFrame(columns=[
                'start_date', 'end_date', 'due_date', 'beginning_balance',
                'ending_balance', 'purchases_amount', 'refunds_amount',
                'payments_amount', 'balance_due', 'extensions_amount'
            ])
            return

        # Get date range from first to last transaction
        min_date = self.transactions['effective_date'].min()
        max_date = self.transactions['effective_date'].max()

        # Start from the first cycle that would include the first transaction
        if min_date.day < self.statement_cycle_start:
            # Current month's cycle already started
            current_start = datetime.date(
                min_date.year, min_date.month, self.statement_cycle_start)
        else:
            # Need to go to previous month's cycle
            if min_date.month == 1:
                current_start = datetime.date(
                    min_date.year - 1, 12, self.statement_cycle_start)
            else:
                current_start = datetime.date(
                    min_date.year, min_date.month - 1, self.statement_cycle_start)

        # If current_start is after min_date, go back one more month
        if current_start > min_date:
            if current_start.month == 1:
                current_start = datetime.date(
                    current_start.year - 1, 12, self.statement_cycle_start)
            else:
                current_start = datetime.date(
                    current_start.year, current_start.month - 1, self.statement_cycle_start)

        statement_list = []

        # Generate statements until we cover all transactions
        while current_start <= max_date:
            # Calculate end date (day before next cycle starts)
            if current_start.month == 12:
                next_cycle_start = datetime.date(
                    current_start.year + 1, 1, self.statement_cycle_start)
            else:
                # Handle months with fewer days than statement_cycle_start
                next_month = current_start.month + 1
                next_year = current_start.year

                # Check if statement_cycle_start exists in next month
                try:
                    next_cycle_start = datetime.date(
                        next_year, next_month, self.statement_cycle_start)
                except ValueError:
                    # Use last day of next month
                    if next_month == 12:
                        next_cycle_start = datetime.date(
                            next_year + 1, 1, 1) - timedelta(days=1)
                    else:
                        next_cycle_start = datetime.date(
                            next_year, next_month + 1, 1) - timedelta(days=1)

            end_date = next_cycle_start - timedelta(days=1)
            due_date = self.get_next_business_day(end_date)

            # Find transactions in this statement period
            stmt_transactions = self.transactions[
                (self.transactions['effective_date'] >= current_start) &
                (self.transactions['effective_date'] <= end_date)
            ]

            # Calculate statement totals
            purchases_amount = stmt_transactions[stmt_transactions['type'] == 'PURCHASE']['amount'].sum(
            )
            refunds_amount = stmt_transactions[stmt_transactions['type'] == 'REFUND']['amount'].sum(
            )
            payments_amount = stmt_transactions[stmt_transactions['type'] == 'PAYMENT']['amount'].sum(
            )
            extensions_amount = stmt_transactions[stmt_transactions['type'] == 'EXTENSION']['amount'].sum(
            )

            # Beginning and ending balance
            if statement_list:
                beginning_balance = statement_list[-1]['ending_balance']
            else:
                # For first statement, get balance before first transaction in period
                txs_before_period = self.transactions[self.transactions['effective_date'] < current_start]
                if txs_before_period.empty:
                    beginning_balance = 0.0
                else:
                    beginning_balance = txs_before_period.iloc[-1]['balance']

            ending_balance = beginning_balance + purchases_amount - \
                refunds_amount - payments_amount - extensions_amount

            # Calculate balance due (will be updated after all statements are created)
            # Placeholder value for now
            balance_due = 0.0

            statement_list.append({
                'start_date': current_start,
                'end_date': end_date,
                'due_date': due_date,
                'beginning_balance': beginning_balance,
                'ending_balance': ending_balance,
                'purchases_amount': purchases_amount,
                'refunds_amount': refunds_amount,
                'payments_amount': payments_amount,
                'extensions_amount': extensions_amount,
                'balance_due': balance_due,
                'transactions': stmt_transactions
            })

            # Move to next cycle
            current_start = next_cycle_start

        # Add next open statement
        if statement_list:
            next_start = current_start
            if next_start.month == 12:
                next_end = datetime.date(
                    next_start.year + 1, 1, self.statement_cycle_start) - timedelta(days=1)
            else:
                try:
                    next_end = datetime.date(
                        next_start.year, next_start.month + 1, self.statement_cycle_start) - timedelta(days=1)
                except ValueError:
                    if next_start.month == 12:
                        next_end = datetime.date(
                            next_start.year + 1, 1, 1) - timedelta(days=1)
                    else:
                        next_end = datetime.date(
                            next_start.year, next_start.month + 2, 1) - timedelta(days=1)

            next_due_date = self.get_next_business_day(next_end)

            statement_list.append({
                'start_date': next_start,
                'end_date': next_end,
                'due_date': next_due_date,
                'beginning_balance': statement_list[-1]['ending_balance'],
                'ending_balance': None,
                'purchases_amount': None,
                'refunds_amount': None,
                'payments_amount': None,
                'extensions_amount': None,
                'balance_due': 0.0,
                'transactions': pd.DataFrame()
            })

        # Create statements dataframe
        self.statements = pd.DataFrame(statement_list)

        # Now update the balance_due for each statement
        for i in range(len(self.statements)):
            prev_idx = i - 1
            if prev_idx >= 0:
                self.statements.loc[i,
                                    'balance_due'] = 0 if self.statements.loc[i, 'beginning_balance'] < 0 else self.statements.loc[i, 'beginning_balance']

    def reset(self):
        """Reset all data in the simulator."""
        self.transactions = pd.DataFrame(columns=[
            'id', 'type', 'direction', 'amount', 'effective_date', 'created_at', 'balance'
        ])
        self.statements = pd.DataFrame(columns=[
            'start_date', 'end_date', 'due_date', 'beginning_balance',
            'ending_balance', 'purchases_amount', 'refunds_amount',
            'payments_amount', 'extensions_amount', 'balance_due'
        ])
        self.extensions = []

    def show_transactions(self):
        """Display the transaction ledger with formatted values."""
        if self.transactions.empty:
            print("No transactions available.")
            return

        # Make a copy for display formatting
        display_df = self.transactions.copy()

        # Format currency columns
        display_df['amount'] = display_df['amount'].apply(
            lambda x: f"${x:.2f}")
        display_df['balance'] = display_df['balance'].apply(
            lambda x: f"${x:.2f}")

        # Format dates - ensure they're properly formatted as strings
        display_df['effective_date'] = display_df['effective_date'].apply(
            lambda x: x.strftime('%Y-%m-%d') if hasattr(x, 'strftime') else str(x))

        # Reorder and select columns for display
        columns = ['effective_date', 'type', 'direction', 'amount', 'balance']
        print(display_df[columns].to_string(index=False))

    def show_statements(self, include_transactions=False):
        """
        Display statement summaries.

        Parameters:
        include_transactions (bool): Whether to show transactions in each statement
        """
        if self.statements.empty:
            print("No statements available.")
            return

        for idx, stmt in self.statements.iterrows():
            print(f"Statement {idx+1}:")
            start_date_str = stmt['start_date'].strftime(
                '%Y-%m-%d') if hasattr(stmt['start_date'], 'strftime') else str(stmt['start_date'])
            end_date_str = stmt['end_date'].strftime(
                '%Y-%m-%d') if hasattr(stmt['end_date'], 'strftime') else str(stmt['end_date'])
            due_date_str = stmt['due_date'].strftime(
                '%Y-%m-%d') if hasattr(stmt['due_date'], 'strftime') else str(stmt['due_date'])

            print(f"Period: {start_date_str} to {end_date_str}")
            print(f"Due Date: {due_date_str}")
            print(
                f"Balance Due (from previous statement): ${stmt['balance_due']:.2f}")
            print(f"Beginning Balance: ${stmt['beginning_balance']:.2f}")
            print(f"Purchases: ${stmt['purchases_amount']:.2f}")
            print(f"Refunds: ${stmt['refunds_amount']:.2f}")
            print(f"Payments: ${stmt['payments_amount']:.2f}")
            if 'extensions_amount' in stmt and stmt['extensions_amount'] > 0:
                print(f"Extensions: ${stmt['extensions_amount']:.2f}")
            print(f"Ending Balance: ${stmt['ending_balance']:.2f}")

            if include_transactions and 'transactions' in stmt and not stmt['transactions'].empty:
                print("\nTransactions in this statement:")
                display_txs = stmt['transactions'].copy()
                display_txs['amount'] = display_txs['amount'].apply(
                    lambda x: f"${x:.2f}")
                display_txs['balance'] = display_txs['balance'].apply(
                    lambda x: f"${x:.2f}")
                display_txs['effective_date'] = display_txs['effective_date'].apply(
                    lambda x: x.strftime('%Y-%m-%d') if hasattr(x, 'strftime') else str(x))
                print(display_txs[['effective_date', 'type',
                      'amount', 'balance']].to_string(index=False))

            print("\n" + "-"*50 + "\n")

    def calculate_period_balance_due(self, date):
        """
        Calculate balance due for a given date, considering all transactions up to that date.

        Gets the beginning balance of most recent past statement and applies PAYMENT/EXTENSION
        transactions up to the given date. Credits decrease balance due, debits increase it.

        Parameters:
        date (datetime): The date to calculate balance due for

        Returns:
        float: The balance due amount as of that date
        """
        # If there are no statements, there's no balance due
        if self.statements.empty:
            return 0.0

        # Find most recent statement before the given date
        past_stmt = self.statements[self.statements['start_date'] <= date]

        if past_stmt.empty:
            return 0.0

        # Get the most recent statement by taking the last row
        current_stmt = past_stmt.iloc[-1:]

        # Get beginning balance of most recent past statement
        balance_due = float(current_stmt.iloc[0]['balance_due'])

        # Get all PAYMENT and EXTENSION transactions up to given date
        relevant_txns = self.transactions[
            ((self.transactions['type'] == 'PAYMENT') |
             (self.transactions['type'] == 'EXTENSION')) &
            (self.transactions['effective_date'] <= date) &
            (self.transactions['effective_date']
             >= current_stmt.iloc[0]['start_date'])
        ]

        # Apply transactions to balance due
        for _, txn in relevant_txns.iterrows():
            if txn['direction'] == 'CREDIT':
                balance_due = max(0, balance_due - txn['amount'])
            else:
                balance_due += txn['amount']

        return balance_due

    def get_unified_timeline(self):
        """
        Get a unified timeline of all card and extension events.

        Returns:
        DataFrame: Timeline of all events sorted by date
        """
        if self.transactions.empty and not self.extensions:
            return pd.DataFrame(columns=['Date', 'Card Event', 'Card Details', 'Extension Event', 'Extension Details'])

        # Initialize timeline with columns for both products
        timeline = pd.DataFrame(columns=[
                                'Date', 'Card Event', 'Card Details', 'Extension Event', 'Extension Details'])

        # Get all dates where something happens (transactions, statements, extension events)
        all_dates = []

        # Add transaction dates
        if not self.transactions.empty:
            all_dates.extend(self.transactions['effective_date'].tolist())

        # Add statement dates
        if not self.statements.empty:
            for _, stmt in self.statements.iterrows():
                all_dates.append(stmt['start_date'])  # New statement
                all_dates.append(stmt['due_date'])    # Payment due

        # Add extension events
        for ext in self.extensions:

            all_dates.append(ext.start_date)  # Extension creation

            all_dates += ext.payment_schedule.loc[:, 'payment_date'].to_list()

            for payment in ext.payments:
                all_dates.append(payment['payment_date'])  # Actual payments

        # Remove duplicates and sort
        all_dates = sorted(list(set(all_dates)))

        # For each date, calculate the correct balance and balance due
        # and add all events that occurred on that date
        for date in all_dates:
            # Calculate the rolling balance and balance due for this date
            txs_on_date = self.transactions[self.transactions['effective_date'] == date]

            if not txs_on_date.empty:
                # For each transaction on this date, add a card event
                for _, tx in txs_on_date.iterrows():
                    # Recalculate balance due properly for this specific transaction
                    # This ensures payments correctly affect the balance due
                    balance_due = self.calculate_period_balance_due(date)

                    event = tx['type']
                    details = f"{tx['direction']}: ${tx['amount']:.2f}, Balance: ${tx['balance']:.2f}, Balance Due: ${balance_due:.2f}"

                    # For extensions, add to both columns
                    if tx['type'] == 'EXTENSION':
                        new_row = pd.DataFrame({
                            'Date': [date],
                            'Card Event': [event],
                            'Card Details': [details],
                            'Extension Event': ['CREATED'],
                            'Extension Details': [f"Amount: ${tx['amount']:.2f} moved to Extension product"]
                        })
                    else:
                        new_row = pd.DataFrame({
                            'Date': [date],
                            'Card Event': [event],
                            'Card Details': [details],
                            'Extension Event': [''],
                            'Extension Details': ['']
                        })

                    timeline = pd.concat(
                        [timeline, new_row], ignore_index=True)

            # Add statement events for this date
            if not self.statements.empty:
                # New statement starts
                stmt_starts = self.statements[self.statements['start_date'] == date]
                if not stmt_starts.empty:
                    for _, stmt in stmt_starts.iterrows():
                        balance_due = stmt['beginning_balance']
                        new_row = pd.DataFrame({
                            'Date': [date],
                            'Card Event': ['NEW STATEMENT'],
                            'Card Details': [f"Beginning Balance: ${stmt['beginning_balance']:.2f}, Balance Due: ${balance_due:.2f}"],
                            'Extension Event': [''],
                            'Extension Details': ['']
                        })
                        timeline = pd.concat(
                            [timeline, new_row], ignore_index=True)

                # Payment due
                stmt_dues = self.statements[self.statements['due_date'] == date]
                if not stmt_dues.empty:
                    for _, stmt in stmt_dues.iterrows():
                        balance_due = self.calculate_period_balance_due(date)
                        new_row = pd.DataFrame({
                            'Date': [date],
                            'Card Event': ['PAYMENT DUE'],
                            'Card Details': [f"Balance Due: ${balance_due:.2f}"],
                            'Extension Event': [''],
                            'Extension Details': ['']
                        })
                        timeline = pd.concat(
                            [timeline, new_row], ignore_index=True)

            # Add extension events for this date
            for ext in self.extensions:
                # Skip extension creation as it's already captured as EXTENSION in transactions
                if ext.start_date == date:
                    continue

                scheduled_payments_list = ext.payment_schedule.to_dict(
                    'records')
                # Check scheduled payments
                scheduled_payments = [
                    p for p in scheduled_payments_list if p['payment_date'] == date]
                for payment in scheduled_payments:
                    new_row = pd.DataFrame({
                        'Date': [date],
                        'Card Event': [''],
                        'Card Details': [''],
                        'Extension Event': ['PAYMENT DUE'],
                        'Extension Details': [f"ID: {ext.extension_id}, Payment: ${payment['payment_amount']:.2f} (P: ${payment['principal_amount']:.2f}, I: ${payment['interest_amount']:.2f})"]
                    })
                    timeline = pd.concat(
                        [timeline, new_row], ignore_index=True)

                # Check actual payments made
                actual_payments = [
                    p for p in ext.payments if p['payment_date'] == date]
                for payment in actual_payments:
                    new_row = pd.DataFrame({
                        'Date': [date],
                        'Card Event': [''],
                        'Card Details': [''],
                        'Extension Event': ['PAYMENT MADE'],
                        'Extension Details': [f"ID: {ext.extension_id}, Amount: ${payment['payment_amount']:.2f}, Remaining: ${payment['remaining_balance']:.2f}"]
                    })
                    timeline = pd.concat(
                        [timeline, new_row], ignore_index=True)

        # Sort by date (again to ensure order after all additions)
        timeline = timeline.sort_values(
            by=['Date', 'Card Event'],
            ascending=[True, True],
            key=lambda x: pd.Categorical(x, categories=[
                'NEW STATEMENT', 'PAYMENT DUE', 'EXTENSION', 'PAYMENT', 'PURCHASE'], ordered=True) if x.name == 'Card Event' else x
        )

        # Reset index
        timeline = timeline.reset_index(drop=True)

        return timeline

    def display_timeline(self):
        """Display a unified timeline of all card and extension events."""
        timeline = self.get_unified_timeline()

        if timeline.empty:
            print("No events to display.")
            return

        # Format the dates for display
        timeline['Date'] = timeline['Date'].apply(
            lambda x: x.strftime('%Y-%m-%d') if hasattr(x, 'strftime') else str(x))

        # Set display options to handle wider tables
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', 150)

        # Print the timeline
        print("=== UNIFIED TIMELINE OF CARD AND EXTENSION EVENTS ===")
        print(timeline.to_string(index=False))

        # Reset display options
        pd.reset_option('display.max_columns')
        pd.reset_option('display.width')

    def get_side_by_side_view(self):
        """
        Get transaction and statement data formatted for side-by-side display.

        Returns: statements_df
        """

        # Format statements
        if not self.statements.empty:
            stmt_display = []
            for _, stmt in self.statements.iterrows():
                start_date_str = stmt['start_date'].strftime(
                    '%Y-%m-%d') if hasattr(stmt['start_date'], 'strftime') else str(stmt['start_date'])
                end_date_str = stmt['end_date'].strftime(
                    '%Y-%m-%d') if hasattr(stmt['end_date'], 'strftime') else str(stmt['end_date'])
                due_date_str = stmt['due_date'].strftime(
                    '%Y-%m-%d') if hasattr(stmt['due_date'], 'strftime') else str(stmt['due_date'])

                row = {
                    'Period': f"{start_date_str} to {end_date_str}",
                    'Due Date': due_date_str,
                    'Balance Due': f"${stmt['balance_due']:.2f}",
                    'Begin Balance': f"${stmt['beginning_balance']:.2f}",
                    'Purchases': f"${stmt['purchases_amount']:.2f}",
                    'Refunds': f"${stmt['refunds_amount']:.2f}",
                    'Payments': f"${stmt['payments_amount']:.2f}",
                }

                if 'extensions_amount' in stmt and stmt['extensions_amount'] > 0:
                    row['Extensions'] = f"${stmt['extensions_amount']:.2f}"

                row['End Balance'] = f"${stmt['ending_balance']:.2f}"

                stmt_display.append(row)

            stmt_display = pd.DataFrame(stmt_display)
        else:
            stmt_display = pd.DataFrame(columns=[
                'Period', 'Due Date', 'Balance Due', 'Begin Balance', 'Purchases',
                'Refunds', 'Payments', 'Extensions', 'End Balance'
            ])

        return stmt_display

    def display_side_by_side(self):
        """Display transactions and statements side by side."""
        stmt_display = self.get_side_by_side_view()

        if stmt_display.empty:
            print("No statements available.")
        else:
            print(stmt_display.to_string(index=False))

    def show_extensions(self):
        """Display all statement extensions and their payment schedules."""
        if not self.extensions:
            print("No statement extensions found.")
            return

        for ext in self.extensions:
            print(f"=== EXTENSION ID: {ext.extension_id} ===")
            print(f"Original Amount: ${ext.original_amount:.2f}")
            print(f"Start Date: {ext.start_date.strftime('%Y-%m-%d')}")
            print(f"Term: {ext.term_months} months")
            print(f"APR: {ext.apr}%")
            print(f"Monthly Payment: ${ext.monthly_payment:.2f}")
            print(f"Current Balance: ${ext.current_balance:.2f}")
            print(f"Status: {ext.status}")

            print("\nPayment Schedule:")
            schedule_df = pd.DataFrame(ext.payment_schedule)
            schedule_df['payment_date'] = schedule_df['payment_date'].apply(
                lambda x: x.strftime('%Y-%m-%d') if hasattr(x, 'strftime') else str(x))
            schedule_df['payment_amount'] = schedule_df['payment_amount'].apply(
                lambda x: f"${x:.2f}")
            schedule_df['principal_amount'] = schedule_df['principal_amount'].apply(
                lambda x: f"${x:.2f}")
            schedule_df['interest_amount'] = schedule_df['interest_amount'].apply(
                lambda x: f"${x:.2f}")
            schedule_df['remaining_principal'] = schedule_df['remaining_principal'].apply(
                lambda x: f"${x:.2f}")
            schedule_df['remaining_interest'] = schedule_df['remaining_interest'].apply(
                lambda x: f"${x:.2f}")

            print(schedule_df.rename(columns={
                'payment_number': 'Payment #',
                'payment_date': 'Due Date',
                'payment_amount': 'Amount',
                'principal_amount': 'Principal',
                'interest_amount': 'Interest',
                'remaining_principal': 'Remaining Principal',
                'remaining_interest': 'Remaining Interest'
            }).to_string(index=False))

            if ext.payments:
                print("\nActual Payments Made:")
                payments_df = pd.DataFrame(ext.payments)
                payments_df['payment_date'] = payments_df['payment_date'].apply(
                    lambda x: x.strftime('%Y-%m-%d') if hasattr(x, 'strftime') else str(x))
                payments_df['payment_amount'] = payments_df['payment_amount'].apply(
                    lambda x: f"${x:.2f}")
                payments_df['principal_paid'] = payments_df['principal_paid'].apply(
                    lambda x: f"${x:.2f}")
                payments_df['interest_paid'] = payments_df['interest_paid'].apply(
                    lambda x: f"${x:.2f}")
                payments_df['remaining_balance'] = payments_df['remaining_balance'].apply(
                    lambda x: f"${x:.2f}")

                print(payments_df.rename(columns={
                    'payment_date': 'Date',
                    'payment_amount': 'Amount',
                    'principal_paid': 'Principal',
                    'interest_paid': 'Interest',
                    'remaining_balance': 'Remaining'
                }).to_string(index=False))

            print("\n" + "="*50 + "\n")
