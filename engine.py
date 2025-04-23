import pandas as pd
import numpy as np
import datetime
import uuid
from datetime import timedelta
from time_utils import add_business_days


class Statement:
    @classmethod
    def get_statement_cycles(cls, start_date, grace_period_days, cycle_count):
        """
        Calculate statement cycles based on start date and grace period.

        Parameters:
        start_date (datetime): Starting date of first statement
        grace_period_days (int): Number of business days after statement end until due date
        cycle_count (int): Number of statement cycles to generate

        Returns:
        list[tuple]: List of (statement_start, statement_end, statement_due) for each cycle
        """
        # Validate start date is not 28/29/30/31/1
        if start_date.day in [1, 28, 29, 30, 31]:
            raise ValueError(
                "Statement start date must not be on the 1st or 28th-31st of month")

        cycles = []
        current_start = start_date

        for _ in range(cycle_count):
            # Calculate end date (start date + 1 month - 1 day)
            if current_start.month == 12:
                end_date = datetime.date(
                    current_start.year + 1, 1, current_start.day - 1)
            else:
                end_date = datetime.date(
                    current_start.year, current_start.month + 1, current_start.day - 1)

            # Calculate due date by adding business days
            due_date = add_business_days(
                end_date, grace_period_days)

            cycles.append((current_start, end_date, due_date))

            # Set up next cycle start date
            if current_start.month == 12:
                current_start = datetime.date(
                    current_start.year + 1, 1, current_start.day)
            else:
                current_start = datetime.date(
                    current_start.year, current_start.month + 1, current_start.day)

        return cycles


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

        self.extension_factory = ExtensionFactory()

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

    def create_statement_extension(self, amount, effective_date, term_months=12, apr=36.0):
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

        if isinstance(effective_date, str):
            effective_date = datetime.datetime.strptime(
                effective_date, '%Y-%m-%d').date()

        # Add an EXTENSION transaction to the card
        self.add_transaction('EXTENSION', amount,
                             effective_date, effective_date)

        # Create the extension product
        extension_id = f"EXT-{len(self.extension_factory.extensions) + 1:04d}"
        extension = self.extension_factory.create_extension(
            extension_id, amount, effective_date, term_months, apr)
        self.extension_factory.extensions.append(extension)

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
        for ext in self.extension_factory.extensions:
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

        # Calculate number of months needed between current_start and max_date
        months_between = (max_date.year - current_start.year) * \
            12 + max_date.month - current_start.month + 1

        # Get statement cycles using Statement class
        statement_cycles = Statement.get_statement_cycles(
            current_start, 1, months_between)

        # Generate statements for each cycle
        for cycle_start, cycle_end, cycle_due in statement_cycles:
            # Stop if we've gone past max_date
            if cycle_start > max_date:
                break

            # Find transactions in this statement period
            stmt_transactions = self.transactions[
                (self.transactions['effective_date'] >= cycle_start) &
                (self.transactions['effective_date'] <= cycle_end)
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
                txs_before_period = self.transactions[self.transactions['effective_date'] < cycle_start]
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
                'start_date': cycle_start,
                'end_date': cycle_end,
                'due_date': cycle_due,
                'beginning_balance': beginning_balance,
                'ending_balance': ending_balance,
                'purchases_amount': purchases_amount,
                'refunds_amount': refunds_amount,
                'payments_amount': payments_amount,
                'extensions_amount': extensions_amount,
                'balance_due': balance_due,
                'transactions': stmt_transactions
            })

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

            next_due_date = add_business_days(next_end, 1)

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
        self.extension_factory.extensions = []

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
        if self.transactions.empty and not self.extension_factory.extensions:
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
        for ext in self.extension_factory.extensions:

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
            for ext in self.extension_factory.extensions:
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
                        'Extension Details': [f"ID: {ext.extension_id}, Payment: ${(payment['remaining_principal'] + payment['remaining_interest']):.2f} (P: ${payment['remaining_principal']:.2f}, I: ${payment['remaining_interest']:.2f})"]
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
        if not self.extension_factory.extensions:
            print("No statement extensions found.")
            return

        for ext in self.extension_factory.extensions:
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
