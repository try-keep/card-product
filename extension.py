import pandas as pd
import datetime


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
        self.total_interest = amount * (apr/100) * (term_months/12)

        # Calculate monthly payment (fixed payment including principal and interest)
        self.monthly_payment = (amount + self.total_interest) / term_months

        # Create payment schedule as a pandas DataFrame
        # Round monthly amounts to 2 decimals for all but last payment
        monthly_principal = round(amount / term_months, 2)
        monthly_interest = round(self.total_interest / term_months, 2)

        # Calculate remainders to add to last payment
        principal_remainder = amount - (monthly_principal * (term_months - 1))
        interest_remainder = self.total_interest - \
            (monthly_interest * (term_months - 1))

        schedule_data = []
        for month in range(1, term_months + 1):
            payment_date = self._add_months(start_date, month)

            # Use remainder amounts for last payment
            if month == term_months:
                principal = principal_remainder
                interest = interest_remainder
            else:
                principal = monthly_principal
                interest = monthly_interest

            schedule_data.append({
                'payment_number': month,
                'payment_date': payment_date,
                'payment_amount': principal + interest,
                'principal_amount': principal,
                'interest_amount': interest,
                'remaining_principal': principal,
                'remaining_interest': interest,
                'remaining_amount': principal + interest,
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

    def get_past_due_installments(self, payment_date):
        """
        Get all past due installments for this extension.
        """
        installments = self.payment_schedule[
            (self.payment_schedule['payment_date'] < payment_date) &
            (~self.payment_schedule['paid'])
        ]
        return installments.sort_values(by='payment_date', ascending=True)

    def get_past_due_amount(self, payment_date):
        """
        Get the amount past due for this extension.
        """
        installments = self.get_past_due_installments(payment_date)
        return installments['remaining_amount'].sum()

    def get_next_installment(self, payment_date):
        """
        Get the next installment for this extension.
        """
        installments = self.payment_schedule[
            (self.payment_schedule['payment_date'] >= payment_date)
        ]
        if installments.empty:
            return None

        return installments.sort_values(by='payment_date', ascending=True).iloc[0]

    def get_next_due_amount(self, payment_date):
        """
        Get the amount due for the next installment.
        """
        installment = self.get_next_installment(payment_date)
        if installment is None or installment['paid']:
            return 0.0

        return installment['remaining_amount']

    def pay_past_due_amount(self, payment_date, payment_amount):
        """
        Pay the past due amount for this extension.
        """
        past_due_amount = self.get_past_due_amount(payment_date)
        if past_due_amount > payment_amount:
            return self.make_payment(payment_amount, payment_date)
        else:
            return self.make_payment(past_due_amount, payment_date)

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

            self.payment_schedule.at[idx,
                                     'remaining_amount'] = self.payment_schedule.at[idx, 'remaining_interest'] + self.payment_schedule.at[idx, 'remaining_principal']

            if remaining_payment <= 0:
                break

        current_installment = self.get_next_installment(payment_date)

        if current_installment is not None and current_installment['paid'] == False and remaining_payment > 0:
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


class ExtensionFactory:
    def __init__(self):
        self.extensions = []

    def create_extension(self, extension_id, amount, start_date, term_months, apr=36.0):
        extension = ExtensionProduct(
            extension_id, amount, start_date, term_months, apr)
        self.extensions.append(extension)
        return extension

    def get_past_due_amount(self, payment_date):
        """
        Get the total past due amount across all active extensions.

        Parameters:
        payment_date (str or datetime): Date to check past due amount for

        Returns:
        float: Total past due amount across all active extensions
        """
        if isinstance(payment_date, str):
            payment_date = datetime.datetime.strptime(
                payment_date, '%Y-%m-%d').date()

        total_past_due = 0.0
        for extension in self.extensions:
            if extension.status == "ACTIVE":
                total_past_due += extension.get_past_due_amount(payment_date)
        return total_past_due

    def get_next_due_amount(self, payment_date):
        """
        Get the total next due amount across all active extensions.

        Parameters:
        payment_date (str or datetime): Date to check next due amount for

        Returns:
        float: Total next due amount across all active extensions
        """
        if isinstance(payment_date, str):
            payment_date = datetime.datetime.strptime(
                payment_date, '%Y-%m-%d').date()

        total_due = 0.0
        for extension in self.extensions:
            if extension.status == "ACTIVE":
                total_due += extension.get_next_due_amount(payment_date)
        return total_due

    def _make_past_due_next_due_payment(self, payment_date, amount):
        """
        Make a payment towards extensions in order of oldest to newest installments.

        Parameters:
        payment_date (datetime): Date of payment
        amount (float): Payment amount

        Returns:
        dict: Payment details including amounts applied to each extension
        """
        if isinstance(payment_date, str):
            payment_date = datetime.datetime.strptime(
                payment_date, '%Y-%m-%d').date()

        remaining_payment = amount
        payments_made = []

        # Get all past due installments across active extensions
        all_installments = []
        for extension in self.extensions:
            if extension.status == "ACTIVE":
                # Get past due installments
                past_due = extension.get_past_due_installments(payment_date)
                for idx, installment in past_due.iterrows():
                    all_installments.append({
                        'extension': extension,
                        'payment_date': installment['payment_date'],
                        'idx': idx,
                        'remaining_principal': installment['remaining_principal'],
                        'remaining_interest': installment['remaining_interest'],
                        'remaining_amount': installment['remaining_amount']
                    })

                next_due = extension.get_next_installment(payment_date)
                if next_due is not None:
                    all_installments.append({
                        'extension': extension,
                        'payment_date': next_due['payment_date'],
                        'remaining_amount': next_due['remaining_amount']
                    })

        # Sort by payment date
        all_installments.sort(key=lambda x: x['payment_date'])

        # Pay installments in order
        for installment in all_installments:
            if remaining_payment <= 0:
                break

            extension = installment['extension']
            payment_amount = min(
                installment['remaining_amount'], remaining_payment)
            payment = extension.make_payment(
                payment_amount, payment_date)
            remaining_payment -= payment['payment_amount']
            payments_made.append(payment)

        return {
            'payment_date': payment_date,
            'total_amount': amount,
            'payments': payments_made,
            'remaining_amount': remaining_payment
        }
