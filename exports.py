"""Plan exports with explicit sensitive-data opt-in."""

import copy
import csv
import io
import json
from datetime import datetime, timezone
from xml.sax.saxutils import escape

from nutrition import ALLERGY_NOTICE, DISCLAIMER, NUTRIENTS


def export_document(profile, nutrition, safety, days, include_profile=False):
    result = {
        "version": "2.0", "exported_at": datetime.now(timezone.utc).isoformat(),
        "requested_days": profile["duration"], "generated_days": len(days),
        "complete": len(days) == profile["duration"],
        "disclaimer": DISCLAIMER, "allergy_notice": ALLERGY_NOTICE,
        "safety_status": safety["status"],
        "safety_note": "Professional review is required before using these meal ideas." if safety["reasons"] else "Estimates are not a prescription; review ingredients and portions before use.",
        "nutrition_estimates": copy.deepcopy(nutrition), "days": copy.deepcopy(days),
    }
    if include_profile:
        result["profile"] = {key: copy.deepcopy(value) for key, value in profile.items() if key != "consent"}
        result["safety_reasons"] = list(safety["reasons"])
    return result


def spreadsheet_text(value):
    text = str(value)
    if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")):
        return "'" + text
    return text


def export_csv(days):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["day", "meal", "name", "portion", "ingredients", *NUTRIENTS, "explanation", "safety_note"])
    for day in days:
        for meal in day["meals"]:
            ingredients = "; ".join(f"{item['name']}: {item['quantity']}" for item in meal["ingredients"])
            writer.writerow([day["day"], meal["slot"], *[spreadsheet_text(value) for value in [meal["name"], meal["portion"], ingredients]],
                             *[meal[key] for key in NUTRIENTS], spreadsheet_text(meal["explanation"]), DISCLAIMER + " " + ALLERGY_NOTICE])
    return output.getvalue().encode("utf-8-sig")


def export_pdf(document):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    buffer = io.BytesIO()
    styles = getSampleStyleSheet()
    styles["Title"].textColor = colors.HexColor("#2f9e6f")
    story = []

    def paragraph(text, style="BodyText"):
        safe_text = str(text).encode("cp1252", errors="replace").decode("cp1252")
        story.append(Paragraph(escape(safe_text).replace("\n", "<br/>"), styles[style]))
        story.append(Spacer(1, 6))

    paragraph("NutriGuide AI — Nutrition Plan", "Title")
    status = "Complete" if document["complete"] else "PARTIAL PLAN"
    paragraph(f"{status}: {document['generated_days']} of {document['requested_days']} days")
    paragraph(document["disclaimer"])
    paragraph(document["allergy_notice"])
    paragraph(document["safety_note"])
    estimates = document["nutrition_estimates"]
    if estimates["calories"] is not None:
        paragraph(f"Estimated BMI: {estimates['bmi']} | BMR: {estimates['bmr']} kcal/day | Maintenance: {estimates['tdee']} kcal/day | Goal: {estimates['calories']} kcal/day")
        paragraph("Estimated daily macro targets: " + "; ".join(f"{key}: {value} g" for key, value in estimates["macros"].items()))
    else:
        paragraph("No automated calorie or macro targets. Meal values, if present, are estimates only.")
    if "profile" in document:
        paragraph("Sensitive profile — included at your request", "Heading2")
        for key, value in document["profile"].items():
            paragraph(f"{key}: {json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value}")
        for reason in document.get("safety_reasons", []):
            paragraph(reason)
    for day in document["days"]:
        paragraph(f"Day {day['day']}", "Heading1")
        paragraph("Estimated totals: " + "; ".join(f"{key}: {value:g}" for key, value in day["totals"].items()))
        for meal in day["meals"]:
            paragraph(f"{meal['slot'].title()} — {meal['name']}", "Heading2")
            paragraph(f"Portion: {meal['portion']}")
            for ingredient in meal["ingredients"]:
                paragraph(f"• {ingredient['name']} — {ingredient['quantity']}")
            paragraph(f"Estimated {meal['calories']:g} kcal | Protein {meal['protein_g']:g} g | Carbohydrate {meal['carbs_g']:g} g | Fat {meal['fat_g']:g} g")
            paragraph(meal["explanation"])
    def footer(canvas, document_template):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.drawString(36, 22, "NutriGuide AI | Estimates only; not medical advice")
        canvas.drawRightString(A4[0] - 36, 22, f"Page {document_template.page}")
        canvas.restoreState()
    SimpleDocTemplate(buffer, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=42).build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()