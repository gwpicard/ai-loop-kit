# Masterplan

## Build path

Path: Build and run it
Why: An internal tool for one team of nine. Nothing it holds is irreplaceable,
nobody outside the company signs in, and the team can explain and operate it.
Sensitive areas: none
Accepted: none
Recheck when: someone outside the company needs to sign in; money moves through
it; it starts holding the only copy of anything; another team comes to depend
on it.
Last checked: 2026-05-04

## What it does, and for whom

Bramble tracks equipment loans for the events team. Nine people share about two
hundred items: cameras, microphones, lighting stands, cables. Before Bramble
they used a spreadsheet that two people edited at once and neither trusted.

Someone books an item for a date range, collects it, and returns it. The tool
answers one question well: what is free on the day I need it.

## Key terms

An **item** is one physical thing with one label. A **kit** is a named group of
items that usually travel together, but a kit is booked as its parts, so a
half-available kit is visible rather than hidden.

A **loan** is one item going out to one person for one date range.

## Who can see and do what

Everyone on the team sees everything and can book anything. Two people are
marked as stewards and can cancel someone else's loan and edit the item list.
There is no other distinction. Sign-in is the company's existing Google
account; nobody outside the company has an account.

## What data it holds, and where it comes from

The item list was typed in once from the old spreadsheet and is maintained by
hand. Loans are created in the tool. No customer data, no payment details, no
personal information beyond a staff name and work email.

One thing leaves: confirmed loans are published to the team's shared Google
Calendar, so people who live in their calendar see what is out. This is a
convenience and the tool is correct without it.

The old spreadsheet still exists, untouched, as a fallback.

## How it is used, step by step

Someone opens the calendar and picks a date range. They see what is free. They
book what they need and the item shows as out. When they collect it they mark
it collected, and when it comes back a steward marks it returned. Overdue loans
appear at the top of the steward's page.

## What correct looks like

An item can never be in two overlapping loans. This is the rule the tool exists
to enforce and the one that broke the spreadsheet.

A booking that would overlap is refused with a message naming the loan that
blocks it.

Availability shown for a date range matches what is actually free, counting a
loan as occupying every day from collection to return inclusive.

## What happens when it fails

If Bramble is unavailable the team falls back to the old spreadsheet and
reconciles afterwards; a lost afternoon of bookings is annoying and recoverable.
Priya owns recovery. Nothing about a failure is urgent enough to wake anyone.

## Out of scope

Bramble does not handle purchasing, depreciation, repairs, or anything to do
with cost. It does not notify anyone by email. It does not track consumables
such as batteries or tape, because counting them was never the problem.
