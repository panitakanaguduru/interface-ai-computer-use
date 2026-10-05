def is_repeating_action(
    action,
    history,
    max_repeats=3
):
    """
    Detect repeated identical actions.

    Example:

    fill
    fill
    fill
    fill

    The fourth identical action will
    be blocked when max_repeats=3.
    """

    recent_actions = history.get_recent(
        max_repeats
    )

    if len(recent_actions) < max_repeats:
        return False

    return all(
        previous_action == action
        for previous_action in recent_actions
    )