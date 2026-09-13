"""Deterministic profile, nutrition and output validation; no UI or API dependencies."""

import copy
import math
import re
import unicodedata


ACTIVITY = {
    "Sedentary": 1.2,
    "Lightly active": 1.375,
    "Moderately active": 1.55,
    "Very active": 1.725,
    "Extra active": 1.9,
}
GOALS = ["Weight loss", "Weight maintenance", "Weight gain", "General healthy eating"]
DIETS = ["Omnivore", "Vegetarian", "Vegan", "Pescatarian"]
SCREENING = ["No", "Yes", "Not sure"]
CONDITIONS = [
    "Diabetes", "Hypertension", "Cardiovascular disease", "Kidney disease",
    "Liver disease", "Gastrointestinal conditions", "Thyroid disorders", "Anemia",
    "Eating disorder", "Severe malnutrition", "Other",
]
MEALS = ["breakfast", "lunch", "dinner", "snack"]
NUTRIENTS = ["calories", "protein_g", "carbs_g", "fat_g"]
DISCLAIMER = (
    "General nutrition education, not medical advice or a treatment diet. "
    "Calorie and nutrient values are estimates, not lab-tested measurements. "
    "Do not start, stop, or change medication based on this app. "
    "Consult a registered dietitian, physician, or pharmacist for individualized care."
)
CONSULTATION_NOTE = (
    "Kindly consult a medical officer or registered dietitian for professional advice "
    "before making dietary changes. Ask a pharmacist about food–medication interactions."
)
ALLERGY_NOTICE = (
    "Ingredient screening is not an allergy-safety guarantee. Check every ingredient, "
    "product label and preparation environment for allergens and cross-contact. "
    "Never eat an uncertain food; ask your allergy clinician or the manufacturer."
)
ALLERGENS = {
    "Milk": ["milk", "dairy", "cheese", "yogurt", "yoghurt", "butter", "cream", "whey", "casein", "ghee", "paneer", "kefir"],
    "Egg": ["egg", "eggs", "mayonnaise", "albumin", "meringue"],
    "Fish": ["fish", "salmon", "tuna", "cod", "sardine", "anchovy", "tilapia", "trout", "mackerel", "haddock"],
    "Shellfish": ["shellfish", "shrimp", "prawn", "crab", "lobster", "crayfish", "clam", "mussel", "oyster", "scallop", "squid"],
    "Tree nuts": ["tree nut", "nuts", "almond", "walnut", "cashew", "pecan", "pistachio", "hazelnut", "macadamia", "brazil nut", "pine nut", "marzipan"],
    "Peanut": ["peanut", "groundnut", "arachis"],
    "Wheat": ["wheat", "flour", "semolina", "bulgur", "couscous", "spelt", "farro", "seitan", "bread", "pasta", "roti", "chapati"],
    "Soy": ["soy", "soya", "soybean", "tofu", "tempeh", "edamame", "miso"],
    "Sesame": ["sesame", "tahini", "til", "gingelly"],
}
MEAT = ["beef", "pork", "chicken", "turkey", "lamb", "mutton", "bacon", "ham", "sausage", "gelatin", "gelatine", "lard", "duck", "meat"]
RESTRICTIONS = ["Gluten-free", "Dairy-free", "Egg-free", "Pork-free", "Alcohol-free"]
MEDICAL_TERMS = (
    "medication", "medicine", "prescription", "dose", "dosage", "insulin", "tablet",
    "pill", "metformin", "warfarin", "levothyroxine", "supplement", "treatment",
    "diagnose", "cure", "diabetes", "kidney", "liver", "pregnan", "breastfeed",
    "fasting", "starve", "detox", "purge", "binge", "calorie deficit", "weight loss",
)


class ValidationError(ValueError):
    pass


def normalized(value):
    return unicodedata.normalize("NFKC", str(value)).casefold().strip()


def has_term(text, term):
    return re.search(r"(?<!\w)" + re.escape(normalized(term)) + r"(?:s|es)?(?!\w)", normalized(text)) is not None


def text_value(value, label, maximum=1000, optional=False):
    if not isinstance(value, str) or len(value) > maximum or (not optional and not value.strip()):
        raise ValidationError(f"{label} must be {'non-empty ' if not optional else ''}text of at most {maximum} characters.")
    return value.strip()


def number_value(value, label, lower, upper, integer=False):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValidationError(f"{label} must be a finite number.")
    if not lower <= value <= upper or (integer and int(value) != value):
        raise ValidationError(f"{label} must be {'a whole number ' if integer else ''}between {lower} and {upper}.")
    return int(value) if integer else float(value)


def string_list(value, label, allowed=None):
    if not isinstance(value, list) or len(value) > 30:
        raise ValidationError(f"{label} must contain at most 30 entries.")
    result = [text_value(item, label, 100) for item in value]
    if allowed is not None and any(item not in allowed for item in result):
        raise ValidationError(f"Choose a supported value for {label}.")
    return list(dict.fromkeys(result))


def profile_errors(raw, step=None, require_consent=False):
    errors = {}
    groups = {}

    def check(field, group, validation):
        groups[field] = group
        try:
            validation()
        except ValidationError as error:
            errors[field] = str(error)

    for field, label, lower, upper, group in [
        ("age", "age", 13, 100, 0), ("height_cm", "height in cm", 120, 230, 0),
        ("weight_kg", "weight in kg", 30, 300, 0), ("duration", "plan duration", 1, 90, 3),
    ]:
        if raw.get(field) is None:
            groups[field] = group
            errors[field] = f"Kindly fill this field: {label}."
        else:
            check(field, group, lambda: number_value(raw[field], label, lower, upper, field in ["age", "duration"]))
    for field, label, choices, group in [
        ("sex", "an equation option", ["Female", "Male", "Prefer not to use this equation"], 0),
        ("activity", "your activity level", ACTIVITY, 0), ("goal", "your goal", GOALS, 3),
        ("diet", "a dietary preference", DIETS, 2),
        ("condition_status", "Yes, No or Not sure", SCREENING, 1),
        ("medication_status", "Yes, No or Not sure", SCREENING, 1),
    ]:
        groups[field] = group
        if raw.get(field) not in list(choices):
            errors[field] = f"Kindly select {label}."
    if raw.get("condition_status") == "Yes":
        if not raw.get("conditions") and not str(raw.get("other_condition", "")).strip():
            groups["conditions"] = 1
            errors["conditions"] = "Kindly select a condition or enter its name below. If unsure, choose Not sure."
        if isinstance(raw.get("conditions"), list) and "Other" in raw["conditions"] and not str(raw.get("other_condition", "")).strip():
            groups["other_condition"] = 1
            errors["other_condition"] = "Kindly fill this field: other condition name."
    medications = raw.get("medications", [])
    if raw.get("medication_status") == "Yes" and isinstance(medications, list):
        for index, medication in enumerate(medications or [{}]):
            field = f"medication_{index}_name"
            groups[field] = 1
            if not isinstance(medication, dict) or not str(medication.get("name", "")).strip():
                errors[field] = "Kindly fill this field: medication name. If unsure, choose Not sure."
    for field, choices, group in [("conditions", CONDITIONS, 1), ("allergies", ALLERGENS, 2), ("restrictions", RESTRICTIONS, 2), ("other_allergies", None, 2), ("avoid_foods", None, 2)]:
        check(field, group, lambda: string_list(raw.get(field, []), field, choices))
    for field in ["other_condition", "health_notes", "diet_notes", "favourite_foods", "cuisine", "budget"]:
        check(field, 1 if field in ["other_condition", "health_notes"] else 2,
              lambda: text_value(raw.get(field, ""), field, optional=True))
    if require_consent and raw.get("consent") is not True:
        groups["consent"] = 4
        errors["consent"] = "Kindly give your consent before using AI features. A local report does not need AI consent."
    return {field: message for field, message in errors.items() if step is None or groups[field] == step}


def validate_profile(raw, require_consent=False):
    if not isinstance(raw, dict):
        raise ValidationError("A profile is required.")
    errors = profile_errors(raw, require_consent=require_consent)
    if errors:
        raise ValidationError(next(iter(errors.values())))
    profile = {}
    for key, lower, upper in [("age", 13, 100), ("height_cm", 120, 230), ("weight_kg", 30, 300), ("duration", 1, 90)]:
        profile[key] = number_value(raw.get(key), key, lower, upper, key in ["age", "duration"])
    choices = {
        "sex": ["Female", "Male", "Prefer not to use this equation"],
        "activity": ACTIVITY, "goal": GOALS, "diet": DIETS,
        "condition_status": SCREENING, "medication_status": SCREENING,
    }
    for key, options in choices.items():
        if raw.get(key) not in options:
            raise ValidationError(f"Choose a supported value for {key}.")
        profile[key] = raw[key]
    for key in ["pregnant_or_breastfeeding", "specialist_care", "consent"]:
        if type(raw.get(key)) is not bool:
            raise ValidationError(f"Please answer {key}.")
        profile[key] = raw[key]
    for key, options in [("conditions", CONDITIONS), ("allergies", ALLERGENS), ("restrictions", RESTRICTIONS), ("other_allergies", None), ("avoid_foods", None)]:
        profile[key] = string_list(raw.get(key, []), key, options)
    for key in ["other_condition", "health_notes", "diet_notes", "favourite_foods", "cuisine", "budget"]:
        profile[key] = text_value(raw.get(key, ""), key, optional=True)
    medications = raw.get("medications", [])
    if not isinstance(medications, list) or len(medications) > 10:
        raise ValidationError("Provide at most 10 medications; discuss complex regimens with your pharmacist.")
    profile["medications"] = []
    if profile["medication_status"] == "Yes":
        for medication in medications:
            if not isinstance(medication, dict):
                raise ValidationError("Each medication needs a name, optional dose and optional frequency.")
            profile["medications"].append({key: text_value(medication.get(key, ""), key, 120, key != "name") for key in ["name", "dose", "frequency"]})
        if not profile["medications"]:
            raise ValidationError("Enter at least one medication name or select Not sure.")
    if profile["condition_status"] == "Yes":
        if not profile["conditions"] and not profile["other_condition"]:
            raise ValidationError("Identify your condition or select Not sure.")
        if "Other" in profile["conditions"] and not profile["other_condition"]:
            raise ValidationError("Please describe the other condition.")
    elif profile["conditions"] or profile["other_condition"]:
        raise ValidationError("Set medical condition screening to Yes when providing a condition.")
    return profile


def assess_safety(profile):
    reasons = []
    blocked = False
    bmi = profile["weight_kg"] / (profile["height_cm"] / 100) ** 2
    health = normalized(" ".join(profile["conditions"]) + " " + profile["other_condition"] + " " + profile["health_notes"])
    if profile["age"] < 18:
        reasons.append("This planning workflow is for adults; ask a qualified professional for age-appropriate nutrition support.")
        blocked = True
    if profile["pregnant_or_breastfeeding"] or profile["specialist_care"]:
        reasons.append("Pregnancy, breastfeeding or specialist nutrition care requires an individualized professional assessment.")
        blocked = True
    if any(term in health for term in ["kidney", "renal", "liver", "eating disorder", "anorexi", "bulimi", "malnutrition", "pregnan", "breastfeed", "dialysis", "type 1", "type i diabetes"]):
        reasons.append("Your report focuses on general guidance and questions for your care team; a treatment meal plan needs professional review.")
        blocked = True
    if bmi < 18.5 or bmi >= 40:
        reasons.append("These body measurements are outside this app's standard planning range; this is not a diagnosis.")
        blocked = True
    if len(profile["medications"]) >= 2:
        reasons.append("Multiple medications require a pharmacist's review of dietary considerations.")
        blocked = True
    if profile["condition_status"] != "No" or profile["health_notes"]:
        reasons.append("Discuss condition-specific nutrition with a clinician or registered dietitian. Automated calorie targets are withheld.")
    if profile["medication_status"] != "No":
        reasons.append("Ask your pharmacist about food–medication interactions. This app does not check interactions or change prescriptions; calorie targets are withheld.")
    if profile["sex"] == "Prefer not to use this equation":
        reasons.append("Calorie estimates are withheld because no equation coefficient was selected.")
    if profile["diet_notes"]:
        reasons.append("Free-text dietary rules need professional review before automated planning. Use structured restrictions or individual foods to avoid.")
        blocked = True
    return {"blocked": blocked, "standard_calories": not reasons, "reasons": reasons, "status": "Guidance report with professional review" if blocked else "Cautious guidance" if reasons else "Standard adult estimates"}


def build_guidance_report(profile, safety):
    return {
        "title": "Your nutrition guidance report",
        "mode": "guidance_only" if safety["blocked"] else "guidance_and_optional_meals",
        "summary": (
            "This report provides general nutrition support and a checklist for a professional consultation. "
            "It is not a diagnosis, treatment diet or prescription."
        ),
        "consultation_note": CONSULTATION_NOTE,
        "guidance": [
            "Use your existing clinician-provided nutrition instructions as the starting point; this report does not replace them.",
            "Record your usual meals, food preferences, allergies and any difficulties with eating to discuss at your appointment.",
            "Check ingredient labels and preparation methods against your allergies and dietary restrictions.",
            "Avoid starting restrictive diets or supplements, and do not change medication based on this report.",
        ],
        "questions_for_professional": [
            "Which foods and portions are appropriate for my conditions and current care plan?",
            "Do I need individualized energy, protein, fluid or mineral guidance?",
            "Could any of my medicines or supplements affect food choices or meal timing?",
            "What changes should I monitor, and when should my nutrition plan be reviewed?",
        ],
        "next_steps": [
            "Arrange a consultation with a medical officer or registered dietitian; take this report with you.",
            "Bring your current medication list and any existing diet instructions. Include sensitive profile details in the download only if you want to share them.",
        ],
    }


def calculate_nutrition(profile, safety):
    if not safety["standard_calories"]:
        return {"bmi": None, "bmr": None, "tdee": None, "calories": None, "macros": None}
    coefficient = 5 if profile["sex"] == "Male" else -161
    bmr = 10 * profile["weight_kg"] + 6.25 * profile["height_cm"] - 5 * profile["age"] + coefficient
    tdee = bmr * ACTIVITY[profile["activity"]]
    adjustment = {"Weight loss": -0.10, "Weight gain": 0.10}.get(profile["goal"], 0)
    target = round(max(bmr, tdee * (1 + adjustment)))
    return {
        "bmi": round(profile["weight_kg"] / (profile["height_cm"] / 100) ** 2, 1),
        "bmr": round(bmr), "tdee": round(tdee), "calories": target,
        "macros": {"protein_g": round(target * 0.20 / 4), "carbs_g": round(target * 0.50 / 4), "fat_g": round(target * 0.30 / 9)},
    }


def blocked_terms(profile):
    terms = set()
    for allergen in profile["allergies"]:
        terms.update(ALLERGENS[allergen])
    for term in profile["other_allergies"] + profile["avoid_foods"]:
        terms.add(normalized(term))
        for aliases in ALLERGENS.values():
            if any(has_term(term, alias) for alias in aliases):
                terms.update(aliases)
    if profile["diet"] in ["Vegetarian", "Vegan", "Pescatarian"]:
        terms.update(MEAT)
    if profile["diet"] in ["Vegetarian", "Vegan"]:
        terms.update(ALLERGENS["Fish"] + ALLERGENS["Shellfish"])
    if profile["diet"] == "Vegan":
        terms.update(ALLERGENS["Milk"] + ALLERGENS["Egg"] + ["honey"])
    restriction_terms = {
        "Gluten-free": ALLERGENS["Wheat"] + ["barley", "rye", "malt"],
        "Dairy-free": ALLERGENS["Milk"], "Egg-free": ALLERGENS["Egg"],
        "Pork-free": ["pork", "bacon", "ham", "lard"],
        "Alcohol-free": ["alcohol", "wine", "beer", "rum", "vodka", "whiskey"],
    }
    for restriction in profile["restrictions"]:
        terms.update(restriction_terms[restriction])
    return sorted(terms)


def validate_language(value):
    text = normalized(value)
    if re.search(r"https?://|www\.|<[^>]+>", text):
        raise ValidationError("External links or embedded markup are not allowed in generated content.")
    if any(term in text for term in MEDICAL_TERMS):
        raise ValidationError("The AI response included clinical or restrictive-diet language and was withheld.")
    if re.search(r"\b(treats?|reverse[sd]?|heal[sd]?|guarantee[sd]?|\d+\s*mg)\b", text):
        raise ValidationError("The AI response included an unsupported health or safety claim.")


def validate_food_text(value, profile):
    for term in blocked_terms(profile):
        if has_term(value, term):
            raise ValidationError("Generated content conflicts with a food constraint and was not saved.")


def validate_meal(raw, profile):
    if not isinstance(raw, dict):
        raise ValidationError("A meal must be an object.")
    meal = {key: text_value(raw.get(key), key, maximum) for key, maximum in [("name", 150), ("portion", 300), ("explanation", 600)]}
    if raw.get("slot") not in MEALS:
        raise ValidationError("Unknown meal slot.")
    meal["slot"] = raw["slot"]
    ingredients = raw.get("ingredients")
    if not isinstance(ingredients, list) or not 1 <= len(ingredients) <= 25:
        raise ValidationError("A meal needs 1–25 explicitly named ingredients.")
    meal["ingredients"] = []
    for ingredient in ingredients:
        if not isinstance(ingredient, dict):
            raise ValidationError("Ingredients must include names and quantities.")
        meal["ingredients"].append({key: text_value(ingredient.get(key), key, 150) for key in ["name", "quantity"]})
    for nutrient in NUTRIENTS:
        meal[nutrient] = number_value(raw.get(nutrient), nutrient, 0 if nutrient != "calories" else 20, 2500 if nutrient == "calories" else 400)
    macro_calories = meal["protein_g"] * 4 + meal["carbs_g"] * 4 + meal["fat_g"] * 9
    if abs(macro_calories - meal["calories"]) > max(30, meal["calories"] * 0.20):
        raise ValidationError("Meal calories and macros are inconsistent.")
    text = " ".join([meal["name"], meal["portion"], meal["explanation"]] + [item["name"] + " " + item["quantity"] for item in meal["ingredients"]])
    validate_language(text)
    validate_food_text(text, profile)
    return meal


def day_totals(day):
    return {key: round(sum(meal[key] for meal in day["meals"]), 1) for key in NUTRIENTS}


def validate_day(raw, profile, nutrition):
    if not isinstance(raw, dict):
        raise ValidationError("A day must be an object.")
    day_number = number_value(raw.get("day"), "day", 1, profile["duration"], True)
    meals = raw.get("meals")
    if not isinstance(meals, list) or len(meals) != len(MEALS):
        raise ValidationError("Each day needs breakfast, lunch, dinner and a snack.")
    result = {"day": day_number, "meals": [validate_meal(meal, profile) for meal in meals]}
    if sorted(meal["slot"] for meal in result["meals"]) != sorted(MEALS):
        raise ValidationError("Meal slots must be unique and complete.")
    result["meals"].sort(key=lambda meal: MEALS.index(meal["slot"]))
    totals = day_totals(result)
    if nutrition["calories"] is not None:
        if abs(totals["calories"] - nutrition["calories"]) > nutrition["calories"] * 0.20:
            raise ValidationError("Daily calories differ from the estimated target by more than 20%.")
        for nutrient, target in nutrition["macros"].items():
            if abs(totals[nutrient] - target) > max(10, target * 0.35):
                raise ValidationError("Daily macros differ too far from the estimated distribution.")
    result["totals"] = totals
    return result


def validate_batch(raw, expected_days, profile, nutrition):
    if not isinstance(raw, dict) or not isinstance(raw.get("days"), list):
        raise ValidationError("The response must contain a days list.")
    if len(raw["days"]) != len(expected_days):
        raise ValidationError("The response has an incorrect day count.")
    days = [validate_day(day, profile, nutrition) for day in raw["days"]]
    if [day["day"] for day in days] != list(expected_days):
        raise ValidationError("The response has duplicate, missing or out-of-order days.")
    return days


def replace_meal(days, day_number, slot, raw_meal, profile, nutrition):
    result = copy.deepcopy(days)
    day = next((day for day in result if day["day"] == day_number), None)
    if day is None:
        raise ValidationError("Choose a generated day.")
    meal = validate_meal(raw_meal, profile)
    if meal["slot"] != slot:
        raise ValidationError("The replacement changed the selected meal slot.")
    original = next((item for item in day["meals"] if item["slot"] == slot), None)
    if original is None:
        raise ValidationError("Choose a valid meal slot.")
    if nutrition["calories"] is not None and abs(meal["calories"] - original["calories"]) > original["calories"] * 0.25:
        raise ValidationError("The replacement must stay within 25% of the original meal's calories.")
    day["meals"][day["meals"].index(original)] = meal
    validated = validate_day(day, profile, nutrition)
    result[result.index(day)] = validated
    return result


def needs_professional_reply(message, profile):
    text = normalized(message)
    keywords = list(MEDICAL_TERMS) + ["allerg", "intoleran", "diagnos", "condition", "blood pressure", "hypertension", "celiac", "coeliac", "thyroid", "anemia", "anaemia", "cancer", "disease", "disorder", "symptom", "surgery", "rapid weight", "lose weight", "gain weight", "kcal", "calories a day", "calories per day"]
    keywords += [normalized(item["name"]) for item in profile["medications"]]
    return any(term in text for term in keywords) or re.search(r"\b\d{3,4}\s*(?:cal|kcal)", text) is not None