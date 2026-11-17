"""Email HTML for a v2 Main Street AI Brief issue.

``feed2_email(issue, ctx)`` is the post-cutover replacement for ``build.py``
``feed2``. ``ctx`` is a dict or object with the names already in scope there:
``FB``, ``REPLY``, ``plink``, ``walk_mail``, ``exhtml``, ``lead_tag``,
``hero_for``, and ``IMG``.

Wire-in (v2 issues only; leave ``feed2`` itself unchanged)::

    body = select_body(i, ctx, feed2) if is2(i) else feed1(i)

Issues dated before ``EMAIL_REFRESH_FROM`` stay on ``feed2`` so an existing
item's description stays byte-identical. Dates are ``YYYY-MM-DD`` and compare
in that lexical order.
"""

import html
import re
from datetime import datetime
from urllib.parse import urlparse

E = html.escape

# First issue date that uses the new body. Elon sets the final value.
# A far-future date is the rollback: rebuild, redeploy the preview feed.
EMAIL_REFRESH_FROM = "2026-10-27"

NAVY = "#14213D"
ORANGE = "#FF6B1A"
CREAM = "#FDF5E8"
INK = "#1B2433"
LINE = "#D9D2C3"
GREY = "#5A6273"
PROMPT_BG = "#F3F0E8"
SANS = "Arial,Helvetica,sans-serif"
MONO = "Consolas,'Courier New',Courier,monospace"

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Same date tail as srccard() in redesign.py.
_DATE = re.compile(
    r"\s*\(((?:effective )?(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)"
    r"[a-z]* \d{1,2}, \d{4}[^)]*)\)$"
)

_IMG_STYLE = "display:block;width:100%;max-width:600px;height:auto;border:0;border-radius:6px"


def _g(ctx, name):
    if isinstance(ctx, dict):
        return ctx[name]
    return getattr(ctx, name)


def dshort(d):
    """``Mon D, YYYY`` without relying on locale ``%b``."""
    day = datetime.strptime(d, "%Y-%m-%d")
    return f"{_MONTHS[day.month - 1]} {day.day}, {day.year}"


def kick_text(i):
    """Audience and issue date. Topic tags stay off this line (see NOTES.md)."""
    label = i.get("audience") or " · ".join(i.get("tags") or [])
    if label:
        return f"{label} · {dshort(i['date'])}"
    return dshort(i["date"])


def parse_source(url, source, pub=None, hl=None):
    """Publisher, headline, date, domain. Same split as ``srccard()``.

    ``pub`` and ``hl`` are honoured only when both are provided. Otherwise the
    source string is split, including overwriting a single explicit value,
    matching redesign.py.
    """
    text = source
    date = ""
    match = _DATE.search(text)
    if match:
        date = match.group(1)
        text = text[:match.start()]
    if pub is None or hl is None:
        found = [(text.find(token), token) for token in (", ", ": ") if token in text]
        if found:
            at, token = min(found)
            pub, hl = text[:at], text[at + len(token):]
        else:
            pub, _, hl = text.partition(" ")
    host = (urlparse(url).hostname or "").removeprefix("www.")
    return pub, hl, date, host


def uses_refresh(i, cutover=None):
    """True when this v2 issue should use ``feed2_email``."""
    start = EMAIL_REFRESH_FROM if cutover is None else cutover
    return "do_today" in i and i.get("date", "") >= start


def select_body(i, ctx, legacy_feed2):
    """Description HTML for one v2 issue. ``legacy_feed2`` is build.py ``feed2``."""
    if uses_refresh(i):
        return feed2_email(i, ctx)
    return legacy_feed2(i)


def _link(href, inner):
    return (
        f'<a href="{href}" style="color:{NAVY};text-decoration:underline">{inner}</a>'
    )


def _hero(page, i, ctx):
    folder, stem, _width, _height, alt = _g(ctx, "IMG")[
        _g(ctx, "hero_for")(i["slug"], _g(ctx, "lead_tag")(i), i.get("hero"))
    ]
    src = f'{_g(ctx, "FB")}assets/img/{folder}/{stem}-800.jpg'
    img = (
        f'<img src="{E(src)}" width="600" alt="{E(alt)}" style="{_IMG_STYLE}">'
    )
    return f'<a href="{E(page)}" style="text-decoration:none">{img}</a>', src


def _kicker(i):
    return (
        f'<p style="margin:14px 0 8px;font-family:{SANS};font-size:14px;font-weight:bold;'
        f'letter-spacing:1px;text-transform:uppercase;color:{ORANGE}">{E(kick_text(i))}</p>'
    )


def _opener(i):
    return (
        f'<p style="margin:0 0 16px;font-size:18px;line-height:1.45;color:{NAVY}">'
        f'<i>{E(i["opener"])}</i></p>'
    )


def restyle_example(fragment):
    """Turn ``exhtml(..., email=True)`` borders into the email table.

    Assumes the generator's email table shape: one ``<table>`` per pipe-row
    block, header cells as plain ``<th>``, body cells as plain ``<td>``.
    """
    # table-layout:fixed makes width="100%" win, so a phone wraps cells instead of
    # hiding the last column. The overflow div is only a fallback for a long token.
    table = (
        f'<table width="100%" border="1" cellpadding="6" cellspacing="0" '
        f'style="border-collapse:collapse;width:100%;table-layout:fixed;box-sizing:border-box;'
        f'border:1px solid {LINE}">'
    )
    fragment = re.sub(r"<table\b[^>]*>", table, fragment)
    th = (
        f'<th style="background:{NAVY};color:#ffffff;padding:6px;border:1px solid {LINE};'
        f'text-align:left;font-weight:bold;font-size:16px;overflow-wrap:break-word">'
    )
    td = (
        f'<td style="padding:6px;border:1px solid {LINE};text-align:left;'
        f'vertical-align:top;font-size:16px;overflow-wrap:break-word">'
    )
    fragment = fragment.replace("<th>", th).replace("<td>", td)
    return re.sub(
        r"(<table\b.*?</table>)",
        '<div style="overflow-x:auto;width:100%;max-width:100%">\\1</div>',
        fragment,
        flags=re.DOTALL,
    )


def _callout(do, ctx):
    steps = "".join(f'<li style="margin:0 0 8px">{E(step)}</li>' for step in do["steps"])
    prompt = E(do["prompt"]).replace("\n", "<br>")
    example = restyle_example(_g(ctx, "exhtml")(do["example"], email=True))
    inner = (
        f'<h3 style="margin:0 0 8px;font-family:{SANS};font-size:14px;font-weight:bold;'
        f'letter-spacing:1px;text-transform:uppercase;color:{ORANGE}">Do this today</h3>'
        f'<p style="margin:0 0 10px;font-size:20px;line-height:1.3;color:{NAVY}"><b>{E(do["task"])}</b></p>'
        f'<p style="margin:0 0 10px"><b>Setup:</b> {E(do["setup"])} · <b>Saves:</b> {E(do["saves"])}</p>'
        f'<ol style="margin:0 0 12px;padding-left:22px">{steps}</ol>'
        f'<p style="margin:12px 0 6px"><b>Copy-paste prompt:</b></p>'
        f'<blockquote style="margin:0 0 14px;padding:12px;border:0;background:{PROMPT_BG};'
        f'white-space:pre-wrap;overflow-wrap:anywhere;font-family:{MONO};font-size:16px;'
        f'line-height:1.45;color:{INK}">{prompt}</blockquote>'
        f'<p style="margin:0 0 12px"><b>Privacy:</b> {E(do["privacy"])}</p>'
        f'<p style="margin:0 0 6px"><b>Example output (illustrative, not real data):</b></p>'
        f"{example}"
    )
    return (
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="border-collapse:collapse;width:100%;box-sizing:border-box;'
        f'border-left:4px solid {ORANGE};background:{CREAM};margin:0 0 18px">'
        f'<tr><td bgcolor="{CREAM}" style="padding:16px 16px 8px 18px;background:{CREAM};'
        f'font-family:{SANS};font-size:16px;line-height:1.5;color:{INK}">{inner}</td></tr></table>'
    )


def _walk(fb, i):
    href = f"{fb}use-cases/{E(i['usecase'])}.html"
    return (
        f'<p style="margin:0 0 18px">{_link(href, "<b>Full walkthrough &rarr;</b>")} '
        f"(steps, tool note and watch-outs)</p>"
    )


def _tool(tool):
    inner = (
        f'<h3 style="margin:0 0 8px;font-family:{SANS};font-size:18px;line-height:1.3;color:{NAVY}">'
        f'TOOL PICK: {E(tool["name"])}</h3>'
        f'<p style="margin:0 0 8px">{E(tool["what"])}</p>'
        f'<p style="margin:0"><b>Price:</b> {E(tool["price"])} (checked {E(tool["checked"])} on '
        f'{_link(E(tool["price_url"]), "the vendor\'s pricing page")}). '
        f'<b>For:</b> {E(tool["for"])} <b>Skip it if:</b> {E(tool["skip_if"])} Not sponsored.</p>'
    )
    return (
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="border-collapse:collapse;width:100%;box-sizing:border-box;'
        f'border:1px solid {LINE};background:#ffffff;margin:0 0 18px">'
        f'<tr><td style="padding:14px 16px;font-family:{SANS};font-size:16px;line-height:1.5;color:{INK}">'
        f"{inner}</td></tr></table>"
    )


def _source_card(url, source, pub=None, hl=None):
    publisher, headline, date, host = parse_source(url, source, pub, hl)
    meta = f"{date} · {host} ↗" if date else f"{host} ↗"
    return (
        f'<div style="border:1px solid {LINE};border-left:3px solid {ORANGE};background:#ffffff;'
        f'padding:12px 14px;margin:10px 0">'
        f'<p style="margin:0 0 4px;font-size:14px"><b style="color:{NAVY}">{E(publisher)}</b></p>'
        f'<p style="margin:0 0 4px;font-size:16px">{_link(E(url), f"<u>{E(headline)}</u>")}</p>'
        f'<p style="margin:0;font-size:14px;color:{GREY}">{E(meta)}</p>'
        f"</div>"
    )


def _worth(i):
    items = []
    for entry in i["worth_knowing"]:
        card = _source_card(entry["url"], entry["source"], entry.get("pub"), entry.get("hl"))
        items.append(
            f'<li style="margin:0 0 18px">{E(entry["text"])}'
            f'<p style="margin:8px 0 0"><b>So what:</b> {E(entry["sowhat"])}</p>'
            f"{card}</li>"
        )
    return (
        f'<h3 style="margin:8px 0 10px;font-family:{SANS};font-size:18px;line-height:1.3;color:{NAVY}">'
        f"WORTH KNOWING</h3>"
        f'<ul style="margin:0 0 8px;padding-left:22px">{"".join(items)}</ul>'
    )


def _close(i, page, reply, ctx):
    blocks = []
    if reply:
        blocks.append(
            '<p style="margin:14px 0">Questions or a task you want covered? Email us at '
            f'{_link("mailto:" + E(reply), E(reply))}.</p>'
        )
    linked = _g(ctx, "plink")(i["close"]["product"], i["slug"], "email")
    if linked:
        product, url = linked
        blocks.append(
            f'<p style="margin:14px 0">{E(i["close"].get("line", ""))} '
            f'{_link(E(url), E(product["name"]) + " (" + E(product["price"]) + ")")}</p>'
        )
    blocks.append(
        '<p style="margin:14px 0 0">Know an owner who\'d use this? Forward it. '
        f'{_link(E(page), "Read this issue on the web")}.</p>'
    )
    return blocks


def _shell(inner):
    return (
        f'<div style="max-width:600px;box-sizing:border-box;padding:0 16px 8px;'
        f'font-family:{SANS};font-size:16px;line-height:1.5;color:{INK};overflow-wrap:break-word">'
        f"{inner}</div>"
    )


def feed2_email(i, ctx):
    """Return the email fragment for v2 issue ``i``. The hero link is first.

    No ``<h1>``: follow.it already prints the item title above this fragment.
    """
    page = f'{_g(ctx, "FB")}issues/{i["slug"]}.html'
    hero, _src = _hero(page, i, ctx)
    blocks = [_kicker(i), _opener(i), _callout(i["do_today"], ctx)]
    if _g(ctx, "walk_mail")(i):
        blocks.append(_walk(_g(ctx, "FB"), i))
    if i.get("tool_pick"):
        blocks.append(_tool(i["tool_pick"]))
    blocks.append(_worth(i))
    blocks.extend(_close(i, page, _g(ctx, "REPLY"), ctx))
    return hero + _shell("".join(blocks))
