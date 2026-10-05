def validate_action(action, observation):
    """
    Validate an LLM action before allowing
    the executor to perform it.

    Returns:
        (True, message)
        (False, message)
    """

    # -----------------------------------
    # BASIC FORMAT
    # -----------------------------------

    if not isinstance(action, dict):
        return False, "Action must be a dictionary."

    action_type = action.get("action")

    if not action_type:
        return False, "Action type is missing."

    allowed_actions = {
        "fill",
        "click",
        "done",
    }

    if action_type not in allowed_actions:
        return False, (
            f"Unsupported action: {action_type}"
        )

    # -----------------------------------
    # DONE
    # -----------------------------------

    if action_type == "done":
        return True, "Done action is valid."

    # -----------------------------------
    # SELECTOR
    # -----------------------------------

    selector = action.get("selector")

    if not selector:
        return False, "Selector is missing."

    # Our current MVP only allows ID selectors.
    if not selector.startswith("#"):
        return False, (
            "Only ID selectors are currently allowed."
        )

    element_id = selector[1:]

    # -----------------------------------
    # OBSERVED ELEMENTS
    # -----------------------------------

    input_ids = {
        element.get("id")
        for element in observation.get(
            "inputs",
            []
        )
        if element.get("id")
    }

    button_ids = {
        element.get("id")
        for element in observation.get(
            "buttons",
            []
        )
        if element.get("id")
    }

    # -----------------------------------
    # FILL VALIDATION
    # -----------------------------------

    if action_type == "fill":

        if element_id not in input_ids:

            return False, (
                f"Cannot fill {selector}: "
                "input was not observed."
            )

        if "value" not in action:

            return False, (
                "Fill action is missing a value."
            )

        return True, "Fill action is valid."

    # -----------------------------------
    # CLICK VALIDATION
    # -----------------------------------

    if action_type == "click":

        if element_id not in button_ids:

            return False, (
                f"Cannot click {selector}: "
                "button was not observed."
            )

        return True, "Click action is valid."

    return False, "Action could not be validated."