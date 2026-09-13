# NutriGuide AI — PRD upgrade

The uploaded `app.py` is upgraded in place from an ongoing-guidance MVP to the
core workflow in **NutriGuide AI PRD v1.1**: profile → health/medication context →
deterministic estimates → duration-based meal plan → contextual chat → reviewed,
individual meal replacement. `main.tex` and the uploaded PRD are unchanged.

## Run

Use an existing Python 3.10+ environment with the packages in `requirements.txt`.
Run from the project workspace:

```bash
cd prism-uploads
cp .env.example .env
```

Set `GROQ_API_KEY` in `.env` without committing it, then run:

```bash
streamlit run app.py
```

Alternatively launch `streamlit run prism-uploads/app.py` from the workspace root
with `GROQ_API_KEY` set in the environment. `python-dotenv` discovers the `.env`
beside the app. Streamlit hosting can use secrets instead:

```toml
GROQ_API_KEY = "your-key"
GROQ_MODEL = "openai/gpt-oss-120b"
```

`GROQ_MODEL` is configurable; the default preserves the MVP's model selection,
not a promise that the provider will keep offering it. Select a model that supports
JSON object mode and `max_completion_tokens`. No API key is needed to open the
application, review onboarding, or calculate eligible estimates. AI features are
disabled until configured. No API key is exposed in the UI.

The app uses an ivory, white and forest-green light theme with explicit dark text
and high-contrast controls. Matching `.streamlit/config.toml` files support launching
from either the workspace root or `prism-uploads`. Restart Streamlit after changing
theme configuration and refresh the browser to load the updated styles.

No dependencies were installed, no virtual environment was created, and no live
Groq calls were made in the editing workspace. Its Python environment does not
contain Streamlit, Groq or ReportLab. The declared dependency ranges need resolution
and a live smoke test in the deployment environment; they are not a verified lockfile.

## What changed

| PRD requirements | Implementation |
| --- | --- |
| FR-01, FR-06 | Exact age, equation sex coefficient, cm/kg measurements, activity; finite numeric bounds, required fields, consent and structured validation. |
| FR-02–05 | Yes/No/Not sure health and medication screening; multiple conditions; medication names, optional dose and frequency. |
| FR-07–08 | All four goals; 7/14/30/60/90 days and custom 1–90 days; 30-day default. |
| FR-09–10 | Python BMI, Mifflin–St Jeor resting energy, activity-adjusted maintenance, goal estimate and illustrative macros. Safety checks precede estimates. |
| FR-11 | Actual numbered days, four meal slots, ingredients, portions, estimated calories and macros, explanations and calculated daily totals. |
| FR-12–13 | Structured common allergies and dietary restrictions, other allergens, dislikes, dietary pattern and conservative alias matching on generated food content. |
| FR-14–16, FR-21 | Deterministic caution/referral gates; medication context passed to the model; no interaction checker or medication decisions. Higher-risk profiles cannot generate plans. |
| FR-17–20 | Contextual chat, on-demand meal/ingredient alternatives, preview/apply/discard, and revalidated updates to only the selected meal. Explanations accompany every meal. |
| Reliability | Two-day generation requests, batch checkpoints, bounded retries, JSON/type/nutrient validation, sanitized errors, and no publication of a failing batch. |
| Privacy | Explicit provider consent, session-only app state, no application database or health logs, clear-session control, sensitive export opt-in. |
| Existing functionality | Streamlit/Groq stack, green visual styling and downloadable PDF retained; JSON and CSV downloads added. |

### Workflow

1. Complete the five-step wizard. Back/forward navigation retains draft answers.
2. Review all data and the safety decision before saving. Saving a new profile
   replaces the existing plan and clears chat/proposals; editing alone does not.
3. Generate the next six days or all remaining days. Each request covers at most
   two days. One repair attempt is allowed for invalid AI output. API errors have
   at most three attempts with short backoff; each request has a 60-second timeout.
4. All 30/60/90 requested days are individually generated, not a repeating week.
   The most recent seven days of meal names are included to encourage variety.
   Variety is prompted, not guaranteed by a semantic duplicate detector.
5. If an API call or validation fails, accepted batches stay in the session. Resume
   starts at the next missing day. Profile and targets remain frozen during this process.
6. Inspect the selected day, then choose a day and meal in **Ask & refine**.
   Request a cheaper alternative, ingredient substitution, or explanation.
7. Replacements are proposals, not automatic changes. **Apply** validates again,
   checks the plan revision, updates just that meal and recomputes daily totals.
   Discard leaves the plan untouched. A new request replaces any pending proposal.
8. Download the current plan. JSON/PDF mark partial plans explicitly. CSV contains
   generated meal rows only (not a complete-plan manifest) and safety notes.
   PDF downloads are invalidated when the plan or sensitive-data selection changes.

## Architecture

- `app.py`: Streamlit UI, session state, resumable workflow and proposal review.
- `nutrition.py`: dependency-free profile validation, calculation, safety policy,
  food constraints, schema checks, totals and immutable meal replacement.
- `ai_service.py`: Groq adapter, fixed system policy, JSON requests, error handling,
  prompt context, batch validation and conversational proposals.
- `exports.py`: independent JSON, CSV and optional ReportLab PDF serialization.
- `.env.example`: secret-free configuration template.

No new test suite or framework was added because the uploaded app had no tests.
The core and AI adapter accept ordinary dictionaries and an injected client so a
future suite can exercise them without Streamlit or live API calls.

## Nutrition and safety policy

These rules are conservative **prototype product policies**, not a clinically
validated nutrition protocol:

- Standard estimates are offered only to eligible adults without reported medical
  concerns or relevant medications. Users may decline the equation's sex coefficient.
- Age below 18, pregnancy/breastfeeding, declared specialist nutrition care,
  recognized high-risk health terms (including kidney/liver conditions), BMI outside
  the app's 18.5–<40 planning range, two or more listed medications, and unstructured
  dietary rules pause automated planning for professional review. BMI is not used
  to diagnose a condition. Input limits are 13–100 years, 120–230 cm, 30–300 kg.
- Other reported conditions, any health notes, single medications and uncertain
  screening answers withhold calorie/BMI/macro targets. General meal ideas can still
  be generated with cautious context and professional-referral notices. These are
  not therapeutic diets and should be reviewed before use.
- Mifflin–St Jeor is calculated as `10*kg + 6.25*cm - 5*years + coefficient`
  (`+5` male, `-161` female). Activity multipliers are explicitly listed in the UI.
  Maintenance uses unrounded resting energy. Goal adjustments are ±10%, floored at
  calculated resting energy. No goal-weight or time-to-weight promises are made.
- Illustrative macro targets use 20% protein, 50% carbohydrate and 30% fat.
  These ratios and the goal adjustment are app defaults, not a medical prescription.
- Meal estimates must have finite, bounded numeric nutrients. Energy must agree
  with `4*protein + 4*carbohydrate + 9*fat` within the larger of 30 kcal or 20%.
  Eligible daily totals must be within 20% of estimated calories and within the
  larger of 10 g or 35% of each macro target. Replacements must also stay within
  25% of the original meal's calories when targets are enabled. These tolerances
  catch inconsistent output; they cannot prove nutrition accuracy.
- Food matching includes common aliases for the nine major allergen groups, extra
  shellfish terms, supported diets/restrictions, and literal custom ingredients.
  It checks meal names, ingredients, portions, explanations and chat answers.
  It is deliberately conservative: for example, names such as “almond milk” can be
  rejected for a milk restriction. It does not certify ingredient provenance,
  hidden ingredients, cross-contact, synonyms in every language, or product labels.
- Free-text dietary rules pause generation because exact food matching cannot
  reliably interpret them. Use structured restrictions and explicit ingredient
  names; custom ingredients still have incomplete synonym coverage.
- Medical/medication/target-change requests matching the local safety filter get a
  fixed referral response without an API call. AI outputs with recognized clinical
  terms, unsupported claims, external links or embedded HTML are withheld. These
  are defense-in-depth checks, not a complete semantic safety classifier. A model
  can still produce incorrect guidance that lexical checks do not detect.
- Medication names/doses/frequencies are context, not an interactions database.
  The app provides pharmacist referrals instead of inventing verified interactions.
  New persistent allergies or health details must be saved through the profile and
  trigger a fresh plan; chat cannot silently change the clinical/constraint record.

### Evidence and API references

The equation follows Mifflin et al., *A new predictive equation for resting energy
expenditure in healthy individuals*, 1990, PMID **2305711**, DOI
**10.1093/ajcn/51.2.241**. Adult-only cautions are consistent with the NIDDK's
*About the Body Weight Planner* disclaimer (not an endorsement of this app's
policy). Allergen group names use the FDA's *Food Allergies: What You Need to Know*;
FDA guidance emphasizes labels and cross-contact, which this app cannot verify.
The adapter uses the official *Groq API Reference*, *Structured Outputs* documentation,
and `groq/groq-python` SDK interfaces. JSON mode provides syntax, not application
schema or medical-safety validation; the local validators are still necessary.

## Privacy and operational limits

- No authentication, durable history, clinical audit trail or cross-device syncing.
- State is held by the Streamlit server for the browser session. Reload/disconnect
  or server restart may discard it. No shared cache stores health profiles.
- Groq receives profile details and relevant recent conversation after consent.
  Provider and hosting retention/access controls must be evaluated before real
  sensitive-data use. Clearing the app does not delete provider records or exports.
- No live FDA/drug database, food nutrient database, clinical approval, or compliance
  certification is claimed. Do not deploy as a clinical service without qualified
  review, security/privacy assessment and stronger verification.
- PDF uses ReportLab's standard fonts; unsupported characters are replaced with
  `?` in the PDF rather than causing failure. JSON and CSV preserve Unicode.
- There is no offline AI fallback or synthetic demo presented as a real plan.
  With missing dependencies/key or unavailable models, configure the deployment;
  do not expect live generation to work in this document-editing environment.

## Validation performed

In this workspace, Python syntax parsing and dependency-free, inline checks covered
known equation outputs, goal adjustments, all duration options and bounds,
missing/inconsistent inputs, minors and higher-risk referral, cautious targets,
all nine allergen groups, dietary restrictions, complete batch ordering, nutrition
totals, immutable meal replacement, mocked Groq responses, one-shot output repair,
truncated responses, auth/rate-limit/server failures, medication referral without
an API call, export privacy and spreadsheet formula escaping.

A lightweight Streamlit stub also exercised all wizard pages, conditional medication
rows, custom duration, empty/complete/referral views, proposal application and stale
proposal rejection, plus checkpoint/resume after a simulated mid-plan failure.
This checks Python control flow only; it does not verify real Streamlit widget
lifecycle, browser layout, SDK compatibility or ReportLab output.

**Still required in an environment with the declared dependencies:**

1. Launch without an API key; verify onboarding/eligible estimates remain available.
2. Navigate back and forth through all wizard steps, including conditional medication
   rows and custom duration; verify retained values and profile regeneration.
3. With a real key, generate a short plan and a 30-day plan; verify all requested days,
   model JSON compatibility, actual latency/cost and ingredient/portion plausibility.
4. Exercise a quota/network failure mid-plan and resume without losing accepted days.
5. Request, discard and apply alternatives; verify other days and meals do not change.
6. Review allergy cases and health contexts with qualified domain reviewers, including
   attempts to bypass prompts and uncommon ingredient/drug names.
7. Download PDF, JSON and CSV before/after replacement; inspect PDF pagination and
   sensitive-data opt-in. Verify profile changes clear old selectors and proposals.
8. Test browser refresh, Clear session, multiple concurrent users and mobile layout.

## PRD section 26 — future development

The PRD explicitly labels progress/adherence tracking, grocery lists, recipes,
food database integration, food-image recognition, smart reassessment and professional
integration as **future** work. These are not implemented as production features in
this core upgrade. Local/cultural food preference input is implemented; location-aware
food data is not. In particular, there is no pretend food-image analysis or unverified
clinical-professional integration. Those features need separately defined storage,
data sources, model capabilities, privacy controls and clinical review requirements.