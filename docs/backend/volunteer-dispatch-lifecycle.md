# Volunteer dispatch lifecycle

A dispatch notification is an offer until the volunteer accepts it.

## States

Volunteer states:

- `available`: eligible for matching
- `pending_response`: one offer is waiting for accept or decline
- `busy`: one accepted assignment is active
- `inactive`: not eligible for matching

Dispatch states:

- `sent`: offer sent, response pending
- `accepted`: volunteer accepted the assignment
- `declined`: volunteer declined the offer
- `done`: accepted assignment completed
- `cancelled`: assignment cancelled by dispatch

## Commands

While an offer is pending:

- `accept` or `/accept`: accept the offer
- `decline` or `/decline`: decline the offer
- `/cancel`: decline the offer
- natural phrases such as `I can come` and `I can't come` are recognized

After acceptance:

- `done` or `/done`: complete the assignment

A volunteer with a pending or accepted dispatch is excluded from new matching. A declined volunteer is skipped when the same incident is offered again. The next ranked available volunteer is tried instead.

When a volunteer accepts, the incident bot sends the original reporter a message naming the volunteer who accepted. The reporter is not told that a volunteer is responding before acceptance.