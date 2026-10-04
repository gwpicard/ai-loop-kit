"""Bramble: equipment loans for the events team.

Small on purpose. The replay harness needs a project that has something real in
it, so that a scenario about fixing a bug or adding a feature has code to act
on. Without this the kit correctly says there is nothing here to run, and the
run proves nothing about the scenario under test.
"""

from datetime import date


class Overlap(Exception):
    """Raised when a booking would put one item in two loans at once."""

    def __init__(self, blocking):
        self.blocking = blocking
        super().__init__(
            "item %s is already out on loan %s from %s to %s"
            % (blocking.item, blocking.reference, blocking.starts, blocking.ends)
        )


class Loan:
    def __init__(self, reference, item, borrower, starts, ends):
        if ends < starts:
            raise ValueError("a loan cannot end before it starts")
        self.reference = reference
        self.item = item
        self.borrower = borrower
        self.starts = starts
        self.ends = ends
        self.returned_on = None

    def covers(self, day):
        """A loan occupies every day from collection to return, inclusive."""
        last = self.returned_on or self.ends
        return self.starts <= day <= last

    def clashes_with(self, starts, ends):
        last = self.returned_on or self.ends
        return starts <= last and ends >= self.starts


class Bramble:
    def __init__(self, items):
        self.items = list(items)
        self.loans = []
        self._next = 1

    def book(self, item, borrower, starts, ends):
        if item not in self.items:
            raise ValueError("no such item: %s" % item)
        for loan in self.loans:
            if loan.item == item and loan.clashes_with(starts, ends):
                raise Overlap(loan)
        loan = Loan("L%03d" % self._next, item, borrower, starts, ends)
        self._next += 1
        self.loans.append(loan)
        return loan

    def give_back(self, reference, on):
        for loan in self.loans:
            if loan.reference == reference:
                loan.returned_on = on
                return loan
        raise ValueError("no such loan: %s" % reference)

    def free_between(self, starts, ends):
        """Items free for every day of the range."""
        taken = {
            loan.item
            for loan in self.loans
            if loan.clashes_with(starts, ends)
        }
        return [item for item in self.items if item not in taken]

    def overdue(self, today=None):
        today = today or date.today()
        late = [
            loan
            for loan in self.loans
            if loan.returned_on is None and loan.ends < today
        ]
        return sorted(late, key=lambda loan: loan.ends)
