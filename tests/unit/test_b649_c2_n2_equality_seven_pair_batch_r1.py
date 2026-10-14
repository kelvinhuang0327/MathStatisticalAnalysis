"""Focused arithmetic, by-value identity, native controls and partial sealing."""
import importlib.util
import itertools
import json
import math
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("seven_pair", ROOT/"tools/b649_c2_n2_equality_seven_pair_batch_r1.py")
batch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(batch)


class SevenPairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="b649-seven-focused-")
        cls.folder = Path(cls.temp.name)
        cls.identities, cls.donor, cls.dependencies = batch.load_inputs()
        cls.pilot = batch.pilot_namespace()
        cls.source, cls.provenance = batch.c_source(cls.donor)
        cls.binary, _, _ = batch.compile_c(cls.source, cls.folder, time.monotonic()+15)
        cls.lib = batch.native_library(cls.binary)
        # Must pass before any small-domain gain call; no real 49-number gains.
        cls.controls = batch.synthetic_capabilities(cls.lib, cls.folder)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_fixed_seven_full_ticket_mapping(self):
        self.assertEqual(len(self.identities), 7)
        self.assertEqual(sum(i["ORBIT_SIZE"] for i in self.identities), 37)
        for identity, s in zip(self.identities, batch.ALLOWLIST):
            self.assertEqual(identity["PAIR_ORDERED"], list(s[0]))
            self.assertEqual(identity["PAIR_ENGINE"], list(s[1]))
            self.assertEqual(len(identity["ORDERED_TICKETS"]), 20)
            self.assertEqual(len(identity["UNTOUCHED_TICKETS"]), 18)
            self.assertEqual(identity["REMOVED_TICKETS"], [identity["ORDERED_TICKETS"][i] for i in s[0]])
            self.assertEqual(identity["UNTOUCHED_TICKETS"], [t for i,t in enumerate(identity["ORDERED_TICKETS"]) if i not in s[0]])
        self.assertEqual(self.identities[0]["PAIR_ENGINE"], [0,11])

    def test_wrong_engine_and_orbit_row_rejected(self):
        identity = self.identities[0]
        for key, value in (("ENGINE_PAIR",[0,6]), ("ORBIT_INDEX",4), ("ORBIT_SIZE",2), ("IS_REPRESENTATIVE",False)):
            row = {**identity["PAIR_MAPPING_ROW"], key:value}
            with self.assertRaises(ValueError):
                batch.pair_identity(identity["ORDERED_TICKETS"], identity["ENGINE_TICKETS"], identity["ORDERED_TO_ENGINE_SLOTS"], row, batch.ALLOWLIST[0])
        slots = list(identity["ORDERED_TO_ENGINE_SLOTS"]); slots[6]=6
        with self.assertRaises(ValueError):
            batch.pair_identity(identity["ORDERED_TICKETS"],identity["ENGINE_TICKETS"],slots,identity["PAIR_MAPPING_ROW"],batch.ALLOWLIST[0])

    def test_integer_e_formula_odd_even_same_bucket_distinct_pairs(self):
        gains = [0,0,1,2,2,3,4,4,5]
        buckets = [[g,gains.count(g)] for g in sorted(set(gains))]
        for target in range(11):
            exact, table = self.pilot["equality_count"](buckets,target,complete=True)
            classes = [0,0,0]
            for a,b in itertools.combinations(gains,2):
                classes[(a+b>target)-(a+b<target)+1] += 1
            self.assertEqual(sum(classes),math.comb(len(gains),2))
            self.assertEqual(exact,classes[1])
            self.assertEqual(exact,sum(r["CONTRIBUTION"] for r in table))
            self.assertTrue(all(r["A"]<=r["B"] and r["A"]+r["B"]==target for r in table))
        exact, table = self.pilot["equality_count"]([[2,4]],4,complete=True)
        self.assertEqual(exact,6)
        self.assertEqual(table[0]["RULE"],"CHOOSE_2_DISTINCT")

    def test_partial_and_invalid_histograms_rejected(self):
        for buckets in ([[0,0]],[[0,2],[0,3]],[[1.0,3]],[[0,True]],[[-1,2]]):
            with self.assertRaises(ValueError):
                self.pilot["equality_count"](buckets,2,complete=True)
        with self.assertRaises(ValueError):
            self.pilot["equality_count"]([[0,2]],0,complete=False)

    def test_donor_core_and_formula_are_verbatim(self):
        core = self.donor[self.donor.index("static void init_binom("):self.donor.index("/* Table-free two-ticket")]
        self.assertIn(core,self.source)
        self.assertEqual(batch.sha(core.encode()),self.provenance["VERBATIM_CORE_SHA256"])
        self.assertNotIn("G[r6].rank = r6;",self.source)
        self.assertIn("s3 - C4 * s4 + C5 * s5 - C6",self.source)

    def test_synthetic_pair_and_batch_deadlines_rss_and_capacity(self):
        self.assertEqual([r["RETURN_CODE"] for r in self.controls],[1,2,3,4])
        self.assertTrue(all(r["ELAPSED_SECONDS"]<.25 for r in self.controls))
        self.assertTrue(all(r["STATE_ZERO"] for r in self.controls))
        self.assertEqual(self.lib.native_pid(),os.getpid())

    def test_falsifiability_broken_stop_is_prelaunch_blocked(self):
        class BrokenStop:
            def native_rss(self): return 1
            def native_now(self): return time.monotonic()
            def native_synthetic(self,*args): return 0
        with self.assertRaisesRegex(batch.StopBatch,"BLOCKED_PRELAUNCH: synthetic PAIR_DEADLINE"):
            batch.synthetic_capabilities(BrokenStop(),self.folder)

    def test_all_forbidden_native_entrypoints_refuse(self):
        for mode in range(7):
            self.assertEqual(self.lib.native_guard(mode),5)
            self.assertIn(b"FORBIDDEN",self.lib.native_reason())
            self.assertTrue(self.lib.native_state_zero())

    def test_native_and_python_clocks_match(self):
        before=time.monotonic(); native=self.lib.native_now(); after=time.monotonic()
        self.assertLessEqual(before-.001,native)
        self.assertLessEqual(native,after+.001)

    def test_compiler_preparation_deadline_terminates_owned_child(self):
        original_popen = subprocess.Popen
        children=[]
        def sleeper(*args,**kwargs):
            child=original_popen([sys.executable,"-B","-c","import time; time.sleep(2)"],**kwargs)
            children.append(child)
            return child
        with tempfile.TemporaryDirectory(prefix="b649-compiler-stop-") as folder:
            start=time.monotonic()
            with patch.object(batch.subprocess,"Popen",side_effect=sleeper):
                # Patch only the compiler spawn: ps sampling uses subprocess.run.
                with patch.object(batch.subprocess,"run",return_value=type("Sample",(),{"stdout":"1"})()):
                    with self.assertRaisesRegex(batch.StopBatch,"BATCH_DEADLINE"):
                        batch.compile_c("synthetic no gain fixture",folder,start+.05)
            self.assertEqual(len(children),1)
            self.assertIsNotNone(children[0].poll())
            self.assertLess(time.monotonic()-start,.5)

    def test_pilot_pair_01_and_wrong_engine_06_rejected_before_gain(self):
        identity = self.identities[0]
        for pair in ([0,1],[0,6],[1,3]):
            inp,out = self.folder/"reject.in",self.folder/"reject.out"
            inp.write_text(self.pilot["input_text"](49,identity["ENGINE_TICKETS"],pair))
            now=time.monotonic()
            code=self.lib.native_histogram(os.fsencode(inp),os.fsencode(out),now+1,now+1,batch.RSS_LIMIT,10000)
            self.assertEqual(code,5)
            self.assertIn(b"outside seven-pair allowlist",self.lib.native_reason())
            self.assertTrue(self.lib.native_state_zero())
            inp.unlink();out.unlink()

    def small(self,pair):
        tickets = [[1,2,3,4,5,6],[1,2,3,7,8,9],[7,8,9,10,11,12]]
        inp,out = self.folder/"small.in",self.folder/"small.out"
        inp.write_text(self.pilot["input_text"](12,tickets,pair))
        now=time.monotonic()
        code=self.lib.native_histogram(os.fsencode(inp),os.fsencode(out),now+3,now+3,batch.RSS_LIMIT,1<<20)
        self.assertEqual(code,0,self.lib.native_reason())
        data=json.loads(out.read_bytes()); inp.unlink();out.unlink()
        self.assertTrue(self.lib.native_state_zero())
        return data,tickets

    def test_repeated_calls_clear_histogram_and_cij(self):
        first,tickets = self.small([0,2])
        second,_ = self.small([0,1])
        third,_ = self.small([0,2])
        for k in ("C_ij","HISTOGRAM","SINGLE_GAINS_SMALL_TEST_ONLY","RAW_SINGLE_TICKETS","EXCLUDED_UNTOUCHED_TICKETS"):
            self.assertEqual(first[k],third[k])
        self.assertNotEqual(first["UNTOUCHED_TICKETS"],second["UNTOUCHED_TICKETS"])
        self.assertEqual(sum(c for _,c in first["HISTOGRAM"]),math.comb(12,6)-1)
        untouched = set(tickets[1])
        uncovered = [set(w) for w in itertools.combinations(range(1,13),7) if len(untouched.intersection(w))<3]
        brute = [sum(len(set(t).intersection(w))>=3 for w in uncovered) for t in itertools.combinations(range(1,13),6)]
        self.assertEqual(first["SINGLE_GAINS_SMALL_TEST_ONLY"],brute)

    def test_stop_preserves_complete_and_marks_only_current_incomplete(self):
        rows=[batch.empty_row(i) for i in self.identities]
        rows[0].update(STATUS="COMPLETE",E=99,HISTOGRAM_COMPLETE=True,HISTOGRAM=[[0,2]],ARTIFACT_COMPLETE=True)
        result={"TASK_STATUS":"PARTIAL","SEVEN_PAIRS":rows}
        batch.mark_partial(result,1,"PAIR_DEADLINE")
        path=self.folder/"partial.json"
        batch.archive(result,path,self.folder)
        read=json.loads(path.read_bytes());path.unlink()
        self.assertEqual([r["STATUS"] for r in read["SEVEN_PAIRS"]],["COMPLETE","INCOMPLETE"]+["NOT_RUN"]*5)
        self.assertEqual(read["SEVEN_PAIRS"][0]["E"],99)
        self.assertEqual(read["SEVEN_PAIRS"][0]["HISTOGRAM"],[[0,2]])
        self.assertTrue(all(r["E"] is None and not r["HISTOGRAM_COMPLETE"] for r in read["SEVEN_PAIRS"][1:]))

    def test_result_and_temp_caps_preserve_previous_full_archive(self):
        path=self.folder/"capacity.json"
        batch.archive({"saved":"COMPLETE"},path,self.folder)
        before=path.read_bytes()
        for caps in ({"result_limit":10},{"temp_limit":batch.folder_bytes(self.folder)+10}):
            with self.assertRaises(batch.StopBatch):
                batch.archive({"HISTOGRAM":[[i,1] for i in range(100)]},path,self.folder,**caps)
            self.assertEqual(path.read_bytes(),before)
        path.unlink()

    def test_archive_deadline_and_actual_size_accounting(self):
        path=self.folder/"seal-deadline.json"
        peaks={"RESULT":0,"TEMP":0}
        prior=batch.folder_bytes(self.folder)
        size=batch.archive({"saved":"COMPLETE"},path,self.folder,peaks=peaks)
        self.assertEqual(peaks,{"RESULT":size,"TEMP":prior+size})
        before=path.read_bytes()
        with self.assertRaisesRegex(batch.StopBatch,"BATCH_DEADLINE"):
            batch.archive({"saved":"INCOMPLETE"},path,self.folder,deadline=time.monotonic()-1)
        self.assertEqual(path.read_bytes(),before)
        path.unlink()

    def test_batch_reserve_and_aggregate_temp_stop(self):
        with self.assertRaisesRegex(batch.StopBatch,"BATCH_DEADLINE"):
            batch.check_limits(time.monotonic()-1,self.folder)
        with self.assertRaisesRegex(batch.StopBatch,"TEMP_CAPACITY"):
            batch.check_limits(time.monotonic()+1,self.folder,temp_limit=1)
        self.assertEqual(batch.RESERVE,5)

    def test_wrong_untouched_measurement_values_fail(self):
        identity=self.identities[0]
        data={"COUNTING_UNIT":"7_SET","HISTOGRAM_COMPLETE":True,"RAW_SINGLE_TICKETS":13983816,
              "EXCLUDED_UNTOUCHED_TICKETS":18,"LEGAL_SINGLE_TICKETS":13983798,"HISTOGRAM":[[0,13983798]],
              "REMOVED_TICKETS":identity["REMOVED_TICKETS"],"UNTOUCHED_TICKETS":identity["ORDERED_TICKETS"][2:]}
        with self.assertRaisesRegex(ValueError,"untouched tickets differ"):
            self.pilot["validate_measurement"](data,identity)

    def test_source_coverage_uses_pilot_7_set_units(self):
        identity=self.identities[0]
        self.assertEqual(identity["EXPECTED_COVERED_P_7_SET"],44751984)
        fixture={"COVERED_P":44751984,"COVERED_R":40000000,"C_ij":4751984}
        batch.validate_source_coverage(fixture,identity)
        with self.assertRaises(ValueError):
            batch.validate_source_coverage({**fixture,"COVERED_P":313263888},identity)
        with self.assertRaises(ValueError):
            batch.validate_source_coverage(fixture,{**identity,"EXPECTED_COVERED_P_7_SET":313263888})
        with self.assertRaises(ValueError):
            batch.validate_source_coverage({**fixture,"C_ij":fixture["C_ij"]*7},identity)


if __name__ == "__main__":
    unittest.main()
