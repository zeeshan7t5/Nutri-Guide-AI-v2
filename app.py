"""NutriGuide AI: profile → safety → estimates → validated plan → refinement."""

import copy
import json
import os

import streamlit as st
from dotenv import load_dotenv

from ai_service import AIError, NutritionAI
from exports import export_csv, export_document, export_pdf
from nutrition import (
    ACTIVITY, ALLERGENS, ALLERGY_NOTICE, CONDITIONS, DIETS, DISCLAIMER, GOALS,
    MEALS, RESTRICTIONS, SCREENING, ValidationError, assess_safety,
    calculate_nutrition, replace_meal, validate_profile,
)


st.set_page_config(page_title="NutriGuide AI", page_icon="🥗", layout="wide")
load_dotenv()

STEPS = ["Your profile", "Health context", "Food preferences", "Goal & duration", "Review"]
DEFAULT_PROFILE = {
    "age": 30, "sex": "Female", "height_cm": 165.0, "weight_kg": 65.0,
    "activity": "Moderately active", "condition_status": "No", "conditions": [],
    "other_condition": "", "health_notes": "", "medication_status": "No", "medications": [],
    "pregnant_or_breastfeeding": False, "specialist_care": False,
    "diet": "Omnivore", "allergies": [], "other_allergies": [], "restrictions": [],
    "avoid_foods": [], "diet_notes": "", "favourite_foods": "", "cuisine": "", "budget": "",
    "goal": "General healthy eating", "duration": 30, "consent": False,
}
DEFAULT_STATE = {
    "page": "home", "wizard_step": 0, "draft": DEFAULT_PROFILE,
    "profile": None, "nutrition": None, "safety": None,
    "days": [], "history": [], "pending": None, "revision": 0, "pdf": None,
}
for state_key, default_value in DEFAULT_STATE.items():
    if state_key not in st.session_state:
        st.session_state[state_key] = copy.deepcopy(default_value)

st.markdown("""
<style>
    :root {
        color-scheme:light;
        --leaf:#176b58; --leaf-dark:#105040; --mint:#e4f1e9;
        --paper:#f7f5f0; --surface:#ffffff; --ink:#1e293b;
        --muted:#526174; --line:#d5ded8; --input-border:#7e8e88;
        --focus:#a95b00;
    }
    .stApp { background:var(--paper); color:var(--ink); }
    [data-testid="stHeader"] { background:var(--paper); color:var(--ink); }
    [data-testid="stSidebar"] { background:#eeefe9; border-right:1px solid var(--line); }
    .block-container { max-width:1180px; padding:2rem 2rem 4rem; }
    h1,h2,h3,h4,h5,h6 { color:var(--ink) !important; letter-spacing:-.025em; }
    [data-testid="stMarkdownContainer"], [data-testid="stText"],
    [data-testid="stWidgetLabel"], [data-testid="stWidgetLabel"] p,
    [data-testid="stMetricLabel"], [data-testid="stMetricValue"],
    [data-testid="stExpander"] summary { color:var(--ink) !important; }
    [data-testid="stCaptionContainer"],
    [data-testid="stCaptionContainer"] [data-testid="stMarkdownContainer"] {
        color:var(--muted) !important;
    }
    [data-testid="stMarkdownContainer"] a { color:var(--leaf); text-decoration:underline; }
    .brand { color:var(--leaf); font-size:1.15rem; font-weight:750; margin-bottom:1rem; }
    .eyebrow { text-transform:uppercase; letter-spacing:.12em; color:var(--leaf); font-size:.78rem; }
    .hero {
        background:var(--surface); border:1px solid var(--line); border-left:6px solid var(--leaf);
        border-radius:18px; padding:2rem; margin:1rem 0 2rem;
        box-shadow:0 8px 28px rgba(30,41,59,.05);
    }
    .hero h1 { font-size:clamp(2rem,5vw,3.5rem); max-width:750px; }
    .hero p { max-width:650px; font-size:1.1rem; color:var(--muted); line-height:1.65; }
    [data-testid="stMetric"], [data-testid="stExpander"], [data-testid="stForm"] {
        background:var(--surface); border:1px solid var(--line); border-radius:14px; padding:.8rem;
    }
    [data-testid="stMetricValue"] { font-weight:700; }
    [data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="textarea"],
    [data-baseweb="select"] > div, [data-testid="stChatInput"] {
        background:var(--surface) !important; color:var(--ink) !important;
        border-color:var(--input-border) !important;
    }
    .stApp input, .stApp textarea, [data-baseweb="select"] input {
        background:var(--surface) !important; color:var(--ink) !important;
        -webkit-text-fill-color:var(--ink); caret-color:var(--leaf);
    }
    .stApp input::placeholder, .stApp textarea::placeholder {
        color:var(--muted) !important; -webkit-text-fill-color:var(--muted); opacity:1;
    }
    [data-baseweb="select"] [data-baseweb="tag"] {
        background:var(--mint) !important; color:var(--leaf-dark) !important;
    }
    [data-baseweb="select"] span, [data-baseweb="select"] svg { color:inherit; }
    [data-baseweb="popover"], [data-baseweb="menu"], [role="listbox"], [role="option"] {
        background:var(--surface) !important; color:var(--ink) !important;
    }
    [role="option"]:hover, [role="option"][aria-selected="true"] {
        background:var(--mint) !important; color:var(--leaf-dark) !important;
    }
    [data-testid="stNumberInput"] button {
        background:#edf2ee !important; color:var(--ink) !important;
    }
    .stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button {
        background:var(--surface); color:var(--ink); border:1px solid var(--input-border);
        border-radius:10px; min-height:44px; font-weight:600;
    }
    .stButton > button [data-testid="stMarkdownContainer"],
    .stDownloadButton > button [data-testid="stMarkdownContainer"],
    [data-testid="stFormSubmitButton"] > button [data-testid="stMarkdownContainer"] {
        color:inherit !important;
    }
    .stButton > button:hover:not(:disabled), .stDownloadButton > button:hover:not(:disabled),
    [data-testid="stFormSubmitButton"] > button:hover:not(:disabled) {
        background:var(--mint); color:var(--leaf-dark); border-color:var(--leaf);
    }
    .stButton > button[kind="primary"], [data-testid="stFormSubmitButton"] > button[kind="primary"] {
        background:var(--leaf); border-color:var(--leaf); color:#ffffff;
    }
    .stButton > button[kind="primary"]:hover:not(:disabled),
    [data-testid="stFormSubmitButton"] > button[kind="primary"]:hover:not(:disabled) {
        background:var(--leaf-dark); border-color:var(--leaf-dark); color:#ffffff;
    }
    .stButton > button:disabled, .stDownloadButton > button:disabled,
    [data-testid="stFormSubmitButton"] > button:disabled {
        background:#e5e9e5; color:var(--muted); border-color:var(--input-border); opacity:1;
        cursor:not-allowed;
    }
    .stApp button:focus-visible, .stApp a:focus-visible, .stApp input:focus-visible,
    .stApp textarea:focus-visible, [data-baseweb="select"]:focus-within {
        outline:3px solid var(--focus) !important; outline-offset:3px;
    }
    [data-baseweb="tab-list"] { background:#e9eee9; padding:.35rem; border-radius:12px; gap:.35rem; }
    button[data-baseweb="tab"] { color:var(--muted) !important; border-radius:8px; }
    button[data-baseweb="tab"][aria-selected="true"] { background:var(--surface); color:var(--leaf-dark) !important; }
    button[data-baseweb="tab"] [data-testid="stMarkdownContainer"] { color:inherit !important; }
    [data-baseweb="tab-highlight"] { background:var(--leaf); }
    [data-testid="stChatMessage"] { background:var(--surface); border:1px solid var(--line); border-radius:14px; }
    [data-testid="stBottomBlockContainer"] { background:var(--paper); }
    [data-testid="stAlert"] {
        background:#fff4dc !important; border:1px solid #c18b36 !important;
        border-left:4px solid #946000 !important; color:#654315 !important; border-radius:12px;
    }
    [data-testid="stAlert"] [data-testid="stMarkdownContainer"] { color:#654315 !important; }
    [data-testid="stAlert"] svg { color:#654315 !important; }
    [data-testid="stAlert"]:has([data-testid="stAlertContentInfo"]) {
        background:#edf4fc !important; border-color:#7593b8 !important; border-left-color:#315b8a !important;
    }
    [data-testid="stAlertContentInfo"] [data-testid="stMarkdownContainer"],
    [data-testid="stAlert"]:has([data-testid="stAlertContentInfo"]) svg { color:#284b73 !important; }
    [data-testid="stAlert"]:has([data-testid="stAlertContentError"]) {
        background:#fff0ee !important; border-color:#c7817a !important; border-left-color:#a13232 !important;
    }
    [data-testid="stAlertContentError"] [data-testid="stMarkdownContainer"],
    [data-testid="stAlert"]:has([data-testid="stAlertContentError"]) svg { color:#8f2929 !important; }
    [data-testid="stAlert"]:has([data-testid="stAlertContentSuccess"]) {
        background:var(--mint) !important; border-color:#78a28d !important; border-left-color:var(--leaf) !important;
    }
    [data-testid="stAlertContentSuccess"] [data-testid="stMarkdownContainer"],
    [data-testid="stAlert"]:has([data-testid="stAlertContentSuccess"]) svg { color:var(--leaf-dark) !important; }
    hr { border-color:var(--line) !important; }
    @media(max-width:760px) { .block-container {padding:1.2rem 1rem 3rem;} .hero {padding:1.3rem;} }
</style>
""", unsafe_allow_html=True)


def setting(name, fallback=""):
    try:
        value = st.secrets.get(name)
    except (FileNotFoundError, RuntimeError, KeyError):
        value = None
    return str(value or os.getenv(name, fallback)).strip()


def get_ai():
    return NutritionAI(setting("GROQ_API_KEY"), setting("GROQ_MODEL", "openai/gpt-oss-120b"))


def navigate(page):
    st.session_state.page = page
    st.rerun()


def clear_session():
    for key in list(st.session_state):
        del st.session_state[key]
    st.rerun()


def select_field(field, label, options):
    data = st.session_state.draft
    data[field] = st.selectbox(label, list(options), index=list(options).index(data[field]), key=f"profile_{field}")


def text_field(field, label, help_text=None):
    data = st.session_state.draft
    data[field] = st.text_area(label, value=data[field], max_chars=1000, help=help_text, key=f"profile_{field}")


def list_field(field, label):
    data = st.session_state.draft
    value = st.text_area(label, value="\n".join(data[field]), max_chars=2000,
                         help="One ingredient or food per line; use English ingredient names. Do not enter sentences or 'none'.",
                         key=f"profile_{field}")
    data[field] = [item.strip() for item in value.replace(",", "\n").splitlines() if item.strip()]


def multi_field(field, label, options):
    data = st.session_state.draft
    data[field] = st.multiselect(label, options, default=data[field], key=f"profile_{field}")


def show_safety(safety):
    st.caption(DISCLAIMER)
    if safety["reasons"]:
        st.warning("\n\n".join(safety["reasons"]))
    if safety["blocked"]:
        st.info("Personalized plan generation is paused. Bring your profile to a qualified professional; this app cannot provide medical nutrition therapy.")
    st.caption(ALLERGY_NOTICE)


def show_estimates(nutrition):
    if nutrition["calories"] is None:
        st.info("No automated calorie, BMI or macro targets are shown for this profile. Any available meals are general ideas, not a prescribed diet.")
        return
    columns = st.columns(4)
    for column, label, field in zip(columns, ["BMI (screening estimate)", "Resting energy (kcal/day)", "Maintenance (kcal/day)", "Goal estimate (kcal/day)"], ["bmi", "bmr", "tdee", "calories"]):
        column.metric(label, nutrition[field])
    st.caption("Illustrative daily macro distribution: " + " · ".join(f"{label} {nutrition['macros'][field]} g" for label, field in [("Protein", "protein_g"), ("Carbohydrate", "carbs_g"), ("Fat", "fat_g")]))
    with st.expander("How estimates are calculated"):
        st.write("Mifflin–St Jeor: 10 × weight (kg) + 6.25 × height (cm) − 5 × age + sex coefficient (+5 male, −161 female). Maintenance = resting estimate × activity multiplier.")
        st.write("App policy: weight-loss and weight-gain goals adjust estimated maintenance by −10% and +10%; other goals use maintenance. The estimate never falls below the calculated resting energy. Macros use an illustrative 20% protein / 50% carbohydrate / 30% fat split, not an individualized clinical prescription.")
        st.write("Activity multipliers: " + "; ".join(f"{name}: {factor}" for name, factor in ACTIVITY.items()))
        st.caption("These are configurable product assumptions, not a guarantee of an appropriate intake. Meal nutrients are AI estimates; totals are added and checked by Python. Source: Mifflin et al., 1990, PMID 2305711.")


def show_home():
    st.markdown('<div class="hero"><div class="eyebrow">Personal nutrition, thoughtfully planned</div><h1>A plan that fits your life.<br>And changes with it.</h1><p>Build practical meals around your preferences, understand the estimates, and adjust one meal without starting over.</p></div>', unsafe_allow_html=True)
    columns = st.columns(3)
    for column, title, text in zip(columns, ["01 · Get understood", "02 · Make a plan", "03 · Make it yours"], ["Your routine, food preferences and relevant health context.", "1–90 days, with portions and estimated nutrients. Default: 30 days.", "Ask questions, preview alternatives and apply only the changes you want."]):
        with column:
            st.subheader(title)
            st.write(text)
    st.info("Built for general adult nutrition support. Higher-risk profiles are referred for professional review rather than receiving an automated diet.")
    if st.button("Build my nutrition plan", type="primary"):
        navigate("profile")
    if st.session_state.profile and st.button("Return to current plan"):
        navigate("plan")
    with st.expander("Privacy and limitations"):
        st.write("No account or database is used. Your inputs and plan are held in this Streamlit server session, not deliberately saved to application files. A page reload or server restart can lose them. Use Clear session to remove this session's application state.")
        st.write("AI requests send your profile, health and medication information, relevant meals and recent chat to Groq. Only proceed with your consent; do not enter names or identifying details. Your hosting and API providers have their own logging and retention practices. Clearing this session does not delete provider records or downloaded files.")
        st.write("This prototype is not clinically validated, an interaction checker, or an allergy-certified system.")
    st.caption(DISCLAIMER)


def show_profile():
    current = st.session_state.wizard_step
    data = st.session_state.draft
    st.title("Tell us what works for you")
    st.progress((current + 1) / len(STEPS))
    st.caption(f"Step {current + 1} of {len(STEPS)} · {STEPS[current]}")
    if current == 0:
        st.subheader("Your everyday profile")
        left, right = st.columns(2)
        with left:
            data["age"] = st.number_input("Age (years)", 13, 100, int(data["age"]), key="profile_age")
            select_field("sex", "Sex coefficient for the energy equation", ["Female", "Male", "Prefer not to use this equation"])
            st.caption("The original equation uses binary sex coefficients; this is not a question about gender identity. You can opt out of calorie estimates.")
        with right:
            data["height_cm"] = st.number_input("Height (cm)", 120.0, 230.0, float(data["height_cm"]), step=0.5, key="profile_height")
            data["weight_kg"] = st.number_input("Weight (kg)", 30.0, 300.0, float(data["weight_kg"]), step=0.5, key="profile_weight")
        select_field("activity", "Usual activity level", ACTIVITY)
        st.caption("Sedentary: little exercise · Light: 1–3 days/week · Moderate: 3–5 · Very active: 6–7 · Extra: highly physical work plus exercise. These categories are approximate.")
    elif current == 1:
        st.subheader("Health and medication context")
        select_field("condition_status", "Do you have any medical condition that may affect your diet or nutritional needs?", SCREENING)
        if data["condition_status"] == "Yes":
            multi_field("conditions", "Conditions (select all that apply)", CONDITIONS)
            text_field("other_condition", "Other condition or additional details")
        else:
            data["conditions"], data["other_condition"] = [], ""
        data["pregnant_or_breastfeeding"] = st.checkbox("Pregnant or breastfeeding", value=data["pregnant_or_breastfeeding"], key="profile_pregnancy")
        data["specialist_care"] = st.checkbox("I need specialist nutrition care (for example, an eating disorder, severe malnutrition or complex diabetes management)", value=data["specialist_care"], key="profile_specialist")
        text_field("health_notes", "Other health information (optional)", "Any health notes suspend standard calorie targets pending professional advice.")
        select_field("medication_status", "Are you taking medications that may be relevant to diet or nutrition?", SCREENING)
        if data["medication_status"] == "Yes":
            count = st.number_input("Number of medications", 1, 10, max(1, len(data["medications"])), key="medication_count")
            existing = data["medications"]
            medications = []
            for index in range(count):
                medication = existing[index] if index < len(existing) else {"name": "", "dose": "", "frequency": ""}
                columns = st.columns(3)
                record = {}
                for column, field, label in zip(columns, ["name", "dose", "frequency"], ["Name", "Strength / dose (optional)", "Frequency (optional)"]):
                    record[field] = column.text_input(f"Medication {index + 1}: {label}", value=medication[field], max_chars=120, key=f"medication_{index}_{field}")
                medications.append(record)
            data["medications"] = medications
        else:
            data["medications"] = []
        st.info("Medication details are dietary context only. The app cannot verify interactions or advise changes to medication. Ask your pharmacist.")
    elif current == 2:
        st.subheader("Food preferences and boundaries")
        select_field("diet", "Dietary preference", DIETS)
        multi_field("allergies", "Food allergies", list(ALLERGENS))
        list_field("other_allergies", "Other food allergens")
        multi_field("restrictions", "Dietary restrictions", RESTRICTIONS)
        list_field("avoid_foods", "Foods you dislike or want to avoid")
        text_field("diet_notes", "Other dietary rules (optional)", "Complex free-text rules require professional review; structured restrictions and foods-to-avoid support automated checking.")
        text_field("favourite_foods", "Favourite or available foods")
        text_field("cuisine", "Preferred cuisine or local food traditions (optional)")
        text_field("budget", "Budget and cooking constraints (optional)")
        st.caption(ALLERGY_NOTICE)
    elif current == 3:
        st.subheader("Your goal and planning horizon")
        select_field("goal", "Primary nutrition goal", GOALS)
        choices = [7, 14, 30, 60, 90, "Custom"]
        current_duration = data["duration"] if data["duration"] in choices else "Custom"
        duration = st.selectbox("Plan duration", choices, index=choices.index(current_duration), format_func=lambda value: f"{value} days" if isinstance(value, int) else value, key="duration_choice")
        if duration == "Custom":
            data["duration"] = st.number_input("Custom duration (days)", 1, 90, int(data["duration"]), key="custom_duration")
        else:
            data["duration"] = duration
        st.caption("30 days is the recommended default. Custom plans are limited to 90 days per profile to bound API cost and response size. Long plans are generated in small, resumable batches.")
    else:
        st.subheader("Review before anything is sent")
        st.write(f"{data['age']} years · {data['height_cm']:g} cm · {data['weight_kg']:g} kg · {data['activity']}")
        st.write(f"{data['goal']} · {data['diet']} · {data['duration']} days")
        with st.expander("Review all profile fields"):
            st.json({key: value for key, value in data.items() if key != "consent"})
        st.warning("Generating a new plan replaces the current plan and clears its chat and pending edits. Download the current plan first if you want to keep it.")
        data["consent"] = st.checkbox("I understand this is general education and consent to sending my profile, health/medication context and relevant conversation to Groq when I use AI features.", value=data["consent"], key="profile_consent")
        try:
            reviewed = validate_profile({**data, "consent": True})
            safety = assess_safety(reviewed)
            show_safety(safety)
            show_estimates(calculate_nutrition(reviewed, safety))
        except ValidationError as error:
            st.error(str(error))
        if st.button("Save profile & open plan", type="primary", disabled=not data["consent"]):
            try:
                profile = validate_profile(data)
                safety = assess_safety(profile)
                st.session_state.update({"profile": profile, "safety": safety,
                                         "nutrition": calculate_nutrition(profile, safety),
                                         "days": [], "history": [], "pending": None,
                                         "revision": st.session_state.revision + 1, "pdf": None})
                for key in ["view_day", "chat_day", "chat_slot", "export_profile"]:
                    st.session_state.pop(key, None)
                navigate("plan")
            except ValidationError as error:
                st.error(str(error))
    st.divider()
    back, forward = st.columns(2)
    if back.button("Back" if current else "Home", use_container_width=True):
        if current:
            st.session_state.wizard_step -= 1
            st.rerun()
        navigate("home")
    if current < len(STEPS) - 1 and forward.button("Continue", type="primary", use_container_width=True):
        st.session_state.wizard_step += 1
        st.rerun()


def generate_days(limit=None):
    profile = st.session_state.profile
    progress = st.progress(len(st.session_state.days) / profile["duration"])
    try:
        ai = get_ai()
        remaining = profile["duration"] - len(st.session_state.days)
        end_day = len(st.session_state.days) + (min(limit, remaining) if limit else remaining)
        while len(st.session_state.days) < end_day:
            first = len(st.session_state.days) + 1
            day_numbers = list(range(first, min(first + 2, end_day + 1)))
            with st.spinner(f"Generating and validating days {day_numbers[0]}–{day_numbers[-1]}…"):
                batch = ai.generate_batch(profile, st.session_state.nutrition, st.session_state.safety, day_numbers, st.session_state.days)
            st.session_state.days = st.session_state.days + batch
            st.session_state.revision += 1
            st.session_state.pending = None
            st.session_state.pdf = None
            progress.progress(len(st.session_state.days) / profile["duration"])
        st.rerun()
    except (AIError, ValidationError) as error:
        st.error(str(error))
        st.info(f"{len(st.session_state.days)} validated days retained. Retry to resume at the next missing day; the profile is unchanged.")


def render_meal(meal):
    st.subheader(meal["name"])
    st.write(f"Portion: {meal['portion']}")
    st.caption(f"Estimated {meal['calories']:g} kcal · Protein {meal['protein_g']:g} g · Carbs {meal['carbs_g']:g} g · Fat {meal['fat_g']:g} g")
    for ingredient in meal["ingredients"]:
        st.write(f"• {ingredient['name']} — {ingredient['quantity']}")
    st.write(meal["explanation"])


def request_edit(message, day_number, slot):
    st.session_state.pending = None
    try:
        with st.spinner("Checking your request against your profile and selected meal…"):
            response = get_ai().converse(message, st.session_state.profile, st.session_state.nutrition,
                                         st.session_state.safety, st.session_state.days,
                                         day_number, slot, st.session_state.history)
        st.session_state.history += [{"role": "user", "content": f"Day {day_number}, {slot}: {message}"},
                                     {"role": "assistant", "content": response["answer"]}]
        st.session_state.history = st.session_state.history[-40:]
        if response["replacement"] is not None:
            st.session_state.pending = {"day": day_number, "slot": slot,
                                        "meal": response["replacement"], "revision": st.session_state.revision}
        st.rerun()
    except (AIError, ValidationError) as error:
        st.error(str(error))
        st.caption("Your current plan has not changed. You can retry or rephrase the request.")


def show_pending():
    pending = st.session_state.pending
    if not pending:
        return
    st.info(f"Proposed change only: day {pending['day']}, {pending['slot']}. Nothing changes until you apply it.")
    render_meal(pending["meal"])
    apply_column, discard_column = st.columns(2)
    if apply_column.button("Apply this replacement", type="primary"):
        try:
            if pending["revision"] != st.session_state.revision:
                raise ValidationError("The plan has changed. Request a fresh alternative.")
            st.session_state.days = replace_meal(st.session_state.days, pending["day"], pending["slot"], pending["meal"], st.session_state.profile, st.session_state.nutrition)
            st.session_state.revision += 1
            st.session_state.pdf = None
            st.session_state.pending = None
            st.session_state.history.append({"role": "assistant", "content": f"Applied replacement to day {pending['day']}, {pending['slot']}. Other meals are unchanged."})
            st.rerun()
        except ValidationError as error:
            st.session_state.pending = None
            st.error(str(error))
    if discard_column.button("Discard proposal"):
        st.session_state.pending = None
        st.session_state.history.append({"role": "assistant", "content": "Proposal discarded. The plan has not changed."})
        st.rerun()


def show_downloads():
    st.subheader("Take your plan with you")
    st.caption("Exports include all generated days, current replacements, estimated totals and safety notes. Partial plans are labeled. Profile, health and medication details are excluded unless you opt in.")
    include_profile = st.checkbox("Include sensitive profile / health / medication details in exports", key="export_profile")
    document = export_document(st.session_state.profile, st.session_state.nutrition, st.session_state.safety, st.session_state.days, include_profile)
    st.download_button("Download plan JSON", json.dumps(document, ensure_ascii=False, indent=2), "nutriguide-plan.json", "application/json")
    st.download_button("Download meals CSV", export_csv(st.session_state.days), "nutriguide-meals.csv", "text/csv")
    if st.button("Prepare PDF report"):
        try:
            st.session_state.pdf = {"data": export_pdf(document), "revision": st.session_state.revision, "include_profile": include_profile}
        except ImportError:
            st.error("PDF export requires reportlab from requirements.txt in your deployment environment.")
    cached = st.session_state.pdf
    if cached and cached["revision"] == st.session_state.revision and cached["include_profile"] == include_profile:
        st.download_button("Download PDF report", cached["data"], "nutriguide-plan.pdf", "application/pdf")


def show_plan():
    if st.session_state.profile is None:
        st.info("Create a profile first.")
        if st.button("Create profile"):
            navigate("profile")
        return
    profile = st.session_state.profile
    safety = st.session_state.safety
    st.title(f"Your {profile['duration']}-day nutrition plan")
    st.caption(f"{profile['goal']} · {profile['diet']} · {safety['status']}")
    if st.button("Edit profile"):
        for key in list(st.session_state):
            if key.startswith(("profile_", "medication_")) or key in ["duration_choice", "custom_duration"]:
                del st.session_state[key]
        st.session_state.draft = copy.deepcopy(profile)
        st.session_state.wizard_step = 0
        st.session_state.pending = None
        navigate("profile")
    show_safety(safety)
    show_estimates(st.session_state.nutrition)
    if safety["blocked"]:
        with st.expander("Export profile for a professional consultation"):
            show_downloads()
        return
    generated = len(st.session_state.days)
    st.progress(generated / profile["duration"])
    st.write(f"{generated} / {profile['duration']} days generated and validated" + (" · Complete" if generated == profile["duration"] else " · Partial plan"))
    if generated < profile["duration"]:
        st.caption("Each request generates at most two days. Completed batches are retained if a later request fails. Long plans can take several minutes and incur API charges; six-day chunks let you pause between requests.")
        left, right = st.columns(2)
        if left.button("Generate next 6 days", type="primary", disabled=not setting("GROQ_API_KEY")):
            generate_days(6)
        if right.button("Generate / resume all remaining days", disabled=not setting("GROQ_API_KEY")):
            generate_days()
    if not st.session_state.days:
        return
    plan_tab, chat_tab, export_tab = st.tabs(["Daily meals", "Ask & refine", "Downloads"])
    with plan_tab:
        selected_day = st.selectbox("View day", [day["day"] for day in st.session_state.days], key="view_day")
        day = next(day for day in st.session_state.days if day["day"] == selected_day)
        totals = day["totals"]
        st.write(f"Estimated daily total: **{totals['calories']:g} kcal** · Protein {totals['protein_g']:g} g · Carbs {totals['carbs_g']:g} g · Fat {totals['fat_g']:g} g")
        for meal in day["meals"]:
            with st.expander(meal["slot"].title(), expanded=True):
                render_meal(meal)
        st.caption("Want a different ingredient or meal? Open Ask & refine and select this day and meal.")
    with chat_tab:
        st.subheader("A small change, not a fresh start")
        st.caption("Select the exact day and meal before asking a question or requesting a change. Persistent food rules, new allergies and health updates belong in Edit profile. Chat retains the last 40 messages; only the most recent 8 accompany each request.")
        left, right = st.columns(2)
        day_number = left.selectbox("Conversation day", [day["day"] for day in st.session_state.days], key="chat_day")
        slot = right.selectbox("Conversation meal", MEALS, format_func=str.title, key="chat_slot")
        for message in st.session_state.history:
            with st.chat_message(message["role"]):
                st.write(message["content"])
        show_pending()
        with st.form("meal_alternative"):
            instructions = st.text_input("Alternative / ingredient request", max_chars=1200, placeholder="I don't have oats; use another ingredient. Or: make this dinner cheaper.")
            if st.form_submit_button("Suggest an alternative", disabled=not setting("GROQ_API_KEY")):
                request_edit(instructions or "Suggest a different meal with similar nutritional balance.", day_number, slot)
        message = st.chat_input("Ask why this meal was chosen, or request a change", max_chars=1500, disabled=not setting("GROQ_API_KEY"))
        if message:
            request_edit(message, day_number, slot)
    with export_tab:
        show_downloads()


st.markdown('<div class="brand">🥗 NutriGuide AI · personalized nutrition support</div>', unsafe_allow_html=True)
with st.sidebar:
    st.header("NutriGuide AI")
    if st.button("Home", use_container_width=True):
        navigate("home")
    if st.session_state.profile and st.button("Current plan", use_container_width=True):
        navigate("plan")
    st.caption("Session-only storage. Download your work before refreshing or leaving.")
    confirm_clear = st.checkbox("I understand clearing removes this session's profile, plan and chat")
    if st.button("Clear session", disabled=not confirm_clear, use_container_width=True):
        clear_session()
if not setting("GROQ_API_KEY"):
    st.warning("AI is not configured. You can still review the app, enter a profile and calculate eligible estimates. Set GROQ_API_KEY in your environment or Streamlit secrets to generate meals and chat.")

if st.session_state.page == "profile":
    show_profile()
elif st.session_state.page == "plan":
    show_plan()
else:
    show_home()
