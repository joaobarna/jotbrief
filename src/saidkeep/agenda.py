"""Convidados da reunião a partir da agenda (feed iCal secreto do Google Agenda): sugestões de nome para as vozes."""
from __future__ import annotations

import re
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

try:  # o Windows não traz fusos; o Brasil não tem horário de verão desde 2019
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore[assignment]

_BR = timezone(timedelta(hours=-3))
_DAYS = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}


@dataclass
class Event:
    start: datetime
    end: datetime
    summary: str = ""
    attendees: list[str] = field(default_factory=list)
    rrule: dict[str, str] = field(default_factory=dict)
    exdates: set[datetime] = field(default_factory=set)


def fetch_ics(url: str, timeout: float = 10.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "saidkeep"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 - URL do próprio usuário
        return r.read().decode("utf-8", "replace")


def _unfold(text: str) -> list[str]:
    lines: list[str] = []
    for ln in text.replace("\r\n", "\n").split("\n"):
        if ln[:1] in (" ", "\t") and lines:
            lines[-1] += ln[1:]
        else:
            lines.append(ln)
    return lines


def _tz(name: str):
    if ZoneInfo is not None:
        try:
            return ZoneInfo(name)
        except Exception:  # noqa: BLE001
            pass
    return _BR if "Sao_Paulo" in name or "Brasilia" in name else None  # None = horário local da máquina


def _dt(value: str, params: dict[str, str]) -> datetime | None:
    v = value.strip()
    try:
        if v.endswith("Z"):
            return datetime.strptime(v, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        if "T" in v:
            d = datetime.strptime(v, "%Y%m%dT%H%M%S")
            tz = _tz(params["TZID"]) if "TZID" in params else None
            return d.replace(tzinfo=tz) if tz else d.astimezone()  # sem fuso: horário local
        return datetime.strptime(v, "%Y%m%d").astimezone()  # dia inteiro
    except ValueError:
        return None


def _prop(line: str) -> tuple[str, dict[str, str], str]:
    head, _, value = line.partition(":")
    name, *rest = head.split(";")
    params = {}
    for p in rest:
        k, _, v = p.partition("=")
        params[k.upper()] = v.strip('"')
    return name.upper(), params, value


def _person(params: dict[str, str], value: str) -> str:
    cn = params.get("CN", "").strip()
    if cn and "@" not in cn:
        return " ".join(cn.split())
    mail = value.lower().removeprefix("mailto:")
    local = mail.split("@")[0]
    return " ".join(w.capitalize() for w in re.split(r"[._\-]+", local) if w)


def parse_events(text: str) -> list[Event]:
    events: list[Event] = []
    cur: dict | None = None
    for ln in _unfold(text):
        if ln == "BEGIN:VEVENT":
            cur = {"att": [], "ex": set()}
        elif ln == "END:VEVENT" and cur is not None:
            if cur.get("start"):
                end = cur.get("end") or cur["start"] + timedelta(hours=1)
                events.append(Event(cur["start"], end, cur.get("summary", ""), cur["att"],
                                    cur.get("rrule", {}), cur["ex"]))
            cur = None
        elif cur is not None and ":" in ln:
            name, params, value = _prop(ln)
            if name == "DTSTART":
                cur["start"] = _dt(value, params)
            elif name == "DTEND":
                cur["end"] = _dt(value, params)
            elif name == "SUMMARY":
                cur["summary"] = value
            elif name == "RRULE":
                cur["rrule"] = dict(kv.split("=", 1) for kv in value.split(";") if "=" in kv)
            elif name == "EXDATE":
                cur["ex"] |= {d for v in value.split(",") if (d := _dt(v, params))}
            elif name in ("ATTENDEE", "ORGANIZER") and params.get("PARTSTAT") != "DECLINED":
                who = _person(params, value)
                if who and who not in cur["att"]:
                    cur["att"].append(who)
    return events


def occurrences(ev: Event, around: datetime, span: timedelta) -> list[tuple[datetime, datetime]]:
    """Ocorrências do evento que tocam [around - span, around + span] (suporta DAILY e WEEKLY simples)."""
    length = ev.end - ev.start
    lo, hi = around - span, around + span
    if not ev.rrule:
        return [(ev.start, ev.end)] if ev.start < hi and ev.end > lo else []
    freq = ev.rrule.get("FREQ")
    if freq not in ("DAILY", "WEEKLY"):
        return [(ev.start, ev.end)] if ev.start < hi and ev.end > lo else []
    step = int(ev.rrule.get("INTERVAL", 1))
    until = _dt(ev.rrule["UNTIL"], {}) if "UNTIL" in ev.rrule else None
    count = int(ev.rrule.get("COUNT", 0)) or None
    days = [_DAYS[d[-2:]] for d in ev.rrule.get("BYDAY", "").split(",") if d[-2:] in _DAYS] or [ev.start.weekday()]
    out: list[tuple[datetime, datetime]] = []
    n = 0
    day0 = ev.start.date()
    d = day0
    limit = (hi.date() - day0).days + 1
    for i in range(0, max(limit, 0) + 1):
        d = day0 + timedelta(days=i)
        if freq == "DAILY":
            ok = i % step == 0
        else:
            weeks = (d - (day0 - timedelta(days=day0.weekday()))).days // 7
            ok = weeks % step == 0 and d.weekday() in days
        if not ok:
            continue
        s = ev.start.replace(year=d.year, month=d.month, day=d.day)
        n += 1
        if count and n > count:
            break
        if until and s > until:
            break
        if s in ev.exdates:
            continue
        if s < hi and s + length > lo:
            out.append((s, s + length))
    return out


def attendees_for(text: str, start: datetime, duration_s: float = 1800.0) -> list[str]:
    """Convidados do evento que mais combina com a reunião (início da gravação `start`, horário local)."""
    if start.tzinfo is None:
        start = start.astimezone()
    end = start + timedelta(seconds=max(duration_s, 60))
    best: tuple[float, Event] | None = None
    for ev in parse_events(text):
        if not ev.attendees or len(ev.attendees) < 2:
            continue
        for s, e in occurrences(ev, start, timedelta(hours=1)):
            overlap = (min(e, end) - max(s, start)).total_seconds()
            gap = abs((s - start).total_seconds())
            if overlap <= 0 and gap > 900:
                continue
            score = overlap - gap  # sobreposição alta e início próximo
            if best is None or score > best[0]:
                best = (score, ev)
    return best[1].attendees if best else []
