SAFE_ACTIONS = {"fill", "click", "done"}

SENSITIVE_WORDS = {
    "delete",
    "remove",
    "purchase",
    "buy",
    "pay",
    "submit",
    "transfer",
    "send money",
    "confirm payment",
}


def check_action_safety(action):
    """
    Decide whether an AI-generated action is safe to execute.

    Returns:
        (allowed, reason)
    """

    action_type = action.get("action")

    if action_type not in SAFE_ACTIONS:
        return False, f"Unsupported action type: {action_type}"

    if action_type == "done":
        return True, "Done action is safe."

    selector = str(action.get("selector", "")).lower()
    value = str(action.get("value", "")).lower()

    combined = f"{selector} {value}"

    for word in SENSITIVE_WORDS:
        if word in combined:
            return False, f"Potentially sensitive action detected: {word}"

    return True, "Action passed safety check."