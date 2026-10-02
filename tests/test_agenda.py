from datetime import datetime, timezone

from jotbrief import agenda

ICS = """BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART:20260929T190000Z
DTEND:20260929T200000Z
SUMMARY:Alinhamento
ORGANIZER;CN=Ana Souza:mailto:ana@x.com
ATTENDEE;CN=Pedro Lima;PARTSTAT=ACCEPTED:mailto:pedro@x.com
ATTENDEE;CN=Fulano;PARTSTAT=DECLINED:mailto:fulano@x.com
ATTENDEE;PARTSTAT=NEEDS-ACTION:mailto:maria.clara@x.com
END:VEVENT
BEGIN:VEVENT
DTSTART:20260929T140000Z
DTEND:20260929T150000Z
SUMMARY:Outra
ATTENDEE;CN=Zé:mailto:ze@x.com
ATTENDEE;CN=Lu:mailto:lu@x.com
END:VEVENT
BEGIN:VEVENT
DTSTART;TZID=America/Sao_Paulo:20260901T160000
DTEND;TZID=America/Sao_Paulo:20260901T170000
RRULE:FREQ=WEEKLY;BYDAY=TU
SUMMARY:Semanal
ATTENDEE;CN=Rui:mailto:rui@x.com
ATTENDEE;CN=Bia:mailto:bia@x.com
END:VEVENT
END:VCALENDAR
"""


def utc(h, m=0, d=29):
    return datetime(2026, 9, d, h, m, tzinfo=timezone.utc)


def test_picks_event_by_time_and_skips_declined():
    got = agenda.attendees_for(ICS, utc(19, 2), 1800)
    assert got == ["Ana Souza", "Pedro Lima", "Maria Clara"]  # sem o "DECLINED"; e-mail vira nome


def test_no_event_no_names():
    assert agenda.attendees_for(ICS, utc(3), 600) == []


def test_weekly_recurrence_matches_later_week():
    # 29/09/2026 é terça; 16:00 em São Paulo = 19:00 UTC, mas a "Alinhamento" (19–20 UTC) também bate:
    # vence a de maior sobreposição/início mais próximo, então pegamos outra terça só com a semanal
    got = agenda.attendees_for(ICS, utc(19, 0, d=22), 1800)
    assert got == ["Rui", "Bia"]


def test_line_unfolding_and_single_attendee_ignored():
    text = "BEGIN:VEVENT\nDTSTART:20260929T190000Z\nATTENDEE;CN=So\n  Um:mailto:a@x.com\nEND:VEVENT\n"
    assert agenda.attendees_for(text, utc(19), 600) == []  # evento com 1 pessoa só não serve de sugestão
