import argparse
import json
import os
from typing import Any, Dict, Optional

from playwright.sync_api import Page, sync_playwright

from artifact_store import load_artifact, validate_artifact
from error_handler import (
    build_recovery_plan,
    create_human_escalation,
)

from intervention_manager import (
    create_intervention,
    start_human_intervention,
    complete_human_action,
    mark_resumed,
    mark_completed,
)


# ============================================================
# CONFIG
# ============================================================

DEFAULT_TARGET_URL = os.getenv(
    "TARGET_APP_URL",
    "http://localhost:8000",
)

ACTION_TIMEOUT_MS = 3000
NAVIGATION_TIMEOUT_MS = 8000
POST_ACTION_WAIT_MS = 300


# ============================================================
# PARAMETER RESOLUTION
# ============================================================

def resolve_value(
    value: Any,
    parameters: Dict[str, Any],
):
    if isinstance(value, str):
        resolved = value

        for key, parameter_value in parameters.items():
            placeholder = "{{" + str(key) + "}}"
            resolved = resolved.replace(
                placeholder,
                str(parameter_value),
            )

        return resolved

    if isinstance(value, list):
        return [
            resolve_value(item, parameters)
            for item in value
        ]

    if isinstance(value, dict):
        return {
            key: resolve_value(item, parameters)
            for key, item in value.items()
        }

    return value


# ============================================================
# PARAMETER VALIDATION
# ============================================================

def validate_parameters(
    artifact: Dict[str, Any],
    parameters: Dict[str, Any],
):
    inputs = artifact.get("inputs", {})
    missing = []

    for name, definition in inputs.items():

        if not isinstance(definition, dict):
            continue

        required = definition.get(
            "required",
            False,
        )

        if required and (
            name not in parameters
            or parameters[name] is None
            or str(parameters[name]).strip() == ""
        ):
            missing.append(name)

    return len(missing) == 0, missing


# ============================================================
# EXECUTE ACTION
# ============================================================

def execute_replay_action(
    page: Page,
    action: Dict[str, Any],
    parameters: Dict[str, Any],
):
    resolved_action = resolve_value(
        action,
        parameters,
    )

    action_type = str(
        resolved_action.get("action", "")
    ).strip().lower()

    selector = resolved_action.get(
        "selector"
    )

    if action_type == "fill":

        if not selector:
            raise ValueError(
                "Replay fill action is missing selector."
            )

        page.locator(selector).fill(
            str(
                resolved_action.get(
                    "value",
                    "",
                )
            ),
            timeout=ACTION_TIMEOUT_MS,
        )

        return resolved_action

    if action_type == "click":

        if not selector:
            raise ValueError(
                "Replay click action is missing selector."
            )

        page.locator(selector).click(
            timeout=ACTION_TIMEOUT_MS,
        )

        return resolved_action

    if action_type == "type":

        if not selector:
            raise ValueError(
                "Replay type action is missing selector."
            )

        page.locator(selector).type(
            str(
                resolved_action.get(
                    "value",
                    "",
                )
            ),
            timeout=ACTION_TIMEOUT_MS,
        )

        return resolved_action

    if action_type == "press":

        if not selector:
            raise ValueError(
                "Replay press action is missing selector."
            )

        key = resolved_action.get("key")

        if not key:
            raise ValueError(
                "Replay press action is missing key."
            )

        page.locator(selector).press(
            str(key),
            timeout=ACTION_TIMEOUT_MS,
        )

        return resolved_action

    if action_type == "select":

        if not selector:
            raise ValueError(
                "Replay select action is missing selector."
            )

        value = resolved_action.get(
            "value"
        )

        if value is None:
            raise ValueError(
                "Replay select action is missing value."
            )

        page.locator(selector).select_option(
            str(value),
            timeout=ACTION_TIMEOUT_MS,
        )

        return resolved_action

    if action_type == "check":

        if not selector:
            raise ValueError(
                "Replay check action is missing selector."
            )

        page.locator(selector).check(
            timeout=ACTION_TIMEOUT_MS,
        )

        return resolved_action

    if action_type == "uncheck":

        if not selector:
            raise ValueError(
                "Replay uncheck action is missing selector."
            )

        page.locator(selector).uncheck(
            timeout=ACTION_TIMEOUT_MS,
        )

        return resolved_action

    if action_type == "wait":

        milliseconds = int(
            resolved_action.get(
                "milliseconds",
                500,
            )
        )

        page.wait_for_timeout(
            milliseconds
        )

        return resolved_action

    if action_type == "navigate":

        url = resolved_action.get("url")

        if not url:
            raise ValueError(
                "Replay navigate action is missing URL."
            )

        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=NAVIGATION_TIMEOUT_MS,
        )

        return resolved_action

    if action_type == "scroll":

        amount = int(
            resolved_action.get(
                "amount",
                500,
            )
        )

        page.mouse.wheel(
            0,
            amount,
        )

        return resolved_action

    raise ValueError(
        f"Unsupported replay action: {action_type}"
    )


# ============================================================
# DETERMINISTIC RECOVERY
# ============================================================

def attempt_action_recovery(
    page: Page,
    action: Dict[str, Any],
    parameters: Dict[str, Any],
    step_number: int,
    original_error: Exception,
    force_failure: bool = False,
):
    """
    One bounded deterministic recovery.

    No LLM.
    Saved artifact is never modified.
    """

    resolved_action = resolve_value(
        action,
        parameters,
    )

    recovery_plan = build_recovery_plan(
        resolved_action,
        original_error,
        step_number,
    )

    if force_failure:

        return {
            "attempted": True,
            "success": False,
            "plan": recovery_plan,
            "strategy": None,
            "original_selector":
                resolved_action.get("selector"),
            "error": (
                "Recovery failure was intentionally "
                "simulated for testing."
            ),
            "simulated": True,
        }

    if not recovery_plan.get("allowed"):

        return {
            "attempted": False,
            "success": False,
            "plan": recovery_plan,
            "error": recovery_plan.get(
                "reason",
                "Recovery is not allowed for this action.",
            ),
        }

    action_type = str(
        resolved_action.get(
            "action",
            "",
        )
    ).lower()

    original_selector = str(
        resolved_action.get(
            "selector",
            "",
        )
    )

    value = resolved_action.get(
        "value",
        "",
    )

    candidates = []

    # --------------------------------------------------------
    # MEMBER ID FIELD RECOVERY
    # --------------------------------------------------------

    if action_type in {
        "fill",
        "type",
    }:

        is_member_action = (
            "member"
            in original_selector.lower()
            or "{{member_id}}"
            in str(
                action.get(
                    "value",
                    "",
                )
            )
            or (
                "member_id" in parameters
                and str(value)
                == str(
                    parameters.get(
                        "member_id"
                    )
                )
            )
        )

        if is_member_action:

            candidates = [
                {
                    "strategy":
                        "known_member_id_selector",
                    "locator":
                        page.locator(
                            "#member-id"
                        ),
                },
                {
                    "strategy":
                        "accessible_member_id_label",
                    "locator":
                        page.get_by_label(
                            "Member ID",
                            exact=False,
                        ),
                },
                {
                    "strategy":
                        "member_input_attributes",
                    "locator":
                        page.locator(
                            "input[id*='member'], "
                            "input[name*='member']"
                        ),
                },
            ]

    # --------------------------------------------------------
    # SEARCH BUTTON RECOVERY
    # --------------------------------------------------------

    elif action_type == "click":

        is_search_action = (
            "search"
            in original_selector.lower()
            or "button"
            in original_selector.lower()
        )

        if is_search_action:

            candidates = [
                {
                    "strategy":
                        "known_search_button_selector",
                    "locator":
                        page.locator(
                            "#search-button"
                        ),
                },
                {
                    "strategy":
                        "accessible_search_member_button",
                    "locator":
                        page.get_by_role(
                            "button",
                            name="Search member",
                            exact=False,
                        ),
                },
                {
                    "strategy":
                        "accessible_search_button",
                    "locator":
                        page.get_by_role(
                            "button",
                            name="Search",
                            exact=False,
                        ),
                },
            ]

    if not candidates:

        return {
            "attempted": True,
            "success": False,
            "plan": recovery_plan,
            "error": (
                "No approved deterministic fallback "
                "exists for this action."
            ),
        }

    errors = []

    for candidate in candidates:

        locator = candidate["locator"]

        try:

            count = locator.count()

            if count < 1:
                continue

            target = locator.first

            if not target.is_visible(
                timeout=1000
            ):
                continue

            if action_type == "fill":

                target.fill(
                    str(value),
                    timeout=ACTION_TIMEOUT_MS,
                )

            elif action_type == "type":

                target.fill(
                    "",
                    timeout=ACTION_TIMEOUT_MS,
                )

                target.type(
                    str(value),
                    timeout=ACTION_TIMEOUT_MS,
                )

            elif action_type == "click":

                target.click(
                    timeout=ACTION_TIMEOUT_MS,
                )

            else:
                continue

            return {
                "attempted": True,
                "success": True,
                "plan": recovery_plan,
                "strategy":
                    candidate["strategy"],
                "original_selector":
                    original_selector,
                "error": None,
            }

        except Exception as recovery_error:

            errors.append(
                str(recovery_error)
            )

    return {
        "attempted": True,
        "success": False,
        "plan": recovery_plan,
        "original_selector":
            original_selector,
        "error": (
            errors[-1]
            if errors
            else "No recovery locator matched."
        ),
    }


# ============================================================
# WAIT FOR MEMBER
# ============================================================

def wait_for_member_result(
    page: Page,
    member_id: str,
):
    if not member_id:
        return

    page.wait_for_function(
        """
        expectedMemberId => {
            const element =
                document.querySelector("#member-number");

            if (!element) {
                return false;
            }

            return (
                element.textContent || ""
            ).trim() === expectedMemberId;
        }
        """,
        member_id,
        timeout=5000,
    )


# ============================================================
# BROWSER EVIDENCE
# ============================================================

def capture_replay_evidence(
    page: Page,
    parameters: Dict[str, Any],
):
    expected_member_id = str(
        parameters.get(
            "member_id",
            "",
        )
    ).strip()

    try:

        body_text = page.locator(
            "body"
        ).inner_text(
            timeout=ACTION_TIMEOUT_MS
        )

    except Exception:

        body_text = ""

    rendered_member_id = None

    try:

        member_locator = page.locator(
            "#member-number"
        )

        if member_locator.count() > 0:

            rendered_member_id = (
                member_locator
                .first
                .inner_text(
                    timeout=ACTION_TIMEOUT_MS
                )
                .strip()
            )

    except Exception:

        rendered_member_id = None

    member_visible = bool(
        expected_member_id
        and rendered_member_id
        and expected_member_id
        == rendered_member_id
    )

    claims_container_present = False
    claim_statuses = []
    empty_state_text = None

    try:

        claims_container = page.locator(
            "#claims-container"
        )

        claims_container_present = (
            claims_container.count()
            > 0
        )

        if claims_container_present:

            status_locator = page.locator(
                "#claims-container .claim-status"
            )

            claim_statuses = [
                status.strip()
                for status
                in status_locator.all_text_contents()
                if status.strip()
            ]

            empty_locator = page.locator(
                "#claims-container .empty-state"
            )

            if empty_locator.count() > 0:

                empty_state_text = (
                    empty_locator
                    .first
                    .inner_text(
                        timeout=ACTION_TIMEOUT_MS
                    )
                    .strip()
                )

    except Exception:

        claim_statuses = []

    pending_claim_count = sum(
        1
        for status in claim_statuses
        if status.strip().lower()
        == "pending"
    )

    browser_output = {
        "member_id":
            rendered_member_id,

        "claim_statuses":
            claim_statuses,

        "total_claims":
            len(claim_statuses),

        "pending_claim_count":
            pending_claim_count,

        "source":
            "browser_dom",
    }

    return {
        "url":
            page.url,

        "member_id":
            expected_member_id
            or None,

        "rendered_member_id":
            rendered_member_id,

        "member_visible":
            member_visible,

        "claims_container_present":
            claims_container_present,

        "empty_state_text":
            empty_state_text,

        "body_text":
            body_text,

        "body_text_length":
            len(body_text),

        "browser_output":
            browser_output,
    }


# ============================================================
# PENDING CLAIMS CHECKPOINT
# ============================================================

def verify_pending_claims_result(
    page: Page,
    parameters: Dict[str, Any],
):
    evidence = capture_replay_evidence(
        page,
        parameters,
    )

    expected_member_id = str(
        parameters.get(
            "member_id",
            "",
        )
    ).strip()

    rendered_member_id = str(
        evidence.get(
            "rendered_member_id"
        )
        or ""
    ).strip()

    if not expected_member_id:

        return {
            "success": False,
            "type":
                "pending_claims_result",
            "message":
                "Runtime member_id is missing.",
            "evidence":
                evidence,
        }

    if (
        rendered_member_id
        != expected_member_id
    ):

        return {
            "success": False,
            "type":
                "pending_claims_result",
            "message": (
                "Browser rendered member "
                f"'{rendered_member_id}' "
                "instead of expected member "
                f"'{expected_member_id}'."
            ),
            "evidence":
                evidence,
        }

    if not evidence.get(
        "claims_container_present"
    ):

        return {
            "success": False,
            "type":
                "pending_claims_result",
            "message": (
                "Claims container was not found "
                "in the rendered DOM."
            ),
            "evidence":
                evidence,
        }

    browser_output = evidence.get(
        "browser_output",
        {},
    )

    claim_statuses = browser_output.get(
        "claim_statuses",
        [],
    )

    empty_state_text = str(
        evidence.get(
            "empty_state_text"
        )
        or ""
    ).strip()

    normalized_empty_state = (
        empty_state_text
        .rstrip(".")
        .strip()
        .lower()
    )

    valid_empty_state = (
        normalized_empty_state
        == "no claims found"
    )

    if (
        not claim_statuses
        and not valid_empty_state
    ):

        return {
            "success": False,
            "type":
                "pending_claims_result",
            "message": (
                "Claims area rendered, but no "
                "claim statuses or recognized "
                "'No claims found.' state was found."
            ),
            "evidence":
                evidence,
        }

    if (
        "pending_claim_count"
        not in browser_output
    ):

        return {
            "success": False,
            "type":
                "pending_claims_result",
            "message": (
                "Pending claim count could not "
                "be extracted from the DOM."
            ),
            "evidence":
                evidence,
        }

    return {
        "success": True,

        "type":
            "pending_claims_result",

        "message": (
            "Pending claims result was verified "
            "from the rendered browser DOM."
        ),

        "evidence":
            evidence,

        "browser_output":
            browser_output,

        "output_source":
            "browser_dom",
    }


# ============================================================
# GENERIC SUCCESS CONDITION
# ============================================================

def verify_success_condition(
    page: Page,
    artifact: Dict[str, Any],
    parameters: Dict[str, Any],
):
    metadata = artifact.get(
        "metadata",
        {},
    )

    capability_name = str(
        metadata.get(
            "capability_name",
            "",
        )
        or ""
    ).strip().lower()

    if (
        capability_name
        == "pending_claims_lookup"
    ):

        return verify_pending_claims_result(
            page,
            parameters,
        )

    condition = resolve_value(
        artifact.get(
            "success_condition",
            {},
        ),
        parameters,
    )

    condition_type = condition.get(
        "type"
    )

    evidence = capture_replay_evidence(
        page,
        parameters,
    )

    if condition_type == "agent_completion":

        success = (
            evidence.get(
                "body_text_length",
                0,
            )
            > 0
        )

        return {
            "success":
                success,

            "type":
                "agent_completion",

            "message": (
                "All recorded actions completed "
                "and browser evidence was captured."
                if success
                else
                "No browser evidence was captured."
            ),

            "evidence":
                evidence,
        }

    if condition_type == "url_contains":

        expected = condition.get(
            "value"
        )

        success = bool(
            expected
            and str(expected)
            in page.url
        )

        return {
            "success":
                success,

            "type":
                "url_contains",

            "message": (
                "URL checkpoint passed."
                if success
                else
                "URL checkpoint failed."
            ),

            "evidence":
                evidence,
        }

    if condition_type == "text_contains":

        expected = str(
            condition.get(
                "value",
                "",
            )
        )

        body_text = evidence.get(
            "body_text",
            "",
        )

        success = bool(
            expected
            and expected
            in body_text
        )

        return {
            "success":
                success,

            "type":
                "text_contains",

            "message": (
                "Text checkpoint passed."
                if success
                else
                "Text checkpoint failed."
            ),

            "evidence":
                evidence,
        }

    success = (
        evidence.get(
            "body_text_length",
            0,
        )
        > 0
    )

    return {
        "success":
            success,

        "type":
            condition_type
            or "browser_evidence",

        "message": (
            "Browser evidence was captured."
            if success
            else
            "Browser evidence could not be verified."
        ),

        "evidence":
            evidence,
    }


# ============================================================
# ESCALATION
# ============================================================

def build_escalation(
    artifact_id: str,
    capability_name: Optional[str],
    failed_step: Optional[int],
    failed_action: Optional[
        Dict[str, Any]
    ],
    reason: str,
    recovery_attempted: bool,
    recovery_error: Optional[str],
):
    try:

        escalation = create_human_escalation(
            artifact_id=artifact_id,
            capability_name=capability_name,
            failed_step=failed_step,
            failed_action=failed_action,
            reason=reason,
            recovery_attempted=
                recovery_attempted,
            recovery_error=
                recovery_error,
        )

    except Exception:

        escalation = {
            "required": True,
            "reason": reason,
            "artifact_id":
                artifact_id,
            "capability_name":
                capability_name,
            "failed_step":
                failed_step,
            "failed_action":
                failed_action,
            "recovery_attempted":
                recovery_attempted,
            "recovery_error":
                recovery_error,
        }

    if not isinstance(
        escalation,
        dict,
    ):
        escalation = {}

    escalation["required"] = True

    escalation.setdefault(
        "reason",
        reason,
    )

    escalation.setdefault(
        "artifact_id",
        artifact_id,
    )

    escalation.setdefault(
        "capability_name",
        capability_name,
    )

    escalation.setdefault(
        "failed_step",
        failed_step,
    )

    escalation.setdefault(
        "failed_action",
        failed_action,
    )

    escalation.setdefault(
        "recovery_attempted",
        recovery_attempted,
    )

    escalation.setdefault(
        "recovery_error",
        recovery_error,
    )

    return escalation


# ============================================================
# CREATE PERSISTENT INTERVENTION
# ============================================================

def create_persistent_intervention(
    artifact_id: str,
    capability_name: Optional[str],
    parameters: Dict[str, Any],
    failed_step: int,
    failed_action: Dict[str, Any],
    reason: str,
    recovery_attempted: bool,
    recovery_error: Optional[str],
    target_url: str,
    page: Page,
):
    try:

        browser_state = {
            "url":
                page.url,

            "evidence":
                capture_replay_evidence(
                    page,
                    parameters,
                ),
        }

    except Exception as error:

        browser_state = {
            "url":
                getattr(
                    page,
                    "url",
                    None,
                ),

            "capture_error":
                str(error),
        }

    return create_intervention(
        artifact_id=artifact_id,
        capability_name=capability_name,
        parameters=parameters,
        failed_step=failed_step,
        failed_action=failed_action,
        reason=reason,
        recovery_attempted=
            recovery_attempted,
        recovery_error=
            recovery_error,
        target_url=
            target_url,
        browser_state=
            browser_state,
    )


# ============================================================
# LIVE HUMAN HANDOFF
# ============================================================

def run_human_intervention(
    page: Page,
    intervention: Dict[str, Any],
    failed_action: Dict[str, Any],
):
    """
    SAME Playwright page remains open.

    Human manually performs the failed action and presses Enter.

    No LLM is used.
    """

    intervention_id = (
        intervention[
            "intervention_id"
        ]
    )

    start_human_intervention(
        intervention_id,
        notes=(
            "Human operator received control "
            "of the live browser session."
        ),
    )

    print()
    print(
        "========================================"
    )
    print(
        "HUMAN INTERVENTION REQUIRED"
    )
    print(
        "========================================"
    )

    print(
        "Intervention ID:",
        intervention_id,
    )

    print(
        "Failed step:",
        intervention.get(
            "failed_step"
        ),
    )

    print(
        "Failed action:"
    )

    print(
        json.dumps(
            failed_action,
            indent=2,
            ensure_ascii=False,
        )
    )

    print()
    print(
        ">>> The SAME Chromium window remains open."
    )

    print(
        ">>> Complete the failed action manually."
    )

    print()
    print(
        "For this test:"
    )

    print(
        "1. Member ID 10002 should already be filled."
    )

    print(
        "2. Click the real Search member button."
    )

    print(
        "3. Wait for Sarah Patel and claims to appear."
    )

    print(
        "4. Return here."
    )

    print(
        "5. Press ENTER."
    )

    print()

    try:

        input(
            "Press ENTER after completing "
            "the browser action: "
        )

    except (
        EOFError,
        KeyboardInterrupt,
    ):

        return {
            "success": False,
            "intervention_id":
                intervention_id,
            "error": (
                "Human intervention was not "
                "completed."
            ),
        }

    complete_human_action(
        intervention_id,
        action_taken=(
            "Human manually completed the "
            "failed action in the live browser."
        ),
        notes=(
            "Human confirmed completion before "
            "deterministic replay resumed."
        ),
    )

    mark_resumed(
        intervention_id
    )

    return {
        "success": True,
        "intervention_id":
            intervention_id,
        "transferred":
            True,
        "resumed":
            True,
        "llm_used":
            False,
    }


# ============================================================
# FINAL CHECKPOINT
# ============================================================

def run_final_checkpoint(
    page: Page,
    artifact: Dict[str, Any],
    parameters: Dict[str, Any],
):
    member_id = str(
        parameters.get(
            "member_id",
            "",
        )
    ).strip()

    if member_id:

        try:

            wait_for_member_result(
                page,
                member_id,
            )

        except Exception:

            # Semantic checkpoint below is authoritative.
            pass

    page.wait_for_timeout(
        250
    )

    return verify_success_condition(
        page,
        artifact,
        parameters,
    )


# ============================================================
# REPLAY
# ============================================================

def replay_artifact(
    artifact_id: str,
    parameters: Optional[
        Dict[str, Any]
    ] = None,
    target_url: Optional[str] = None,
    simulate_selector_failure_step:
        Optional[int] = None,
    force_recovery_failure: bool = False,
    allow_human_intervention: bool = False,
    headless: bool = True,
):
    """
    Deterministic capability replay.

    No LLM is used.

    With allow_human_intervention=True:
        deterministic recovery failure
            -> persistent intervention
            -> same live browser handed to human
            -> human completes failed action
            -> replay resumes
            -> semantic checkpoint
    """

    parameters = parameters or {}

    artifact = load_artifact(
        artifact_id
    )

    # --------------------------------------------------------
    # ARTIFACT NOT FOUND
    # --------------------------------------------------------

    if artifact is None:

        escalation = build_escalation(
            artifact_id=artifact_id,
            capability_name=None,
            failed_step=None,
            failed_action=None,
            reason="Artifact not found.",
            recovery_attempted=False,
            recovery_error=
                "Artifact not found.",
        )

        return {
            "success": False,
            "mode": "escalated",
            "artifact_id":
                artifact_id,
            "error":
                "Artifact not found.",
            "recovery_attempted":
                False,
            "recovery_succeeded":
                False,
            "recovery_events":
                [],
            "human_escalation":
                escalation,
            "llm_used":
                False,
        }

    valid, validation_errors = (
        validate_artifact(
            artifact
        )
    )

    metadata = artifact.get(
        "metadata",
        {},
    )

    capability_name = metadata.get(
        "capability_name"
    )

    # --------------------------------------------------------
    # INVALID ARTIFACT
    # --------------------------------------------------------

    if not valid:

        escalation = build_escalation(
            artifact_id=artifact_id,
            capability_name=
                capability_name,
            failed_step=None,
            failed_action=None,
            reason=
                "Artifact validation failed.",
            recovery_attempted=False,
            recovery_error=
                str(
                    validation_errors
                ),
        )

        return {
            "success": False,
            "mode": "escalated",
            "artifact_id":
                artifact_id,
            "capability_name":
                capability_name,
            "error":
                "Artifact validation failed.",
            "validation_errors":
                validation_errors,
            "recovery_attempted":
                False,
            "recovery_succeeded":
                False,
            "recovery_events":
                [],
            "human_escalation":
                escalation,
            "llm_used":
                False,
        }

    parameters_valid, missing = (
        validate_parameters(
            artifact,
            parameters,
        )
    )

    # --------------------------------------------------------
    # PARAMETER FAILURE
    # --------------------------------------------------------

    if not parameters_valid:

        escalation = build_escalation(
            artifact_id=artifact_id,
            capability_name=
                capability_name,
            failed_step=None,
            failed_action=None,
            reason=(
                "Required replay parameters "
                "are missing."
            ),
            recovery_attempted=False,
            recovery_error=(
                "Missing parameters: "
                + ", ".join(missing)
            ),
        )

        return {
            "success": False,
            "mode": "escalated",
            "artifact_id":
                artifact_id,
            "capability_name":
                capability_name,
            "error": (
                "Required replay parameters "
                "are missing."
            ),
            "missing_parameters":
                missing,
            "recovery_attempted":
                False,
            "recovery_succeeded":
                False,
            "recovery_events":
                [],
            "human_escalation":
                escalation,
            "llm_used":
                False,
        }

    # --------------------------------------------------------
    # HUMAN INTERVENTION REQUIRES VISIBLE BROWSER
    # --------------------------------------------------------

    if (
        allow_human_intervention
        and headless
    ):

        return {
            "success": False,
            "mode": "configuration_error",
            "artifact_id":
                artifact_id,
            "capability_name":
                capability_name,
            "error": (
                "Human intervention requires "
                "a headed browser."
            ),
            "llm_used":
                False,
        }

    url = (
        target_url
        or metadata.get(
            "target_url"
        )
        or metadata.get(
            "final_url"
        )
        or DEFAULT_TARGET_URL
    )

    actions = artifact.get(
        "steps",
        [],
    )

    executed_actions = []
    recovery_events = []

    recovery_attempted_any = False
    recovery_succeeded_any = False

    human_intervention_used = False
    active_intervention = None

    # ========================================================
    # SAME PLAYWRIGHT LIFETIME COVERS REPLAY + HUMAN + RESUME
    # ========================================================

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=headless
        )

        page = browser.new_page()

        page.set_default_timeout(
            ACTION_TIMEOUT_MS
        )

        page.set_default_navigation_timeout(
            NAVIGATION_TIMEOUT_MS
        )

        try:

            print()
            print(
                "=============================="
            )
            print(
                "DETERMINISTIC CAPABILITY REPLAY"
            )
            print(
                "=============================="
            )

            print(
                "Artifact:",
                artifact_id,
            )

            print(
                "Capability:",
                capability_name,
            )

            print(
                "LLM used: False"
            )

            print(
                "Human intervention:",
                allow_human_intervention,
            )

            print(
                "Headless:",
                headless,
            )

            page.goto(
                url,
                wait_until=
                    "domcontentloaded",
                timeout=
                    NAVIGATION_TIMEOUT_MS,
            )

            # =================================================
            # ACTION LOOP
            # =================================================

            for (
                index,
                original_action,
            ) in enumerate(
                actions,
                start=1,
            ):

                print(
                    f"[REPLAY] Step "
                    f"{index}/{len(actions)}"
                )

                action = dict(
                    original_action
                )

                # =============================================
                # TEST-ONLY FAILURE INJECTION
                # =============================================

                if (
                    simulate_selector_failure_step
                    is not None
                    and index
                    == simulate_selector_failure_step
                    and action.get(
                        "selector"
                    )
                ):

                    print(
                        "[TEST] Simulating stale "
                        f"selector at step {index}."
                    )

                    original_selector = str(
                        action.get(
                            "selector",
                            "",
                        )
                    )

                    if (
                        action.get(
                            "action"
                        )
                        == "click"
                        and (
                            "search"
                            in original_selector.lower()
                            or "button"
                            in original_selector.lower()
                        )
                    ):

                        action[
                            "selector"
                        ] = (
                            "#search-button-broken"
                        )

                    elif (
                        action.get(
                            "action"
                        )
                        in {
                            "fill",
                            "type",
                        }
                        and "member"
                        in original_selector.lower()
                    ):

                        action[
                            "selector"
                        ] = (
                            "#member-id-broken"
                        )

                    else:

                        action[
                            "selector"
                        ] = (
                            "#__simulated_stale_selector__"
                        )

                # =============================================
                # EXECUTE
                # =============================================

                try:

                    resolved_action = (
                        execute_replay_action(
                            page,
                            action,
                            parameters,
                        )
                    )

                    executed_actions.append(
                        resolved_action
                    )

                # =============================================
                # ACTION FAILURE
                # =============================================

                except Exception as action_error:

                    print(
                        f"[FAILURE] Step {index}: "
                        f"{action_error}"
                    )

                    recovery_attempted_any = True

                    recovery = (
                        attempt_action_recovery(
                            page=page,
                            action=action,
                            parameters=
                                parameters,
                            step_number=
                                index,
                            original_error=
                                action_error,
                            force_failure=
                                force_recovery_failure,
                        )
                    )

                    recovery_event = {
                        "step":
                            index,

                        "action":
                            resolve_value(
                                action,
                                parameters,
                            ),

                        **recovery,
                    }

                    recovery_events.append(
                        recovery_event
                    )

                    # =========================================
                    # RECOVERY SUCCESS
                    # =========================================

                    if recovery.get(
                        "success"
                    ):

                        recovery_succeeded_any = True

                        print(
                            "[RECOVERY] Success using:",
                            recovery.get(
                                "strategy"
                            ),
                        )

                        executed_actions.append(
                            resolve_value(
                                action,
                                parameters,
                            )
                        )

                    # =========================================
                    # RECOVERY FAILURE
                    # =========================================

                    else:

                        print(
                            "[RECOVERY] Failed."
                        )

                        failed_action = (
                            resolve_value(
                                action,
                                parameters,
                            )
                        )

                        reason = (
                            "Recorded capability "
                            "could not be safely replayed."
                        )

                        escalation = (
                            build_escalation(
                                artifact_id=
                                    artifact_id,
                                capability_name=
                                    capability_name,
                                failed_step=
                                    index,
                                failed_action=
                                    failed_action,
                                reason=
                                    reason,
                                recovery_attempted=
                                    recovery.get(
                                        "attempted",
                                        False,
                                    ),
                                recovery_error=
                                    recovery.get(
                                        "error"
                                    ),
                            )
                        )

                        # =====================================
                        # PERSIST INTERVENTION
                        # =====================================

                        intervention = (
                            create_persistent_intervention(
                                artifact_id=
                                    artifact_id,
                                capability_name=
                                    capability_name,
                                parameters=
                                    parameters,
                                failed_step=
                                    index,
                                failed_action=
                                    failed_action,
                                reason=
                                    reason,
                                recovery_attempted=
                                    recovery.get(
                                        "attempted",
                                        False,
                                    ),
                                recovery_error=
                                    recovery.get(
                                        "error"
                                    ),
                                target_url=
                                    url,
                                page=
                                    page,
                            )
                        )

                        active_intervention = (
                            intervention
                        )

                        intervention_id = (
                            intervention.get(
                                "intervention_id"
                            )
                        )

                        escalation[
                            "intervention_id"
                        ] = intervention_id

                        print(
                            "[INTERVENTION] Created:",
                            intervention_id,
                        )

                        # =====================================
                        # NO LIVE HUMAN MODE
                        # =====================================

                        if not allow_human_intervention:

                            return {
                                "success":
                                    False,

                                "mode":
                                    "waiting_for_human",

                                "artifact_id":
                                    artifact_id,

                                "capability_name":
                                    capability_name,

                                "intervention_id":
                                    intervention_id,

                                "intervention_status":
                                    "waiting_for_human",

                                "error":
                                    reason,

                                "failed_step":
                                    index,

                                "failed_action":
                                    failed_action,

                                "steps_executed":
                                    len(
                                        executed_actions
                                    ),

                                "recovery_attempted":
                                    recovery.get(
                                        "attempted",
                                        False,
                                    ),

                                "recovery_succeeded":
                                    False,

                                "recovery_events":
                                    recovery_events,

                                "human_escalation":
                                    escalation,

                                "human_intervention":
                                    {
                                        "required":
                                            True,

                                        "transferred":
                                            False,

                                        "resumed":
                                            False,
                                    },

                                "llm_used":
                                    False,
                            }

                        # =====================================
                        # LIVE SAME-BROWSER HUMAN HANDOFF
                        # =====================================

                        human_intervention_used = True

                        human_result = (
                            run_human_intervention(
                                page=
                                    page,
                                intervention=
                                    intervention,
                                failed_action=
                                    failed_action,
                            )
                        )

                        if not human_result.get(
                            "success"
                        ):

                            return {
                                "success":
                                    False,

                                "mode":
                                    "escalated",

                                "artifact_id":
                                    artifact_id,

                                "capability_name":
                                    capability_name,

                                "intervention_id":
                                    intervention_id,

                                "error":
                                    human_result.get(
                                        "error"
                                    ),

                                "failed_step":
                                    index,

                                "failed_action":
                                    failed_action,

                                "recovery_attempted":
                                    True,

                                "recovery_succeeded":
                                    False,

                                "recovery_events":
                                    recovery_events,

                                "human_escalation":
                                    escalation,

                                "human_intervention":
                                    {
                                        "required":
                                            True,

                                        "transferred":
                                            True,

                                        "resumed":
                                            False,
                                    },

                                "llm_used":
                                    False,
                            }

                        print(
                            "[HUMAN] Manual action confirmed."
                        )

                        print(
                            "[RESUME] Deterministic workflow resumed."
                        )

                        # Human completed the failed step.
                        # Therefore the loop proceeds to the next
                        # artifact action instead of retrying it.

                        executed_actions.append(
                            {
                                **failed_action,

                                "execution_source":
                                    "human_intervention",
                            }
                        )

                page.wait_for_timeout(
                    POST_ACTION_WAIT_MS
                )

            # =================================================
            # FINAL SEMANTIC CHECKPOINT
            # =================================================

            checkpoint = (
                run_final_checkpoint(
                    page,
                    artifact,
                    parameters,
                )
            )

            evidence = checkpoint.get(
                "evidence",
                {},
            )

            browser_output = (
                checkpoint.get(
                    "browser_output"
                )
                or evidence.get(
                    "browser_output"
                )
            )

            output_source = (
                checkpoint.get(
                    "output_source"
                )
            )

            if (
                browser_output
                and not output_source
            ):

                output_source = (
                    browser_output.get(
                        "source"
                    )
                )

            # =================================================
            # CHECKPOINT FAILURE
            # =================================================

            if not checkpoint.get(
                "success"
            ):

                reason = checkpoint.get(
                    "message",
                    "Semantic checkpoint failed.",
                )

                escalation = build_escalation(
                    artifact_id=
                        artifact_id,
                    capability_name=
                        capability_name,
                    failed_step=None,
                    failed_action=None,
                    reason=reason,
                    recovery_attempted=
                        recovery_attempted_any,
                    recovery_error=
                        reason,
                )

                return {
                    "success":
                        False,

                    "mode":
                        "escalated",

                    "artifact_id":
                        artifact_id,

                    "capability_name":
                        capability_name,

                    "intervention_id":
                        (
                            active_intervention.get(
                                "intervention_id"
                            )
                            if active_intervention
                            else None
                        ),

                    "error":
                        reason,

                    "steps_executed":
                        len(
                            executed_actions
                        ),

                    "recovery_attempted":
                        recovery_attempted_any,

                    "recovery_succeeded":
                        recovery_succeeded_any,

                    "recovery_events":
                        recovery_events,

                    "checkpoint":
                        checkpoint,

                    "browser_output":
                        browser_output,

                    "output_source":
                        output_source,

                    "human_escalation":
                        escalation,

                    "human_intervention":
                        {
                            "used":
                                human_intervention_used,

                            "transferred":
                                human_intervention_used,

                            "resumed":
                                human_intervention_used,
                        },

                    "llm_used":
                        False,
                }

            # =================================================
            # SUCCESS MODE
            # =================================================

            if human_intervention_used:

                mode = (
                    "human_resumed_replay"
                )

            elif recovery_succeeded_any:

                mode = (
                    "recovered_replay"
                )

            else:

                mode = "replay"

            result = {
                "success":
                    True,

                "mode":
                    mode,

                "artifact_id":
                    artifact_id,

                "capability_name":
                    capability_name,

                "parameters":
                    parameters,

                "steps_executed":
                    len(
                        executed_actions
                    ),

                "recovery_attempted":
                    recovery_attempted_any,

                "recovery_succeeded":
                    recovery_succeeded_any,

                "recovery_events":
                    recovery_events,

                "checkpoint":
                    checkpoint,

                "browser_output":
                    browser_output,

                "output_source":
                    output_source,

                "human_intervention":
                    {
                        "used":
                            human_intervention_used,

                        "transferred":
                            human_intervention_used,

                        "resumed":
                            human_intervention_used,
                    },

                "llm_used":
                    False,
            }

            # =================================================
            # COMPLETE INTERVENTION RECORD
            # =================================================

            if (
                human_intervention_used
                and active_intervention
            ):

                intervention_id = (
                    active_intervention.get(
                        "intervention_id"
                    )
                )

                result[
                    "intervention_id"
                ] = intervention_id

                try:

                    completed = mark_completed(
                        intervention_id,
                        result,
                    )

                    result[
                        "intervention_status"
                    ] = completed.get(
                        "status"
                    )

                except Exception as error:

                    result[
                        "intervention_status"
                    ] = (
                        "resume_succeeded_"
                        "but_persistence_failed"
                    )

                    result[
                        "intervention_persistence_error"
                    ] = str(error)

            return result

        # =====================================================
        # UNEXPECTED ERROR
        # =====================================================

        except Exception as unexpected_error:

            reason = (
                "Unexpected deterministic replay failure: "
                f"{unexpected_error}"
            )

            escalation = build_escalation(
                artifact_id=
                    artifact_id,
                capability_name=
                    capability_name,
                failed_step=None,
                failed_action=None,
                reason=reason,
                recovery_attempted=
                    recovery_attempted_any,
                recovery_error=
                    str(
                        unexpected_error
                    ),
            )

            return {
                "success":
                    False,

                "mode":
                    "escalated",

                "artifact_id":
                    artifact_id,

                "capability_name":
                    capability_name,

                "error":
                    reason,

                "steps_executed":
                    len(
                        executed_actions
                    ),

                "recovery_attempted":
                    recovery_attempted_any,

                "recovery_succeeded":
                    recovery_succeeded_any,

                "recovery_events":
                    recovery_events,

                "human_escalation":
                    escalation,

                "llm_used":
                    False,
            }

        finally:

            try:

                browser.close()

            except Exception:

                pass


# ============================================================
# CLI PARAMETER
# ============================================================

def parse_parameter(
    raw_parameter: str,
):
    if "=" not in raw_parameter:

        raise ValueError(
            "Parameter must use key=value format."
        )

    key, value = raw_parameter.split(
        "=",
        1,
    )

    key = key.strip()
    value = value.strip()

    if not key:

        raise ValueError(
            "Parameter name cannot be empty."
        )

    return key, value


# ============================================================
# CLI
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Deterministically replay a saved "
            "browser capability artifact."
        )
    )

    parser.add_argument(
        "artifact_id",
        help=(
            "Saved artifact ID."
        ),
    )

    parser.add_argument(
        "--member-id",
        dest="member_id",
        help="Runtime member ID.",
    )

    parser.add_argument(
        "--param",
        action="append",
        default=[],
        help=(
            "Additional key=value parameter. "
            "May be repeated."
        ),
    )

    parser.add_argument(
        "--target-url",
        dest="target_url",
        default=None,
        help="Optional target URL override.",
    )

    parser.add_argument(
        "--simulate-selector-failure-step",
        type=int,
        default=None,
        help=(
            "TEST ONLY: inject a stale selector "
            "at this step."
        ),
    )

    parser.add_argument(
        "--force-recovery-failure",
        action="store_true",
        help=(
            "TEST ONLY: force deterministic "
            "recovery to fail."
        ),
    )

    # --------------------------------------------------------
    # NEW
    # --------------------------------------------------------

    parser.add_argument(
        "--human-intervention",
        action="store_true",
        help=(
            "After deterministic recovery failure, "
            "hand the same browser session to a "
            "human and resume afterward."
        ),
    )

    parser.add_argument(
        "--headed",
        action="store_true",
        help=(
            "Show Chromium instead of running "
            "headless."
        ),
    )

    args = parser.parse_args()

    if (
        args.human_intervention
        and not args.headed
    ):

        parser.error(
            "--human-intervention requires "
            "--headed."
        )

    parameters = {}

    if args.member_id:

        parameters[
            "member_id"
        ] = args.member_id

    for raw_parameter in args.param:

        key, value = parse_parameter(
            raw_parameter
        )

        parameters[
            key
        ] = value

    result = replay_artifact(
        artifact_id=
            args.artifact_id,

        parameters=
            parameters,

        target_url=
            args.target_url,

        simulate_selector_failure_step=
            args.simulate_selector_failure_step,

        force_recovery_failure=
            args.force_recovery_failure,

        allow_human_intervention=
            args.human_intervention,

        headless=
            not args.headed,
    )

    print()
    print(
        "=============================="
    )
    print(
        "REPLAY RESULT"
    )
    print(
        "=============================="
    )

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()