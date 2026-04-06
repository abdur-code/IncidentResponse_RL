"""
Deterministic grading engine for the SRE Incident Response environment.
Scores episodes on a 0.0-1.0 scale based on weighted rubric components.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List

from models import (
    ActionType,
    GraderResult,
    INVESTIGATION_ACTIONS,
    RootCauseCategory,
)

if TYPE_CHECKING:
    from env.environment import Session


def grade_episode(session: Session) -> GraderResult:
    """Grade a completed episode and return a GraderResult."""
    scenario = session.scenario
    weights = scenario.weights
    diagnosis = session.diagnosis
    notes: List[str] = []
    breakdown: Dict[str, float] = {}

    score = 0.0

    # ── 1. Root cause service identification ──
    service_score = 0.0
    if diagnosis and diagnosis.root_cause_service:
        if diagnosis.root_cause_service in scenario.root_cause_services:
            service_score = weights.get("correct_service", 0)
            notes.append(f"Correct root cause service: {diagnosis.root_cause_service}")
        else:
            notes.append(
                f"Wrong root cause service: {diagnosis.root_cause_service} "
                f"(expected one of: {scenario.root_cause_services})"
            )
    else:
        notes.append("No root cause service submitted.")
    breakdown["correct_service"] = service_score
    score += service_score

    # ── 2. Root cause category ──
    category_score = 0.0
    if diagnosis and diagnosis.root_cause_category:
        if diagnosis.root_cause_category in scenario.root_cause_categories:
            category_score = weights.get("correct_category", 0)
            notes.append(f"Correct root cause category: {diagnosis.root_cause_category.value}")
        else:
            notes.append(
                f"Wrong root cause category: {diagnosis.root_cause_category.value} "
                f"(expected one of: {[c.value for c in scenario.root_cause_categories]})"
            )
    else:
        notes.append("No root cause category submitted.")
    breakdown["correct_category"] = category_score
    score += category_score

    # ── 3. Primary fix applied ──
    fix_score = 0.0
    primary_fix = scenario.required_fixes[0] if scenario.required_fixes else None
    if primary_fix and primary_fix.service in session.fixed_services:
        fix_score = weights.get("correct_fix", 0)
        notes.append(f"Primary fix applied: {primary_fix.action}({primary_fix.service})")
    elif primary_fix:
        notes.append(
            f"Primary fix NOT applied. Expected: {primary_fix.action}({primary_fix.service})"
        )
    breakdown["correct_fix"] = fix_score
    score += fix_score

    # ── 4. Secondary fixes (hard tier) ──
    secondary_score = 0.0
    secondary_weight = weights.get("secondary_fix", 0)
    if secondary_weight > 0 and len(scenario.required_fixes) > 1:
        secondary_fixes = scenario.required_fixes[1:]
        fixed_count = sum(
            1 for f in secondary_fixes if f.service in session.fixed_services
        )
        fraction = fixed_count / len(secondary_fixes)
        secondary_score = secondary_weight * fraction
        if fixed_count == len(secondary_fixes):
            notes.append(f"All {len(secondary_fixes)} secondary fix(es) applied.")
        elif fixed_count > 0:
            notes.append(
                f"Partial secondary fixes: {fixed_count}/{len(secondary_fixes)} applied."
            )
        else:
            notes.append(f"No secondary fixes applied (needed {len(secondary_fixes)}).")
    breakdown["secondary_fix"] = secondary_score
    score += secondary_score

    # ── 5. Diagnosis text quality (keyword matching) ──
    text_score = 0.0
    text_weight = weights.get("diagnosis_text", 0)
    if diagnosis and diagnosis.fix_description:
        desc_lower = diagnosis.fix_description.lower()
        keywords = scenario.diagnosis_keywords
        matched = sum(1 for kw in keywords if kw.lower() in desc_lower)
        fraction = min(matched / max(len(keywords) // 2, 1), 1.0)  # need half the keywords for full marks
        text_score = text_weight * fraction
        notes.append(
            f"Diagnosis text: {matched}/{len(keywords)} keywords matched "
            f"({fraction:.0%} of required)"
        )
    else:
        notes.append("No diagnosis description submitted.")
    breakdown["diagnosis_text"] = round(text_score, 4)
    score += text_score

    # ── 6. Investigation thoroughness ──
    invest_score = 0.0
    invest_weight = weights.get("investigation", 0)
    # Check if agent investigated at least one root cause service
    investigated_root = any(
        svc in session.services_investigated
        for svc in scenario.root_cause_services
    )
    if investigated_root:
        invest_score = invest_weight
        notes.append(
            f"Investigation: examined root cause service(s) "
            f"({session.services_investigated & set(scenario.root_cause_services)})"
        )
    else:
        notes.append(
            f"Investigation: did NOT examine any root cause service. "
            f"Investigated: {session.services_investigated or 'none'}"
        )
    breakdown["investigation"] = invest_score
    score += invest_score

    # ── 7. Wrong remediation penalties ──
    penalty = 0.0
    penalty_per = weights.get("wrong_penalty", 0.05)
    wrong_count = 0
    for rem in session.remediations_applied:
        is_correct = False
        for req_fix in scenario.required_fixes:
            if rem["action"] == req_fix.action and rem["service"] == req_fix.service:
                if req_fix.target_version and rem.get("target_version") != req_fix.target_version:
                    continue
                is_correct = True
                break
        # Also accept scale_up on root cause services as correct
        if rem["service"] in scenario.root_cause_services and rem["action"] in ("restart_service", "scale_up", "rollback_deploy"):
            is_correct = True
        if not is_correct:
            wrong_count += 1
            penalty += penalty_per

    if wrong_count > 0:
        notes.append(f"Penalty: {wrong_count} wrong remediation(s) (-{penalty:.2f})")
    breakdown["wrong_penalty"] = -round(penalty, 4)
    score -= penalty

    # ── Final clamp ──
    score = round(max(0.0, min(1.0, score)), 4)
    solved = score >= 0.7

    return GraderResult(
        score=score,
        solved=solved,
        breakdown=breakdown,
        notes=notes,
    )
