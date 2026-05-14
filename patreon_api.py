from __future__ import annotations

import csv
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

API_BASE = "https://www.patreon.com/api/oauth2/v2"
TOKEN_URL = "https://www.patreon.com/api/oauth2/token"
USER_AGENT = "Patreon Member Exporter - Local Dashboard"

MEMBER_FIELDS = [
    "campaign_lifetime_support_cents",
    "currently_entitled_amount_cents",
    "email",
    "full_name",
    "is_follower",
    "is_free_trial",
    "is_gifted",
    "last_charge_date",
    "last_charge_status",
    "lifetime_support_cents",
    "next_charge_date",
    "note",
    "patron_status",
    "pledge_cadence",
    "pledge_relationship_start",
    "will_pay_amount_cents",
]

USER_FIELDS = [
    "about",
    "can_see_nsfw",
    "created",
    "email",
    "first_name",
    "full_name",
    "hide_pledges",
    "image_url",
    "is_creator",
    "is_email_verified",
    "last_name",
    "like_count",
    "social_connections",
    "thumb_url",
    "url",
    "vanity",
]

TIER_FIELDS = [
    "amount_cents",
    "created_at",
    "description",
    "discord_role_ids",
    "edited_at",
    "image_url",
    "patron_count",
    "post_count",
    "published",
    "published_at",
    "remaining",
    "requires_shipping",
    "title",
    "unpublished_at",
    "url",
    "user_limit",
]

CAMPAIGN_FIELDS = [
    "created_at",
    "creation_name",
    "currency",
    "discord_server_id",
    "google_analytics_id",
    "has_rss",
    "has_sent_rss_notify",
    "image_small_url",
    "image_url",
    "is_charged_immediately",
    "is_eligible_for_live",
    "is_monthly",
    "is_nsfw",
    "main_video_embed",
    "main_video_url",
    "name",
    "one_liner",
    "patron_count",
    "pay_per_name",
    "pledge_url",
    "published_at",
    "rss_artwork_url",
    "rss_feed_title",
    "show_earnings",
    "summary",
    "thanks_embed",
    "thanks_msg",
    "thanks_video_url",
    "url",
    "vanity",
]

PLEDGE_EVENT_FIELDS = [
    "amount_cents",
    "currency_code",
    "date",
    "payment_status",
    "pledge_payment_status",
    "tier_id",
    "tier_title",
    "type",
]

ADDRESS_FIELDS = [
    "addressee",
    "city",
    "country",
    "created_at",
    "line_1",
    "line_2",
    "phone_number",
    "postal_code",
    "state",
]

PATREON_FIELDS = [
    "member_id",
    "user_id",
    "campaign_id",
    "full_name",
    "email",
    "discord_user_id",
    "discord_username",
    "patron_status",
    "is_follower",
    "is_gifted",
    "is_free_trial",
    "tier_title",
    "tier_ids",
    "tier_amount_cents",
    "tier_discord_role_ids",
    "tier_created_at",
    "tier_description",
    "tier_edited_at",
    "tier_image_url",
    "tier_patron_count",
    "tier_post_count",
    "tier_published",
    "tier_published_at",
    "tier_remaining",
    "tier_requires_shipping",
    "tier_unpublished_at",
    "tier_url",
    "tier_user_limit",
    "currently_entitled_amount_cents",
    "will_pay_amount_cents",
    "last_charge_date",
    "last_charge_status",
    "next_charge_date",
    "pledge_relationship_start",
    "pledge_cadence",
    "lifetime_support_cents",
    "campaign_lifetime_support_cents",
    "note",
    "pledge_event_count",
    "first_pledge_event_date",
    "first_pledge_event_type",
    "last_pledge_event_date",
    "last_pledge_event_type",
    "last_pledge_event_amount_cents",
    "last_pledge_event_currency",
    "last_pledge_event_payment_status",
    "last_pledge_event_pledge_payment_status",
    "last_pledge_event_tier_id",
    "last_pledge_event_tier_title",
    "pledge_history_json",
    "user_about",
    "user_created",
    "user_first_name",
    "user_last_name",
    "user_full_name",
    "user_email",
    "user_hide_pledges",
    "user_image_url",
    "user_url",
    "user_vanity",
    "user_can_see_nsfw",
    "user_is_creator",
    "user_is_email_verified",
    "user_like_count",
    "thumb_url",
    "social_connections_json",
    "campaign_created_at",
    "campaign_creation_name",
    "campaign_currency",
    "campaign_discord_server_id",
    "campaign_google_analytics_id",
    "campaign_has_rss",
    "campaign_has_sent_rss_notify",
    "campaign_image_small_url",
    "campaign_image_url",
    "campaign_is_charged_immediately",
    "campaign_is_eligible_for_live",
    "campaign_is_monthly",
    "campaign_is_nsfw",
    "campaign_main_video_embed",
    "campaign_main_video_url",
    "campaign_name",
    "campaign_one_liner",
    "campaign_patron_count",
    "campaign_pay_per_name",
    "campaign_pledge_url",
    "campaign_published_at",
    "campaign_rss_artwork_url",
    "campaign_rss_feed_title",
    "campaign_show_earnings",
    "campaign_summary",
    "campaign_thanks_embed",
    "campaign_thanks_msg",
    "campaign_thanks_video_url",
    "campaign_url",
    "campaign_vanity",
    "address_id",
    "address_addressee",
    "address_city",
    "address_country",
    "address_created_at",
    "address_line_1",
    "address_line_2",
    "address_phone_number",
    "address_postal_code",
    "address_state",
]


@dataclass
class PatreonCredentials:
    client_id: str
    client_secret: str
    access_token: str
    refresh_token: str

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "PatreonCredentials":
        return cls(
            client_id=data.get("client_id", "").strip(),
            client_secret=data.get("client_secret", "").strip(),
            access_token=data.get("access_token", "").strip(),
            refresh_token=data.get("refresh_token", "").strip(),
        )

    def is_complete(self) -> bool:
        return all([self.client_id, self.client_secret, self.access_token, self.refresh_token])

    def as_dict(self) -> dict[str, str]:
        return {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
        }


class PatreonApiError(RuntimeError):
    pass


class PatreonClient:
    def __init__(self, credentials_path: Path) -> None:
        self.credentials_path = credentials_path
        self.credentials = load_credentials(credentials_path)
        if not self.credentials.is_complete():
            raise PatreonApiError("Patreon API credentials are incomplete.")

    def get_campaigns(self) -> list[dict[str, Any]]:
        params = {
            "fields[campaign]": ",".join(CAMPAIGN_FIELDS),
            "include": "tiers",
            "fields[tier]": ",".join(TIER_FIELDS),
        }
        payload = self._request_json("GET", f"{API_BASE}/campaigns", params=params)
        campaigns = []
        for item in payload.get("data", []):
            attrs = item.get("attributes", {})
            campaign = {"id": item.get("id", "")}
            campaign.update({field: attrs.get(field) for field in CAMPAIGN_FIELDS})
            campaigns.append(campaign)
        return campaigns

    def get_members(self, campaign_id: str) -> list[dict[str, str]]:
        params = {
            "include": "currently_entitled_tiers,user,campaign,pledge_history,address",
            "fields[member]": ",".join(MEMBER_FIELDS),
            "fields[tier]": ",".join(TIER_FIELDS),
            "fields[user]": ",".join(USER_FIELDS),
            "fields[campaign]": ",".join(CAMPAIGN_FIELDS),
            "fields[pledge-event]": ",".join(PLEDGE_EVENT_FIELDS),
            "fields[address]": ",".join(ADDRESS_FIELDS),
            "page[count]": "1000",
        }
        try:
            return self._get_members_with_params(campaign_id, params)
        except PatreonApiError as exc:
            if "address" not in params["include"]:
                raise
            # Address requires an additional OAuth scope. If the token does not
            # have it, keep the main member sync working and export the rest.
            fallback = dict(params)
            fallback["include"] = "currently_entitled_tiers,user,campaign,pledge_history"
            fallback.pop("fields[address]", None)
            try:
                return self._get_members_with_params(campaign_id, fallback)
            except PatreonApiError:
                raise exc

    def _get_members_with_params(self, campaign_id: str, params: dict[str, str]) -> list[dict[str, str]]:
        url = f"{API_BASE}/campaigns/{campaign_id}/members"
        rows: list[dict[str, str]] = []
        request_params = dict(params)
        while url:
            payload = self._request_json("GET", url, params=request_params if "?" not in url else None)
            included = index_included(payload.get("included", []))
            for item in payload.get("data", []):
                rows.append(member_to_row(item, included))
            next_url = payload.get("links", {}).get("next")
            if not next_url:
                next_url = payload.get("meta", {}).get("pagination", {}).get("links", {}).get("next")
            if not next_url:
                cursor = payload.get("meta", {}).get("pagination", {}).get("cursors", {}).get("next")
                if cursor:
                    request_params["page[cursor]"] = cursor
                    next_url = url
                else:
                    next_url = ""
            if next_url and next_url.startswith("/"):
                next_url = "https://www.patreon.com" + next_url
            url = next_url
            if next_url and next_url != f"{API_BASE}/campaigns/{campaign_id}/members":
                request_params = {}
        return rows

    def refresh_access_token(self) -> None:
        form = urllib.parse.urlencode(
            {
                "grant_type": "refresh_token",
                "refresh_token": self.credentials.refresh_token,
                "client_id": self.credentials.client_id,
                "client_secret": self.credentials.client_secret,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            TOKEN_URL,
            data=form,
            method="POST",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": USER_AGENT,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = read_error_body(exc)
            raise PatreonApiError(f"Patreon token refresh failed: HTTP {exc.code} {detail}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise PatreonApiError(f"Patreon token refresh failed: {exc}") from exc
        access_token = payload.get("access_token")
        refresh_token = payload.get("refresh_token")
        if not access_token or not refresh_token:
            raise PatreonApiError("Patreon token refresh did not return new tokens.")
        self.credentials.access_token = access_token
        self.credentials.refresh_token = refresh_token
        save_credentials(self.credentials_path, self.credentials)

    def _request_json(
        self,
        method: str,
        url: str,
        params: dict[str, str] | None = None,
        retry_refresh: bool = True,
    ) -> dict[str, Any]:
        if params:
            url = url + "?" + urllib.parse.urlencode(params)
        request = urllib.request.Request(
            url,
            method=method,
            headers={
                "Authorization": f"Bearer {self.credentials.access_token}",
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 401 and retry_refresh:
                self.refresh_access_token()
                return self._request_json(method, url, params=None, retry_refresh=False)
            detail = read_error_body(exc)
            raise PatreonApiError(f"Patreon API request failed: HTTP {exc.code} {detail}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise PatreonApiError(f"Patreon API request failed: {exc}") from exc


def load_credentials(path: Path) -> PatreonCredentials:
    if not path.exists():
        return PatreonCredentials("", "", "", "")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PatreonApiError(f"Invalid Patreon credentials JSON: {path}") from exc
    return PatreonCredentials.from_dict(data)


def save_credentials(path: Path, credentials: PatreonCredentials) -> None:
    path.write_text(
        json.dumps(credentials.as_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def index_included(included: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    return {(item.get("type", ""), item.get("id", "")): item for item in included}


def member_to_row(item: dict[str, Any], included: dict[tuple[str, str], dict[str, Any]]) -> dict[str, str]:
    attrs = item.get("attributes", {})
    relationships = item.get("relationships", {})

    tiers = related_many(relationships, "currently_entitled_tiers", included)
    tier_titles = joined_resource_values(tiers, "title")
    tier_amounts = joined_resource_values(tiers, "amount_cents", cents=True)
    tier_ids = " / ".join(str(tier.get("id", "")) for tier in tiers if tier.get("id"))
    tier_discord_role_ids = joined_resource_values(tiers, "discord_role_ids")

    user_ref = relationships.get("user", {}).get("data") or {}
    user = related_one(relationships, "user", included)
    user_attrs = user.get("attributes", {})
    email = attrs.get("email") or user_attrs.get("email") or ""
    full_name = attrs.get("full_name") or user_attrs.get("full_name") or ""
    discord = extract_discord_connection(user_attrs.get("social_connections"))
    campaign = related_one(relationships, "campaign", included)
    campaign_attrs = campaign.get("attributes", {})
    address = related_one(relationships, "address", included)
    address_attrs = address.get("attributes", {})
    pledge_events = related_many(relationships, "pledge_history", included)
    pledge_summary = summarize_pledge_events(pledge_events)

    return {
        "member_id": str(item.get("id", "")),
        "user_id": str(user.get("id") or user_ref.get("id") or ""),
        "campaign_id": str(campaign.get("id") or relationship_id(relationships, "campaign") or ""),
        "full_name": str(full_name or ""),
        "email": str(email or ""),
        "discord_user_id": discord["user_id"],
        "discord_username": discord["username"],
        "patron_status": str(attrs.get("patron_status") or ""),
        "is_follower": bool_to_str(attrs.get("is_follower")),
        "is_gifted": bool_to_str(attrs.get("is_gifted")),
        "is_free_trial": bool_to_str(attrs.get("is_free_trial")),
        "tier_title": tier_titles,
        "tier_ids": tier_ids,
        "tier_amount_cents": tier_amounts,
        "tier_discord_role_ids": tier_discord_role_ids,
        "tier_created_at": joined_resource_values(tiers, "created_at"),
        "tier_description": joined_resource_values(tiers, "description"),
        "tier_edited_at": joined_resource_values(tiers, "edited_at"),
        "tier_image_url": joined_resource_values(tiers, "image_url"),
        "tier_patron_count": joined_resource_values(tiers, "patron_count"),
        "tier_post_count": joined_resource_values(tiers, "post_count"),
        "tier_published": joined_resource_values(tiers, "published"),
        "tier_published_at": joined_resource_values(tiers, "published_at"),
        "tier_remaining": joined_resource_values(tiers, "remaining"),
        "tier_requires_shipping": joined_resource_values(tiers, "requires_shipping"),
        "tier_unpublished_at": joined_resource_values(tiers, "unpublished_at"),
        "tier_url": joined_resource_values(tiers, "url"),
        "tier_user_limit": joined_resource_values(tiers, "user_limit"),
        "currently_entitled_amount_cents": cents_to_str(attrs.get("currently_entitled_amount_cents")),
        "will_pay_amount_cents": cents_to_str(attrs.get("will_pay_amount_cents")),
        "last_charge_date": str(attrs.get("last_charge_date") or ""),
        "last_charge_status": str(attrs.get("last_charge_status") or ""),
        "next_charge_date": str(attrs.get("next_charge_date") or ""),
        "pledge_relationship_start": str(attrs.get("pledge_relationship_start") or ""),
        "pledge_cadence": str(attrs.get("pledge_cadence") or ""),
        "lifetime_support_cents": cents_to_str(attrs.get("lifetime_support_cents")),
        "campaign_lifetime_support_cents": cents_to_str(attrs.get("campaign_lifetime_support_cents")),
        "note": str(attrs.get("note") or ""),
        **pledge_summary,
        "user_about": str(user_attrs.get("about") or ""),
        "user_created": str(user_attrs.get("created") or ""),
        "user_first_name": str(user_attrs.get("first_name") or ""),
        "user_last_name": str(user_attrs.get("last_name") or ""),
        "user_full_name": str(user_attrs.get("full_name") or ""),
        "user_email": str(user_attrs.get("email") or ""),
        "user_hide_pledges": bool_to_str(user_attrs.get("hide_pledges")),
        "user_image_url": str(user_attrs.get("image_url") or ""),
        "user_url": str(user_attrs.get("url") or ""),
        "user_vanity": str(user_attrs.get("vanity") or ""),
        "user_can_see_nsfw": bool_to_str(user_attrs.get("can_see_nsfw")),
        "user_is_creator": bool_to_str(user_attrs.get("is_creator")),
        "user_is_email_verified": bool_to_str(user_attrs.get("is_email_verified")),
        "user_like_count": value_to_cell(user_attrs.get("like_count")),
        "thumb_url": str(user_attrs.get("thumb_url") or ""),
        "social_connections_json": json_compact(user_attrs.get("social_connections")),
        **prefixed_attrs("campaign", CAMPAIGN_FIELDS, campaign_attrs),
        "address_id": str(address.get("id") or relationship_id(relationships, "address") or ""),
        **prefixed_attrs("address", ADDRESS_FIELDS, address_attrs),
    }


def relationship_id(relationships: dict[str, Any], name: str) -> str:
    data = relationships.get(name, {}).get("data") or {}
    return str(data.get("id") or "") if isinstance(data, dict) else ""


def related_one(relationships: dict[str, Any], name: str, included: dict[tuple[str, str], dict[str, Any]]) -> dict[str, Any]:
    data = relationships.get(name, {}).get("data") or {}
    if not isinstance(data, dict):
        return {}
    return included.get((data.get("type", ""), data.get("id", "")), {})


def related_many(relationships: dict[str, Any], name: str, included: dict[tuple[str, str], dict[str, Any]]) -> list[dict[str, Any]]:
    data = relationships.get(name, {}).get("data") or []
    if not isinstance(data, list):
        return []
    return [included.get((ref.get("type", ""), ref.get("id", "")), {}) for ref in data if isinstance(ref, dict)]


def joined_resource_values(resources: list[dict[str, Any]], field: str, cents: bool = False) -> str:
    values = []
    for resource in resources:
        value = resource.get("attributes", {}).get(field)
        text = cents_to_str(value) if cents else value_to_cell(value)
        if text:
            values.append(text)
    return " / ".join(values)


def prefixed_attrs(prefix: str, fields: list[str], attrs: dict[str, Any]) -> dict[str, str]:
    return {f"{prefix}_{field}": value_to_cell(attrs.get(field)) for field in fields}


def summarize_pledge_events(events: list[dict[str, Any]]) -> dict[str, str]:
    event_rows = []
    for event in events:
        attrs = event.get("attributes", {})
        event_rows.append({"id": event.get("id", ""), **{field: attrs.get(field) for field in PLEDGE_EVENT_FIELDS}})
    event_rows.sort(key=lambda row: str(row.get("date") or ""))
    first = event_rows[0] if event_rows else {}
    last = event_rows[-1] if event_rows else {}
    return {
        "pledge_event_count": str(len(event_rows)),
        "first_pledge_event_date": value_to_cell(first.get("date")),
        "first_pledge_event_type": value_to_cell(first.get("type")),
        "last_pledge_event_date": value_to_cell(last.get("date")),
        "last_pledge_event_type": value_to_cell(last.get("type")),
        "last_pledge_event_amount_cents": cents_to_str(last.get("amount_cents")),
        "last_pledge_event_currency": value_to_cell(last.get("currency_code")),
        "last_pledge_event_payment_status": value_to_cell(last.get("payment_status")),
        "last_pledge_event_pledge_payment_status": value_to_cell(last.get("pledge_payment_status")),
        "last_pledge_event_tier_id": value_to_cell(last.get("tier_id")),
        "last_pledge_event_tier_title": value_to_cell(last.get("tier_title")),
        "pledge_history_json": json_compact(event_rows),
    }


def extract_discord_connection(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {"user_id": "", "username": ""}
    discord = value.get("discord")
    if not isinstance(discord, dict):
        return {"user_id": "", "username": str(discord or "")}
    user_id = discord.get("user_id") or discord.get("id") or discord.get("external_id") or ""
    username = (
        discord.get("username")
        or discord.get("name")
        or discord.get("display_name")
        or discord.get("user_name")
        or ""
    )
    return {"user_id": str(user_id or ""), "username": str(username or "")}


def value_to_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return bool_to_str(value)
    if isinstance(value, (list, tuple, set)):
        return " / ".join(value_to_cell(item) for item in value if value_to_cell(item))
    if isinstance(value, dict):
        return json_compact(value)
    return str(value)


def json_compact(value: Any) -> str:
    if value in (None, "", [], {}):
        return ""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def cents_to_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return f"{int(value) / 100:.2f}"
    except (TypeError, ValueError):
        return str(value)


def bool_to_str(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    return ""


def write_patreon_members_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=PATREON_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in PATREON_FIELDS})


def read_error_body(exc: urllib.error.HTTPError) -> str:
    try:
        return exc.read().decode("utf-8", errors="replace")[:1000]
    except Exception:
        return ""
