class ActionHistory:
    """
    Stores actions successfully executed
    by the browser agent.
    """

    def __init__(self):
        self.actions = []

    def add(self, action):
        """
        Save an executed action.
        """

        self.actions.append(
            action.copy()
        )

    def get(self):
        """
        Return all previous actions.
        """

        return self.actions.copy()

    def get_recent(self, count=5):
        """
        Return the most recent actions.
        """

        return self.actions[-count:]

    def clear(self):
        """
        Clear action history.
        """

        self.actions = []

    def __len__(self):
        return len(self.actions)