from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

API_BASE = "https://discord.com/api/v10"
USER_AGENT = "Patreon Chart Discord Resolver"

DISCORD_FIELDS = [
    "discord_lookup_status",
    "discord_resolved_at",
    "discord_display_name",
    "discord_global_name",
    "discord_nick",
    "discord_role_ids",
    "discord_role_names",
    "discord_joined_at",
    "discord_premium_since",
    "discord_member_avatar",
    "discord_user_avatar",
    "discord_bot",
    "discord_system",
    "discord_member_json",
]


@dataclass
class DiscordCredentials:
    bot_token: str
    guild_id: str

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "DiscordCredentials":
        return cls(
            bot_token=data.get("bot_token", "").strip(),
            guild_id=data.get("guild_id", "").strip(),
        )

    def is_complete(self) -> bool:
        return bool(self.bot_token and self.guild_id)

    def as_dict(self) -> dict[str, str]:
        return {
            "bot_token": self.bot_token,
            "guild_id": self.guild_id,
        }


class DiscordApiError(RuntimeError):
    pass


class DiscordClient:
    def __init__(self, credentials_path: Path) -> None:
        self.credentials_path = credentials_path
        self.credentials = load_credentials(credentials_path)
        if not self.credentials.is_complete():
            raise DiscordApiError("Discord bot token and guild ID are incomplete.")

    def get_role_names(self) -> dict[str, str]:
        payload = self._request_json("GET", f"{API_BASE}/guilds/{self.credentials.guild_id}/roles")
        if not isinstance(payload, list):
            return {}
        return {
            str(role.get("id", "")): str(role.get("name", ""))
            for role in payload
            if isinstance(role, dict) and role.get("id")
        }

    def get_guild_member(self, user_id: str) -> dict[str, Any] | None:
        try:
            payload = self._request_json(
                "GET",
                f"{API_BASE}/guilds/{self.credentials.guild_id}/members/{user_id}",
            )
        except DiscordApiError as exc:
            if "HTTP 404" in str(exc):
                return None
            raise
        return payload if isinstance(payload, dict) else None

    def resolve_member(self, user_id: str, role_names: dict[str, str]) -> dict[str, str]:
        member = self.get_guild_member(user_id)
        if member is None:
            return {
                "discord_lookup_status": "not_in_server",
                "discord_resolved_at": now_iso(),
            }

        user = member.get("user") if isinstance(member.get("user"), dict) else {}
        roles = [str(role_id) for role_id in member.get("roles", []) if role_id]
        names = [role_names.get(role_id, "") for role_id in roles]
        names = [name for name in names if name and name != "@everyone"]
        username = str(user.get("username", "") or "")
        global_name = str(user.get("global_name", "") or "")
        nick = str(member.get("nick", "") or "")
        display_name = nick or global_name or username

        return {
            "discord_lookup_status": "found",
            "discord_resolved_at": now_iso(),
            "discord_username": username,
            "discord_display_name": display_name,
            "discord_global_name": global_name,
            "discord_nick": nick,
            "discord_role_ids": " / ".join(roles),
            "discord_role_names": " / ".join(names),
            "discord_joined_at": str(member.get("joined_at", "") or ""),
            "discord_premium_since": str(member.get("premium_since", "") or ""),
            "discord_member_avatar": str(member.get("avatar", "") or ""),
            "discord_user_avatar": str(user.get("avatar", "") or ""),
            "discord_bot": bool_to_text(user.get("bot")),
            "discord_system": bool_to_text(user.get("system")),
            "discord_member_json": json_compact(member),
        }

    def _request_json(self, method: str, url: str, *, retries: int = 5) -> Any:
        request = urllib.request.Request(
            url,
            method=method,
            headers={
                "Authorization": f"Bot {self.credentials.bot_token}",
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
            },
        )
        for attempt in range(retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                if exc.code == 429 and attempt < retries:
                    retry_after = parse_retry_after(detail, exc.headers.get("Retry-After"))
                    time.sleep(retry_after)
                    continue
                raise DiscordApiError(f"Discord API request failed: HTTP {exc.code} {detail}") from exc
            except urllib.error.URLError as exc:
                raise DiscordApiError(f"Discord API request failed: {exc}") from exc
        raise DiscordApiError("Discord API request failed after retrying.")


def enrich_rows_with_discord(
    rows: list[dict[str, str]],
    credentials_path: Path,
) -> tuple[list[dict[str, str]], dict[str, int]]:
    client = DiscordClient(credentials_path)
    role_names = client.get_role_names()
    cache: dict[str, dict[str, str]] = {}
    stats = {"checked": 0, "found": 0, "not_in_server": 0, "missing_id": 0}
    enriched: list[dict[str, str]] = []

    for row in rows:
        updated = dict(row)
        user_id = updated.get("discord_user_id", "").strip()
        if not user_id:
            stats["missing_id"] += 1
            enriched.append(updated)
            continue
        if user_id not in cache:
            cache[user_id] = client.resolve_member(user_id, role_names)
            stats["checked"] += 1
            status = cache[user_id].get("discord_lookup_status", "")
            if status == "found":
                stats["found"] += 1
            elif status == "not_in_server":
                stats["not_in_server"] += 1
        updated.update(cache[user_id])
        enriched.append(updated)

    return enriched, stats


def load_credentials(path: Path) -> DiscordCredentials:
    if not path.exists():
        return DiscordCredentials("", "")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DiscordApiError(f"Invalid Discord credentials JSON: {path}") from exc
    return DiscordCredentials.from_dict(data)


def save_credentials(path: Path, credentials: DiscordCredentials) -> None:
    path.write_text(
        json.dumps(credentials.as_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def bool_to_text(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return ""


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def parse_retry_after(detail: str, header_value: str | None) -> float:
    if header_value:
        try:
            return max(0.25, float(header_value))
        except ValueError:
            pass
    try:
        payload = json.loads(detail)
    except json.JSONDecodeError:
        return 1.0
    try:
        return max(0.25, float(payload.get("retry_after", 1.0)))
    except (TypeError, ValueError):
        return 1.0


def json_compact(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError):
        return str(value)
