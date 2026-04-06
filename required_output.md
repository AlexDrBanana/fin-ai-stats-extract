**AI Mention Detection, Attitude Classification, Initiator Attribution, and Confidence Classification**

Five stages applied to each earnings call transcript. Full methodology is encoded in the LLM instructions within `extract.toml`.

In `extract.toml`, these outputs are configured as a flat `[output].format` list. Each field has a name and a freeform description that is passed directly into the LLM instructions.

**Stage 1 — AI Mention Detection**

- ai_mentioned: "yes" / "no" — whether at least one core AI keyword appears
- keyword_hit_count: total keyword matches (core + contextual when applicable, 0 when no)
- top_sentences: up to 3 most keyword-dense sentences joined by " | ", or null

**Stage 2 — Attitude Classification**

- ai_attitude: "excited" / "concerned" / "neutral" / "n/a"

**Stage 3 — Initiator Attribution**

- ai_initiator: "management" / "analyst" / "both" / "unclear" / "n/a"

**Stage 4 — Confidence Classification**

- confidence_label: "hopeful" / "confident" / "transformational" / "authoritative" / "n/a"
- hedge_score: count of AI sentences with future/conditional language
- exec_score: count of AI sentences with execution/delivery language
- quant_score: count of AI sentences with quantitative patterns
- strat_score: count of AI sentences with market-expansion language

**Note:** The tool's metadata columns (`event_id`, `company_name`, `quarter`, `date`, `headline`, `source_file`) are fixed in the writer and differ from the expert's example CSV headers (`filename`, `company`, `ticker`, `date`). A future code change can align these if needed.
