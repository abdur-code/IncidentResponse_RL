"""
Deterministic grading engine for the SRE Incident Response environment.
Scores episodes on a 0.0-1.0 scale based on weighted rubric components.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Set, Tuple

from models import (
    GraderResult,
)
from env.scenario import RequiredFix

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

    # ── 1. Root cause service identification (partial credit) ──
    service_score = 0.0
    submitted_services = _collect_submitted_services(diagnosis)
    expected_services = {_normalize_text(service) for service in scenario.root_cause_services}
    if submitted_services:
        matched_services = submitted_services & expected_services
        service_fraction = len(matched_services) / max(len(expected_services), 1)
        service_score = weights.get("correct_service", 0) * service_fraction
        notes.append(
            f"Root cause services: matched {len(matched_services)}/{len(expected_services)} "
            f"({sorted(matched_services) or 'none'})"
        )
        missing_services = expected_services - matched_services
        if missing_services:
            notes.append(f"Missing root cause services: {sorted(missing_services)}")
    else:
        notes.append("No root cause service(s) submitted.")
    breakdown["correct_service"] = round(service_score, 4)
    score += service_score

    # ── 2. Root cause category (partial credit) ──
    category_score = 0.0
    submitted_categories = _collect_submitted_categories(diagnosis)
    expected_categories = set(scenario.root_cause_categories)
    if submitted_categories:
        matched_categories = submitted_categories & expected_categories
        category_fraction = len(matched_categories) / max(len(expected_categories), 1)
        category_score = weights.get("correct_category", 0) * category_fraction
        notes.append(
            f"Root cause categories: matched {len(matched_categories)}/{len(expected_categories)} "
            f"({[c.value for c in sorted(matched_categories, key=lambda c: c.value)] or 'none'})"
        )
        missing_categories = expected_categories - matched_categories
        if missing_categories:
            notes.append(
                "Missing root cause categories: "
                f"{[c.value for c in sorted(missing_categories, key=lambda c: c.value)]}"
            )
    else:
        notes.append("No root cause category/categories submitted.")
    breakdown["correct_category"] = round(category_score, 4)
    score += category_score

    # ── 3. Required fix coverage (set-based, order-independent) ──
    required_fix_fraction = 0.0
    if scenario.required_fixes:
        matched_required_fixes = _matched_required_fix_count(
            scenario.required_fixes,
            session.remediations_applied,
        )
        required_fix_fraction = matched_required_fixes / len(scenario.required_fixes)
        notes.append(
            f"Required fixes matched: {matched_required_fixes}/{len(scenario.required_fixes)}"
        )
    correct_fix_weight = weights.get("correct_fix", 0)
    secondary_fix_weight = weights.get("secondary_fix", 0)
    fix_score = correct_fix_weight * required_fix_fraction
    secondary_score = secondary_fix_weight * required_fix_fraction
    breakdown["correct_fix"] = round(fix_score, 4)
    breakdown["secondary_fix"] = round(secondary_score, 4)
    score += fix_score + secondary_score

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
        is_correct = any(_remediation_matches_required_fix(rem, req_fix) for req_fix in scenario.required_fixes)
        if not is_correct:
            wrong_count += 1
            penalty += penalty_per

    if wrong_count > 0:
        notes.append(f"Penalty: {wrong_count} wrong remediation(s) (-{penalty:.2f})")
    breakdown["wrong_penalty"] = -round(penalty, 4)
    score -= penalty

    # ── 8. No-fix cap ──
    if scenario.required_fixes:
        matched_required_fixes = _matched_required_fix_count(
            scenario.required_fixes,
            session.remediations_applied,
        )
        fix_fraction = matched_required_fixes / len(scenario.required_fixes)
        base_cap = scenario.no_fix_score_cap
        dynamic_cap = base_cap + (1.0 - base_cap) * fix_fraction
        if fix_fraction < 1.0 and score > dynamic_cap:
            score = dynamic_cap
            notes.append(
                "Required fix coverage is partial; "
                f"score capped at {dynamic_cap:.2f} ({matched_required_fixes}/{len(scenario.required_fixes)} fixes)."
            )

    # ── Final clamp — strictly within (0, 1), never exactly 0.0 or 1.0 ──
    score = round(max(0.001, min(0.999, score)), 4)
    solved = score >= 0.7

    return GraderResult(
        score=score,
        solved=solved,
        breakdown=breakdown,
        notes=notes,
    )


def _collect_submitted_services(diagnosis) -> Set[str]:
    if diagnosis is None:
        return set()

    submitted: Set[str] = set()
    if diagnosis.root_cause_service:
        submitted.add(_normalize_text(diagnosis.root_cause_service))
    if diagnosis.root_cause_services:
        submitted.update(_normalize_text(service) for service in diagnosis.root_cause_services)
    return submitted


def _collect_submitted_categories(diagnosis) -> Set:
    if diagnosis is None:
        return set()

    submitted = set()
    if diagnosis.root_cause_category:
        submitted.add(diagnosis.root_cause_category)
    if diagnosis.root_cause_categories:
        submitted.update(diagnosis.root_cause_categories)
    return submitted


def _remediation_matches_required_fix(remediation: Dict, required_fix: RequiredFix) -> bool:
    return _canonical_remediation(remediation) == _canonical_required_fix(required_fix)


def _matched_required_fix_count(required_fixes: List[RequiredFix], remediations: List[Dict]) -> int:
    matched = 0
    for req_fix in required_fixes:
        if any(_remediation_matches_required_fix(rem, req_fix) for rem in remediations):
            matched += 1
    return matched


def _normalize_text(value: object) -> str:
    return str(value).strip().lower()


def _canonical_required_fix(required_fix: RequiredFix) -> Tuple[str, str, str, str]:
    target_version = _normalize_text(required_fix.target_version) if required_fix.target_version else ""
    replicas = str(required_fix.replicas) if required_fix.replicas is not None else ""
    return (
        _normalize_text(required_fix.action),
        _normalize_text(required_fix.service),
        target_version,
        replicas,
    )


def _canonical_remediation(remediation: Dict) -> Tuple[str, str, str, str]:
    target_version = remediation.get("target_version")
    replicas = remediation.get("replicas")
    return (
        _normalize_text(remediation.get("action", "")),
        _normalize_text(remediation.get("service", "")),
        _normalize_text(target_version) if target_version else "",
        str(replicas) if replicas is not None else "",
    )
