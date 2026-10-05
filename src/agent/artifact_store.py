import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ============================================================
# PATHS
# ============================================================

BASE_DIR = (
    Path(__file__)
    .resolve()
    .parent
    .parent
    .parent
)

ARTIFACT_DIR = BASE_DIR / "artifacts"

ARTIFACT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# HELPERS
# ============================================================

def _timestamp() -> str:
    """
    Return the current UTC timestamp.
    """

    return datetime.now(
        timezone.utc
    ).isoformat()


def _artifact_path(
    artifact_id: str,
) -> Path:
    """
    Return the JSON path for one artifact.
    """

    return (
        ARTIFACT_DIR
        / f"{artifact_id}.json"
    )


# ============================================================
# CREATE ARTIFACT
# ============================================================

def create_artifact(
    goal: str,
    app: str,
    steps: List[Dict[str, Any]],
    inputs: Optional[
        Dict[str, Any]
    ] = None,
    outputs: Optional[
        Dict[str, Any]
    ] = None,
    success_condition: Optional[
        Dict[str, Any]
    ] = None,
) -> Dict[str, Any]:
    """
    Create a versioned, replayable capability artifact.

    The artifact captures:

    - what goal was accomplished
    - which application was used
    - ordered UI actions
    - typed input parameters
    - expected outputs
    - replay success condition
    """

    artifact_id = (
        "artifact_"
        + datetime.now(
            timezone.utc
        ).strftime(
            "%Y%m%d_%H%M%S_%f"
        )
    )

    artifact = {
        "artifact_id":
            artifact_id,

        "version":
            1,

        "created_at":
            _timestamp(),

        "updated_at":
            _timestamp(),

        "capability": {
            "goal":
                goal,

            "application":
                app,
        },

        "inputs":
            inputs or {},

        "steps":
            steps,

        "outputs":
            outputs or {},

        "success_condition":
            success_condition or {},

        "metadata": {
            "status":
                "approved",

            "replayable":
                True,
        },
    }

    path = _artifact_path(
        artifact_id
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            artifact,
            file,
            indent=2,
            ensure_ascii=False,
        )

    return artifact


# ============================================================
# SAVE ARTIFACT
# ============================================================

def save_artifact(
    artifact: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Persist an existing artifact.
    """

    if "artifact_id" not in artifact:

        raise ValueError(
            "Artifact must contain artifact_id."
        )

    artifact[
        "updated_at"
    ] = _timestamp()

    path = _artifact_path(
        artifact["artifact_id"]
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            artifact,
            file,
            indent=2,
            ensure_ascii=False,
        )

    return artifact


# ============================================================
# LOAD ARTIFACT
# ============================================================

def load_artifact(
    artifact_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Load one saved artifact.
    """

    path = _artifact_path(
        artifact_id
    )

    if not path.exists():

        return None

    try:

        with path.open(
            "r",
            encoding="utf-8",
        ) as file:

            return json.load(
                file
            )

    except (
        json.JSONDecodeError,
        OSError,
    ):

        return None


# ============================================================
# LIST ARTIFACTS
# ============================================================

def list_artifacts() -> List[
    Dict[str, Any]
]:
    """
    Return all saved capability artifacts.

    Full artifacts are returned rather than
    metadata-only summaries.

    This allows the capability registry to
    inspect:

    - capability
    - inputs
    - steps
    - outputs
    - success conditions
    - metadata
    """

    artifacts = []

    for path in sorted(
        ARTIFACT_DIR.glob(
            "artifact_*.json"
        )
    ):

        try:

            with path.open(
                "r",
                encoding="utf-8",
            ) as file:

                artifact = json.load(
                    file
                )

            artifacts.append(
                artifact
            )

        except (
            json.JSONDecodeError,
            OSError,
        ):

            continue

    return artifacts


# ============================================================
# DELETE ARTIFACT
# ============================================================

def delete_artifact(
    artifact_id: str,
) -> bool:
    """
    Delete an artifact.
    """

    path = _artifact_path(
        artifact_id
    )

    if not path.exists():

        return False

    path.unlink()

    return True


# ============================================================
# VALIDATE ARTIFACT
# ============================================================

def validate_artifact(
    artifact: Dict[str, Any],
) -> tuple[
    bool,
    List[str],
]:
    """
    Validate the minimum contract required
    for deterministic replay.
    """

    errors = []

    # --------------------------------------------------------
    # Artifact ID
    # --------------------------------------------------------

    if not artifact.get(
        "artifact_id"
    ):

        errors.append(
            "Missing artifact_id."
        )

    # --------------------------------------------------------
    # Version
    # --------------------------------------------------------

    if not artifact.get(
        "version"
    ):

        errors.append(
            "Missing version."
        )

    # --------------------------------------------------------
    # Capability
    # --------------------------------------------------------

    capability = artifact.get(
        "capability"
    )

    if not isinstance(
        capability,
        dict,
    ):

        errors.append(
            "Missing capability object."
        )

    else:

        if not capability.get(
            "goal"
        ):

            errors.append(
                "Missing capability.goal."
            )

        if not capability.get(
            "application"
        ):

            errors.append(
                "Missing capability.application."
            )

    # --------------------------------------------------------
    # Steps
    # --------------------------------------------------------

    steps = artifact.get(
        "steps"
    )

    if not isinstance(
        steps,
        list,
    ):

        errors.append(
            "steps must be a list."
        )

    elif len(steps) == 0:

        errors.append(
            "Artifact must contain at least one step."
        )

    else:

        for index, step in enumerate(
            steps,
            start=1,
        ):

            if not isinstance(
                step,
                dict,
            ):

                errors.append(
                    f"Step {index} must be an object."
                )

                continue

            if not step.get(
                "action"
            ):

                errors.append(
                    f"Step {index} is missing action."
                )

    # --------------------------------------------------------
    # Inputs
    # --------------------------------------------------------

    inputs = artifact.get(
        "inputs"
    )

    if not isinstance(
        inputs,
        dict,
    ):

        errors.append(
            "inputs must be an object."
        )

    # --------------------------------------------------------
    # Outputs
    # --------------------------------------------------------

    outputs = artifact.get(
        "outputs"
    )

    if not isinstance(
        outputs,
        dict,
    ):

        errors.append(
            "outputs must be an object."
        )

    # --------------------------------------------------------
    # Success condition
    # --------------------------------------------------------

    success_condition = artifact.get(
        "success_condition"
    )

    if not isinstance(
        success_condition,
        dict,
    ):

        errors.append(
            "success_condition must be an object."
        )

    # --------------------------------------------------------
    # Metadata
    # --------------------------------------------------------

    metadata = artifact.get(
        "metadata"
    )

    if not isinstance(
        metadata,
        dict,
    ):

        errors.append(
            "metadata must be an object."
        )

    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    return (
        len(errors) == 0,
        errors,
    )


# ============================================================
# FIND ARTIFACT BY CAPABILITY
# ============================================================

def find_artifact_by_capability(
    capability_name: str,
) -> Optional[
    Dict[str, Any]
]:
    """
    Find the newest approved, replayable
    artifact for an exact capability name.

    This lookup itself does NOT use an LLM.

    Example:

        pending_claims_lookup

    can map to a reusable artifact containing:

        fill #member-id -> {{member_id}}
        click #search-button
    """

    capability_name = str(
        capability_name or ""
    ).strip().lower()

    if not capability_name:

        return None

    matches = []

    for artifact in list_artifacts():

        # ----------------------------------------------------
        # Metadata
        # ----------------------------------------------------

        metadata = artifact.get(
            "metadata",
            {},
        )

        if not isinstance(
            metadata,
            dict,
        ):

            continue

        # ----------------------------------------------------
        # Must be replayable
        # ----------------------------------------------------

        if not metadata.get(
            "replayable",
            False,
        ):

            continue

        # ----------------------------------------------------
        # Must be approved
        # ----------------------------------------------------

        if metadata.get(
            "status"
        ) != "approved":

            continue

        # ----------------------------------------------------
        # Exact capability name
        # ----------------------------------------------------

        stored_name = str(
            metadata.get(
                "capability_name",
                "",
            )
        ).strip().lower()

        if (
            stored_name
            == capability_name
        ):

            matches.append(
                artifact
            )

    # --------------------------------------------------------
    # No capability found
    # --------------------------------------------------------

    if not matches:

        return None

    # --------------------------------------------------------
    # Newest artifact wins
    # --------------------------------------------------------

    matches.sort(
        key=lambda item:
            item.get(
                "updated_at",
                "",
            ),
        reverse=True,
    )

    return matches[0]


# ============================================================
# ARTIFACT SUMMARY
# ============================================================

def get_artifact_summary(
    artifact: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Return a lightweight summary for APIs,
    logs, or future capability registry UI.
    """

    capability = artifact.get(
        "capability",
        {},
    )

    metadata = artifact.get(
        "metadata",
        {},
    )

    return {
        "artifact_id":
            artifact.get(
                "artifact_id"
            ),

        "version":
            artifact.get(
                "version"
            ),

        "goal":
            capability.get(
                "goal"
            ),

        "application":
            capability.get(
                "application"
            ),

        "capability_name":
            metadata.get(
                "capability_name"
            ),

        "status":
            metadata.get(
                "status"
            ),

        "replayable":
            metadata.get(
                "replayable",
                False,
            ),

        "replay_requires_llm":
            metadata.get(
                "replay_requires_llm"
            ),

        "step_count":
            len(
                artifact.get(
                    "steps",
                    [],
                )
            ),

        "created_at":
            artifact.get(
                "created_at"
            ),

        "updated_at":
            artifact.get(
                "updated_at"
            ),
    }