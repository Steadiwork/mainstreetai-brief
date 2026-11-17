"""Render the three sample v2 issues and check the email refresh.

Stdlib does the feed, the previews, and every acceptance check. Playwright is
optional and only takes the screenshots (skipped, exit 0, when it is absent).

Run from the repo root or from this directory:

    python3 email-refresh/test_render.py
"""

import html
import json
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))

import feed_email

E = html.escape
FB = "https://mainstreetaibrief.com/"
REPLY = "hello@mainstreetaibrief.com"
NAME = "Main Street AI Brief"
TAGLINE = (
    "Plain-English AI for small business owners: what works, what to avoid, "
    "and what it means for your shop."
)
AUDIENCES = [
    "All businesses",
    "Trades & Services",
    "Retail & Food",
    "Professional services",
    "Personal care",
]
PRODUCT = {
    "kit": {
        "name": "AI Readiness Checklist & Kit",
        "price": "$29",
        "url": "https://steadiwork.gumroad.com/l/ai-readiness-kit",
    },
    "library": {
        "name": "Small-Business Prompt Library",
        "price": "$19",
        "url": "https://steadiwork.gumroad.com/l/small-business-prompt-library",
    },
    "bundle": {
        "name": "Kit + Prompt Library bundle",
        "price": "$39",
        "url": "https://steadiwork.gumroad.com/l/ai-starter-bundle",
    },
}
SLUGS = (
    "salon-instagram-captions",
    "write-a-change-order",
    "holiday-hours-notice",
)
WIDTHS = (600, 375)
LIMIT = 25 * 1024

# IMG / HERO / hero_for copied from redesign.py (2026-10-23).
IMG = {
    "owner-checklist": ("illustrations", "owner-checklist", 1152, 864, "Illustrated shop owner holding a checklist"),
    "cat-trades": ("illustrations", "cat-trades", 1152, 864, "Illustrated trades storefront with tools and a hard hat"),
    "cat-retail": ("illustrations", "cat-retail", 1152, 864, "Illustrated clothing shop with a sale sign"),
    "cat-food": ("illustrations", "cat-food", 1152, 864, "Illustrated cafe counter with coffee and pastries"),
    "cat-office": ("illustrations", "cat-office", 1152, 864, "Illustrated office desk with a laptop and a plant"),
    "cat-personal-care": ("illustrations", "cat-personal-care", 1152, 864, "Illustration of a salon station with chair, mirror and styling tools"),
    "hero-main-street": ("illustrations", "hero-main-street", 1280, 720, "Illustrated main street of small shops"),
    "boutique": ("photos", "retail-boutique-counter", 1600, 1067, "Shopper standing at a boutique counter"),
    "accountant": ("photos", "office-accountant-calculator", 1600, 1066, "Person reviewing paperwork with a calculator"),
    "jars": ("photos", "shop-owner-laptop-jars", 1600, 1067, "Shop owner working on a laptop beside product jars"),
    "cafe-owner": ("photos", "cafe-owner-portrait", 1600, 900, "Cafe owner standing inside a coffee shop"),
    "laptop-orders": ("photos", "owner-laptop-orders", 1600, 1068, "Shop owner at a laptop beside shipping boxes"),
    "salon": ("photos", "salon-haircut", 1600, 1067, "Hair stylist cutting a client's hair"),
    "pipe-wrench": ("photos", "trades-pipe-wrench", 1600, 1060, "Gloved hands using a wrench on a pipe"),
    "florist": ("photos", "florist-laptop", 1600, 1067, "Florist working on a laptop in a flower shop"),
    "restaurant": ("photos", "restaurant-tables", 1600, 1066, "Person working among restaurant tables"),
    "contractor": ("photos", "contractor-measuring-wall", 1600, 1066, "Construction worker measuring a wall"),
    "panel": ("photos", "trades-electrician-panel", 1600, 1064, "Electrician inspecting a residential fuse panel"),
    "ladder": ("photos", "trades-electrician-ladder", 1600, 1067, "Electrician on a ladder holding cables"),
}
AUD_DEFAULT = {
    "All businesses": "owner-checklist",
    "Trades & Services": "cat-trades",
    "Retail & Food": "cat-retail",
    "Professional services": "cat-office",
    "Personal care": "cat-personal-care",
}
HERO = {
    "ai-confidence-gap": "laptop-orders",
    "ai-policy-gap": "accountant",
    "expertise-not-cost": "jars",
    "holiday-hours-notice": "cafe-owner",
    "salon-instagram-captions": "salon",
    "write-a-change-order": "pipe-wrench",
    "announce-a-price-increase": "ladder",
    "answer-google-reviews": "boutique",
    "answer-repeat-customer-questions": "restaurant",
    "chase-unpaid-invoices": "accountant",
    "cut-no-shows": "owner-checklist",
    "follow-up-on-quotes": "panel",
    "get-client-documents-on-time": "accountant",
    "job-notes-to-estimate": "contractor",
    "meeting-notes-to-client-recap": "cat-office",
    "rebook-lapsed-clients": "florist",
    "write-a-job-post": "jars",
    "write-product-descriptions": "laptop-orders",
}


def hero_for(slug, audience=None, explicit=None):
    key = explicit or HERO.get(slug)
    if key in IMG:
        return key
    return AUD_DEFAULT.get(audience, "owner-checklist")


def lead_tag(i):
    return next((t for t in i["tags"] if t in AUDIENCES), i["tags"][0] if i["tags"] else None)


def plink(key, slug, medium):
    product = PRODUCT[key]
    url = product["url"]
    if not url.startswith("https://"):
        return None
    joiner = "&" if "?" in url else "?"
    return product, url + joiner + f"utm_source=mainstreetaibrief&utm_medium={medium}&utm_campaign={slug}"


def exhtml(txt, email=False):
    """build.py exhtml, including the email table shape feed2 uses today."""
    out = []
    rows = []

    def flush():
        if not rows:
            return
        st = ' border="1" cellpadding="4" style="border-collapse:collapse"' if email else ' class="ex"'
        table = (
            f"<table{st}><tr>"
            + "".join(f"<th>{E(cell.strip())}</th>" for cell in rows[0])
            + "</tr>"
            + "".join(
                "<tr>" + "".join(f"<td>{E(cell.strip())}</td>" for cell in row) + "</tr>"
                for row in rows[1:]
            )
            + "</table>"
        )
        out.append(table if email else f'<div class="exw">{table}</div>')
        rows.clear()

    for line in txt.split("\n"):
        if " | " in line:
            rows.append(line.split(" | "))
            continue
        flush()
        if line.strip():
            out.append(f'<p style="margin:4px 0">{E(line)}</p>')
    flush()
    return "".join(out)


def walk_mail(i):
    slugs = {path.stem for path in (REPO / "use-cases").glob("*.html")}
    return bool(i.get("usecase")) and i["usecase"] in slugs


def legacy_feed2(i):
    """build.py feed2 as of 2026-10-25. Oracle for pre-cutover descriptions."""
    do = i["do_today"]
    tool = i.get("tool_pick")
    page = f"{FB}issues/{i['slug']}.html"
    body = (
        f'<p><i>{E(i["opener"])}</i></p>'
        f'<h3>DO THIS TODAY: {E(do["task"])}</h3>'
        f'<p><b>Setup:</b> {E(do["setup"])} · <b>Saves:</b> {E(do["saves"])}</p><ol>'
        + "".join(f"<li>{E(step)}</li>" for step in do["steps"])
        + "</ol>"
    )
    body += (
        f'<p><b>Copy-paste prompt:</b></p><blockquote>{E(do["prompt"]).replace(chr(10), "<br>")}</blockquote>'
        f'<p><b>Privacy:</b> {E(do["privacy"])}</p>'
    )
    body += f'<p><b>Example output (illustrative, not real data):</b></p>{exhtml(do["example"], email=True)}'
    if walk_mail(i):
        body += (
            f'<p><a href="{FB}use-cases/{E(i["usecase"])}.html"><b>Full walkthrough &rarr;</b></a> '
            f"(steps, tool note and watch-outs)</p>"
        )
    if tool:
        body += (
            f'<h3>TOOL PICK: {E(tool["name"])}</h3><p>{E(tool["what"])}</p>'
            f'<p><b>Price:</b> {E(tool["price"])} (checked {E(tool["checked"])} on '
            f'<a href="{E(tool["price_url"])}">the vendor\'s pricing page</a>). '
            f'<b>For:</b> {E(tool["for"])} <b>Skip it if:</b> {E(tool["skip_if"])} Not sponsored.</p>'
        )
    body += "<h3>WORTH KNOWING</h3><ul>" + "".join(
        f'<li>{E(entry["text"])} <b>So what:</b> {E(entry["sowhat"])} '
        f'(<a href="{E(entry["url"])}">{E(entry["source"])}</a>)</li>'
        for entry in i["worth_knowing"]
    ) + "</ul>"
    linked = plink(i["close"]["product"], i["slug"], "email")
    if REPLY:
        body += (
            f'<p>Questions or a task you want covered? Email us at '
            f'<a href="mailto:{E(REPLY)}">{E(REPLY)}</a>.</p>'
        )
    if linked:
        body += (
            f'<p>{E(i["close"].get("line", ""))} '
            f'<a href="{E(linked[1])}">{E(linked[0]["name"])} ({E(linked[0]["price"])})</a></p>'
        )
    body += f'<p>Know an owner who\'d use this? Forward it. <a href="{page}">Read this issue on the web</a>.</p>'
    return body


def make_ctx(hero_calls):
    def spy(slug, audience, explicit):
        hero_calls.append((slug, audience, explicit))
        return hero_for(slug, audience, explicit)

    return {
        "FB": FB,
        "REPLY": REPLY,
        "plink": plink,
        "walk_mail": walk_mail,
        "exhtml": exhtml,
        "lead_tag": lead_tag,
        "hero_for": spy,
        "IMG": IMG,
    }


def rd(day):
    return format_datetime(datetime.strptime(day, "%Y-%m-%d").replace(hour=10, tzinfo=timezone.utc))


def rss_document(issues, body_for):
    items = []
    for issue in sorted(issues, key=lambda row: row["date"], reverse=True):
        link = f"{FB}issues/{issue['slug']}.html"
        body = body_for(issue)
        items.append(
            f"<item><title>{E(issue['title'])}</title><link>{link}</link>"
            f'<guid isPermaLink="true">{link}</guid><pubDate>{rd(issue["date"])}</pubDate>'
            f"<description>{E(body)}</description></item>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>'
        f"<title>{E(NAME)}</title><link>{FB}</link><description>{E(TAGLINE)}</description>"
        f'<language>en-us</language><atom:link href="{FB}feed.xml" rel="self" type="application/rss+xml"/>'
        + "".join(items)
        + "</channel></rss>"
    )


def preview_page(fragment, title):
    """Standalone viewer. The issue title is the document title only, not an h1."""
    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{E(title)}</title></head>"
        f'<body style="margin:0;padding:0;background:#F7F5F0">{fragment}</body></html>'
    )


def strip_styles(fragment):
    return re.sub(r'\sstyle="[^"]*"', "", fragment)


def raw_items(xml_text):
    found = {}
    for item in re.findall(r"<item>(.*?)</item>", xml_text):
        def grab(tag, text=item):
            match = re.search(rf"<{tag}(?: [^>]*)?>(.*?)</{tag}>", text)
            if not match:
                raise AssertionError(f"missing {tag}")
            return match.group(1)

        link = grab("link")
        found[link] = {
            "title": grab("title"),
            "link": link,
            "guid": grab("guid"),
            "pubDate": grab("pubDate"),
            "description": grab("description"),
        }
    return found


def http_status(url):
    """Return an int status, or None when the network is unreachable."""
    headers = {"User-Agent": "mainstreet-email-refresh-test"}
    for method in ("HEAD", "GET"):
        request = urllib.request.Request(url, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return response.status
        except urllib.error.HTTPError as exc:
            if method == "HEAD" and exc.code in (403, 405, 501):
                continue
            return exc.code
        except (urllib.error.URLError, TimeoutError, OSError):
            return None
    return None


class Check:
    def __init__(self):
        self.fails = []

    def ok(self, cond, msg):
        print(("PASS  " if cond else "FAIL  ") + msg)
        if not cond:
            self.fails.append(msg)

    def done(self):
        print()
        if self.fails:
            print(f"{len(self.fails)} failed")
            for msg in self.fails:
                print(f" - {msg}")
            return 1
        print("All checks passed")
        return 0


def mismatch(left, right):
    limit = min(len(left), len(right))
    for index in range(limit):
        if left[index] != right[index]:
            return f"at {index}: {left[max(0, index - 30):index + 30]!r} != {right[max(0, index - 30):index + 30]!r}"
    return f"length {len(left)} != {len(right)}"


def load_issues():
    issues = json.loads((HERE / "sample-issues-v2.json").read_text(encoding="utf-8"))
    by_slug = {issue["slug"]: issue for issue in issues}
    missing = [slug for slug in SLUGS if slug not in by_slug]
    if missing or len(issues) != 3:
        raise SystemExit(f"sample issues must be exactly {SLUGS}")
    return [by_slug[slug] for slug in SLUGS]


def check_fragment(check, issue, fragment, src):
    slug = issue["slug"]
    check.ok(fragment.startswith("<a href="), f"{slug}: hero link is the first element")
    check.ok("<h1" not in fragment.lower(), f"{slug}: no h1 (follow.it prints the title)")
    check.ok(fragment.lower().count("<img") == 1, f"{slug}: exactly one img")
    check.ok(src.startswith("https://mainstreetaibrief.com/assets/img/"), f"{slug}: hero host {src}")
    check.ok(src.endswith("-800.jpg"), f"{slug}: 800px hero")
    check.ok('width="600"' in fragment and "alt=" in fragment, f"{slug}: width and alt present")
    for banned in ("<style", "<script", "<link", "<form", " class=", " id=", "srcset=", "loading=", "http://", "base64"):
        check.ok(banned not in fragment.lower(), f"{slug}: no {banned.strip()}")
    for match in re.finditer(r'\b(?:href|src)="([^"]*)"', fragment):
        url = match.group(1)
        allowed = url.startswith("https://") or url.startswith("mailto:")
        check.ok(allowed, f"{slug}: absolute url {url}")
    check.ok(len(fragment.encode("utf-8")) < LIMIT, f"{slug}: {len(fragment.encode('utf-8'))} bytes under 25KB")
    check.ok("Do this today" in fragment, f"{slug}: callout label")
    check.ok(E(issue["do_today"]["task"]) in fragment, f"{slug}: task text kept")
    check.ok("<b>So what:</b>" in fragment, f"{slug}: so-what line")
    check.ok("Copy-paste prompt:" in fragment, f"{slug}: prompt label")
    check.ok('width="100%"' in fragment and "overflow-x:auto" in fragment, f"{slug}: example table can scroll")
    stripped = strip_styles(fragment)
    check.ok("style=" not in stripped, f"{slug}: styles strip cleanly")
    for needle in (E(issue["do_today"]["task"]), "<b>So what:</b>", "<ol>", "<blockquote>", 'width="600"'):
        check.ok(needle in stripped, f"{slug}: stripped still has {needle[:40]}")
    return stripped


def screenshot_pages(check, pages):
    """Optional Playwright pass. ``pages`` is a list of (html_path, png_path, width)."""
    if sync_playwright is None:
        print("SKIP  screenshots: Playwright is not installed")
        return
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            channel="chrome",
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        try:
            for html_path, png_path, width in pages:
                page = browser.new_page(viewport={"width": width, "height": 900})
                page.goto(html_path.as_uri(), wait_until="networkidle", timeout=45000)
                metrics = page.evaluate(
                    "() => ({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth})"
                )
                page.screenshot(path=str(png_path), full_page=True)
                check.ok(png_path.stat().st_size > 0, f"screenshot {png_path.name}")
                if "stripped" in png_path.name:
                    # width="600" on the hero survives style removal, so the
                    # layout is 600px even in a 375px viewport.
                    check.ok(
                        metrics["sw"] <= 601,
                        f"{png_path.name}: stripped layout is {metrics['sw']}px (hero width is 600)",
                    )
                else:
                    check.ok(
                        metrics["sw"] <= metrics["cw"] + 1,
                        f"{png_path.name}: no page-level horizontal scroll ({metrics['sw']} <= {metrics['cw']})",
                    )
                page.close()
        finally:
            browser.close()


def main():
    check = Check()
    issues = load_issues()
    hero_calls = []
    ctx = make_ctx(hero_calls)
    bodies = {}
    stripped = {}
    for issue in issues:
        bodies[issue["slug"]] = feed_email.feed2_email(issue, ctx)
        src_match = re.search(r'<img src="([^"]+)"', bodies[issue["slug"]])
        src = src_match.group(1) if src_match else ""
        stripped[issue["slug"]] = check_fragment(check, issue, bodies[issue["slug"]], src)
        check.ok(
            hero_calls[-1] == (issue["slug"], lead_tag(issue), issue.get("hero")),
            f"{issue['slug']}: hero_for called with lead_tag and explicit hero",
        )
        status = http_status(src)
        if status is None:
            print(f"SKIP  {issue['slug']}: hero HEAD/GET offline ({src})")
        else:
            check.ok(status == 200, f"{issue['slug']}: hero HTTP {status} {src}")

    check.ok(
        "Personal care · Oct 23, 2026" in bodies["salon-instagram-captions"],
        "salon kicker is audience and date",
    )
    check.ok("Trades &amp; Services · Oct 20, 2026" in bodies["write-a-change-order"], "change-order kicker")
    check.ok("All businesses · Oct 19, 2026" in bodies["holiday-hours-notice"], "holiday kicker")
    check.ok("TOOL PICK:" in bodies["write-a-change-order"], "change-order tool pick kept")
    check.ok("TOOL PICK:" not in bodies["salon-instagram-captions"], "salon has no invented tool pick")
    check.ok(
        "Oct 22, 2026 · goldmansachs.com ↗" in bodies["salon-instagram-captions"],
        "Goldman source card meta",
    )
    check.ok(
        "Sept 29, 2026; updated Oct 8, 2026 · about.fb.com ↗" in bodies["salon-instagram-captions"],
        "Meta source card meta",
    )

    published = raw_items((REPO / "feed.xml").read_text(encoding="utf-8"))
    live = raw_items((HERE / "live-feed-item-newest.xml").read_text(encoding="utf-8"))
    salon_link = f"{FB}issues/salon-instagram-captions.html"
    check.ok(salon_link in live and salon_link in published, "live item and repo feed both have the salon link")
    if salon_link in live and salon_link in published:
        for field in ("title", "link", "guid", "pubDate", "description"):
            same = live[salon_link][field] == published[salon_link][field]
            check.ok(same, f"attachment matches repo feed {field}")
            if not same:
                print("   ", mismatch(live[salon_link][field], published[salon_link][field]))

    for issue in issues:
        link = f"{FB}issues/{issue['slug']}.html"
        legacy = legacy_feed2(issue)
        chosen = feed_email.select_body(issue, ctx, lambda row, legacy=legacy: legacy)
        raw_desc = published[link]["description"]
        same = E(legacy) == raw_desc
        check.ok(same, f"{issue['slug']}: legacy description matches published feed bytes")
        if not same:
            print("   ", mismatch(E(legacy), raw_desc))
        check.ok(not feed_email.uses_refresh(issue), f"{issue['slug']}: before cutover, refresh is off")
        check.ok(chosen == legacy, f"{issue['slug']}: select_body stays on feed2")
        check.ok(E(bodies[issue["slug"]]) != raw_desc, f"{issue['slug']}: new body differs from the live description")
        later = dict(issue)
        later["date"] = "2026-10-27"
        check.ok(feed_email.uses_refresh(later), f"{issue['slug']}: on the cutover date, refresh is on")

    new_feed = rss_document(issues, lambda issue: bodies[issue["slug"]])
    (HERE / "feed.xml").write_text(new_feed, encoding="utf-8")
    root = ET.fromstring(new_feed)
    channel = root.find("channel")
    parsed_items = channel.findall("item")
    check.ok(len(parsed_items) == 3, f"feed parses as XML with {len(parsed_items)} items")
    rendered = raw_items(new_feed)
    for issue in issues:
        link = f"{FB}issues/{issue['slug']}.html"
        for field in ("title", "link", "guid", "pubDate"):
            check.ok(
                rendered[link][field] == published[link][field],
                f"{issue['slug']}: feed {field} matches published item",
            )
        desc_text = next(item.findtext("description") for item in parsed_items if item.findtext("link") == link)
        check.ok(desc_text == bodies[issue["slug"]], f"{issue['slug']}: description round-trips through XML")
        check.ok(
            rendered[link]["guid"] == link and 'isPermaLink="true"' in new_feed,
            f"{issue['slug']}: guid is the issue URL",
        )

    pages = []
    for issue in issues:
        slug = issue["slug"]
        full = HERE / f"preview-{slug}.html"
        bare = HERE / f"preview-{slug}-stripped.html"
        full.write_text(preview_page(bodies[slug], issue["title"]), encoding="utf-8")
        bare.write_text(preview_page(stripped[slug], issue["title"] + " (styles stripped)"), encoding="utf-8")
        for width in WIDTHS:
            pages.append((full, HERE / f"preview-{slug}-{width}.png", width))
            pages.append((bare, HERE / f"preview-{slug}-stripped-{width}.png", width))
    screenshot_pages(check, pages)

    boilerplate = Path(feed_email.__file__).read_text(encoding="utf-8")
    check.ok("\u2014" not in boilerplate, "no em dash in feed_email.py")
    return check.done()


if __name__ == "__main__":
    sys.exit(main())
