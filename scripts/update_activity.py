#!/usr/bin/env python3
"""Render 60 days of GitHub's public contribution counts, without credentials."""

import argparse
from datetime import date, datetime, timedelta, timezone
from html import escape
from html.parser import HTMLParser
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

WINDOW_DAYS = 60
START = "<!-- ACTIVITY:START -->"
END = "<!-- ACTIVITY:END -->"


class CalendarParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.cells = {}
        self.labels = {}
        self.target = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "td" and "data-date" in attrs:
            self.cells[attrs["id"]] = (
                date.fromisoformat(attrs["data-date"]), int(attrs["data-level"])
            )
        if tag == "tool-tip":
            self.target = attrs.get("for")
            if self.target:
                self.labels[self.target] = ""

    def handle_data(self, data):
        if self.target:
            self.labels[self.target] += data

    def handle_endtag(self, tag):
        if tag == "tool-tip":
            self.target = None

    def counts(self):
        result = {}
        for key, (day, level) in self.cells.items():
            label = " ".join(self.labels.get(key, "").split())
            match = re.match(r"^(No|[\d,]+) contributions? on ", label)
            if not match or level not in range(5):
                raise ValueError(f"Unrecognized contribution data for {day}")
            count = 0 if match[1] == "No" else int(match[1].replace(",", ""))
            if (count == 0) != (level == 0):
                raise ValueError(f"Inconsistent contribution data for {day}")
            result[day] = (count, level)
        return result


def fetch_calendar(username, year):
    query = urlencode({"from": f"{year}-01-01", "to": f"{year}-12-31"})
    url = f"https://github.com/users/{username}/contributions?{query}"
    request = Request(url, headers={
        "User-Agent": "GitHub-Profile-Activity/1.0",
        "Accept-Language": "en-US,en;q=0.9",
    })
    for attempt in range(3):
        try:
            with urlopen(request, timeout=30) as response:
                parser = CalendarParser()
                parser.feed(response.read().decode("utf-8"))
                return parser.counts()
        except HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise
        except (URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(2 ** attempt)


def select_window(calendars, end):
    start = end - timedelta(days=WINDOW_DAYS - 1)
    days = [start + timedelta(days=i) for i in range(WINDOW_DAYS)]
    missing = [day.isoformat() for day in days if day not in calendars]
    if missing:
        raise ValueError(f"Incomplete calendar; missing {len(missing)} days")
    return [(day, *calendars[day]) for day in days]


def render_svg(days):
    start, end = days[0][0], days[-1][0]
    total = sum(count for _, count, _ in days)
    active = sum(count > 0 for _, count, _ in days)
    peak_day, peak, _ = max(days, key=lambda item: item[1])
    summary = f"{total:,} contributions across {active} active days"
    parts = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="840" height="270" viewBox="0 0 840 270" role="img" aria-labelledby="title desc">
<title id="title">Last {WINDOW_DAYS} days: {summary}</title>
<desc id="desc">{start:%d %b %Y} to {end:%d %b %Y}, UTC. Daily GitHub contribution counts, including publicly shared anonymized private activity.</desc>
<style>
text{{font-family:system-ui,-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;fill:#1f2328}}
.muted{{fill:#59636e}} .card{{fill:#f6f8fa;stroke:#d1d9e0}} .l0{{fill:#e5e9ed}}
.l1{{fill:#b5e3ce}} .l2{{fill:#6ac49f}} .l3{{fill:#269b70}} .l4{{fill:#08764f}}
@media(prefers-color-scheme:dark){{text{{fill:#e6edf3}} .muted{{fill:#9198a1}} .card{{fill:#161b22;stroke:#30363d}} .l0{{fill:#30363d}}}}
</style>
<rect class="card" x="0.5" y="0.5" width="839" height="269" rx="12"/>
<text x="28" y="38" font-size="22" font-weight="650">Last {WINDOW_DAYS} days</text>
<text class="muted" x="28" y="63" font-size="13">{start:%d %b} – {end:%d %b %Y} · UTC</text>
<text x="28" y="124" font-size="38" font-weight="650">{total:,}</text>
<text class="muted" x="28" y="147" font-size="14">contributions</text>
<text x="232" y="124" font-size="38" font-weight="650">{active}</text>
<text class="muted" x="232" y="147" font-size="14">active days</text>
<text class="muted" x="28" y="196" font-size="13">Busiest day: {peak:,} contributions · {peak_day:%d %b}</text>
<text class="muted" x="28" y="236" font-size="11">Updated {end:%d %b %Y} · Today's count may still grow</text>''']
    # Sunday-first columns, including empty cells outside the exact rolling window.
    origin = start - timedelta(days=(start.weekday() + 1) % 7)
    columns = (end - origin).days // 7 + 1
    grid_x = 486 + (14 - columns) * 11
    previous_month = None
    month_labels = {}
    for day, count, level in days:
        column, row = divmod((day - origin).days, 7)
        x, y = grid_x + column * 22, 71 + row * 22
        if day.month != previous_month:
            if month_labels and x - next(reversed(month_labels)) < 44:
                month_labels.popitem()
            month_labels[x] = day.strftime("%b")
            previous_month = day.month
        label = escape(f"{day.isoformat()}: {count:,} contributions")
        parts.append(f'<rect class="l{level}" x="{x}" y="{y}" width="17" height="17" rx="3"><title>{label}</title></rect>')
    for x, label in month_labels.items():
        parts.append(f'<text class="muted" x="{x}" y="53" font-size="11">{label}</text>')
    for row, label in [(1, "Mon"), (3, "Wed"), (5, "Fri")]:
        parts.append(f'<text class="muted" x="{grid_x - 35}" y="{84 + row * 22}" font-size="10">{label}</text>')
    parts.append('<text class="muted" x="594" y="245" font-size="10">Less</text>')
    for level in range(5):
        parts.append(f'<rect class="l{level}" x="{625 + level * 21}" y="233" width="16" height="16" rx="3"/>')
    parts.append('<text class="muted" x="736" y="245" font-size="10">More</text></svg>\n')
    return "\n".join(parts)


def update_readme(text, days):
    total = sum(count for _, count, _ in days)
    active = sum(count > 0 for _, count, _ in days)
    block = f'''{START}
## Last {WINDOW_DAYS} days

![{total:,} GitHub contributions across {active} active days over the last {WINDOW_DAYS} days](assets/activity-60-days.svg)

**Current focus:** [Warehouse design](https://github.com/karthikbala/aislewise-showcase) · [Contract intelligence](https://github.com/karthikbala/ace-contract-intelligence-showcase) · [Logistics and tracking](https://github.com/karthikbala/container-sourcing)

<sub>Updated daily from GitHub's public contribution calendar, including anonymized private counts you choose to share. Repository names and private content are not collected. Counts follow GitHub's contribution rules.</sub>
{END}'''
    if START in text or END in text:
        if text.count(START) != 1 or text.count(END) != 1 or text.index(START) > text.index(END):
            raise ValueError("Invalid activity markers")
        return text[:text.index(START)] + block + text[text.index(END) + len(END):]
    marker = "## Products I work on"
    if marker not in text:
        raise ValueError("Profile insertion point not found")
    return text.replace(marker, block + "\n\n" + marker, 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", default="karthikbala")
    parser.add_argument("--end-date", type=date.fromisoformat)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9-]+", args.username):
        raise ValueError("Invalid GitHub username")
    end = args.end_date or datetime.now(timezone.utc).date()
    start = end - timedelta(days=WINDOW_DAYS - 1)
    calendar = {}
    for year in range(start.year, end.year + 1):
        calendar.update(fetch_calendar(args.username, year))
    days = select_window(calendar, end)
    root = Path(__file__).resolve().parents[1]
    # Validate everything before touching the last successfully generated files.
    svg = render_svg(days)
    readme = update_readme((root / "README.md").read_text(), days)
    (root / "assets").mkdir(exist_ok=True)
    (root / "assets/activity-60-days.svg").write_text(svg)
    (root / "README.md").write_text(readme)
    print(f"{start} to {end}: {sum(d[1] for d in days):,} contributions, "
          f"{sum(d[1] > 0 for d in days)} active days")


if __name__ == "__main__":
    main()
