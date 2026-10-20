"""Read-only pytest collector that records node IDs and terminal reports."""
import json, os

class R3PytestCollector:
    def __init__(self):
        self.items = []
        self.reports = []

    def pytest_collection_finish(self, session):
        self.items = [item.nodeid for item in session.items]
        path = os.environ["FABLE_R3_NODEIDS_PATH"]
        payload = {"run_tag": os.environ["FABLE_R3_RUN_TAG"], "count": len(self.items), "node_ids": self.items}
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())

    def pytest_runtest_logreport(self, report):
        self.reports.append({"node_id": report.nodeid, "when": report.when, "outcome": report.outcome,
                             "wasxfail": getattr(report, "wasxfail", None), "duration": report.duration})

    def pytest_sessionfinish(self, session, exitstatus):
        path = os.environ["FABLE_R3_OUTCOMES_PATH"]
        payload = {"run_tag": os.environ["FABLE_R3_RUN_TAG"], "exitstatus": int(exitstatus),
                   "collected": len(self.items), "reports": self.reports}
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())

def pytest_configure(config):
    config.pluginmanager.register(R3PytestCollector(), "r3-gate-nodeid-collector")
