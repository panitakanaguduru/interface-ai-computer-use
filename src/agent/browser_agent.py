import os

from playwright.sync_api import sync_playwright

from observer import observe_page
from llm_planner import llm_plan
from executor import execute_action
from action_validator import validate_action
from action_history import ActionHistory
from loop_guard import is_repeating_action
from safety import check_action_safety
from run_logger import RunLogger
from error_handler import handle_agent_error

from result_reporter import (
    build_final_result,
    print_final_result,
)

from artifact_store import (
    create_artifact,
    save_artifact,
    validate_artifact,
)


# ============================================================
# CONFIGURATION
# ============================================================

MAX_STEPS = 10

PORTAL_URL = os.getenv(
    "TARGET_APP_URL",
    (
        "https://interface-ai-computer-use.onrender.com"
        if os.getenv("RENDER")
        else "http://localhost:8000"
    ),
)


# ============================================================
# OBSERVATION DISPLAY
# ============================================================

def print_observation(observation):
    """
    Print a compact representation of the
    current browser observation.
    """

    print("\n--- OBSERVATION ---")

    print(
        "URL:",
        observation.get("url"),
    )

    print(
        "Title:",
        observation.get("title"),
    )

    print(
        "Inputs:",
        observation.get("inputs"),
    )

    print(
        "Buttons:",
        observation.get("buttons"),
    )

    print("-------------------")


# ============================================================
# PARAMETERIZATION
# ============================================================

def parameterize_value(
    value,
    member_id,
):
    """
    Replace a concrete member ID with the
    reusable {{member_id}} parameter.

    Example:

        10002

    becomes:

        {{member_id}}
    """

    if not member_id:
        return value

    if isinstance(value, str):

        return value.replace(
            str(member_id),
            "{{member_id}}",
        )

    if isinstance(value, list):

        return [
            parameterize_value(
                item,
                member_id,
            )
            for item in value
        ]

    if isinstance(value, dict):

        return {
            key: parameterize_value(
                item,
                member_id,
            )
            for key, item in value.items()
        }

    return value


def parameterize_actions(
    actions,
    member_id=None,
):
    """
    Convert discovered browser actions into
    reusable artifact actions.
    """

    return [
        parameterize_value(
            action,
            member_id,
        )
        for action in actions
    ]


# ============================================================
# CREATE DISCOVERY ARTIFACT
# ============================================================

def create_discovery_artifact(
    task,
    actions,
    member_id=None,
    final_url=None,
    capability_name=None,
):
    """
    Convert a successful LLM discovery run
    into a reusable capability artifact.

    capability_name is a stable identifier
    used later to find and replay the workflow.

    Example:

        pending_claims_lookup
    """

    reusable_actions = parameterize_actions(
        actions,
        member_id,
    )

    # --------------------------------------------------------
    # Runtime inputs
    # --------------------------------------------------------

    artifact_inputs = {}

    if member_id:

        artifact_inputs = {
            "member_id": {
                "type": "string",
                "required": True,
                "placeholder": "{{member_id}}",
                "description":
                    "Member identifier used by the capability.",
            }
        }

    # --------------------------------------------------------
    # Create base artifact
    # --------------------------------------------------------

    artifact = create_artifact(
        goal=task,
        app="MemberOps Operations Portal",
        steps=reusable_actions,
        inputs=artifact_inputs,
        outputs={
            "type":
                "natural_language_answer",

            "description":
                "Answer produced after successfully "
                "completing the browser workflow.",
        },
        success_condition={
            "type":
                "agent_completion",

            "description":
                "The discovered workflow completes "
                "and reaches the agent done state.",
        },
    )

    # --------------------------------------------------------
    # Discovery metadata
    # --------------------------------------------------------

    artifact["metadata"].update(
        {
            "capability_name":
                capability_name,

            "mode":
                "discovery",

            "discovered_by":
                "llm",

            "replay_requires_llm":
                False,

            "final_url":
                final_url,
        }
    )

    # --------------------------------------------------------
    # Validate artifact
    # --------------------------------------------------------

    valid, errors = validate_artifact(
        artifact
    )

    if not valid:

        raise ValueError(
            "Artifact validation failed: "
            + "; ".join(errors)
        )

    # --------------------------------------------------------
    # Save artifact
    # --------------------------------------------------------

    artifact = save_artifact(
        artifact
    )

    return artifact


# ============================================================
# MAIN AGENT
# ============================================================

def run_agent(
    task,
    headless=True,
    member_id=None,
    capability_name=None,
):
    """
    Run the MemberOps computer-use discovery agent.

    Discovery:

        Natural-language task
                ↓
            Observe UI
                ↓
           LLM planning
                ↓
           Validation
                ↓
             Safety
                ↓
           Execution
                ↓
            Observe
                ↓
              Done
                ↓
        Capability artifact

    The saved artifact can later be replayed
    deterministically without browser-planning
    LLM calls.
    """

    task = str(
        task or ""
    ).strip()

    if capability_name is not None:

        capability_name = str(
            capability_name
        ).strip().lower()

        if not capability_name:
            capability_name = None

    # --------------------------------------------------------
    # Validate task
    # --------------------------------------------------------

    if not task:

        return {
            "success": False,
            "task": "",
            "answer": None,
            "steps": 0,
            "actions": [],
            "final_url": None,
            "log_file": None,
            "artifact_id": None,
            "artifact_file": None,
            "capability_name":
                capability_name,
            "error":
                "No task was provided.",
        }

    # --------------------------------------------------------
    # Display run information
    # --------------------------------------------------------

    print(
        f"\nTask: {task}"
    )

    print(
        f"Target application: {PORTAL_URL}"
    )

    if member_id:

        print(
            f"Authorized member: {member_id}"
        )

    if capability_name:

        print(
            f"Capability: {capability_name}"
        )

    # --------------------------------------------------------
    # State
    # --------------------------------------------------------

    history = ActionHistory()

    logger = RunLogger()

    logger.log(
        "task_started",
        {
            "task":
                task,

            "target_url":
                PORTAL_URL,

            "member_id":
                member_id,

            "capability_name":
                capability_name,

            "mode":
                "discovery",
        },
    )

    result = {
        "success": False,
        "task": task,
        "answer": None,
        "steps": 0,
        "actions": [],
        "final_url": None,

        "log_file": str(
            logger.file_path
        ),

        "artifact_id": None,
        "artifact_file": None,

        "capability_name":
            capability_name,

        "error": None,
    }

    # ========================================================
    # PLAYWRIGHT
    # ========================================================

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=headless
        )

        page = browser.new_page()

        try:

            # =================================================
            # OPEN TARGET APPLICATION
            # =================================================

            print(
                "\nOpening target application:"
            )

            print(
                PORTAL_URL
            )

            page.goto(
                PORTAL_URL,
                wait_until="domcontentloaded",
            )

            # =================================================
            # DISCOVERY LOOP
            # =================================================

            for step in range(
                1,
                MAX_STEPS + 1,
            ):

                result["steps"] = step

                print(
                    f"\n========== "
                    f"AGENT STEP {step} "
                    f"=========="
                )

                # =============================================
                # OBSERVE
                # =============================================

                observation = observe_page(
                    page
                )

                print_observation(
                    observation
                )

                logger.log_observation(
                    observation
                )

                # =============================================
                # LLM PLAN
                # =============================================

                action = llm_plan(
                    task,
                    observation,
                )

                print(
                    "\n--- AI PLAN ---"
                )

                print(
                    action
                )

                print(
                    "---------------"
                )

                logger.log_plan(
                    action
                )

                # =============================================
                # VALIDATION
                # =============================================

                (
                    is_valid,
                    validation_message,
                ) = validate_action(
                    action,
                    observation,
                )

                print(
                    "\n--- VALIDATION ---"
                )

                print(
                    validation_message
                )

                print(
                    "------------------"
                )

                if not is_valid:

                    logger.log(
                        "validation_failed",
                        {
                            "action":
                                action,

                            "message":
                                validation_message,
                        },
                    )

                    result["error"] = (
                        "Agent stopped because "
                        "the planned action was invalid. "
                        f"{validation_message}"
                    )

                    break

                # =============================================
                # SAFETY
                # =============================================

                (
                    is_safe,
                    safety_message,
                ) = check_action_safety(
                    action
                )

                print(
                    "\n--- SAFETY ---"
                )

                print(
                    safety_message
                )

                print(
                    "--------------"
                )

                if not is_safe:

                    logger.log(
                        "safety_blocked",
                        {
                            "action":
                                action,

                            "message":
                                safety_message,
                        },
                    )

                    result["error"] = (
                        "Agent stopped because "
                        "the action failed the "
                        "safety check. "
                        f"{safety_message}"
                    )

                    break

                # =============================================
                # DONE
                # =============================================

                if (
                    action.get("action")
                    == "done"
                ):

                    answer = action.get(
                        "message",
                        "Task completed.",
                    )

                    print(
                        "\n--- TASK COMPLETE ---"
                    )

                    print(
                        answer
                    )

                    logger.log(
                        "task_completed",
                        {
                            "answer":
                                answer,

                            "capability_name":
                                capability_name,
                        },
                    )

                    # -----------------------------------------
                    # Final observation
                    # -----------------------------------------

                    final_observation = (
                        observe_page(
                            page
                        )
                    )

                    # -----------------------------------------
                    # Build final result
                    # -----------------------------------------

                    final_result = (
                        build_final_result(
                            task,
                            answer,
                            final_observation,
                            history,
                        )
                    )

                    logger.log_result(
                        final_result
                    )

                    print_final_result(
                        final_result
                    )

                    result.update(
                        {
                            "success":
                                True,

                            "answer":
                                answer,

                            "final_url":
                                final_observation.get(
                                    "url"
                                ),

                            "error":
                                None,
                        }
                    )

                    # =========================================
                    # CREATE DISCOVERY ARTIFACT
                    # =========================================

                    try:

                        artifact = (
                            create_discovery_artifact(
                                task=task,

                                actions=result[
                                    "actions"
                                ],

                                member_id=
                                    member_id,

                                final_url=
                                    result[
                                        "final_url"
                                    ],

                                capability_name=
                                    capability_name,
                            )
                        )

                        result[
                            "artifact_id"
                        ] = artifact[
                            "artifact_id"
                        ]

                        result[
                            "artifact_file"
                        ] = (
                            "artifacts/"
                            f"{artifact['artifact_id']}.json"
                        )

                        logger.log(
                            "artifact_created",
                            {
                                "artifact_id":
                                    artifact[
                                        "artifact_id"
                                    ],

                                "artifact_file":
                                    result[
                                        "artifact_file"
                                    ],

                                "capability_name":
                                    artifact[
                                        "metadata"
                                    ].get(
                                        "capability_name"
                                    ),

                                "action_count":
                                    len(
                                        result[
                                            "actions"
                                        ]
                                    ),

                                "replay_requires_llm":
                                    artifact[
                                        "metadata"
                                    ].get(
                                        "replay_requires_llm",
                                        False,
                                    ),
                            },
                        )

                        print(
                            "\n--- CAPABILITY ARTIFACT ---"
                        )

                        print(
                            "Artifact created:"
                        )

                        print(
                            result[
                                "artifact_file"
                            ]
                        )

                        print(
                            "Capability name:",
                            artifact[
                                "metadata"
                            ].get(
                                "capability_name"
                            ),
                        )

                        print(
                            "Actions recorded:",
                            len(
                                result[
                                    "actions"
                                ]
                            ),
                        )

                        print(
                            "Replay requires LLM:",
                            artifact[
                                "metadata"
                            ].get(
                                "replay_requires_llm",
                                False,
                            ),
                        )

                        print(
                            "----------------------------"
                        )

                    except Exception as artifact_error:

                        print(
                            "\n--- ARTIFACT CREATION ERROR ---"
                        )

                        print(
                            artifact_error
                        )

                        print(
                            "--------------------------------"
                        )

                        logger.log(
                            "artifact_creation_failed",
                            {
                                "error":
                                    str(
                                        artifact_error
                                    ),
                            },
                        )

                        # Discovery itself succeeded.
                        # Artifact creation failed separately.

                        result[
                            "artifact_error"
                        ] = str(
                            artifact_error
                        )

                    break

                # =============================================
                # LOOP GUARD
                # =============================================

                if is_repeating_action(
                    action,
                    history,
                ):

                    print(
                        "\n--- LOOP GUARD ---"
                    )

                    print(
                        "Repeated action detected. "
                        "Stopping agent."
                    )

                    print(
                        "------------------"
                    )

                    logger.log(
                        "loop_detected",
                        {
                            "action":
                                action
                        },
                    )

                    result["error"] = (
                        "The agent detected a repeated "
                        "action and stopped to avoid "
                        "getting stuck."
                    )

                    break

                # =============================================
                # EXECUTE
                # =============================================

                try:

                    print(
                        "\n--- EXECUTION ---"
                    )

                    execute_action(
                        page,
                        action,
                    )

                    print(
                        "-----------------"
                    )

                    # -----------------------------------------
                    # Record successful discovered action
                    # -----------------------------------------

                    history.add(
                        action
                    )

                    result[
                        "actions"
                    ].append(
                        action
                    )

                    logger.log_execution(
                        action
                    )

                    # -----------------------------------------
                    # Let UI settle
                    # -----------------------------------------

                    page.wait_for_timeout(
                        750
                    )

                except Exception as error:

                    error_info = (
                        handle_agent_error(
                            error
                        )
                    )

                    print(
                        "\n--- ACTION ERROR ---"
                    )

                    print(
                        error_info[
                            "message"
                        ]
                    )

                    print(
                        "--------------------"
                    )

                    logger.log_error(
                        error
                    )

                    if not error_info[
                        "recoverable"
                    ]:

                        result[
                            "error"
                        ] = (
                            error_info[
                                "message"
                            ]
                        )

                        break

            # =================================================
            # MAX STEPS
            # =================================================

            else:

                print(
                    "\nAgent stopped because "
                    "maximum steps were reached."
                )

                logger.log(
                    "max_steps_reached",
                    {
                        "max_steps":
                            MAX_STEPS
                    },
                )

                result["error"] = (
                    "Maximum agent steps were reached."
                )

        # ====================================================
        # AGENT ERROR
        # ====================================================

        except Exception as error:

            error_info = (
                handle_agent_error(
                    error
                )
            )

            print(
                "\n--- AGENT ERROR ---"
            )

            print(
                error_info[
                    "message"
                ]
            )

            print(
                "-------------------"
            )

            logger.log_error(
                error
            )

            result["error"] = (
                error_info[
                    "message"
                ]
            )

        # ====================================================
        # FINALLY
        # ====================================================

        finally:

            try:

                result["final_url"] = (
                    result["final_url"]
                    or page.url
                )

            except Exception:

                pass

            print(
                f"\nRun log saved to: "
                f"{logger.file_path}"
            )

            browser.close()

    return result


# ============================================================
# TERMINAL MODE
# ============================================================

def main():

    task = input(
        "What would you like me to do? "
    ).strip()

    if not task:

        print(
            "No task was provided."
        )

        return

    result = run_agent(
        task,
        headless=False,
    )

    if result["success"]:

        print(
            "\n=============================="
        )

        print(
            "FINAL AGENT RESULT"
        )

        print(
            "=============================="
        )

        print(
            f"Task: {result['task']}"
        )

        print(
            f"Answer: {result['answer']}"
        )

        print(
            "Browser actions executed:",
            len(
                result["actions"]
            ),
        )

        print(
            "Final URL:",
            result["final_url"],
        )

        if result.get(
            "capability_name"
        ):

            print(
                "Capability:",
                result[
                    "capability_name"
                ],
            )

        if result.get(
            "artifact_file"
        ):

            print(
                "Capability artifact:",
                result[
                    "artifact_file"
                ],
            )

        print(
            "=============================="
        )

    else:

        print(
            "\n=============================="
        )

        print(
            "AGENT DID NOT COMPLETE TASK"
        )

        print(
            "=============================="
        )

        print(
            result.get(
                "error"
            )
            or "Unknown error."
        )

        print(
            "=============================="
        )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()