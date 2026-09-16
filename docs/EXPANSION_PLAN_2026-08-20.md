# Sourcer Expansion Plan — LinkedIn People Search and Continuous Outreach (2026-08-20)

Status: planned on 2026-08-20 in Codex session `01a01f1c`, not implemented (user-set hard cutoff stopped execution before any code change). This is the next major feature wave.

---

## Full product plan

<proposed_plan>
# LinkedIn People Search and Continuous Outreach

## Summary

Add two connected but independently controlled capabilities:

1. A new `linkedin_extract` source lane for ordinary LinkedIn people search, separate from Sales Navigator. It supports Boolean queries, account-visible filters, manual or risk-gated bounded extraction, bulk profile normalization, checkpoints, and partial datasets.
2. An organization-wide contact and conversation layer that turns outreach into a recurring qualification, nurture, and referral loop. Trust and referral eligibility remain vacancy-specific, while contact identity, consent, and conversation history persist across vacancies.

Acquisition, grading, outreach, and interview handoff remain separate reviewable steps. No pipeline stage silently launches the next one.

## Key Changes

### LinkedIn source

- Add `linkedin_extract` across backend `StageType`, stage validation/dispatch, database constraints, frontend types, source presentation, progress events, and `AGENTS.md`.
- Create a dedicated ordinary-LinkedIn scraper. Reuse the persistent visible Chromium session, public-profile extraction, rate-limit detection, conservative pacing, and dataset services without coupling it to Sales Navigator selectors or URLs.
- Introduce a typed `LinkedInSearchConfig` containing:
  - Boolean query.
  - Normalized filter selections.
  - Browser session ID.
  - `automated` or `manual_confirmed` execution mode.
  - Maximum results, pages, profiles, and runtime.
  - Filter/UI snapshot version and locked people-search URL.
- Support ordinary LinkedIn’s account-visible people filters: connection degree, location, current/past company, connections/followers relationships, school, industry, profile language, actively hiring where available, volunteering/service categories, and keywords.
- Discover filters from the active session instead of assuming every account has the same options. Known filters map to stable typed fields; unknown filters are preserved as display label, selected value, and DOM-derived descriptor for manual confirmation rather than silently ignored.
- Validate LinkedIn Boolean syntax: uppercase `AND`/`OR`/`NOT`, quotes, and parentheses; reject unsupported wildcards/brackets and surface query-complexity errors before extraction.
- Use a compact source card with automation as the primary action and an Advanced toggle for “Review filters manually.” Both modes lock the final search URL before extraction.
- Execute in two bounded phases:
  1. Collect visible result identities and public profile URLs with page/checkpoint state.
  2. Open a bounded number of profiles, verify profile identity, extract raw evidence, and normalize records.
- Stop safely on authentication challenges, scraping warnings, rate-limit panels, unexpected result identity, or UI incompatibility. Preserve completed rows as a `partial` dataset and transition to `awaiting_auth` or `awaiting_user`.
- Output an independent dataset with query/filter provenance, raw profile evidence, extraction coverage, and `normalized` capability. Bulk rules, similarity, and AI grading remain existing downstream stages selected by the recruiter.

### Continuous relationship and outreach model

- Add an organization-scoped `relationship_contacts` identity layer. Deduplicate by normalized LinkedIn URL, Telegram identity, email, and explicit recruiter merges; never merge uncertain identities automatically.
- Retain `outreach_leads` as campaign membership, adding `contact_id`, source dataset/record lineage, and vacancy-specific relationship state.
- Add:
  - `relationship_assessments` for per-vacancy trust, qualification, referral eligibility, and recruiter notes.
  - `outreach_threads` for contact/channel conversations, with messages linked to both thread and campaign where relevant.
  - `outreach_policies` as versioned campaign automation envelopes.
  - `outreach_actions` for scheduled, pending, approved, sent, cancelled, failed, and escalated work.
  - `referrals` linking referrer, referred contact or unresolved referral, vacancy, conversation evidence, and resulting candidate dataset lineage.
  - `prompt_versions` and `llm_runs` for prompt provenance, model use, structured output, approval, final sent text, latency, and errors.
- Backfill existing outreach leads into contacts per organization, create threads from existing message streams, and preserve current campaign/message APIs through compatibility adapters.
- Separate lifecycle dimensions:
  - Global contactability: `active`, `paused`, `do_not_contact`, `deleted`.
  - Vacancy relationship: `new`, `contacted`, `conversing`, `qualified`, `interview_ready`, `handed_off`, `rejected`, `nurture`.
  - Trust/referral eligibility remains per vacancy and may expire or be revoked.
- Immediately apply opt-outs organization-wide across campaigns and cancel all pending actions for that contact.

### Automation and prompt system

- Campaign approval becomes the authorization boundary for broad autopilot. Approval locks the audience rules, channels, prompt/policy versions, cadence, quiet hours, rate limits, allowed sequence types, and reviewed sample outputs.
- Any material policy or prompt change creates a new version and requires campaign reapproval.
- Permit automatic first contact, factual follow-ups, qualification questions, nurture messages, and eligible referral asks only when:
  - The campaign is approved and active.
  - The action is inside cadence/channel limits.
  - Structured output validates.
  - Every factual claim is grounded in approved vacancy/contact data.
  - Confidence exceeds the policy threshold.
  - No escalation or sensitivity flag is present.
- Always pause for human review on opt-outs, unclear consent, protected-trait content, harassment, legal/visa uncertainty, unknown compensation answers, promises or negotiations, identity mismatch, contradictory conversation state, interview handoff, or repeated model/provider failure.
- Replace embedded outreach prompts with a versioned prompt registry composed from:
  - Non-editable safety and factual-grounding policy.
  - Organization voice/persona.
  - Vacancy facts and approved answers.
  - Sequence instructions.
  - Contact and vacancy-specific relationship context.
  - Recent conversation window plus durable summary.
  - Strict output schema.
- Use a provider-neutral LLM gateway with direct Anthropic support and existing Gemini/OpenRouter fallbacks. Default high-volume classification/drafting to the current Haiku-class model, while storing model IDs in configuration rather than code.
- Require structured output containing intent, confidence, next action, draft, grounded facts, missing information, risk flags, send eligibility, and proposed schedule. Use prompt caching for stable policy/vacancy prefixes.
- Expand classification to include interest, factual question, scheduling, compensation, referral offered, referral supplied, not-now, decline, opt-out, wrong person, sensitive/escalation, and unknown.
- On malformed output, provider failure, or fallback-model disagreement, save a review draft; never auto-send a generic fallback.
- Add a Prompt Studio for draft/published versions, structured policy fields, test conversations, diffing, evaluation results, and rollback. The chat inbox shows relationship timeline, AI reasoning summary, facts used, scheduled action, and override controls.

### Recurring sourcing, referrals, and handoff

- Celery Beat evaluates active vacancy policies and creates sourcing-cycle suggestions based on schedule, pipeline yield, stale searches, and candidate shortfall. A recruiter must approve each new acquisition run.
- Approved campaigns may schedule referral asks automatically when a trusted contact satisfies vacancy relevance, inactivity minimum, quiet hours, cooldown, annual cap, no pending conversation, and global contactability rules.
- Referral responses create provenance-preserving referral records. New people enter a new source dataset and proceed through explicit merge/dedup and grading.
- Create an interview-handoff queue rather than calendar or ATS integration in this release. Recruiter approval seals an `interview_ready` dataset containing confirmed candidate facts, qualification answers, evidence-linked conversation summary, unresolved questions, and source lineage.
- Add funnel reporting by source query/filter, campaign, prompt version, and referral relationship: discovered, unique, contacted, replied, qualified, interview-ready, opt-out, referral yield, time-to-response, and cost.

## Delivery Sequence

1. **Safety and tenancy prerequisite**
   - Scope all outreach Celery queries and writes by `org_id`; pass `org_id` into tasks and reject cross-organization campaign/lead/contact access.
   - Add idempotency keys for inbound messages, scheduled actions, and sends.
2. **LinkedIn source**
   - Add migration `011_linkedin_people_search.sql`, scraper/browser-agent support, stage dispatch, compact setup UI, fixtures, and bounded live validation.
3. **Relationship and policy foundation**
   - Add migration `012_continuous_outreach.sql`, contact backfill, threads, vacancy assessments, referrals, actions, and policy approval.
4. **LLM and automation**
   - Add the provider-neutral gateway, Anthropic adapter, structured prompt registry, evaluation suite, autopilot routing, escalation, and audit records.
5. **Continuous loop and handoff**
   - Add sourcing suggestions, referral scheduling, interview-ready datasets, dashboards, retention/deletion controls, and update operational documentation.

## Test Plan

- Boolean parser tests for precedence, unsupported syntax, filter normalization, and account-dependent filter discovery.
- Browser fixtures for result scoping, pagination, virtualized results, exact profile matching, checkpoints, manual takeover, authentication challenges, and rate-limit pauses.
- Stage tests proving independent dataset creation, partial recovery, rerun from locked URL, lineage, and explicit downstream review gates.
- Positive and cross-organization denial tests for every new contact, thread, action, referral, prompt, and task path.
- Migration tests for clean initialization and backfilling existing campaigns/messages without losing history.
- State-machine tests for campaign approval, policy-version invalidation, action idempotency, quiet hours, cooldowns, annual caps, opt-outs, and pause/cancel behavior.
- Prompt evaluations covering all intents, hallucination resistance, unsupported questions, multilingual conversations, prompt injection, sensitive content, referral extraction, invalid JSON, and provider failure.
- End-to-end simulations for:
  - LinkedIn discovery through interview-ready handoff.
  - Decline followed by global opt-out.
  - Trusted contact referral producing a new source dataset.
  - Changed vacancy facts forcing policy reapproval.
- Verify with focused backend tests, workflow transition/dataset tests, frontend production build, browser-agent Docker build, migration checks, `git diff --check`, and `git status --short`.
- Live LinkedIn validation remains bounded to one search page and one profile before any larger run.

## Assumptions and Constraints

- V1 outreach channels are LinkedIn and Telegram; email and calendar/ATS integrations remain extension points.
- Repeat sourcing runs are suggested on schedule but require recruiter approval. Actions inside an already approved outreach campaign may auto-send within its policy.
- Manual LinkedIn review is available under Advanced controls without expanding the default interface.
- LinkedIn officially supports Boolean search and ordinary people filters, but limits consumer Boolean complexity. Its current agreement also prohibits third-party scraping and automated access/messaging; risk gating reduces operational exposure but does not make automation compliant. Deployment therefore requires explicit organization-admin acknowledgment and an operator kill switch. [LinkedIn Boolean search](https://www.linkedin.com/help/linkedin/answer/a524335/using-boolean-search-on-linkedin?lang=en), [people search filters](https://www.linkedin.com/help/linkedin/answer/a524179), [User Agreement](https://www.linkedin.com/legal/user-agreement).
- The default model should be configurable; current Anthropic documentation identifies Haiku 4.5 as its lightweight model and supports constrained structured outputs and prompt caching. [Claude models](https://platform.claude.com/docs/en/about-claude/models/overview), [structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs), [prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching).
- AI may support communication and qualification, but cannot make final hiring decisions, invent vacancy facts, override opt-outs, or independently mark a candidate as handed off.
</proposed_plan>
---

## Minimal implementation plan (fallback scope)

<proposed_plan>
# Minimal Implementation Plan

## Current Stop Condition

- Current time is 14:27 Europe/Warsaw.
- The 14:25 verification window has already begun, so no implementation was started.
- No repository files were changed.
- Any execution must stop by 14:35, preserving existing uncommitted work and reporting incomplete items honestly.

## Minimal Product Shape

- One compact `linkedin_extract` source card:
  - Boolean query.
  - Essential filters.
  - Result/profile limits.
  - Primary automated action.
  - Advanced “Review manually” toggle.
- Reuse the existing visible browser, public-profile parser, datasets, checkpoints, downstream analysis stages, and rate-limit handling.
- One outreach control center:
  - Inbox.
  - Next actions.
  - Interview-ready queue.
  - Referral queue.
  - Campaign policy.
- Hide prompt versions, cadence, model selection, and advanced safeguards behind progressive disclosure.

## Implementation Order

1. Fix missing `org_id` scoping in outreach background tasks.
2. Add the `linkedin_extract` stage and bounded ordinary-LinkedIn scraper.
3. Add shared contacts with vacancy-specific trust/referral state.
4. Add approved campaign policies, scheduled actions, referrals, and global opt-outs.
5. Add a provider-neutral LLM gateway with Anthropic Haiku support, structured prompt versions, audit records, and existing-provider fallback.
6. Add scheduled sourcing suggestions and immutable interview-ready handoff datasets.
7. Update frontend types, migrations, tests, `.env.example`, README, and `AGENTS.md`.

## Verification

- Focused tenancy, stage-transition, dataset, Boolean/filter, outreach-policy, prompt, and referral tests.
- Frontend production build.
- Browser-agent Docker build.
- Clean-init and upgrade migration checks.
- `git diff --check` and `git status --short`.
- Live LinkedIn testing limited to one page and one profile.

## Defaults

- LinkedIn automation is risk-gated; manual review is optional under Advanced controls.
- LinkedIn and Telegram only.
- Campaign approval authorizes autopilot within a versioned policy.
- Sensitive, uncertain, opt-out, and interview-handoff cases require human review.
- Repeated sourcing runs are suggested but never launched automatically.
- Minimal UI takes priority over exposing every internal control.
</proposed_plan>