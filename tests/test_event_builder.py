from datetime import datetime, timezone
from app.services.event_builder import EventBuilder
from app.db.session import SessionLocal
from app.db.models.email_raw import EmailRaw
from app.db.models.parsed_candidate import ParsedTransactionCandidate


# def test_event_builder_creates_spend_event():
#     session = SessionLocal()

#     email = EmailRaw(
#         gmail_message_id="test-msg-001",
#         internal_date=datetime(2026, 3, 2, 14, 0, tzinfo=timezone.utc),
#     )
#     session.add(email)
#     session.commit()

#     pc = ParsedTransactionCandidate(
#         email_id=email.id,
#         amount=10.50,
#         currency="SGD",
#         datetime_sgt=datetime(2026, 3, 2, 14, 0),
#         inferred_sender="PayLah",
#         inferred_receiver="VEGETARIAN PANCAKE",
#         debit_credit="spend",
#         type_info="spend",
#     )

#     session.add(pc)
#     session.commit()

#     builder = EventBuilder()
#     event = builder.process_candidate(pc.id)

#     assert event is not None
#     assert event.event_type == "Spend"
#     assert event.amount == 10.50
#     assert len(event.raw_email_ids) == 1

#     session.close()