"""
Human Intervention Manager

Stores and manages human-in-the-loop intervention records for
browser capability replay.

This module does NOT use an LLM.

Lifecycle:

    waiting_for_human
            ↓
    human_in_control
            ↓
    ready_to_resume
            ↓
        resumed
            ↓
       completed

Interventions are persisted as JSON files so that the state survives
HTTP requests and can be inspected later as assessment evidence.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_INTERVENTION_DIR = (
    PROJECT_ROOT
    / "artifacts"
    / "interventions"
)

INTERVENTION_DIR = Path(
    os.getenv(
        "INTERVENTION_DIR",
        str(DEFAULT_INTERVENTION_DIR),
    )
)

INTERVENTION_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# STATUS CONSTANTS
# ============================================================

STATUS_WAITING_FOR_HUMAN = "waiting_for_human"

STATUS_HUMAN_IN_CONTROL = "human_in_control"

STATUS_READY_TO_RESUME = "ready_to_resume"

STATUS_RESUMED = "resumed"

STATUS_COMPLETED = "completed"

STATUS_CANCELLED = "cancelled"


VALID_STATUSES = {
    STATUS_WAITING_FOR_HUMAN,
    STATUS_HUMAN_IN_CONTROL,
    STATUS_READY_TO_RESUME,
    STATUS_RESUMED,
    STATUS_COMPLETED,
    STATUS_CANCELLED,
}


# ============================================================
# HELPERS
# ============================================================

def utc_now() -> str:
    """
    Return the current UTC time in ISO-8601 format.
    """

    return datetime.now(
        timezone.utc
    ).isoformat()


def generate_intervention_id() -> str:
    """
    Generate a unique intervention ID.
    """

    timestamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%d_%H%M%S")

    random_part = uuid.uuid4().hex[:8]

    return (
        f"intervention_"
        f"{timestamp}_"
        f"{random_part}"
    )


def intervention_path(
    intervention_id: str,
) -> Path:
    """
    Return the JSON path for an intervention.
    """

    safe_id = str(
        intervention_id
    ).strip()

    if not safe_id:
        raise ValueError(
            "intervention_id cannot be empty."
        )

    # Prevent path traversal.
    if (
        "/" in safe_id
        or "\\" in safe_id
        or ".." in safe_id
    ):
        raise ValueError(
            "Invalid intervention_id."
        )

    return (
        INTERVENTION_DIR
        / f"{safe_id}.json"
    )


def _write_json_atomic(
    path: Path,
    data: Dict[str, Any],
):
    """
    Write JSON atomically.

    First write to a temporary file, then replace the target.
    """

    temp_path = path.with_suffix(
        ".tmp"
    )

    with temp_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
        )

    temp_path.replace(path)


# ============================================================
# CREATE INTERVENTION
# ============================================================

def create_intervention(
    artifact_id: str,
    capability_name: Optional[str],
    parameters: Dict[str, Any],
    failed_step: int,
    failed_action: Dict[str, Any],
    reason: str,
    recovery_attempted: bool = False,
    recovery_error: Optional[str] = None,
    target_url: Optional[str] = None,
    browser_state: Optional[
        Dict[str, Any]
    ] = None,
) -> Dict[str, Any]:
    """
    Create a persistent human intervention record.

    failed_step is 1-based.

    Example:
        failed_step = 2

    means step 2 failed.

    The human is expected to complete or repair the failed action.
    After that, deterministic replay can resume from the next step.
    """

    intervention_id = (
        generate_intervention_id()
    )

    now = utc_now()

    next_step = (
        int(failed_step) + 1
        if failed_step is not None
        else None
    )

    intervention = {
        "intervention_id":
            intervention_id,

        "status":
            STATUS_WAITING_FOR_HUMAN,

        "created_at":
            now,

        "updated_at":
            now,

        "artifact_id":
            artifact_id,

        "capability_name":
            capability_name,

        "parameters":
            dict(parameters or {}),

        "failed_step":
            failed_step,

        "next_step":
            next_step,

        "failed_action":
            dict(
                failed_action or {}
            ),

        "reason":
            reason,

        "recovery_attempted":
            bool(
                recovery_attempted
            ),

        "recovery_error":
            recovery_error,

        "target_url":
            target_url,

        "browser_state":
            browser_state or {},

        "human_action": None,

        "human_notes": None,

        "human_started_at": None,

        "human_completed_at": None,

        "resume_started_at": None,

        "completed_at": None,

        "resume_result": None,

        "llm_used":
            False,

        "history": [
            {
                "timestamp":
                    now,

                "event":
                    "intervention_created",

                "status":
                    STATUS_WAITING_FOR_HUMAN,

                "details": {
                    "failed_step":
                        failed_step,

                    "reason":
                        reason,
                },
            }
        ],
    }

    save_intervention(
        intervention
    )

    return intervention


# ============================================================
# SAVE
# ============================================================

def save_intervention(
    intervention: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Save an intervention record.
    """

    if not isinstance(
        intervention,
        dict,
    ):
        raise ValueError(
            "Intervention must be a dictionary."
        )

    intervention_id = (
        intervention.get(
            "intervention_id"
        )
    )

    if not intervention_id:
        raise ValueError(
            "Intervention is missing intervention_id."
        )

    status = intervention.get(
        "status"
    )

    if status not in VALID_STATUSES:
        raise ValueError(
            f"Invalid intervention status: {status}"
        )

    intervention[
        "updated_at"
    ] = utc_now()

    path = intervention_path(
        intervention_id
    )

    _write_json_atomic(
        path,
        intervention,
    )

    return intervention


# ============================================================
# LOAD
# ============================================================

def load_intervention(
    intervention_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Load an intervention by ID.

    Returns None when it does not exist.
    """

    path = intervention_path(
        intervention_id
    )

    if not path.exists():
        return None

    try:
        with path.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(
                file
            )

        if not isinstance(
            data,
            dict,
        ):
            return None

        return data

    except (
        json.JSONDecodeError,
        OSError,
    ):
        return None


# ============================================================
# LIST
# ============================================================

def list_interventions(
    status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    List interventions, newest first.

    Optional:
        status="waiting_for_human"
    """

    results = []

    if (
        status is not None
        and status not in VALID_STATUSES
    ):
        raise ValueError(
            f"Invalid intervention status: {status}"
        )

    for path in INTERVENTION_DIR.glob(
        "intervention_*.json"
    ):
        try:
            with path.open(
                "r",
                encoding="utf-8",
            ) as file:
                intervention = (
                    json.load(file)
                )

            if not isinstance(
                intervention,
                dict,
            ):
                continue

            if (
                status is not None
                and intervention.get(
                    "status"
                )
                != status
            ):
                continue

            results.append(
                intervention
            )

        except (
            json.JSONDecodeError,
            OSError,
        ):
            continue

    results.sort(
        key=lambda item: item.get(
            "created_at",
            "",
        ),
        reverse=True,
    )

    return results


# ============================================================
# HISTORY
# ============================================================

def add_history_event(
    intervention: Dict[str, Any],
    event: str,
    details: Optional[
        Dict[str, Any]
    ] = None,
):
    """
    Append an auditable event to intervention history.
    """

    history = intervention.setdefault(
        "history",
        [],
    )

    history.append(
        {
            "timestamp":
                utc_now(),

            "event":
                event,

            "status":
                intervention.get(
                    "status"
                ),

            "details":
                details or {},
        }
    )


# ============================================================
# HUMAN TAKES CONTROL
# ============================================================

def start_human_intervention(
    intervention_id: str,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Mark an intervention as actively controlled by a human.
    """

    intervention = (
        load_intervention(
            intervention_id
        )
    )

    if intervention is None:
        raise ValueError(
            "Intervention not found."
        )

    current_status = intervention.get(
        "status"
    )

    if current_status != (
        STATUS_WAITING_FOR_HUMAN
    ):
        raise ValueError(
            "Human control can only start "
            "from waiting_for_human status. "
            f"Current status: {current_status}"
        )

    intervention[
        "status"
    ] = STATUS_HUMAN_IN_CONTROL

    intervention[
        "human_started_at"
    ] = utc_now()

    if notes:
        intervention[
            "human_notes"
        ] = notes

    add_history_event(
        intervention,
        "human_control_started",
        {
            "notes":
                notes,
        },
    )

    return save_intervention(
        intervention
    )


# ============================================================
# HUMAN COMPLETES FAILED ACTION
# ============================================================

def complete_human_action(
    intervention_id: str,
    action_taken: str,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Record that the human completed the required browser action.

    The intervention becomes ready_to_resume.
    """

    intervention = (
        load_intervention(
            intervention_id
        )
    )

    if intervention is None:
        raise ValueError(
            "Intervention not found."
        )

    current_status = intervention.get(
        "status"
    )

    if current_status not in {
        STATUS_WAITING_FOR_HUMAN,
        STATUS_HUMAN_IN_CONTROL,
    }:
        raise ValueError(
            "Human action cannot be completed "
            f"from status: {current_status}"
        )

    if not str(
        action_taken
    ).strip():
        raise ValueError(
            "action_taken cannot be empty."
        )

    intervention[
        "status"
    ] = STATUS_READY_TO_RESUME

    intervention[
        "human_action"
    ] = str(
        action_taken
    ).strip()

    intervention[
        "human_completed_at"
    ] = utc_now()

    if notes:
        intervention[
            "human_notes"
        ] = notes

    add_history_event(
        intervention,
        "human_action_completed",
        {
            "action_taken":
                intervention[
                    "human_action"
                ],

            "notes":
                notes,
        },
    )

    return save_intervention(
        intervention
    )


# ============================================================
# MARK RESUME STARTED
# ============================================================

def mark_resumed(
    intervention_id: str,
) -> Dict[str, Any]:
    """
    Mark an intervention as resumed.

    Only ready_to_resume interventions may resume.
    """

    intervention = (
        load_intervention(
            intervention_id
        )
    )

    if intervention is None:
        raise ValueError(
            "Intervention not found."
        )

    current_status = intervention.get(
        "status"
    )

    if current_status != (
        STATUS_READY_TO_RESUME
    ):
        raise ValueError(
            "Intervention is not ready to resume. "
            f"Current status: {current_status}"
        )

    intervention[
        "status"
    ] = STATUS_RESUMED

    intervention[
        "resume_started_at"
    ] = utc_now()

    add_history_event(
        intervention,
        "replay_resumed",
        {
            "next_step":
                intervention.get(
                    "next_step"
                ),
        },
    )

    return save_intervention(
        intervention
    )


# ============================================================
# MARK COMPLETED
# ============================================================

def mark_completed(
    intervention_id: str,
    resume_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Mark the intervention as successfully completed.
    """

    intervention = (
        load_intervention(
            intervention_id
        )
    )

    if intervention is None:
        raise ValueError(
            "Intervention not found."
        )

    if intervention.get(
        "status"
    ) != STATUS_RESUMED:
        raise ValueError(
            "Only a resumed intervention "
            "can be completed."
        )

    intervention[
        "status"
    ] = STATUS_COMPLETED

    intervention[
        "completed_at"
    ] = utc_now()

    intervention[
        "resume_result"
    ] = resume_result

    add_history_event(
        intervention,
        "intervention_completed",
        {
            "success":
                bool(
                    resume_result.get(
                        "success"
                    )
                ),

            "llm_used":
                bool(
                    resume_result.get(
                        "llm_used",
                        False,
                    )
                ),
        },
    )

    return save_intervention(
        intervention
    )


# ============================================================
# CANCEL
# ============================================================

def cancel_intervention(
    intervention_id: str,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Cancel an intervention.
    """

    intervention = (
        load_intervention(
            intervention_id
        )
    )

    if intervention is None:
        raise ValueError(
            "Intervention not found."
        )

    if intervention.get(
        "status"
    ) == STATUS_COMPLETED:
        raise ValueError(
            "Completed intervention "
            "cannot be cancelled."
        )

    intervention[
        "status"
    ] = STATUS_CANCELLED

    add_history_event(
        intervention,
        "intervention_cancelled",
        {
            "reason":
                reason,
        },
    )

    return save_intervention(
        intervention
    )


# ============================================================
# READY CHECK
# ============================================================

def is_ready_to_resume(
    intervention_id: str,
) -> bool:
    """
    Return True if the intervention is ready for deterministic resume.
    """

    intervention = (
        load_intervention(
            intervention_id
        )
    )

    if intervention is None:
        return False

    return (
        intervention.get(
            "status"
        )
        == STATUS_READY_TO_RESUME
    )


# ============================================================
# PUBLIC SUMMARY
# ============================================================

def get_intervention_summary(
    intervention_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Return a compact intervention summary suitable for an API response.
    """

    intervention = (
        load_intervention(
            intervention_id
        )
    )

    if intervention is None:
        return None

    return {
        "intervention_id":
            intervention.get(
                "intervention_id"
            ),

        "status":
            intervention.get(
                "status"
            ),

        "artifact_id":
            intervention.get(
                "artifact_id"
            ),

        "capability_name":
            intervention.get(
                "capability_name"
            ),

        "failed_step":
            intervention.get(
                "failed_step"
            ),

        "next_step":
            intervention.get(
                "next_step"
            ),

        "failed_action":
            intervention.get(
                "failed_action"
            ),

        "reason":
            intervention.get(
                "reason"
            ),

        "recovery_attempted":
            intervention.get(
                "recovery_attempted"
            ),

        "recovery_error":
            intervention.get(
                "recovery_error"
            ),

        "human_action":
            intervention.get(
                "human_action"
            ),

        "human_notes":
            intervention.get(
                "human_notes"
            ),

        "created_at":
            intervention.get(
                "created_at"
            ),

        "updated_at":
            intervention.get(
                "updated_at"
            ),

        "completed_at":
            intervention.get(
                "completed_at"
            ),

        "llm_used":
            intervention.get(
                "llm_used",
                False,
            ),
    }