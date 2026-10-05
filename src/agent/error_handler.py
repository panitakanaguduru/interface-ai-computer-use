from datetime import datetime, timezone
from typing import Any, Dict, Optional

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


# ============================================================
# ERROR CLASSIFICATION
# ============================================================

def handle_agent_error(error: Exception) -> Dict[str, Any]:
    """
    Classify an agent/browser failure.

    This function is intentionally deterministic.
    It does not call an LLM.
    """

    if isinstance(error, PlaywrightTimeoutError):
        return {
            "recoverable": True,
            "error_type": "browser_timeout",
            "message": "Browser action timed out.",
        }

    if isinstance(error, KeyError):
        return {
            "recoverable": True,
            "error_type": "missing_action_data",
            "message": (
                f"AI action was missing required data: {error}"
            ),
        }

    if isinstance(error, ValueError):
        return {
            "recoverable": True,
            "error_type": "invalid_action",
            "message": str(error),
        }

    # Playwright selector/action errors frequently arrive as
    # generic exceptions, so inspect the message conservatively.
    message = str(error).lower()

    selector_signals = (
        "locator",
        "selector",
        "waiting for",
        "not found",
        "not visible",
        "timeout",
        "element",
    )

    if any(signal in message for signal in selector_signals):
        return {
            "recoverable": True,
            "error_type": "browser_element_failure",
            "message": str(error),
        }

    return {
        "recoverable": False,
        "error_type": "unexpected_error",
        "message": f"Unexpected agent error: {error}",
    }


# ============================================================
# RECOVERY PLAN
# ============================================================

def build_recovery_plan(
    action: Dict[str, Any],
    error: Exception,
    step_number: int,
) -> Dict[str, Any]:
    """
    Decide whether bounded deterministic recovery is allowed.

    Recovery is deliberately narrow:
    - no LLM
    - no arbitrary exploration
    - no new member IDs
    - no destructive actions
    """

    classification = handle_agent_error(error)

    action_type = str(
        action.get("action", "")
    ).strip().lower()

    selector = str(
        action.get("selector", "")
    ).strip()

    if not classification["recoverable"]:
        return {
            "allowed": False,
            "step_number": step_number,
            "action_type": action_type,
            "original_selector": selector,
            "reason": classification["message"],
            "error_type": classification["error_type"],
        }

    safe_action_types = {
        "fill",
        "click",
        "type",
        "press",
        "select",
        "check",
        "uncheck",
    }

    if action_type not in safe_action_types:
        return {
            "allowed": False,
            "step_number": step_number,
            "action_type": action_type,
            "original_selector": selector,
            "reason": (
                "No bounded recovery strategy exists "
                f"for action '{action_type}'."
            ),
            "error_type": classification["error_type"],
        }

    return {
        "allowed": True,
        "step_number": step_number,
        "action_type": action_type,
        "original_selector": selector,
        "reason": classification["message"],
        "error_type": classification["error_type"],
    }


# ============================================================
# HUMAN ESCALATION
# ============================================================

def create_human_escalation(
    *,
    artifact_id: Optional[str],
    capability_name: Optional[str],
    failed_step: Optional[int],
    failed_action: Optional[Dict[str, Any]],
    reason: str,
    recovery_attempted: bool,
    recovery_error: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Produce a structured escalation record.

    No sensitive browser body text is copied into this object.
    """

    return {
        "required": True,
        "status": "human_review_required",
        "created_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "artifact_id": artifact_id,
        "capability_name": capability_name,
        "failed_step": failed_step,
        "failed_action": {
            "action": (
                failed_action.get("action")
                if isinstance(failed_action, dict)
                else None
            ),
            "selector": (
                failed_action.get("selector")
                if isinstance(failed_action, dict)
                else None
            ),
        },
        "reason": reason,
        "recovery_attempted": recovery_attempted,
        "recovery_error": recovery_error,
        "recommended_action": (
            "Review the saved capability and the current UI "
            "before approving a new workflow."
        ),
    }