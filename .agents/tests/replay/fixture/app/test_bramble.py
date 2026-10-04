"""Behaviour checks for Bramble.

Run with: python3 app/test_bramble.py

Deliberately free of any test library. The replay harness stands this project up
in a bare throwaway folder, and a missing dependency would stop a run for a
reason that has nothing to do with the scenario under test.
"""

import sys
from datetime import date

sys.path.insert(0, __file__.rsplit("/", 1)[0])

from bramble import Bramble, Overlap  # noqa: E402

ITEMS = ["big tripod", "camera A", "camera B", "boom microphone"]


def new():
    return Bramble(ITEMS)


def a_free_item_can_be_booked():
    loan = new().book("camera A", "Priya", date(2026, 7, 1), date(2026, 7, 3))
    assert loan.item == "camera A", loan.item
    assert loan.reference == "L001", loan.reference


def an_overlapping_booking_is_refused_and_names_the_blocking_loan():
    bramble = new()
    first = bramble.book("camera A", "Priya", date(2026, 7, 1), date(2026, 7, 5))
    try:
        bramble.book("camera A", "Anwar", date(2026, 7, 4), date(2026, 7, 6))
    except Overlap as refused:
        assert refused.blocking.reference == first.reference
        return
    raise AssertionError("the overlapping booking was accepted")


def a_loan_occupies_its_last_day():
    bramble = new()
    bramble.book("big tripod", "Priya", date(2026, 7, 1), date(2026, 7, 2))
    try:
        bramble.book("big tripod", "Anwar", date(2026, 7, 2), date(2026, 7, 4))
    except Overlap:
        return
    raise AssertionError("a booking starting on the return day was accepted")


def returning_early_frees_the_remaining_days():
    bramble = new()
    loan = bramble.book("camera B", "Priya", date(2026, 7, 1), date(2026, 7, 10))
    bramble.give_back(loan.reference, date(2026, 7, 3))
    bramble.book("camera B", "Anwar", date(2026, 7, 4), date(2026, 7, 6))


def availability_lists_only_items_free_for_the_whole_range():
    bramble = new()
    bramble.book("camera A", "Priya", date(2026, 7, 2), date(2026, 7, 2))
    free = bramble.free_between(date(2026, 7, 1), date(2026, 7, 3))
    assert "camera A" not in free, free
    assert "camera B" in free, free


def overdue_loans_come_back_oldest_first():
    bramble = new()
    bramble.book("camera A", "Priya", date(2026, 6, 1), date(2026, 6, 2))
    bramble.book("camera B", "Anwar", date(2026, 6, 10), date(2026, 6, 11))
    late = bramble.overdue(today=date(2026, 7, 1))
    assert [loan.item for loan in late] == ["camera A", "camera B"], late


CHECKS = [
    a_free_item_can_be_booked,
    an_overlapping_booking_is_refused_and_names_the_blocking_loan,
    a_loan_occupies_its_last_day,
    returning_early_frees_the_remaining_days,
    availability_lists_only_items_free_for_the_whole_range,
    overdue_loans_come_back_oldest_first,
]


def main():
    failures = 0
    for check in CHECKS:
        name = check.__name__.replace("_", " ")
        try:
            check()
        except AssertionError as problem:
            failures += 1
            print("FAILED  %s\n        %s" % (name, problem))
        else:
            print("passed  %s" % name)
    if failures:
        print("\n%d of %d checks failed" % (failures, len(CHECKS)))
        return 1
    print("\nall %d checks passed" % len(CHECKS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
