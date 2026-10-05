def create_plan(
    task,
    observation,
    member_id
):
    """
    Simple rule-based fallback planner.

    This file is not used by the current
    LLM-driven browser agent.
    """

    page_text = observation.get(
        "text",
        ""
    )

    # If member details are already visible,
    # the task is complete.

    if (
        "Member Details" in page_text
        and "Name:" in page_text
        and "Account:" in page_text
        and "Balance:" in page_text
    ):

        return [
            {
                "action": "done",
                "message":
                    "Member lookup "
                    "completed successfully."
            }
        ]

    # Otherwise fill the member ID
    # and search.

    return [
        {
            "action": "fill",
            "selector": "#member-id",
            "value": str(member_id),
        },
        {
            "action": "click",
            "selector": "#search-button",
        },
    ]