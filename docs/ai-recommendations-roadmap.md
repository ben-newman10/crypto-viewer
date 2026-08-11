# Candidate discovery, diversification grounding, and a track record

## Context

Crypto Viewer's recommendation pipeline is unusually disciplined: indicators are computed in
code, the model may only cite named fields from a closed grounding context, every claim is
re-verified server-side, and confidence is `min(model_confidence, data_ceiling)`. That
discipline is the thing worth preserving.

But it can only ever talk about coins you already own. The candidate set originates in exactly
one place — `context_builder.py:271` `portfolio = await self.coinbase.get_portfolio()` — and is
enforced twice more: the prompt says "Return one recommendation per asset listed in the context"
(`ai_service.py:98`), and `_assemble` drops any recommendation whose symbol is not in
`context.assets` (`recommendation_service.py:147-153`). `CoinbaseService` has no
product-discovery method at all, and `MarketContextService` resolves symbols through a static
15-entry `COINGECKO_IDS` map (`market_context_service.py:41-57`) — so even *existing* holdings
outside those 15 get no market-structure data. The UI has no entry point either: the "search"
box in `Portfolio.tsx` filters rows you already have.

The goal is to let the app say "you don't hold LINK, and here is measured evidence for why it
might suit you" — with the same guarantees, not weaker ones.

**The load-bearing structural fact:** `_assemble`'s closed-world guard needs no change. It drops
any symbol not in `context.assets`; a candidate *is* in `context.assets` because the server put
it there. Widening the context correctly is sufficient — the grounding guarantee comes along for
free.

Decisions already made:
- **Universe:** auto-screened top coins by market cap, intersected with what Coinbase actually
  lists in GBP. No watchlist persistence.
- **Actions:** extend the enum to `buy | sell | hold | watch | avoid`.
- **Quality work:** correlation/diversification, and past-call performance from the audit log.
  Liquidity/volume and multi-timeframe are deferred (Phase 9).

---

## Feature list

| # | Feature | Phase |
| --- | --- | --- |
| 1 | Tradeable-product discovery (Coinbase exchange) + market-cap universe (CoinGecko) | 1 |
| 2 | Dynamic CoinGecko id resolution — retires the static 15-symbol ceiling | 1 |
| 3 | Deterministic in-code screener that stratifies a shortlist of ~5 | 1 |
| 4 | Candidate assets in the grounding context, `role="candidate"` | 2 |
| 5 | `watch` / `avoid` actions, with a server-side legality table | 2 |
| 6 | Portfolio concentration metrics (largest weight, top holding, effective holdings) | 2 |
| 7 | "Worth a look" section in the UI, with a "Not held" chip per card | 3 |
| 8 | "Why not the others" — the screener's rejects, served and disclosed | 3 |
| 9 | Correlation between a candidate and your portfolio's own return series | 5 |
| 10 | Calibration: read the audit log back, score matured calls | 7 |
| 11 | `GET /api/recommendations/calibration` + its own UI panel | 7 |
| — | Retry gating — deferred; see Phase 0, it is not a free refactor | 2 |

---

## Phase 0 — Groundwork, no observable change

**Acceptance criterion: the entire existing pytest and Playwright suite passes *unmodified*.**
That is the whole point of this phase.

**`grounding.py`** — `AssetRole = Literal["holding", "candidate"]`; `AssetContext.role: AssetRole
= "holding"`. The default means every existing construction site and test keeps working.
`role` reads better than `held: bool` in the negative, renders straight into the prompt header,
and is extensible. Add `RecommendationContext.holdings()` / `.candidates()` helpers beside the
existing `asset()` (`:187`).

**`context_builder.py`** — collapse the two `zip(holdings, per_asset)` loops (`:302`, `:321`)
into one pass over a spec list:

```python
@dataclass(frozen=True)
class AssetSpec:
    symbol: str
    role: AssetRole
    product_id: str
    balance: Optional[float]        # None for a candidate
    gecko_id: Optional[str]
    screen_reason: Optional[str]    # None for a holding
    market_cap_rank: Optional[int]

FETCH_CONCURRENCY = 6
```

Bound the fan-out with `asyncio.Semaphore(FETCH_CONCURRENCY)`. Six, because the public exchange
endpoint is IP-rate-limited around 10 req/s and `get_candles` bypasses `_retrying` (`:134`) — it
does not retry a 429.

**`coinbase_service.py`** — a 10-minute TTL candle cache keyed on
`(product_id, granularity, limit)`, wrapping `get_candles` only. Leave `get_historical_data`
uncached; it is the live 24h chart feed. **The cache must live on the service singleton**
(`dependencies.py:30-36`), not on `ContextBuilder` — the builder is constructed per request
(`recommendation_service.py:77`), so a cache there is dead code.

**Retry gating — moved out of this phase.** The original plan put it here as a pure cost
saving. It is not one, and it does not belong in a phase whose criterion is "no observable
change":

- Under `ungrounded-ai` each asset cites four real facts plus one invented field. Only the
  invented one is dropped, leaving four — so any sensible `MIN_FACTS_BEFORE_RETRY` skips the
  retry and breaks `test_a_fabricated_value_is_corrected_retried_and_penalised`, whose comment
  reads "a failed check must trigger one retry". That assertion is a deliberate contract, not
  an incidental detail.
- The argument for gating ("mismatches are auto-corrected anyway") misses that a violation also
  costs a confidence step in `_assemble` (`:159-171`). The retry is the model's one chance to
  earn that back. Gating it makes a single misquote permanently expensive.
- `pick_better` already keeps whichever answer has fewer violations, so the retry can never make
  the payload worse — only cost a call.

Revisit in Phase 2, when the real payload size is known and the trade-off can be priced. If it
is taken then, it needs its own commit and a reasoned update to that test — not a silent
edit.

**Risk:** the refactor silently reorders assets, changing deterministic card order.
`test_the_endpoint_returns_one_structured_call_per_holding` asserts `["BTC","ETH","SOL"]` and
guards it. **Holdings must always precede candidates in `context.assets`.**

---

## Phase 1 — Discovery sources, flag off

### Source choice: the keyless exchange product list × a CoinGecko ranked page

Reject the Advanced Trade SDK's `get_products()`. `get_candles` hits
`api.exchange.coinbase.com` (`:515`), which is a **different listing** from Advanced Trade. A
product on Advanced Trade but not on the exchange API would pass discovery and then fail every
indicator, producing a permanently thin, permanently low-confidence candidate card. Intersecting
against the same host that serves the candles makes "we can analyse this" true by construction.
It also needs no credentials, so discovery survives a credential problem, and adds no new egress
host.

**`coinbase_service.py`:**

```python
PRODUCTS_URL = "https://api.exchange.coinbase.com/products"
PRODUCT_CACHE_TTL_SECONDS = 6 * 60 * 60

async def list_products(self, quote_currency: str = "GBP") -> List[str]:
    """Base symbols Coinbase lists against `quote_currency` and will actually trade.

    Filters on status == "online" and not (trading_disabled or cancel_only or
    post_only or auction_mode). Returns [] on any failure — never raises."""
```

Direct `httpx.AsyncClient` like `get_candles`, not `_retrying` (that wraps the blocking SDK).
Six-hour TTL on the singleton; listings change on the scale of weeks.

**`market_context_service.py`:**

```python
UNIVERSE_PAGE_SIZE = 250

class UniverseRow:
    __slots__ = ("symbol", "gecko_id", "market_cap_rank", "market_cap", "total_volume",
                 "change_24h_pct", "change_7d_pct", "change_30d_pct",
                 "ath_change_pct", "circulating_supply")

async def get_ranked_universe(self, quote_currency: str = "GBP") -> List[UniverseRow]:
    """Top coins by market cap, ranked. [] on any failure."""
```

One request to the existing `COINGECKO_URL` with
`order=market_cap_desc&per_page=250&page=1&price_change_percentage=24h,7d,30d`. Reuse the
existing 15-minute `_cached`/`_store` (`:98-107`) and the degrade-to-empty pattern (`:149-151`).

**Feature 2, free:** rework `get_asset_stats` to resolve ids in this order — **static
`COINGECKO_IDS` first** (curated, known-correct), then the ranked universe by symbol. The static
map becomes an override table rather than the whole world, and holdings outside those 15 symbols
finally get market-structure data. This ships value on its own, with zero candidate risk.

**Symbol collision.** CoinGecko symbols are not unique, and the map's own comment (`:38-40`)
warns that guessing an id "can silently return a *different* asset's market cap". Rule: if two
ranked rows share a symbol and neither is in the static map, **drop it from the candidate pool**
with reason `ambiguous_symbol`. For a *holding* the user owns it and it must still be reported,
so fall back to the highest-cap row and say so in the metric note. A candidate is discretionary
— when in doubt, don't.

### The screener — `server_py/app/services/discovery.py` (new, pure, no I/O)

```python
CANDIDATE_RANK_FLOOR = 100
SHORTLIST_SIZE = 5
MIN_TURNOVER_QUOTE = 10_000_000.0

ScreenReason = Literal["large_cap", "below_ath", "recent_strength", "steady_mover"]
ExclusionReason = Literal["already_held", "not_tradeable", "stablecoin", "duplicate_exposure",
                          "below_rank_floor", "thin_liquidity", "ambiguous_symbol",
                          "not_shortlisted"]

class Candidate:   # symbol, gecko_id, rank, reason: ScreenReason
class Exclusion:   # symbol, reason: ExclusionReason, detail: str

def screen(universe, tradeable: Set[str], held: Set[str],
           limit: int = SHORTLIST_SIZE) -> Tuple[List[Candidate], List[Exclusion]]
```

Hard filters in order, each rejection recorded and never silent: `already_held` →
`not_tradeable` → `stablecoin` → `duplicate_exposure` → `below_rank_floor` → `thin_liquidity`.

- **Stablecoins:** a curated `STABLECOIN_IDS` set **plus** the numeric guard
  `abs(change_30d_pct) < 2.0`. Both — the curated list goes stale, the guard catches newcomers.
  Never regex the symbol.
- **Duplicate exposure:** a curated `WRAPPED_IDS` map (`wrapped-bitcoin → BTC`,
  `staked-ether → ETH`, `wrapped-steth → ETH`, …). Recommending WBTC to a BTC holder is not
  diversification, and excluding it under a named reason beats silently ranking it.

**Selection stratifies; it does not score.** The screener chooses what to *look at*, not what to
recommend. A composite alpha score would be a sampling artefact that the model would inevitably
cite as evidence. So: guarantee one candidate from each of `large_cap` (rank ≤ 20), `below_ath`
(ATH distance below the pool median) and `recent_strength` (7d change in the top quartile), then
fill by rank. Ties broken by rank, so the function is deterministic — testable, and stable
across the 15-minute refetch.

**Grounding consequence.** Emit no composite score. Emit instead:
- `{SYM}.market_cap_rank` — a real measurement, `market_structure`.
- `{SYM}.screen_reason` — a **text** metric in `reference`. Being a closed vocabulary it
  verifies through `groundedness.py:161-180` exactly like `ma_cross_state`; being `reference`
  it is unscored (`grounding.py:55-61`) and cannot inflate the ceiling.

Everything else the screener consulted (7d/30d change) is re-derived from the candle series in
code and emitted as a proper metric — so its availability degrades in step with everything else
candle-derived, rather than depending on CoinGecko.

Rejected candidates live on `RecommendationContext.screened_out: List[Exclusion]`. **Served in
the response, not rendered into the prompt** — it would cost tokens and invite the model to
write about coins it has no data for. "Why not the others" is a product feature, not a grounding
feature.

### Config and degradation

`config.py` gains `CRYPTO_VIEWER_CANDIDATE_DISCOVERY` — **default off for now**, flipped in
Phase 4 — following `external_market_data_enabled()` (`:53`), plus
`CRYPTO_VIEWER_CANDIDATE_LIMIT` (5) and `CRYPTO_VIEWER_UNIVERSE_SIZE` (250).

Both discovery calls return `[]` on failure and never raise. `sources` gains
`coinbase_products` and `coingecko_universe`, each `ok` / `unavailable` / `disabled`. If either
is empty, `candidate_specs = []` and the run proceeds **byte-identically to today's
holdings-only behaviour**. Never guess at tradeability: suggesting a coin the user cannot buy is
worse than suggesting nothing.

**Tests:** new `test_discovery.py` — exclusion reasons, stratification, determinism, stablecoin
/ wrapped / ambiguous handling, empty universe. Additions to `test_coinbase_service.py`.

**Risk:** the CoinGecko free tier rate-limits and a 250-row page is a heavier response. The
15-minute cache and the never-raise contract contain it.

---

## Phase 2 — Candidates in the context and the prompt, flag still off

### 2.1 Fetching a candidate costs 1 request, not 3

**`get_crypto_price` is two outbound requests, not one** — it calls `get_historical_data`
(`:384`, httpx) *and* `client.get_market_trades` (`:389`, SDK). So a holding costs 3 requests
today. Add `_fetch_candidate()` alongside `_fetch_asset()` that **skips `get_crypto_price`
entirely** and derives both price and 24h change from the candle series it must fetch anyway.
This is the single biggest cost lever in the design.

Trade-off: a candidate's `change_24h_pct` is close-to-close where a holding's is
last-trade-to-close. Two assets measuring a same-named field differently is a grounding smell,
so make it visible — put the method in `Metric.note`, which is exactly what `note` is for ("how
it was computed"). `label` and `plain` stay accurate for both, so
`test_a_field_is_labelled_the_same_whether_or_not_its_data_arrived` is unaffected.

Total value is computed from holdings only. A candidate's `balance` is `None` so it contributes
nothing naturally — but assert that explicitly so a later edit cannot break the invariant
silently. `test_portfolio_weights_sum_to_a_hundred_percent_with_cash` is the regression guard.

### 2.2 Position metrics for an unheld coin — emit them, unavailable

Emit `balance`, `holding_value` and `portfolio_weight_pct` with `status="unavailable"` and the
reason "you do not hold this coin, so there is nothing here to measure".

The completeness argument is neutral (`position` is not in `SIGNAL_CATEGORIES`,
`grounding.py:287`), so the real justification is the **closed world in `metric_index()`**. If
`AVAX.balance` simply does not exist, a model citing it hits `unknown_metric` — dropped,
violation, retry. If it exists-and-is-unavailable, an honest "unavailable" is silently dropped
(`groundedness.py:144`) and only an invented number is a `cited_unavailable_metric`. That
distinction matters: only a genuine hallucination should pay for a retry, and "tried to talk
about a position you don't have" is a reasoning error, not a fabrication.

Emit `portfolio_weight_pct` as **unavailable, not zero**. A zero is a measurement asserting the
coin is 0% of the portfolio — true, but it invites "adding it would barely move your
allocation", a claim we have no data for.

### 2.3 Concentration metrics

Added to `_shared_metrics` (`:416`), all **`position`** category:

- `portfolio.largest_weight_pct` — `%`
- `portfolio.top_holding_symbol` — text
- `portfolio.effective_holdings` — `1 / Σwᵢ²` over crypto weights

**`effective_holdings` rather than raw HHI.** HHI's `plain` definition is unwriteable for a
novice; the reciprocal is not: *"If your money were spread perfectly evenly, this is how many
coins that would be the same as. Holding 90% in one coin and 10% in another comes out near 1,
not 2."* Legible, and it answers the diversification question directly. `portfolio.holding_count`
is not added — `asset_count` already means that.

**Keep these `position` (unscored). Do not mint a `diversification` signal category.** Scoring
them would add three always-available fields to every asset's denominator, *raising* the
completeness ratio for a thin asset — exactly the inflation failure mode `grounding.py:11-17`
and CLAUDE.md warn against. Category changes are rubric changes, and the rubric is documented
as "change it in one place" for a reason.

### 2.4 Action legality — new `server_py/app/services/call_policy.py`

`recommendation.py:24` → `Action = Literal["buy", "sell", "hold", "watch", "avoid"]`.

A separate `stance` field loses on the argument that matters: the frontend needs a distinct
visual treatment either way, and `stance` moves that decision out of the type-checked
`Record<RecommendationAction, BadgeTokens>` and into an untyped conditional — strictly worse for
the WCAG guarantee, which the compiler currently enforces.

```python
ALLOWED_ACTIONS: Dict[AssetRole, FrozenSet[Action]] = {
    "holding":   frozenset({"buy", "sell", "hold"}),
    "candidate": frozenset({"buy", "watch", "avoid"}),
}
SAFE_DEFAULT: Dict[AssetRole, Action] = {"holding": "hold", "candidate": "watch"}

def coerce(action: Action, role: AssetRole) -> Tuple[Action, Optional[Action]]:
    """Returns (served_action, coerced_from); coerced_from is None when legal."""
```

Applied in `_assemble` alongside the existing clamp. An illegal action is coerced to the safe
neutral, confidence downgraded one step, and a reader-facing note attached — the same shape as
the existing misquote penalty (`:159-171`). This is `ai_service.py`'s own "the prompt is
necessary but not sufficient" philosophy applied to the call itself: **a model can never emit
`sell` for an unheld coin to a reader**, as a guarantee rather than a request.

Audit trail: `AssetRecommendation.action_coerced_from: Optional[Action] = None`, mirroring
`SupportingFact.model_stated_value`. Do **not** add a new `GroundednessViolation.kind` — that
model is fact-oriented (`facts_checked/dropped/corrected`) and stretching it would ripple into
the frontend type for no benefit.

### 2.5 Prompt and schema — `ai_service.py`

Two new rules, at **grounding priority** (before the audience section, not after):

```
7. Each asset is marked `role=holding` or `role=candidate`. A holding is one the
   reader already owns; a candidate is one they do not own, which the app has
   picked out for you to assess. Never write about a candidate as though it were
   already owned.
8. The permitted calls depend on the role. For a holding: buy, sell or hold. For
   a candidate: buy (worth starting a position), watch (worth following, not
   yet) or avoid. `sell` is meaningless for something the reader does not own,
   and the server rejects it.
```

This renumbers the audience rules 7-11 → 9-13, so the literal `"Rules 1-6 bind you exactly as
before"` becomes `"Rules 1-8 …"`. **That exact string is asserted at `test_ai_service.py:277`**
— the failure is by design; update it in the same commit.

One more audience rule, and its sequencing is deliberate:

```
14. For a candidate, do not claim it would diversify, balance or hedge what the
    reader holds unless a field measuring the relationship between them is
    available and you cite it. Being a different coin is not evidence of that.
```

Until correlation lands (Phase 5) there is no such field, so this is a hard prohibition.
Afterwards it becomes a citation requirement. Shipping candidates *without* it invites exactly
the ungrounded "this diversifies you" claim the pipeline exists to prevent.

Closing line, replacing `:98-100`:

> Return exactly one recommendation for every asset listed in the context — holdings and
> candidates alike — using the required schema. `summary` is two or three sentences about the
> portfolio as a whole, meaning what the reader actually owns, under the same grounding rules.
> Candidates may be mentioned there only as things worth looking at, never as things they hold.

`RESPONSE_FORMAT`: widen `recommendation.enum` to the five values with a description naming
which are legal for which role; update the `recommendations` array description. Do **not** add a
`role` echo field — it invites the model to disagree with the server about a fact the server
owns, and the server would override it anyway. `test_the_response_schema_is_strict_and_closed`
(`:267-296`) protects the change.

`render_context()` — front-load the distinction with a preamble rather than making the model
hold it across 200 lines of metrics, and mark the header line (`:242`):

```
You own: BTC, ETH, SOL.
Candidates you do not own, shortlisted by the app: AVAX, LINK.

Asset BTC (BTC-GBP) [holding] -- data completeness 100% (...)
Asset AVAX (AVAX-GBP) [candidate, not owned] -- data completeness 92% (...)
```

**Raise `max_tokens` from 3000 to 6000** (`:359`). Eight novice-prose cards will not fit in
3000, and the failure mode is a truncated body that fails schema validation and surfaces as
`status="unavailable"` — an easy thing to ship by accident.

### 2.6 Empty portfolio with working discovery

`recommendation_service.py:81` short-circuits on `not context.assets`. A user holding nothing is
arguably the *most* useful case for this feature, so gate it explicitly:

```python
if not context.holdings() and not context.candidates():
    return _empty_response(context)
```

With no holdings the screener falls back to pure rank stratification and every `position` metric
is unavailable. The existing `emptyPortfolio` e2e assertion stays honest because the fake
returns no candidates under that flag; a new `candidates-only` flag covers the new path.

### 2.7 Catalogue, fakes and tests

New `metric_catalog.py` entries — all required, or `spec_for()` raises (`:296-301`):
`market_cap_rank`, `screen_reason`, `largest_weight_pct`, `top_holding_symbol`,
`effective_holdings`, `change_7d_pct`, `change_30d_pct`.

New scenario flags, added to **both** `fakes/scenarios.py` `KNOWN_FLAGS` and
`e2e/support/scenarios.ts`. Do not add any to `_PARTIAL_EXPANSION`:

| Flag | Behaviour |
| --- | --- |
| `candidates` | Discovery on; two candidates shortlisted |
| `error-discovery` | Product listing and universe unreachable → holdings only |
| `candidates-only` | Empty portfolio but discovery works |
| `invalid-action-ai` | Model returns `sell` on a candidate → exercises coercion |

Fixtures: `PRICES` and `_DAILY_SHAPE` gain AVAX-GBP and LINK-GBP (required —
`fake_coinbase_service.get_candles` raises `ValueError` for an unknown product); `MARKET_STATS`
gains matching rows; a new `UNIVERSE` fixture for the ranked page; `FAKE_CALLS` gains candidate
entries emitting **legal** actions. `_FACT_PRIORITY` in `fake_ai_service.py` needs no change —
it already skips unavailable metrics, so a candidate's unavailable position fields drop out
naturally.

Tests: `test_context_builder.py` — role assignment; candidate position fields
present-and-unavailable with the right reason; held coins excluded from the pool; discovery
failure → holdings only; cap respected; candidates contribute nothing to `total_value`;
concentration metrics. **Add the new flags to the two existing `@pytest.mark.parametrize` lists
at `:159` and `:191`** — they catch a missing catalogue entry and a duplicate field name for
free. Plus new `test_call_policy.py`, and updates to `test_ai_service.py` and
`test_recommendations_router.py`.

**Risk:** the highest-blast-radius phase. Mitigated by the flag defaulting off — nothing reaches
a user until Phase 4.

---

## Phase 3 — Frontend, still gated

`src/lib/api.ts`: `RecommendationAction` gains `'watch' | 'avoid'`; `AssetRecommendation` gains
`role` and `action_coerced_from`; `RecommendationResponse` gains `screened_out` and
`candidates_considered`. Leave `context` off the client type — the new UI needs none of it.

`badges.tsx` — `ACTION_TOKENS` is a total `Record<RecommendationAction, BadgeTokens>`, so
`tsc -b` fails until both new states exist. The compiler enforces the a11y contract:

| action | icon | word | fg / bg |
|---|---|---|---|
| `watch` | `ViewIcon` | Watch | `accent.fg` / `accent.subtle` |
| `avoid` | `NotAllowedIcon` | Avoid | `loss.fg` / `loss.subtle` |

`avoid` deliberately shares `sell`'s colour pair — directionally the same family, and icon +
word carry the distinction, so WCAG 1.4.1 holds. `accent.fg`/`accent.subtle` are already
contrast-validated (CLAUDE.md) and unused by the badges, keeping `watch` distinct from `hold`'s
neutral and from `medium` confidence's warning amber.

**Grouping — use section landmarks, not new headings.** Wrap each group in
`<Box as="section" aria-label="Your holdings">` and
`<Box as="section" aria-label="Worth a look — coins you do not hold">`. This preserves the
h2 → h3 outline exactly, changes zero existing assertions, and keeps axe clean. The alternative
— real `<h3>` group headings with cards demoted to `<h4>` — is more navigable but forces changes
to `RecommendationCard`, to `MARKDOWN_COMPONENTS`' shift mapping (`Recommendations.tsx:40-51`)
and to `recommendations.spec.ts:45-52`, which asserts exactly three `h3`s. Take the section
route unless you specifically want headings and accept the h4 move; heading order is the
invariant CLAUDE.md protects.

Add a "Not held" chip to the candidate card header, and put the words inside the `<h3>` via
`VisuallyHidden` so heading navigation carries the distinction out of context.

Feature 8, "why not the others": a keyboard-reachable disclosure below the candidates section,
matching the `SupportingFacts.tsx` pattern (a `Button` with `aria-expanded`/`aria-controls`, not
native `<details>`). Exclusion reasons get a display map in
`src/components/recommendations/exclusions.ts`, mirroring `categories.ts` — a **third** file to
keep in step, so add it to CLAUDE.md's sync note.

The disclaimer stays inside the panel, after both sections. New e2e assertions run under the
`candidates` flag only.

---

## Phase 4 — Flip the default

Deliberately small and separate. `CRYPTO_VIEWER_CANDIDATE_DISCOVERY` defaults on. Update the
hard-coded counts: `recommendations.spec.ts` `toHaveCount(3)` at `:35, :50, :77, :84, :115,
:138, :269, :401`, `dashboard.spec.ts` if affected, and `test_recommendations_router.py:39`.
Re-shoot `screenshots/` via `responsive-screenshots.spec.ts`.

Docs: README gains a "Candidate discovery" section (universe → screener → shortlist, and that an
outage means no candidates rather than guessed ones), the new scenario-flag rows and the new env
vars. CLAUDE.md gains the role/legality rule and the third display-map file. `.env.example`
gains the three new variables.

---

## Phase 5 — Correlation

Rule 14 is a dead letter without this, which is why it follows candidates immediately.

Pure functions in `indicators.py` (it is the home for functions over close series, and
`test_indicators.py` is the matching test file — no new module):

```python
CORRELATION_PERIOD = 90
CORRELATION_MIN_SAMPLES = 30

def simple_returns(closes: Sequence[float]) -> List[float]
def pearson(a: Sequence[float], b: Sequence[float]) -> Optional[float]
def return_correlation(closes_a, closes_b, period=CORRELATION_PERIOD) -> Optional[float]
```

Three traps to test explicitly:
- **Correlate returns, not levels.** Two rising series have level-correlation ≈ 1 regardless of
  their real relationship. This is *the* classic bug — the test should be two series with the
  same drift and independent wiggles, asserting the result is nowhere near 1.0.
- **Align on the shorter tail** — a newer listing has fewer than 300 candles.
- **Zero-variance series → `None`**, not `ZeroDivisionError`.

Metric `{SYM}.correlation_with_portfolio_90d`, measured against the **portfolio's own weighted
aggregate return series** (each holding's daily returns weighted by its portfolio weight),
excluding the asset itself when it is a holding. Better than "correlation with BTC", and it
answers the actual question.

**Category `volatility`, not a new `diversification` category.** It is a co-movement statistic
on the same return series `annualised_volatility` already uses, so it degrades in step with the
other candle-derived fields. A sixth category would silently weaken `HIGH_MIN_CATEGORIES=3`
(three of six is a lower bar than three of five) and change `_ceiling_reason`'s wording. If a
`diversification` category is ever wanted, that is a deliberate rubric revision with its own
migration — not a side effect of adding a metric.

Zero extra requests: it reuses candle series already in hand.

---

## Phase 6 — Calibration

`recommendation_log.py` already writes `price_at_call` per symbol (`:36`) precisely so calls can
be checked against reality. Nothing reads it.

Add a read side to `recommendation_log.py`:

```python
def read_entries(path=None, limit: int = 500) -> Iterator[Dict[str, Any]]:
    """Newest-first. Seeks to the tail and reads backwards in chunks; skips
    unparseable lines rather than raising. Never loads the whole file."""
```

Plus size-based rotation in `record()` (roll to `recommendations.1.jsonl` past ~32 MB), with the
reader consulting at most the two newest files.

New `server_py/app/services/calibration.py`:

```python
HORIZONS_DAYS = (7, 30)
DEAD_BAND_PCT = 1.0
MIN_RESOLVED_CALLS = 20

def summarise(entries, current_prices: Dict[str, float]) -> CalibrationReport
```

Buckets by `(confidence, action)`. A call resolves once its horizon has elapsed since
`generated_at`; a hit is a move in the called direction beyond the dead band, with
`hold`/`watch` scored as staying inside it. New endpoint `GET /api/recommendations/calibration`,
following the existing `_generate` wrapper (`:22`) — a 200 with `status="insufficient"`, never
a 500 — and kept off the recommendation hot path, which is already slow.

**Five things keep it from becoming a database:** read-only with no index and no writes; a
bounded tail read; a 1-hour in-process cache of the computed report; size rotation; and — most
importantly — **the report never feeds back into the confidence ceiling or the prompt**. If
"our high-confidence calls have been right 71% of the time" were a citable field, the model
would use it as an argument for the call it is currently making: self-referential confidence
laundering, and exactly the unfalsifiable claim this pipeline exists to prevent. The ceiling
stays a deterministic function of data completeness. Worth writing into CLAUDE.md's
non-negotiables.

`MIN_RESOLVED_CALLS = 20` is the single most important line: below it the report returns
`status="insufficient"` rather than a number. A hit rate over four calls is noise dressed as
evidence.

Frontend: `api.getCalibration()`, and a panel built on the existing `SectionCard` +
`MetricTile` + `StatePanel` primitives, below the analysis panel in the dashboard's right column
(`DashboardPage.tsx:36`). State the sample size beside every figure, and apply the same novice
prose rule the model is held to.

Tests: new `test_calibration.py` — tail reading including a file smaller than one chunk,
malformed and half-written final lines skipped, age and line caps enforced, hit-rate maths, the
`insufficient` case. New `empty-track-record` scenario flag in both scenario files, plus
`e2e/calibration.spec.ts`.

---

## Phase 9 — Deferred, with reasoning recorded

- **Liquidity / turnover.** `_closes_oldest_first` (`:95`) discards `volume`. A `turnover_24h`
  (volume × close — raw volume is in *base* units and not comparable across assets) and a
  `turnover_ratio_30d` would stop a thin market earning the same confidence as a deep one, and
  it matters more once candidates are in play. **Deferred because it is a deliberate behaviour
  change, not a free add:** today a CoinGecko outage zeroes the whole `market_structure`
  category; a candle-derived member means it survives partially, so under `error-market-context`
  BTC's ceiling rises from `medium` to `high`. That breaks
  `test_a_failed_market_source_costs_two_categories_and_lowers_the_ceiling`
  (`test_context_builder.py:109`), `test_a_missing_market_source_caps_confidence_at_medium`
  (`test_recommendations_router.py:101`) and `recommendations.spec.ts:112`. Worth doing — as an
  intentional change with those three updated, not stumbled into.
- **Multi-timeframe.** Fetching weekly candles costs +1 request per asset, undoing the Phase 2.1
  saving, for signals highly correlated with the daily ones — and it earns no new category, since
  a weekly RSI is still momentum and filing it there would let two readings of the same thing
  count as two independent confirmations, which `grounding.py:39-42` says the scheme exists to
  prevent. If ever done: **resample the 300 daily closes** into ~42 weekly bars for zero extra
  requests.
- **`context` type drift.** The backend serves `context: Optional[RecommendationContext]`
  (`recommendation.py:149`) and `test_recommendations_router.py:58-70` asserts on it, but
  `RecommendationResponse` in `src/lib/api.ts:109-121` has no such member. Harmless; worth
  closing if the UI ever renders the full evidence table.

---

## API cost

| | Coinbase | CoinGecko | alt.me | OpenAI | total |
|---|---|---|---|---|---|
| **Today** (3 holdings) | 9 + ~3 portfolio | 1 | 1 | 1–2 | **~15–16** |
| Naive (25 candidates × 3) | 84 + 3 | 1 | 1 | 1–2 | ~90 |
| **This design, cold** (3 holdings + 5 candidates) | 9 + 3 + 5 + 1 products | 1 | 1 | 1–2 | **~21–22** |
| **This design, warm** (candle + product caches hot) | ~3 | 0 | 0 | 1 | **~4** |

Three levers, in order of impact: a candidate costs **1** request not 3 (skip
`get_crypto_price`); the screener shortlists to 5 using fields already in the ranked page (zero
additional requests); the discovery and candle caches make the 15-minute refetch nearly free.

Prompt size grows roughly 2.5× (eight assets instead of three) and `max_tokens` doubles. At the
15-minute refresh (`Recommendations.tsx:34`) that is pennies a day at gpt-4.1 rates — but it is
a real multiple, worth checking before raising `CRYPTO_VIEWER_CANDIDATE_LIMIT` above 5.

**When discovery is down:** both calls return `[]`, `sources` records it, `candidate_specs` is
empty, and the run is a holdings-only run identical to today's with `candidates_considered: 0`.
The UI shows no candidates section rather than an error — a missing optional source has never
been an error in this codebase and must not become one. The `error-discovery` flag asserts this
end to end.

---

## Verification

Each phase is independently shippable. Verify before moving on.

**Backend** — runs in test mode with no credentials and no third-party calls
(`conftest.py:16`):
```bash
cd server_py && ./venv/bin/python -m pytest
```
Phase 0's acceptance criterion is that this passes *with no test edits at all*.

**Frontend:**
```bash
npm run typecheck && npm run lint
```
The widened `RecommendationAction` will fail `tsc` until `ACTION_TOKENS` is total — the intended
forcing function, not an obstacle.

**End to end** — `e2e/support/fixtures.ts` fails any test whose browser reaches a non-local
host, so "no real third-party calls" stays enforced:
```bash
npx playwright test
```

**Phases 2–3, through the real HTTP path:**
```bash
cd server_py && CRYPTO_VIEWER_TEST_MODE=1 ./venv/bin/python -m uvicorn app.main:app --port 3001

curl -s --cookie 'cv_test_scenario=candidates' localhost:3001/api/recommendations/ \
  | jq '.recommendations[] | {symbol, role, recommendation}'
curl -s --cookie 'cv_test_scenario=error-discovery' localhost:3001/api/recommendations/ \
  | jq '{sources, n: (.recommendations | length)}'
curl -s --cookie 'cv_test_scenario=invalid-action-ai' localhost:3001/api/recommendations/ \
  | jq '.recommendations[] | select(.role=="candidate") | {recommendation, action_coerced_from}'
```
The last must never print `"sell"`. Then `npm run dev` and confirm in the browser: two labelled
sections, the "Not held" chip, both new badges legible in light and dark, and the "why not the
others" disclosure keyboard-operable.

**Against the real APIs, once, before trusting discovery.** The fakes cannot tell you whether
CoinGecko's `symbol` matches Coinbase's base currency in practice, and a mismatch here is the
single most likely way this feature ships subtly broken:
```bash
cd server_py && ./venv/bin/python -c "
import asyncio
from app.services.market_context_service import MarketContextService
from app.services.coinbase_service import CoinbaseService
async def main():
    rows  = await MarketContextService().get_ranked_universe('GBP')
    bases = set(await CoinbaseService().list_products('GBP'))
    print(len(rows), len(bases))
    print(sorted({r.symbol for r in rows} & bases))
asyncio.run(main())
"
```
Eyeball that intersection — it is the actual universe your users get recommended from.

**Phase 6:** generate several runs, backdate some `logged_at` values in a copy pointed at by
`CRYPTO_VIEWER_RECOMMENDATION_LOG`, and check `GET /api/recommendations/calibration` reports
sensible hit rates — and that a truncated final line does not raise.
