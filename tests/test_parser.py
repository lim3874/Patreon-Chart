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


if __name__ == "__main__":
    unittest.main()
