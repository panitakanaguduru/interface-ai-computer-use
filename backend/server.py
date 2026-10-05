import json
import mimetypes
import os
import re
import sys
import traceback

from http.server import (
    SimpleHTTPRequestHandler,
    ThreadingHTTPServer,
)

from pathlib import Path

from urllib.parse import (
    unquote,
    urlparse,
)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

BACKEND_DIR = (
    BASE_DIR / "backend"
)

AGENT_DIR = (
    BASE_DIR
    / "src"
    / "agent"
)

DEMO_DIRECTORY = (
    BASE_DIR / "demo_app"
)

CUSTOMER_DIRECTORY = (
    BASE_DIR / "customer_app"
)


# ============================================================
# PYTHON PATH
# ============================================================

sys.path.insert(
    0,
    str(BACKEND_DIR),
)

sys.path.insert(
    0,
    str(AGENT_DIR),
)


# ============================================================
# PROJECT IMPORTS
# ============================================================

from database import get_member
from browser_agent import run_agent
from replay_engine import replay_artifact

from artifact_store import (
    find_artifact_by_capability,
)


# ============================================================
# CONFIG
# ============================================================

HOST = os.getenv(
    "HOST",
    "0.0.0.0",
)

PORT = int(
    os.getenv(
        "PORT",
        "8000",
    )
)


# ============================================================
# AUTHORIZATION
# ============================================================

def extract_member_ids(text):
    if not text:
        return []

    matches = re.findall(
        r"\b1\d{4}\b",
        str(text),
    )

    return sorted(
        set(matches)
    )


def validate_customer_request(
    member_id,
    task,
):
    member_id = str(
        member_id or ""
    ).strip()

    task = str(
        task or ""
    ).strip()

    if not member_id:
        return (
            False,
            "A member session is required.",
        )

    if not re.fullmatch(
        r"1\d{4}",
        member_id,
    ):
        return (
            False,
            "Invalid member session.",
        )

    referenced_ids = (
        extract_member_ids(
            task
        )
    )

    unauthorized_ids = [
        value
        for value in referenced_ids
        if value != member_id
    ]

    if unauthorized_ids:
        return (
            False,
            (
                "I can only help with "
                "information associated with "
                "your current member session."
            ),
        )

    return True, None


# ============================================================
# CAPABILITY ROUTING
# ============================================================

def classify_customer_capability(
    task,
):
    text = str(
        task or ""
    ).lower().strip()

    normalized = re.sub(
        r"[^a-z0-9\s]",
        " ",
        text,
    )

    normalized = re.sub(
        r"\s+",
        " ",
        normalized,
    ).strip()

    has_claim = (
        "claim" in normalized
    )

    has_pending = (
        "pending" in normalized
        or "waiting" in normalized
        or "not processed" in normalized
        or "still processing" in normalized
    )

    if has_claim and has_pending:
        return (
            "pending_claims_lookup"
        )

    return None


# ============================================================
# BROWSER ANSWER
# ============================================================

def build_browser_answer(
    capability_name,
    replay_result,
):
    """
    Build customer-facing answers only from
    replay output extracted from the browser DOM.

    Do not calculate the answer from get_member().
    """

    if not isinstance(
        replay_result,
        dict,
    ):
        return None, None

    output_source = (
        replay_result.get(
            "output_source"
        )
    )

    browser_output = (
        replay_result.get(
            "browser_output"
        )
    )

    if (
        output_source
        != "browser_dom"
    ):
        return (
            None,
            browser_output,
        )

    if not isinstance(
        browser_output,
        dict,
    ):
        return (
            None,
            browser_output,
        )

    if (
        capability_name
        == "pending_claims_lookup"
    ):
        pending_count = (
            browser_output.get(
                "pending_claim_count"
            )
        )

        if (
            pending_count is None
            or isinstance(
                pending_count,
                bool,
            )
        ):
            return (
                None,
                browser_output,
            )

        try:
            pending_count = int(
                pending_count
            )

        except (
            TypeError,
            ValueError,
        ):
            return (
                None,
                browser_output,
            )

        if pending_count < 0:
            return (
                None,
                browser_output,
            )

        if pending_count == 1:
            return (
                "You have 1 pending claim.",
                browser_output,
            )

        return (
            f"You have "
            f"{pending_count} pending claims.",
            browser_output,
        )

    return (
        None,
        browser_output,
    )


# ============================================================
# AUTHORIZED DISCOVERY TASK
# ============================================================

def build_authorized_task(
    member_id,
    task,
):
    return (
        "AUTHORIZED CUSTOMER SESSION\n\n"
        f"Member ID: {member_id}\n\n"

        "SECURITY RULES:\n"
        f"1. Only access member {member_id}.\n"
        "2. Do not search for another member.\n"
        "3. Do not navigate to another "
        "member's record.\n"
        "4. Do not reveal another member's "
        "information.\n"
        "5. If another member is encountered, "
        "do not reveal their information.\n"
        "6. Answer only the customer's request.\n\n"

        "CUSTOMER REQUEST:\n"
        f"{task}"
    )


# ============================================================
# SERVER
# ============================================================

class PortalHandler(
    SimpleHTTPRequestHandler
):

    def __init__(
        self,
        *args,
        **kwargs,
    ):
        super().__init__(
            *args,
            directory=str(
                DEMO_DIRECTORY
            ),
            **kwargs,
        )

    # ========================================================
    # JSON
    # ========================================================

    def send_json(
        self,
        data,
        status=200,
    ):
        body = json.dumps(
            data,
            ensure_ascii=False,
        ).encode(
            "utf-8"
        )

        self.send_response(
            status
        )

        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8",
        )

        self.send_header(
            "Content-Length",
            str(
                len(body)
            ),
        )

        self.send_header(
            "Cache-Control",
            "no-store",
        )

        self.end_headers()

        self.wfile.write(
            body
        )

    # ========================================================
    # REQUEST BODY
    # ========================================================

    def read_json_body(
        self
    ):
        try:
            content_length = int(
                self.headers.get(
                    "Content-Length",
                    0,
                )
            )

        except ValueError:
            raise ValueError(
                "Invalid Content-Length."
            )

        if content_length <= 0:
            raise ValueError(
                "Request body is required."
            )

        raw_body = (
            self.rfile.read(
                content_length
            )
        )

        try:
            return json.loads(
                raw_body.decode(
                    "utf-8"
                )
            )

        except json.JSONDecodeError:
            raise ValueError(
                "Request body must be valid JSON."
            )

    # ========================================================
    # CUSTOMER FILES
    # ========================================================

    def serve_customer_file(
        self,
        request_path,
    ):
        relative_path = (
            request_path[
                len("/customer/"):
            ].lstrip("/")
        )

        if not relative_path:
            relative_path = (
                "index.html"
            )

        requested_file = (
            CUSTOMER_DIRECTORY
            / relative_path
        ).resolve()

        customer_root = (
            CUSTOMER_DIRECTORY
            .resolve()
        )

        try:
            requested_file.relative_to(
                customer_root
            )

        except ValueError:
            self.send_error(
                403,
                "Forbidden",
            )
            return

        if (
            not requested_file.exists()
            or not requested_file.is_file()
        ):
            self.send_error(
                404,
                "File not found",
            )
            return

        content_type, _ = (
            mimetypes.guess_type(
                str(
                    requested_file
                )
            )
        )

        if content_type is None:
            content_type = (
                "application/octet-stream"
            )

        data = (
            requested_file.read_bytes()
        )

        self.send_response(
            200
        )

        self.send_header(
            "Content-Type",
            content_type,
        )

        self.send_header(
            "Content-Length",
            str(
                len(data)
            ),
        )

        self.send_header(
            "Cache-Control",
            "no-cache",
        )

        self.end_headers()

        self.wfile.write(
            data
        )

    # ========================================================
    # GET
    # ========================================================

    def do_GET(
        self
    ):
        parsed = urlparse(
            self.path
        )

        path = parsed.path

        if path == "/customer":
            self.send_response(
                301
            )

            self.send_header(
                "Location",
                "/customer/",
            )

            self.end_headers()
            return

        if path.startswith(
            "/customer/"
        ):
            self.serve_customer_file(
                path
            )
            return

        if path.startswith(
            "/api/member/"
        ):
            member_id = unquote(
                path.split(
                    "/api/member/",
                    1,
                )[1]
            ).strip()

            if not member_id:
                self.send_json(
                    {
                        "error":
                            "Member ID is required."
                    },
                    400,
                )
                return

            member = get_member(
                member_id
            )

            if member is None:
                self.send_json(
                    {
                        "error":
                            "Member not found."
                    },
                    404,
                )
                return

            self.send_json(
                member
            )
            return

        if path == "/api/health":
            self.send_json(
                {
                    "status":
                        "ok",
                    "service":
                        "MemberOps Agent API",
                }
            )
            return

        super().do_GET()

    # ========================================================
    # POST
    # ========================================================

    def do_POST(
        self
    ):
        parsed = urlparse(
            self.path
        )

        path = parsed.path

        try:
            payload = (
                self.read_json_body()
            )

        except ValueError as error:
            self.send_json(
                {
                    "success":
                        False,
                    "error":
                        str(error),
                },
                400,
            )
            return

        if (
            path
            == "/api/customer/agent"
        ):
            self.handle_customer_agent(
                payload
            )
            return

        if path == "/api/agent":
            self.handle_operations_agent(
                payload
            )
            return

        self.send_json(
            {
                "success":
                    False,
                "error":
                    "Endpoint not found.",
            },
            404,
        )

    # ========================================================
    # CUSTOMER AGENT
    # ========================================================

    def handle_customer_agent(
        self,
        payload,
    ):
        member_id = str(
            payload.get(
                "member_id",
                "",
            )
        ).strip()

        task = str(
            payload.get(
                "task",
                "",
            )
        ).strip()

        if not member_id:
            self.send_json(
                {
                    "success":
                        False,
                    "error":
                        "Member ID is required.",
                },
                400,
            )
            return

        if not task:
            self.send_json(
                {
                    "success":
                        False,
                    "error":
                        "Question is required.",
                },
                400,
            )
            return

        # Database is used ONLY to verify
        # that the member session exists.
        #
        # It is NOT used to calculate the
        # pending claims answer.
        member = get_member(
            member_id
        )

        if member is None:
            self.send_json(
                {
                    "success":
                        False,
                    "blocked":
                        True,
                    "error": (
                        "Member session could "
                        "not be verified."
                    ),
                },
                403,
            )
            return

        (
            allowed,
            security_error,
        ) = validate_customer_request(
            member_id,
            task,
        )

        if not allowed:
            self.send_json(
                {
                    "success":
                        False,
                    "blocked":
                        True,
                    "error":
                        security_error,
                },
                403,
            )
            return

        capability_name = (
            classify_customer_capability(
                task
            )
        )

        print(
            "\n================================="
        )
        print(
            "CUSTOMER AGENT REQUEST"
        )
        print(
            "================================="
        )
        print(
            "Member:",
            member_id,
        )
        print(
            "Task:",
            task,
        )
        print(
            "Capability:",
            capability_name,
        )

        # ====================================================
        # REPLAY FIRST
        # ====================================================

        if capability_name:
            artifact = (
                find_artifact_by_capability(
                    capability_name
                )
            )

            if artifact:
                artifact_id = (
                    artifact.get(
                        "artifact_id"
                    )
                )

                print(
                    "Saved capability:",
                    artifact_id,
                )

                # --------------------------------------------
                # IMPORTANT:
                # Once a saved capability exists, this request
                # enters the deterministic replay path.
                #
                # If replay fails, this request MUST NOT fall
                # through to LLM discovery.
                # --------------------------------------------

                try:
                    replay_result = (
                        replay_artifact(
                            artifact_id=
                                artifact_id,
                            parameters={
                                "member_id":
                                    member_id,
                            },
                        )
                    )

                except Exception as error:
                    print(
                        "Replay runtime error:",
                        error,
                    )

                    self.send_json(
                        {
                            "success":
                                False,
                            "member_id":
                                member_id,
                            "mode":
                                "escalated",
                            "capability_name":
                                capability_name,
                            "artifact_id":
                                artifact_id,
                            "llm_used":
                                False,
                            "error": (
                                "Saved capability "
                                "encountered an unexpected "
                                "replay failure."
                            ),
                            "recovery_attempted":
                                False,
                            "recovery_succeeded":
                                False,
                            "recovery_events":
                                [],
                            "human_escalation": {
                                "required":
                                    True,
                                "reason": (
                                    "Replay raised an "
                                    "unexpected runtime error."
                                ),
                                "artifact_id":
                                    artifact_id,
                                "capability_name":
                                    capability_name,
                                "recovery_error":
                                    str(error),
                            },
                        },
                        409,
                    )
                    return

                # --------------------------------------------
                # SUCCESS / RECOVERED SUCCESS
                # --------------------------------------------

                if replay_result.get(
                    "success"
                ):
                    (
                        answer,
                        browser_output,
                    ) = build_browser_answer(
                        capability_name,
                        replay_result,
                    )

                    if answer is not None:
                        self.send_json(
                            {
                                "success":
                                    True,
                                "member_id":
                                    member_id,
                                "answer":
                                    answer,
                                "mode":
                                    replay_result.get(
                                        "mode",
                                        "replay",
                                    ),
                                "capability_name":
                                    capability_name,
                                "artifact_id":
                                    artifact_id,
                                "artifact_file": (
                                    "artifacts/"
                                    f"{artifact_id}.json"
                                ),
                                "llm_used":
                                    False,
                                "steps_executed":
                                    replay_result.get(
                                        "steps_executed"
                                    ),
                                "output_source":
                                    replay_result.get(
                                        "output_source"
                                    ),
                                "browser_output":
                                    browser_output,
                                "checkpoint":
                                    replay_result.get(
                                        "checkpoint"
                                    ),
                                "recovery_attempted":
                                    replay_result.get(
                                        "recovery_attempted",
                                        False,
                                    ),
                                "recovery_succeeded":
                                    replay_result.get(
                                        "recovery_succeeded",
                                        False,
                                    ),
                                "recovery_events":
                                    replay_result.get(
                                        "recovery_events",
                                        [],
                                    ),
                                "human_escalation":
                                    replay_result.get(
                                        "human_escalation",
                                        {
                                            "required":
                                                False,
                                        },
                                    ),
                            },
                            200,
                        )
                        return

                    # Replay technically completed but did not
                    # produce a trusted browser-derived answer.
                    self.send_json(
                        {
                            "success":
                                False,
                            "member_id":
                                member_id,
                            "mode":
                                "escalated",
                            "capability_name":
                                capability_name,
                            "artifact_id":
                                artifact_id,
                            "llm_used":
                                False,
                            "error": (
                                "Replay completed, but "
                                "a trusted browser-derived "
                                "answer could not be built."
                            ),
                            "recovery_attempted":
                                replay_result.get(
                                    "recovery_attempted",
                                    False,
                                ),
                            "recovery_succeeded":
                                replay_result.get(
                                    "recovery_succeeded",
                                    False,
                                ),
                            "recovery_events":
                                replay_result.get(
                                    "recovery_events",
                                    [],
                                ),
                            "checkpoint":
                                replay_result.get(
                                    "checkpoint"
                                ),
                            "human_escalation": {
                                "required":
                                    True,
                                "reason": (
                                    "Replay output could not "
                                    "be converted into a "
                                    "trusted customer answer."
                                ),
                                "artifact_id":
                                    artifact_id,
                                "capability_name":
                                    capability_name,
                            },
                        },
                        409,
                    )
                    return

                # --------------------------------------------
                # CRITICAL FAILURE BOUNDARY
                # --------------------------------------------
                #
                # Artifact existed.
                # Replay failed.
                #
                # THIS IS TERMINAL FOR AUTOMATION.
                #
                # Do NOT:
                # - call run_agent()
                # - rediscover with an LLM
                # - create a replacement artifact
                #
                # Escalate instead.
                # --------------------------------------------

                escalation = (
                    replay_result.get(
                        "human_escalation"
                    )
                )

                if not isinstance(
                    escalation,
                    dict,
                ):
                    escalation = {}

                escalation[
                    "required"
                ] = True

                escalation.setdefault(
                    "reason",
                    (
                        "Saved capability could "
                        "not be safely replayed."
                    ),
                )

                escalation.setdefault(
                    "artifact_id",
                    artifact_id,
                )

                escalation.setdefault(
                    "capability_name",
                    capability_name,
                )

                self.send_json(
                    {
                        "success":
                            False,
                        "member_id":
                            member_id,
                        "mode":
                            "escalated",
                        "capability_name":
                            capability_name,
                        "artifact_id":
                            artifact_id,
                        "artifact_file": (
                            "artifacts/"
                            f"{artifact_id}.json"
                        ),
                        "llm_used":
                            False,
                        "error":
                            replay_result.get(
                                "error",
                                (
                                    "Saved capability "
                                    "could not be safely "
                                    "replayed."
                                ),
                            ),
                        "failed_step":
                            replay_result.get(
                                "failed_step"
                            ),
                        "failed_action":
                            replay_result.get(
                                "failed_action"
                            ),
                        "steps_executed":
                            replay_result.get(
                                "steps_executed"
                            ),
                        "recovery_attempted":
                            replay_result.get(
                                "recovery_attempted",
                                False,
                            ),
                        "recovery_succeeded":
                            replay_result.get(
                                "recovery_succeeded",
                                False,
                            ),
                        "recovery_events":
                            replay_result.get(
                                "recovery_events",
                                [],
                            ),
                        "output_source":
                            replay_result.get(
                                "output_source"
                            ),
                        "browser_output":
                            replay_result.get(
                                "browser_output"
                            ),
                        "checkpoint":
                            replay_result.get(
                                "checkpoint"
                            ),
                        "human_escalation":
                            escalation,
                    },
                    409,
                )

                # THIS RETURN IS CRITICAL.
                #
                # It prevents the discovery block below
                # from ever running after an existing
                # artifact failed.
                return

        # ====================================================
        # DISCOVERY
        # ====================================================
        #
        # Discovery is allowed ONLY when:
        #
        # 1. no reusable artifact exists, OR
        # 2. capability is not yet known.
        #
        # A failed replay can NEVER reach this block.
        # ====================================================

        authorized_task = (
            build_authorized_task(
                member_id,
                task,
            )
        )

        print(
            "No reusable capability."
        )
        print(
            "Starting discovery."
        )

        try:
            result = run_agent(
                authorized_task,
                headless=True,
                member_id=
                    member_id,
                capability_name=
                    capability_name,
            )

        except Exception as error:
            print(
                "\n========== DISCOVERY ERROR ==========",
                flush=True,
            )
            print(
                f"Error type: {type(error).__name__}",
                flush=True,
            )
            print(
                f"Error message: {error}",
                flush=True,
            )
            traceback.print_exc()
            print(
                "=====================================\n",
                flush=True,
            )

            self.send_json(
                {
                    "success":
                        False,
                    "error": (
                        "The member assistant "
                        "encountered an internal error."
                    ),
                },
                500,
            )
            return

        if result.get(
            "success"
        ):
            self.send_json(
                {
                    "success":
                        True,
                    "member_id":
                        member_id,
                    "answer":
                        result.get(
                            "answer"
                        ),
                    "mode":
                        "discovery",
                    "capability_name":
                        capability_name,
                    "artifact_id":
                        result.get(
                            "artifact_id"
                        ),
                    "artifact_file":
                        result.get(
                            "artifact_file"
                        ),
                    "llm_used":
                        True,
                },
                200,
            )
            return

        self.send_json(
            {
                "success":
                    False,
                "member_id":
                    member_id,
                "mode":
                    "discovery",
                "capability_name":
                    capability_name,
                "error": (
                    result.get(
                        "error"
                    )
                    or
                    "The member assistant could "
                    "not complete the request."
                ),
            },
            422,
        )

    # ========================================================
    # INTERNAL OPERATIONS AGENT
    # ========================================================

    def handle_operations_agent(
        self,
        payload,
    ):
        task = str(
            payload.get(
                "task",
                "",
            )
        ).strip()

        if not task:
            self.send_json(
                {
                    "success":
                        False,
                    "error":
                        "Task is required.",
                },
                400,
            )
            return

        try:
            result = run_agent(
                task,
                headless=True,
            )

        except Exception as error:
            print(
                "Operations agent error:",
                error,
            )

            self.send_json(
                {
                    "success":
                        False,
                    "error": (
                        "The agent encountered "
                        "an internal error."
                    ),
                },
                500,
            )
            return

        if result.get(
            "success"
        ):
            self.send_json(
                {
                    "success":
                        True,
                    "task":
                        result.get(
                            "task"
                        ),
                    "answer":
                        result.get(
                            "answer"
                        ),
                    "steps":
                        result.get(
                            "steps"
                        ),
                    "actions":
                        result.get(
                            "actions",
                            [],
                        ),
                    "action_count":
                        len(
                            result.get(
                                "actions",
                                [],
                            )
                        ),
                    "final_url":
                        result.get(
                            "final_url"
                        ),
                    "artifact_id":
                        result.get(
                            "artifact_id"
                        ),
                    "artifact_file":
                        result.get(
                            "artifact_file"
                        ),
                },
                200,
            )
            return

        self.send_json(
            {
                "success":
                    False,
                "task":
                    result.get(
                        "task"
                    ),
                "answer":
                    result.get(
                        "answer"
                    ),
                "steps":
                    result.get(
                        "steps"
                    ),
                "actions":
                    result.get(
                        "actions",
                        [],
                    ),
                "error": (
                    result.get(
                        "error"
                    )
                    or
                    "Agent could not "
                    "complete the task."
                ),
            },
            422,
        )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    print(
        "\n=========================================="
    )
    print(
        "       MEMBEROPS AGENT SERVER"
    )
    print(
        "=========================================="
    )
    print(
        f"Server:      http://{HOST}:{PORT}"
    )
    print(
        f"Internal UI: http://{HOST}:{PORT}/"
    )
    print(
        f"Customer UI: "
        f"http://{HOST}:{PORT}/customer/"
    )
    print(
        "==========================================\n"
    )

    server = ThreadingHTTPServer(
        (
            HOST,
            PORT,
        ),
        PortalHandler,
    )

    try:
        server.serve_forever()

    except KeyboardInterrupt:
        print(
            "\nServer stopped."
        )

    finally:
        server.server_close()