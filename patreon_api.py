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

PATREON_FIELDS = [
    "member_id",
    "user_id",
    "full_name",
    "email",
    "discord_user_id",
    "discord_username",
    "patron_status",
    "tier_title",
    "tier_amount_cents",
    "currently_entitled_amount_cents",
    "will_pay_amount_cents",
    "last_charge_date",
    "last_charge_status",
    "next_charge_date",
    "pledge_relationship_start",
    "pledge_cadence",
    "is_gifted",
    "is_free_trial",
    "lifetime_support_cents",
    "campaign_lifetime_support_cents",
    "note",
    "user_url",
    "thumb_url",
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
            "fields[campaign]": "created_at,creation_name,currency,patron_count,published_at,summary,url",
            "include": "tiers",
            "fields[tier]": "amount_cents,title,published,patron_count",
        }
        payload = self._request_json("GET", f"{API_BASE}/campaigns", params=params)
        campaigns = []
        for item in payload.get("data", []):
            attrs = item.get("attributes", {})
            campaigns.append(
                {
                    "id": item.get("id", ""),
                    "creation_name": attrs.get("creation_name") or "",
                    "currency": attrs.get("currency") or "",
                    "patron_count": attrs.get("patron_count") or 0,
                    "summary": attrs.get("summary") or "",
                    "url": attrs.get("url") or "",
                }
            )
        return campaigns

    def get_members(self, campaign_id: str) -> list[dict[str, str]]:
        params = {
            "include": "currently_entitled_tiers,user",
            "fields[member]": ",".join(
                [
                    "full_name",
                    "email",
                    "patron_status",
                    "last_charge_date",
                    "last_charge_status",
                    "lifetime_support_cents",
                    "currently_entitled_amount_cents",
                    "campaign_lifetime_support_cents",
                    "pledge_relationship_start",
                    "next_charge_date",
                    "pledge_cadence",
                    "will_pay_amount_cents",
                    "is_gifted",
                    "is_free_trial",
                    "note",
                ]
            ),
            "fields[tier]": "amount_cents,title",
            "fields[user]": "full_name,email,social_connections,url,thumb_url",
            "page[count]": "1000",
        }
        url = f"{API_BASE}/campaigns/{campaign_id}/members"
        rows: list[dict[str, str]] = []
        while url:
            payload = self._request_json("GET", url, params=params if "?" not in url else None)
            included = index_included(payload.get("included", []))
            for item in payload.get("data", []):
                rows.append(member_to_row(item, included))
            next_url = payload.get("links", {}).get("next")
            if not next_url:
                next_url = payload.get("meta", {}).get("pagination", {}).get("links", {}).get("next")
            if not next_url:
                cursor = payload.get("meta", {}).get("pagination", {}).get("cursors", {}).get("next")
                if cursor:
                    params["page[cursor]"] = cursor
                    next_url = url
                else:
                    next_url = ""
            if next_url and next_url.startswith("/"):
                next_url = "https://www.patreon.com" + next_url
            url = next_url
            if next_url and next_url != f"{API_BASE}/campaigns/{campaign_id}/members":
                params = {}
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
    tier_refs = relationships.get("currently_entitled_tiers", {}).get("data", []) or []
    tiers = [included.get((ref.get("type", ""), ref.get("id", "")), {}) for ref in tier_refs]
    tier_titles = []
    tier_amounts = []
    for tier in tiers:
        tier_attrs = tier.get("attributes", {})
        if tier_attrs.get("title"):
            tier_titles.append(str(tier_attrs["title"]))
        if tier_attrs.get("amount_cents") is not None:
            tier_amounts.append(str(tier_attrs["amount_cents"]))
    user_ref = relationships.get("user", {}).get("data") or {}
    user = included.get((user_ref.get("type", ""), user_ref.get("id", "")), {})
    user_attrs = user.get("attributes", {})
    email = attrs.get("email") or user_attrs.get("email") or ""
    full_name = attrs.get("full_name") or user_attrs.get("full_name") or ""
    discord = extract_discord_connection(user_attrs.get("social_connections"))
    return {
        "member_id": str(item.get("id", "")),
        "user_id": str(user.get("id") or user_ref.get("id") or ""),
        "full_name": str(full_name or ""),
        "email": str(email or ""),
        "discord_user_id": discord["user_id"],
        "discord_username": discord["username"],
        "patron_status": str(attrs.get("patron_status") or ""),
        "tier_title": " / ".join(tier_titles),
        "tier_amount_cents": " / ".join(tier_amounts),
        "currently_entitled_amount_cents": cents_to_str(attrs.get("currently_entitled_amount_cents")),
        "will_pay_amount_cents": cents_to_str(attrs.get("will_pay_amount_cents")),
        "last_charge_date": str(attrs.get("last_charge_date") or ""),
        "last_charge_status": str(attrs.get("last_charge_status") or ""),
        "next_charge_date": str(attrs.get("next_charge_date") or ""),
        "pledge_relationship_start": str(attrs.get("pledge_relationship_start") or ""),
        "pledge_cadence": str(attrs.get("pledge_cadence") or ""),
        "is_gifted": bool_to_str(attrs.get("is_gifted")),
        "is_free_trial": bool_to_str(attrs.get("is_free_trial")),
        "lifetime_support_cents": cents_to_str(attrs.get("lifetime_support_cents")),
        "campaign_lifetime_support_cents": cents_to_str(attrs.get("campaign_lifetime_support_cents")),
        "note": str(attrs.get("note") or ""),
        "user_url": str(user_attrs.get("url") or ""),
        "thumb_url": str(user_attrs.get("thumb_url") or ""),
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
