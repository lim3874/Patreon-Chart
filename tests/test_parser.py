import datetime as dt
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from export_patreon_members import (  # noqa: E402
    DEFAULT_CONFIG,
    RateProvider,
    SourceMessage,
    parse_member_record,
)
from patreon_api import extract_discord_connection, member_to_row  # noqa: E402


class PatreonParserTests(unittest.TestCase):
    def setUp(self):
        self.rate_provider = RateProvider(
            cache_path=ROOT / ".cache" / "test-rates.json",
            fallback_rates={},
            exchange_mode="off",
        )

    def parse(self, subject, text):
        message = SourceMessage(
            gmail_id="gmail-1",
            message_id="<msg-1@example.com>",
            subject=subject,
            sender="Patreon <no-reply@info.patreon.com>",
            received_at=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc),
            text=text,
        )
        return parse_member_record(message, DEFAULT_CONFIG, self.rate_provider, set())

    def test_korean_cad_join_maps_to_tier_2(self):
        record = self.parse(
            "새로운 CA$7.50 회원! DykRash님이 새로 가입했습니다",
            "DykRash님이 CA$7.50 회원으로 가입했습니다! DykRash a_armstrong1986@example.com",
        )
        self.assertIsNotNone(record)
        self.assertEqual(record.tier, 2)
        self.assertEqual(record.money.currency, "CAD")
        self.assertEqual(record.member_name, "DykRash")
        self.assertEqual(record.member_email, "a_armstrong1986@example.com")

    def test_korean_eur_join_maps_to_tier_2(self):
        record = self.parse(
            "새로운 €4.50 회원! Sen Bilstring님이 새로 가입했습니다",
            "Sen Bilstring님이 €4.50 회원으로 가입했습니다! valorantsmoerf@example.com",
        )
        self.assertIsNotNone(record)
        self.assertEqual(record.tier, 2)
        self.assertEqual(record.money.currency, "EUR")
        self.assertEqual(record.member_name, "Sen Bilstring")

    def test_dm_message_is_ignored(self):
        record = self.parse(
            "epi487님이 메시지를 보냈습니다",
            "epi487님이 보낸 메시지: hello",
        )
        self.assertIsNone(record)

    def test_payout_message_is_ignored(self):
        record = self.parse(
            "Patreon에서 US$745.37의 금액을 지급해드렸습니다!",
            "곧 출금이 가능해집니다!",
        )
        self.assertIsNone(record)

    def test_discord_social_connection_is_extracted(self):
        discord = extract_discord_connection(
            {
                "discord": {
                    "user_id": "1234567890",
                    "username": "membername",
                }
            }
        )
        self.assertEqual(discord["user_id"], "1234567890")
        self.assertEqual(discord["username"], "membername")

    def test_patreon_member_row_includes_extended_fields(self):
        member = {
            "id": "member-1",
            "attributes": {
                "full_name": "Member Name",
                "email": "member@example.com",
                "patron_status": "active_patron",
                "currently_entitled_amount_cents": 499,
                "is_gifted": True,
                "is_free_trial": False,
                "is_follower": False,
            },
            "relationships": {
                "user": {"data": {"type": "user", "id": "user-1"}},
                "campaign": {"data": {"type": "campaign", "id": "campaign-1"}},
                "currently_entitled_tiers": {"data": [{"type": "tier", "id": "tier-1"}]},
                "pledge_history": {"data": [{"type": "pledge-event", "id": "event-1"}]},
            },
        }
        included = {
            ("user", "user-1"): {
                "id": "user-1",
                "attributes": {
                    "social_connections": {"discord": {"user_id": "111"}},
                    "url": "https://patreon.com/user",
                    "created": "2026-01-01T00:00:00+00:00",
                },
            },
            ("campaign", "campaign-1"): {
                "id": "campaign-1",
                "attributes": {"discord_server_id": "222", "currency": "USD"},
            },
            ("tier", "tier-1"): {
                "id": "tier-1",
                "attributes": {
                    "title": "Tier 2",
                    "amount_cents": 499,
                    "discord_role_ids": ["333"],
                },
            },
            ("pledge-event", "event-1"): {
                "id": "event-1",
                "attributes": {
                    "date": "2026-01-02T00:00:00+00:00",
                    "type": "pledge_start",
                    "payment_status": "Paid",
                },
            },
        }
        row = member_to_row(member, included)
        self.assertEqual(row["discord_user_id"], "111")
        self.assertEqual(row["campaign_discord_server_id"], "222")
        self.assertEqual(row["tier_discord_role_ids"], "333")
        self.assertEqual(row["pledge_event_count"], "1")
        self.assertEqual(row["last_pledge_event_type"], "pledge_start")


if __name__ == "__main__":
    unittest.main()
