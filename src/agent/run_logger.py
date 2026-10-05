import json
from datetime import datetime
from pathlib import Path


LOG_DIRECTORY = Path("artifacts")
LOG_DIRECTORY.mkdir(exist_ok=True)


class RunLogger:

    def __init__(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        self.file_path = (
            LOG_DIRECTORY / f"agent_run_{timestamp}.jsonl"
        )

    def log(self, event_type, data):

        record = {
            "timestamp": datetime.now().isoformat(),
            "event": event_type,
            "data": data,
        }

        with open(self.file_path, "a", encoding="utf-8") as file:
            file.write(json.dumps(record) + "\n")

    def log_observation(self, observation):
        self.log("observation", observation)

    def log_plan(self, action):
        self.log("plan", action)

    def log_execution(self, action):
        self.log("execution", action)

    def log_error(self, error):
        self.log("error", {"message": str(error)})

    def log_result(self, result):
        self.log("result", result)