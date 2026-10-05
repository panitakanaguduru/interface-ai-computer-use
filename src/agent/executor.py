def execute_action(page, action):
    """
    Execute one validated browser action.
    """

    action_type = action.get("action")

    # -----------------------------------
    # FILL
    # -----------------------------------

    if action_type == "fill":

        selector = action["selector"]
        value = action["value"]

        print(
            f"Executor: Fill {selector} with {value}"
        )

        page.fill(
            selector,
            str(value)
        )

        return

    # -----------------------------------
    # CLICK
    # -----------------------------------

    if action_type == "click":

        selector = action["selector"]

        print(
            f"Executor: Click {selector}"
        )

        page.click(selector)

        return

    # -----------------------------------
    # DONE
    # -----------------------------------

    if action_type == "done":

        return action.get(
            "message",
            "Task complete."
        )

    # -----------------------------------
    # UNKNOWN ACTION
    # -----------------------------------

    raise ValueError(
        f"Unknown action: {action_type}"
    )