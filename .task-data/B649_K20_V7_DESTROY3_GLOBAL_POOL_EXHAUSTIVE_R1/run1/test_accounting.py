"""Focused accounting checks; never execute the scientific ticket sweep."""
import copy
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

spec = importlib.util.spec_from_file_location("campaign", Path(__file__).with_name("driver.py"))
campaign = importlib.util.module_from_spec(spec)
spec.loader.exec_module(campaign)


class AccountingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="b649-destroy3-accounting-")
        self.directory = Path(self.temp.name)
        self.triples = campaign.TRIPLES[:3]
        campaign.atomic_json(self.directory / "state.json", {
            "CONTRACT_SHA256": "contract", "COMPLETED_COUNT": 0,
            "JOURNAL_PREFIX_BYTES": 0, "JOURNAL_PREFIX_SHA256": campaign.sha(b"")})

    def tearDown(self):
        self.temp.cleanup()

    def validate(self, row, positions, origin):
        campaign.require(row["POSITIONS"] == list(positions), "WRONG_POSITIONS")

    def journal(self):
        return campaign.Journal(self.directory, "contract", self.triples, self.validate)

    def row(self, index):
        return {"POSITIONS": list(self.triples[index]), "PROVEN_OPTIMALITY_STATUS": "PROVEN_OPTIMAL",
                "TICKETS_SCORED": campaign.UNIVERSE_SIZE, "EXACT_CANDIDATE_TRIPLES_EVALUATED": 59640,
                "BEST_COUNT": campaign.START_COUNT + 7 * index}

    def test_frozen_family(self):
        self.assertEqual(len(campaign.TRIPLES), 1140)
        self.assertEqual(len(set(campaign.TRIPLES)), 1140)
        self.assertEqual(campaign.TRIPLES, tuple(sorted(campaign.TRIPLES)))
        self.assertEqual(campaign.TRIPLES[0], (0, 1, 2))
        self.assertEqual(campaign.TRIPLES[-1], (17, 18, 19))

    def test_complete_suffix_adopted_without_recomputation(self):
        journal = self.journal()
        journal.append(self.row(0), "NEWLY_COMPUTED")
        journal.checkpoint()
        # Crash after the next record was fsynced but before state update.
        journal.append(self.row(1), "PILOT_REUSED")
        resumed = self.journal()
        self.assertEqual(len(resumed.rows), 2)
        resumed.checkpoint()
        self.assertEqual(resumed.state["NEXT_INCOMPLETE_TRIPLE"], list(self.triples[2]))
        self.assertEqual(resumed.state["REUSED_PILOT_TRIPLES"], 1)
        self.assertEqual(resumed.state["NEWLY_COMPUTED_TRIPLES"], 1)
        self.assertEqual(resumed.state["GLOBAL_TICKETS_SCORED"], campaign.UNIVERSE_SIZE * 2)
        self.assertEqual(resumed.state["EXACT_LEAVES_SCORED"], 119280)
        self.assertEqual(resumed.state["NODES_PRUNED"], 0)

    def test_prefix_corruption_rejected(self):
        journal = self.journal()
        journal.append(self.row(0), "NEWLY_COMPUTED")
        journal.checkpoint()
        journal.path.write_bytes(journal.path.read_bytes().replace(b"NEWLY_COMPUTED", b"PILOT_REUSED  ", 1))
        with self.assertRaisesRegex(RuntimeError, "JOURNAL_PREFIX_SHA_MISMATCH"):
            self.journal()

    def test_complete_but_altered_suffix_rejected(self):
        journal = self.journal()
        journal.append(self.row(0), "NEWLY_COMPUTED")
        entry = json.loads(journal.path.read_bytes())
        entry["RECORD"]["BEST_COUNT"] += 7
        journal.path.write_bytes(campaign.encoded(entry) + b"\n")
        with self.assertRaisesRegex(RuntimeError, "RECORD_SHA_MISMATCH"):
            self.journal()

    def test_partial_suffix_quarantined_preserves_completed_record(self):
        journal = self.journal()
        journal.append(self.row(0), "NEWLY_COMPUTED")
        journal.checkpoint()
        verified = journal.path.read_bytes()
        with journal.path.open("ab") as stream:
            stream.write(b'{"SEQUENCE":1,"RECORD":')
        resumed = self.journal()
        self.assertEqual(len(resumed.rows), 1)
        self.assertEqual(resumed.path.read_bytes(), verified)
        self.assertEqual(len(list(self.directory.glob("interrupted-tail-*.bin"))), 1)

    def test_duplicate_out_of_order_and_wrong_contract_rejected(self):
        journal = self.journal()
        with self.assertRaisesRegex(RuntimeError, "WRONG_POSITIONS"):
            journal.append(self.row(1), "NEWLY_COMPUTED")
        journal.append(self.row(0), "NEWLY_COMPUTED")
        with self.assertRaisesRegex(RuntimeError, "WRONG_POSITIONS"):
            journal.append(self.row(0), "NEWLY_COMPUTED")
        state = json.loads(journal.state_path.read_bytes())
        state["CONTRACT_SHA256"] = "other"
        campaign.atomic_json(journal.state_path, state)
        with self.assertRaisesRegex(RuntimeError, "STATE_CONTRACT_MISMATCH"):
            self.journal()

    def test_single_writer(self):
        lock = self.directory / "execution.lock"
        with campaign.writer_lock(lock):
            with self.assertRaises(BlockingIOError):
                with campaign.writer_lock(lock):
                    self.fail("a second writer acquired ownership")

    def test_source_change_detected(self):
        source = self.directory / "source.py"
        source.write_bytes(b"original")
        expected = campaign.sha(source.read_bytes())
        campaign.hash_matches(source, expected)
        source.write_bytes(b"changed")
        with self.assertRaisesRegex(RuntimeError, "SOURCE_IDENTITY_MISMATCH"):
            campaign.hash_matches(source, expected)
        source.write_bytes(b"original")
        campaign.hash_matches(source, expected)

    def test_seal_recovers_staging_and_creates_only_one_commit(self):
        # Real Git behavior in a disposable fixture, with no scientific run.
        repo = self.directory / "seal-fixture"
        repo.mkdir()

        def git(*args):
            return subprocess.check_output(["git", *args], cwd=repo, stderr=subprocess.STDOUT).decode().strip()

        git("init", "-b", "fixture")
        git("config", "user.name", "Accounting Fixture")
        git("config", "user.email", "accounting@example.invalid")
        (repo / "base.txt").write_text("base\n")
        git("add", "base.txt")
        git("commit", "-m", "Fixture base")
        head = git("rev-parse", "HEAD")
        run = repo / "runtime"
        run.mkdir()
        journal_path = run / "set-results.jsonl"
        journal_path.write_bytes(b"verified-journal\n")
        result = repo / "result.json"
        campaign.atomic_json(result, {
            "EXECUTION_CONTRACT_SHA256": "contract", "JOURNAL_SHA256": campaign.sha(journal_path.read_bytes()),
            "DESTROY_TRIPLES_COMPLETED": 1140, "PROVEN_OPTIMAL_TRIPLES": 1140,
            "BEST_CANONICAL_RECOUNT_STATUS": "PASS", "SCIENTIFIC_RESULT": "NO_IMPROVEMENT",
            "BEST_COUNT": campaign.START_COUNT, "BEST_DELTA": 0})
        (repo / "driver.py").write_text("fixture orchestration\n")
        paths = ["result.json", "driver.py"]
        contract = {"SOURCE_HEAD": head, "SOURCE_BRANCH": "fixture", "SEAL_COMMIT_PATHS": paths}
        journal = mock.Mock(contract_sha="contract", state={"PEAK_MEMORY_BYTES": 0})
        with mock.patch.multiple(campaign, ROOT=repo, RUN=run, RESULT=result,
                                 RESULT_REL="result.json", JOURNAL=journal_path):
            (repo / "unrelated.txt").write_text("owner work\n")
            git("add", "unrelated.txt")
            with self.assertRaisesRegex(RuntimeError, "UNRELATED_STAGED_WORK_AT_SEAL"):
                campaign.seal(journal, contract)
            git("restore", "--staged", "unrelated.txt")
            git("add", "result.json")
            campaign.seal(journal, contract)
            self.assertEqual(git("rev-list", "--count", "HEAD"), "2")
            self.assertEqual(git("show", "--format=", "--name-only", "HEAD").splitlines(), sorted(paths))
            campaign.seal(journal, contract)
            self.assertEqual(git("rev-list", "--count", "HEAD"), "2")
            receipt = json.loads((run / "seal-receipt.json").read_bytes())
            self.assertEqual(receipt["RESULT_COMMIT"], git("rev-parse", "HEAD"))
            self.assertEqual((repo / "unrelated.txt").read_text(), "owner work\n")
    def test_real_pilot_accounting_and_rejection_seams(self):
        document, _ = campaign.sealed_identity()
        pilot = campaign.load_pilot()
        start = pilot.current_start()
        _, elites = pilot.verify_elites(start)
        records = campaign.reusable_records(document, start, elites, pilot)
        self.assertEqual(len(records), 64)
        row = next(iter(records.values()))
        positions = tuple(row["POSITIONS"])
        for field, value, error in [
            ("TICKETS_SCORED", 0, "INCOMPLETE_GLOBAL_SCORE"),
            ("PROVEN_OPTIMALITY_STATUS", "UNPROVEN", "UNPROVEN_REPAIR"),
            ("EXACT_CANDIDATE_TRIPLES_EVALUATED", 0, "INCOMPLETE_EXACT_SOLVE"),
            ("BEST_COUNT", 0, "BEST_COUNT_MISMATCH"),
            ("BEST_PORTFOLIO_SHA256", "invalid", "BEST_SHA_TIE_BREAK_MISMATCH"),
        ]:
            mutated = copy.deepcopy(row)
            mutated[field] = value
            with self.assertRaisesRegex(RuntimeError, error):
                campaign.validate_row(mutated, positions, start, elites, pilot)
        campaign.validate_row(row, positions, start, elites, pilot)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(AccountingTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    evidence = {"STATUS": "PASS" if result.wasSuccessful() else "FAIL", "TESTS_RUN": result.testsRun,
                "FAILURES": len(result.failures), "ERRORS": len(result.errors),
                "TEST_SOURCE_SHA256": campaign.sha(Path(__file__).read_bytes()),
                "ORCHESTRATOR_SOURCE_SHA256": campaign.sha(Path(__file__).with_name("driver.py").read_bytes()),
                "FALSIFIABILITY_CHECK": "CONFIRMED" if result.wasSuccessful() else "FAIL",
                "SCIENTIFIC_SWEEP_EXECUTED": False, "AT_UTC": campaign.utc()}
    campaign.atomic_json(Path(__file__).with_name("accounting-test-result.json"), evidence)
    raise SystemExit(0 if result.wasSuccessful() else 1)
