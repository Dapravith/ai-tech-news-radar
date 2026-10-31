# Khmer visual poster quality and editorial release gate

**Status: PUBLICATION ON HOLD until technical QA AND editorial review pass.**

The user's October 31, 2026 private Cambodia news poster contained malformed Khmer
phrasing and square missing-glyph characters. GitHub Actions previously checked
the PNG size and the presence of Khmer script, but not mixed-script glyph support,
Khmer grammar, or source-bound editorial approval.

## Root causes and corrective controls

| Evidence / risk | Cause | Fix |
| --- | --- | --- |
| `□□□□` in mixed-language headlines | The old poster picked one Khmer font for the *entire* line, including foreign-script characters and Latin names | Split Khmer/Latin runs, use the correct Noto font for each run, inspect font CMAP with fonttools, and fail on unsupported code points |
| Odd Khmer headline wording | AI translation validation only checked Khmer presence and added numbers; natural language quality was never independently validated | AI is a **drafting assistant only**. Every public headline AND short Khmer summary must be reviewed and explicitly approved by a human |
| Too-long or broken line wraps | Greedy word splitting could separate Khmer coeng/consonant clusters or overflow a card | Keep Khmer clusters together, measure with the actual script font, wrap within 790 px and truncate safely |
| Green CI despite unreadable image | Tests asserted image size and not content quality | Add a mixed-script image fixture, glyph coverage checks, invalid-square fixtures and a strict per-story approval test |
| Existing production toggle may be enabled | A global switch cannot establish approval for new news every day | Additional opt-in repository variable `VISUAL_PUBLICATION_REVIEWED` defaults OFF; code independently requires exact per-story, per-slot review manifest |

## Review workflow before any public Telegram post

1. Keep Actions repository variable `VISUAL_PUBLICATION_REVIEWED` **unset** (or `false`).
   Existing `VISUAL_NEWS_ENABLED` does not override this hold.
2. From `Khmer Visual News - Cambodia Global Tech Gadget`, manually run an
   edition with `dry_run=true`. **Do not send directly to public**.
3. Download `visual-news-<edition>` artifact. It contains:
   - `<edition>-latest.png`: generated poster to view at 100% on a phone
   - `<edition>-latest.html`: source-linked report
   - `<edition>-review-request.json`: **proposed** Khmer text and precise source
     identifiers. This is *not* an approval.
4. Verify each article at its original publisher. For Google News indexed links,
   verify the original publication separately and retain the indexed attribution.
   Verify dates, people, geography, quote/context, money amounts and whether the
   article is reporting, analysis or rumor. Do **not** apply a generic
   `✅ បានបញ្ជាក់` badge.
5. Proofread Khmer grammar and meaning manually, remove mistranslated words,
   and approve concise titles and summaries. Preserve specific claims only when
   supported by the actual source. Each title and summary must have Khmer
   language content and no placeholder boxes.
6. Commit reviewed values to `config/visual_editorial_approvals.json` through
   a protected pull request and obtain a human code/editorial review.
   Each slot records `reviewed_by`, timezone-aware `reviewed_at` and the
   **exact ordered story IDs, URLs, source headlines, publication timestamps,
   final Khmer headlines and final Khmer summaries**.
7. Preview the poster again, read the Telegram private TEST caption and verify
   it looks right on both Android/iOS. The private test is always labeled TEST.
8. Set Actions repository variable `VISUAL_PUBLICATION_REVIEWED=true` only
   after this process works reliably. The per-story manifest gate still blocks
   every new, unreviewed set and any changes to a previously approved source.

The repository's initial approval manifest is deliberately empty:
```json
{
  "slots": {}
}
```
This results in **zero public new visual posts** until specific current stories
are approved. Old text-only news channels are not affected.

### Example approval format (fictional IDs, NEVER approve as-is)

```json
{
  "slots": {
    "2026-10-31:cambodia:morning": {
      "edition": "cambodia",
      "reviewed_by": "Human newsroom reviewer",
      "reviewed_at": "2026-10-31T08:30:00+07:00",
      "stories": [
        {
          "id": "EXAMPLE_NOT_A_REAL_STORY",
          "source_title": "Exact source headline",
          "source_url": "https://news.google.com/rss/articles/example",
          "source_published_at": "2026-10-31T00:00:00+00:00",
          "khmer_title": "សេចក្ដីប្រកាសថ្មីសម្រាប់ការអភិវឌ្ឍបច្ចេកវិទ្យា",
          "khmer_summary": "អត្ថបទនេះជាសេចក្ដីសង្ខេបដែលត្រូវផ្ទៀងផ្ទាត់ជាមួយប្រភពដើម។"
        }
      ]
    }
  }
}
```

Entries must match all selected stories, including **order**; if newer news
changes the selection between review and scheduled publication, the job fails
closed and must not publish the old approval. An operator may choose to skip
that period rather than rushing an inaccurate story.

## Technical verification

```bash
python3 -m unittest discover -s tests -v

# On the Ubuntu CI runner / an equivalent Linux host:
sudo apt-get install fonts-noto-core
python3 -m pip install -r requirements-visual.txt
python3 -m scripts.check_visual_poster_qa
python3 -m scripts.visual_fixture_preview
python3 visual_news.py --edition cambodia --dry-run
```

Only the poster preview jobs require Pillow, fonttools and installed fonts.
Traditional text-only workflows continue using their own simple dependencies.

**Limitation:** Glyph coverage and Unicode validation cannot prove that a
sentence is idiomatic Khmer, or that an article's claims are correct. Human
copy review is a hard release gate. Also, Telegram photo acceptance and Git
state persistence are not atomic, so incident handlers must still reconcile
ambiguous sends before retries.

The workflow has no feature that autonomously makes a human editorial decision.
Do not ask Hermes or another agent to bypass source approval.
