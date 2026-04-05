"""Represent Anglian Water billing data."""

from datetime import datetime

from .utils import parse_iso_datetime


class PaymentArrangement:
    """Represents a payment arrangement within a billing summary."""

    def __init__(self, data: dict):
        """Initialise PaymentArrangement from a parsed dict."""
        self.payment_type: str = data.get("payment_type", "")
        self.end_term_balance: float = float(data.get("end_term_balance", 0.0))
        self.payment_frequency: str = data.get("payment_frequency", "")
        self.payment_day: int = int(data.get("payment_day", 0))
        self.payment_amount: float = float(data.get("payment_amount", 0.0))
        self.are_request_lines_open: bool = bool(data.get("are_request_lines_open", False))
        self.payment_reminder: bool = bool(data.get("payment_reminder", False))
        self.bill_period_end_date: datetime | None = (
            parse_iso_datetime(data["bill_period_end_date"])
            if data.get("bill_period_end_date")
            else None
        )
        self.regular_payment_amount: float = float(data.get("regular_payment_amount", 0.0))
        self.regular_payment_date: datetime | None = (
            parse_iso_datetime(data["regular_payment_date"])
            if data.get("regular_payment_date")
            else None
        )
        self.has_rejected_direct_debit: bool = bool(data.get("has_rejected_direct_debit", False))
        self.payment_scheme_type: str = data.get("payment_scheme_type", "")
        self.has_retained_payment: bool = bool(data.get("has_retained_payment", False))
        self.retainment_date: datetime | None = (
            parse_iso_datetime(data["retainment_date"])
            if data.get("retainment_date")
            else None
        )
        self.retainment_amount: float = float(data.get("retainment_amount", 0.0))
        self.number_of_retained_payments: int = int(data.get("number_of_retained_payments", 0))
        self.has_pending_payment_plan_change: bool = bool(
            data.get("has_pending_payment_plan_change", False)
        )
        self.retained_payment_frequency: str = data.get("retained_payment_frequency", "")

    def to_dict(self) -> dict:
        """Returns the PaymentArrangement object data as a dictionary."""
        return {
            "payment_type": self.payment_type,
            "end_term_balance": self.end_term_balance,
            "payment_frequency": self.payment_frequency,
            "payment_day": self.payment_day,
            "payment_amount": self.payment_amount,
            "are_request_lines_open": self.are_request_lines_open,
            "payment_reminder": self.payment_reminder,
            "bill_period_end_date": (
                self.bill_period_end_date.isoformat() if self.bill_period_end_date else None
            ),
            "regular_payment_amount": self.regular_payment_amount,
            "regular_payment_date": (
                self.regular_payment_date.isoformat() if self.regular_payment_date else None
            ),
            "has_rejected_direct_debit": self.has_rejected_direct_debit,
            "payment_scheme_type": self.payment_scheme_type,
            "has_retained_payment": self.has_retained_payment,
            "retainment_date": (
                self.retainment_date.isoformat() if self.retainment_date else None
            ),
            "retainment_amount": self.retainment_amount,
            "number_of_retained_payments": self.number_of_retained_payments,
            "has_pending_payment_plan_change": self.has_pending_payment_plan_change,
            "retained_payment_frequency": self.retained_payment_frequency,
        }

    def __iter__(self):
        """Allows the object to be converted to a dictionary using dict()."""
        return iter(self.to_dict().items())


class BillingSummary:
    """Represents a billing summary."""

    def __init__(self, data: dict):
        """Initialise BillingSummary from a parsed dict."""
        self.account_balance: float = float(data.get("account_balance", 0.0))
        self.balance_due_date: datetime | None = (
            parse_iso_datetime(data["balance_due_date"]) if data.get("balance_due_date") else None
        )
        self.next_payment_amount: float = float(data.get("next_payment_amount", 0.0))
        self.next_payment_date: datetime | None = (
            parse_iso_datetime(data["next_payment_date"]) if data.get("next_payment_date") else None
        )
        self.next_bill_date: datetime | None = (
            parse_iso_datetime(data["next_bill_date"]) if data.get("next_bill_date") else None
        )
        self.balance_type: str = data.get("balance_type", "")
        self.last_payment_date: datetime | None = (
            parse_iso_datetime(data["last_payment_date"]) if data.get("last_payment_date") else None
        )
        self.last_payment_amount: float = float(data.get("last_payment_amount", 0.0))
        self.is_behind_with_payment: bool = bool(data.get("is_behind_with_payment", False))
        self.is_direct_debit_claim_in_progress: bool = bool(
            data.get("is_direct_debit_claim_in_progress", False)
        )
        arrangement_data = data.get("payment_arrangement")
        self.payment_arrangement: PaymentArrangement | None = (
            PaymentArrangement(arrangement_data) if arrangement_data else None
        )
        self.overdue_amount: float = float(data.get("overdue_amount", 0.0))
        self.has_quotation_payment_scheme: bool = bool(
            data.get("has_quotation_payment_scheme", False)
        )
        self.refund_amount: float = float(data.get("refund_amount", 0.0))
        self.move_out_refund_threshold_amount: float = float(
            data.get("move_out_refund_threshold_amount", 0.0)
        )
        self.second_payment_amount: float = float(data.get("second_payment_amount", 0.0))
        self.has_court_balance: bool = bool(data.get("has_court_balance", False))

    def to_dict(self) -> dict:
        """Returns the BillingSummary object data as a dictionary."""
        return {
            "account_balance": self.account_balance,
            "balance_due_date": (
                self.balance_due_date.isoformat() if self.balance_due_date else None
            ),
            "next_payment_amount": self.next_payment_amount,
            "next_payment_date": (
                self.next_payment_date.isoformat() if self.next_payment_date else None
            ),
            "next_bill_date": self.next_bill_date.isoformat() if self.next_bill_date else None,
            "balance_type": self.balance_type,
            "last_payment_date": (
                self.last_payment_date.isoformat() if self.last_payment_date else None
            ),
            "last_payment_amount": self.last_payment_amount,
            "is_behind_with_payment": self.is_behind_with_payment,
            "is_direct_debit_claim_in_progress": self.is_direct_debit_claim_in_progress,
            "payment_arrangement": (
                self.payment_arrangement.to_dict() if self.payment_arrangement else None
            ),
            "overdue_amount": self.overdue_amount,
            "has_quotation_payment_scheme": self.has_quotation_payment_scheme,
            "refund_amount": self.refund_amount,
            "move_out_refund_threshold_amount": self.move_out_refund_threshold_amount,
            "second_payment_amount": self.second_payment_amount,
            "has_court_balance": self.has_court_balance,
        }

    def __iter__(self):
        """Allows the object to be converted to a dictionary using dict()."""
        return iter(self.to_dict().items())
