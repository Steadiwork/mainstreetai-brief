# Email refresh

Drop this module in beside `build.py`. Leave `feed2` unchanged. Build one ctx from the names already in scope (`FB`, `REPLY`, `plink`, `walk_mail`, `exhtml`, `lead_tag`, `hero_for`, `IMG`) and use the new body only on or after the cutover:

```python
from feed_email import select_body
body = select_body(i, ctx, feed2) if is2(i) else feed1(i)
```

`EMAIL_REFRESH_FROM` is `2026-10-27`. Elon sets the real date. A far-future date is the rollback: rebuild, redeploy the preview feed. Do not merge this folder to `main`. GitHub Pages would publish it, and the next weekday publish would rewrite it.

## Assumptions

- The kicker is the audience plus `dshort` (`Personal care · Oct 23, 2026`), which is the brief's example. The live issue page also inserts topic tags (`Personal care · Marketing · Oct 23, 2026`). `kick_text()` is the one place to add those tags back.
- Local previews put the issue title in `<title>` only. There is no `<h1>` in the fragment, because follow.it prints the item headline above the description. These screenshots do not show that headline.
- `exhtml(..., email=True)` still supplies the example rows. `restyle_example()` then sets the navy header, `#D9D2C3` borders, 6px padding, `width="100%"`, and an `overflow-x:auto` wrapper. It assumes plain `<th>` / `<td>` tags. `table-layout:fixed` keeps every column on screen at 375px.
- Source cards use the same split as `srccard()`. `pub` and `hl` are honored only when both are set. No images.
- Hero URL is `FB + "assets/img/<folder>/<stem>-800.jpg"` from `hero_for(slug, lead_tag(i), i.get("hero"))`.
- Close copy, the tool-pick sentence, and the walkthrough href match today's `feed2`. Anchor styles are new. The words and URLs are not.
- The three sample issues are dated before the cutover, so a real rebuild would not change their descriptions. `test_render.py` asserts that: legacy `feed2` output matches `feed.xml` in the repo, and the salon item matches `live-feed-item-newest.xml`. `email-refresh/feed.xml` is a preview of the new body in an RSS envelope. Do not copy it over the published feed. `title`, `link`, `guid`, and `pubDate` in that preview are unchanged.

## Not verified with follow.it

No message was sent and follow.it was not called. These are still open:

- Whether follow.it strips `style`, `<img>` attributes, or tables. Styled screenshots fit a 375px and 600px viewport with no page-level horizontal scroll. Stripping every `style` attribute leaves the headings, list, prompt, source-card lines, and a `border="1"` example table. The hero's required `width="600"` then lays the page out at 600px, so a 375px window scrolls sideways. See `preview-*-stripped-*.png`.
- Whether an `<img>` as the first element of the description shows on the free plan. There is no enclosure or `media:content`.
- Whether a description-only change can still make follow.it re-send a self-built feed item. The cutover avoids editing any old item. Title, link, guid, and pubDate are not touched.
- Image blocking. The alt text is the picture's alt from `IMG`. The stripped renders still read with the picture missing its styles, and the words do not depend on the picture.
- Gmail's ~102KB clip. New bodies are 9,648 bytes (salon), 10,065 bytes (change order), and 9,437 bytes (holiday hours).

Hero URLs returned HTTP 200 on 2026-10-25: `salon-haircut-800.jpg`, `trades-pipe-wrench-800.jpg`, `cafe-owner-portrait-800.jpg`.
