"""Replay the pinned 22-event B649 family and add only the independently judged T264 row."""

from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

from . import b649_coowner_ab_22_event_local_authority_r1 as twenty_two
from . import b649_existing_four_owner_local_authority_r1 as four
from . import b649_nine_event_eight_profile_local_authority_r1 as nine
from . import b649_sixteen_event_frozen_lineage_local_authority_r1 as sixteen
from . import b649_t238_twenty_event_local_authority_r1 as twenty

TASK_ID = "B649_T264_23_EVENT_LOCAL_FAMILY_INTEGRATION_R1"
ROOT = Path(__file__).resolve().parents[3]
RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-t264-23-event-local-family-integration-r1-result.json"
)

FROZEN_HEAD = "6569a9667d5e2094c8542cdff9905c3fd89f9e44"
FROZEN_TREE = "986d20859c86be9036b2321ac47e2e9622786a3b"
SIX_ROW_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-min-s2-six-row-existing-s4-family-authority-r1-result.json"
)
SIX_ROW_RESULT_SHA256 = "1f94b064ab7392b88cf4c18ca4d3cb164305601ea9bc2b0f2174c0cddb185e5f"
SEVEN_ROW_RESULT_SHA256 = "880a672a7330a567cc4544170cdeb0f7aa4d3dc5b5e3603c89ef50663cd71743"

BASE_HEAD = "90462d7a6877ced211ee129c82377baecb6c5eed"
BASE_TREE = "54260af5c0d96304f8ec09108afff9f8b55c7b82"
BASE_PARENT = "52da2de3974fbbc85c3dc10b40a8a7ba96ef80f0"
BASE_RESULT_PATH = twenty_two.RESULT_PATH
BASE_RESULT_SHA256 = "526dda20de9f1b95e5191352152470030839c5c252ff6e8bd65853af2420ca5f"
BASE_FULL_DIGEST = "ab7539e97e31b32748e8ebcba395f21de541dc82f22963a1ece5843c336e55ca"
BASE_BOUNDS_DIGEST = "8116ba552b302e7dbd61dccf7d9952b176857b992c0b7d11423d06d42ba1cc05"

DONOR_EVENT_ID = "T264_66555555555521100000"
DONOR_TASK_ID = "B649_NEXT_RESOLVED_COOWNER_66555555555521100000_R1"
PROFILE_ID = "66555555555521100000"
DONOR_HEAD = "cf8ba635b95ac89c7d1255f6fc19e7daf440e03c"
DONOR_TREE = "948a5c9d406ab38fea39314b8b9b85fa88c8c34a"
DONOR_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-next-resolved-coowner-66555555555521100000-r1-result.json"
)
DONOR_RESULT_SHA256 = "92b74e783a47ad900236f37b8814bc9f0366b7bdb600025964a7d961454d86e4"
DONOR_SOURCE_PATH = (
    "src/lottolab/research/"
    "b649_next_resolved_coowner_66555555555521100000_r1.py"
)
DONOR_SOURCE_SHA256 = "9510cfa9de429615b54904d28c438e3a481a47ece1c7cd8f624c2128007d64de"
DONOR_TEST_PATH = (
    "tests/unit/"
    "test_b649_next_resolved_coowner_66555555555521100000_r1.py"
)
DONOR_TEST_SHA256 = "57deeac58026e1d714d6b78badd848864609d27b6b5373a725ebf6898589dded"
HISTORICAL_SOURCE = (
    "b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json:"
    "NB_CERTIFICATES[1445]"
)
SOURCE_LOCATOR_KIND = "FROZEN_ZERO_SOLVE_REPLAY_VIRTUAL_ROW_NOT_STORED_ARRAY"

JUDGE_THREAD_ID = "01a13e14-684d-7fd3-bf85-2fb0e21845e4"
JUDGE_SESSION_ID = "01a13e14-684d-7fd3-bf85-2fb0e21845e4"
JUDGE_FINAL_MESSAGE_SHA256 = "49e1cb46c4606a285695c9f4ab8ce99a8964fe9738d91a84e3048d1b8dbd7fda"
JUDGE_FINAL_MESSAGE = base64.b64decode(
    'KipGUkVTSF9DT05URVhUX1ZFUkRJQ1Q6IFZFUklGSUVEX1dJVEhfQ0FWRUFUUyoqCgrlrozm'
    'lbQgcHJvZmlsZSBgNjY1NTU1NTU1NTU1MjExMDAwMDBgIOeahCAqKlTiiaQyNjQqKiDoiIcg'
    'Um91dGUtQiDkuIrnlYwgKiozMTMsMzgyLDk3MioqIOWdh+mAmumBjueNqOeri+mpl+itieOA'
    'guWUr+S4gCBjYXZlYXQg5piv55uu5qiZ5qqU55qE44CM5YW26aSYNTTlgIvjgI3mt7fnlKjk'
    'uoboqIjmlbjllq7kvY3vvJrmraPnorrpl5zkv4LngrogKio3NCDlgIvmqJnph4/ni4DmhYvv'
    'vJ02OCDlgIvmjpLpmaTvvIs2IOWAi+S/neeVme+8mzYg5YCL5L+d55WZ5bGV6ZaL54K6MjDl'
    'gIsgY3JpdGljYWwg6YWN572uKirjgILpgJnkuI3lvbHpn78gZG9ub3Ig55qE5pW45a2457WQ'
    '6KuW44CCCgpgYGB0ZXh0ClRBU0tfU1RBVFVTOiBDT01QTEVURUQKVEFTS19DTEFTUzogUkVB'
    'RF9PTkxZX0lOREVQRU5ERU5UX1NDSUVOVElGSUNfQ09SUkVDVE5FU1MKV09SS0VSX1JPVVRF'
    'OiBOT1RfQVBQTElDQUJMRQpKVURHRV9NT0RFOiBGUkVTSF9DT05URVhUCkpVREdFX0RFUFRI'
    'OiBCT1VOREVECkpVREdFX0RFUFRIX1JFQVNPTjog5Zau5LiA5a6M5pW0IHByb2ZpbGUg55qE'
    '542o56uL6K2J5piO44CB5pyJ6ZmQ5p6a6IiJ6IiHIGZvY3VzZWQgdGVzdHMKSlVER0VfU0VT'
    'U0lPTl9JRDogMDFhMTNlMTQtNjg0ZC03ZmQzLWJmODUtMmZiMGUyMTg0NWU0CgpQQUNLRVRf'
    'SlVER0VfREVQVEg6IEJPVU5ERUQKQ0FOT05JQ0FMX1JFUVVJUkVEX0pVREdFX0RFUFRIOiBC'
    'T1VOREVECkpVREdFX0RFUFRIX1JFQ09OQ0lMSUFUSU9OOiBNQVRDSApJTVBMRU1FTlRBVElP'
    'Tl9NVVRBVElPTl9SRVFVSVJFRDogTk8KYGBgCgrlj5flr6nlsI3osaHmmK/mjIflrpogW2Rv'
    'bm9yIHNvdXJjZV0oL1VzZXJzL2tlbHZpbi9WaWJlQ29kaW5nLVdvcmtTcGFjZS8ud29ya3Ry'
    'ZWVzL01hdGhTdGF0aXN0aWNhbEFuYWx5c2lzL0I2NDlfTkVYVF9SRVNPTFZFRF9DT09XTkVS'
    'XzY2NTU1NTU1NTU1NTIxMTAwMDAwX1IxL3NyYy9sb3R0b2xhYi9yZXNlYXJjaC9iNjQ5X25l'
    'eHRfcmVzb2x2ZWRfY29vd25lcl82NjU1NTU1NTU1NTUyMTEwMDAwMF9yMS5weSkg6IiHIFtz'
    'ZWFsZWQgcmVzdWx0XSgvVXNlcnMva2VsdmluL1ZpYmVDb2RpbmctV29ya1NwYWNlLy53b3Jr'
    'dHJlZXMvTWF0aFN0YXRpc3RpY2FsQW5hbHlzaXMvQjY0OV9ORVhUX1JFU09MVkVEX0NPT1dO'
    'RVJfNjY1NTU1NTU1NTU1MjExMDAwMDBfUjEvZG9jcy9yZXNlYXJjaC9tYXRyaXgtbmF0aXZl'
    'LXJlc3VsdHMvYjY0OS1uZXh0LXJlc29sdmVkLWNvb3duZXItNjY1NTU1NTU1NTU1MjExMDAw'
    'MDAtcjEtcmVzdWx0Lmpzb24p77yM5LiN5piv55uu5YmN5Li75bel5L2c55uu6YyE55qE5YW2'
    '5LuW54mI5pys44CCCgp8IOi6q+WIhuaqouafpSB8IOeNqOeri+ingOWvnyB8IOWIpOWumiB8'
    'CnwtLS18LS0tfC0tLXwKfCBGcm96ZW4gSEVBRC90cmVlIHwg6IiH5oyH5a6a5YC85LiA6Ie0'
    'IHwgTUFUQ0ggfAp8IEZyb3plbiBwYXJlbnQgfCBgODNkZGFkN2FkZTRhZTI4NmQxMjg5MGVm'
    'ZGJmM2VhNzc2ODEwM2Q1ZWAgfCBNQVRDSCB8CnwgRG9ub3IgSEVBRC90cmVlIHwg6IiH5oyH'
    '5a6a5YC85LiA6Ie0IHwgTUFUQ0ggfAp8IERvbm9yIHBhcmVudCB8IOato+aYryBmcm96ZW4g'
    'SEVBRCB8IE1BVENIIHwKfCBGcm96ZW4vZG9ub3IgcmVzdWx0IFNIQS0yNTYgfCDoiIfmjIfl'
    'rprlgLzkuIDoh7QgfCBNQVRDSCB8CnwgU291cmNlL3Rlc3RzL3Jlc3VsdCBieXRlcyB8IOW3'
    'peS9nOaoueiIhyBjb21taXR0ZWQgYmxvYnMg5LiA6Ie0IHwgTUFUQ0ggfAp8IOS+hua6kOS+'
    'neiztCB8IDM0IOWAiyBpbXBvcnQgY2xvc3VyZSBibG9icyDliqAgcGFja2FnZSByb290IOWd'
    'h+S4gOiHtCB8IE1BVENIIHwKfCBEb25vciDmnIDntYLlt6XkvZzmqLkgfCBjbGVhbiB8IFBB'
    'U1MgfAoKYGBgdGV4dApGUk9aRU5fSEVBRDoKNjU2OWE5NjY3ZDVlMjA5NGM4NTQyY2RmZjk5'
    'MDVjM2ZkODlmOWU0NApGUk9aRU5fVFJFRToKOTg2ZDIwODU5Yzg2YmU5MDM2YjIzMjFhYzQ3'
    'ZTJlOTYyMjc4NmEzYgpGUk9aRU5fUkVTVUxUX1NIQTI1NjoKODgwYTY3MmE3MzMwYTU2N2Nj'
    'NDU0NDE3MGNkZWIwZjdhYTRkM2RjNWI1ZTM2MDNjODllZjUwNjYzY2Q3MTc0MwoKUkVWSUVX'
    'RURfSEVBRDoKY2Y4YmE2MzViOTVhYzg5YzdkMTI1NWY2ZmMxOWU3ZGFmNDQwZTAzYwpSRVZJ'
    'RVdFRF9UUkVFOgo5NDhhNWM5ZDQwNmFiMzhmZWEzOTMxNGI4YjliODVmYTg4YzhjMzRhClJF'
    'VklFV0VEX1JFU1VMVF9TSEEyNTY6CjkyYjc0ZTc4M2E0N2FkOTAwMjM2ZjM3Yjg4MTRiYzlm'
    'MDM2NmI3YmRiNjAwMDI1OTY0YTdkOTYxNDU0ZDg2ZTQKClNPVVJDRV9TSEEyNTY6Cjk1MTBj'
    'ZmE5ZGU0Mjk2MTViNTQ5MDRkMjhjNDM4ZTNhNDgxYTQ3ZWNlMWM3Y2Q4ZjYyNGMyMTI4MDA3'
    'ZDY0ZGUKVEVTVFNfU0hBMjU2Ogo1N2RlZWFjNTgwMjZlMWQ3MTRkNmI3OGJhZGQ4NDg4NjQ2'
    'MDlkMjdiNmI1MzczYTcyNWViZjY4OTg1ODlkZGVkCmBgYAoKRnJvemVuIGF1dGhvcml0eSDn'
    'moTlr6bpmpvlhLLlrZjkvY3nva7oiIcgcmVwbGF5IOWdh+eiuuiqjeS+hua6kCByb3cg54K6'
    'IGNhcDI2NeOAgVM0IGJhc2UxMTLjgIFib3VuZDMxMzM5MjEyOOOAgmBOQl9DRVJUSUZJQ0FU'
    'RVNbMTQ0NV1gIOWDheaMieiZm+aTrCByZXBsYXkgbG9jYXRvciDomZXnkIbvvIzmspLmnInn'
    'lbbmiJDlr6bpq5QgSlNPTiBwb2ludGVy44CCCgrmlbjlrbjpqZforYnku6Xku6XkuIvmmI7n'
    'orrliY3mj5Dngrrnr4TlnI3vvJoyMOW8teelqOOAgeavj+elqDblgIvmqJnnsaTjgIEyMuWA'
    'iyB0cmlwbGUgc3VwcG9ydHPjgIEyN+WAiyBwYWlyIHN1cHBvcnRz77yM5LiU5omA5pyJIHN1'
    'cHBvcnQg5YWn55qE56Wo5bCN5Z2H5LiN6YeN6KSH44CCUHJvZmlsZSDngrogXCg2XjIsNV57'
    'MTB9LDIsMV4yLDBeNVwp44CCCgrlm6DmraQgc2hhZG93LXBsdXMtcGFpciBncmFwaCBcKEdc'
    'KSDmu7/otrMKXFsKZ194PTJkX3grKDYtZF94KT02K2RfeCxccXF1YWQgfEUoRyl8PTkzLgpc'
    'XQrlhbboo5zlnJYgXChIXCkg5pyJOTfmop3pgorjgIHluqbmlbggXCgxMy1kX3hcKeOAgkdv'
    'b2RtYW4gaWRlbnRpdHkg57Wm5Ye6ClxbClQrdChIKT1cYmlub217MjB9ezN9Ci1cZnJhYzEy'
    'XHN1bV94KDYrZF94KSgxMy1kX3gpPTI5My4KXF0KCuaVhSAqKlwoVD0yOTMtdChIKVwpKirv'
    'vIzkuJQgY29yZTE177yPemVybzUg5q2j56K644CC5q+P5YCLIHplcm8g5ZyoIFwoR1wpIOac'
    'iTblgIvkuI3lkIzphLDlsYXvvIzlhbbku5YgemVyb3Mg5Y+q5pyJNOWAi++8jOaJgOS7peav'
    'j+WAi+WQiOazlSByZWFsaXphdGlvbiDpg73mnIkgKipcKFx6ZXRhX3VcZ2UyXCkqKuOAggoK'
    '5LukIFwoSz1ce2Q+MFx9LFo9XHtkPTBcfVwp77yM5Lim5a6a576pClxbClxzaWdtYV94PXxO'
    'X0coeClcY2FwIFp8LFxxdWFkClx6ZXRhX3U9fE5fRyh1KVxjYXAgS3wsXHF1YWQKcj1cc3Vt'
    'X0tcc2lnbWE9XHN1bV9aXHpldGEuClxdCui3qOmCiuWPquiDveS+huiHqiBwYWlyIHN1cHBv'
    'cnRz77yM5Zug5q2kIFwoXHNpZ21hX3hcbGU2LWRfeFwp44CC5Y+WIFwoTT1IW0tdXCnjgIFc'
    'KEE9SFtaXVwp77yM5YmHClxbClxkZWdfTSh4KT04LWRfeCtcc2lnbWFfeCxccXVhZApcZGVn'
    'X0EodSk9XHpldGFfdS0yLApcXQpcWwp8TXw9KDU0K3IpLzIsXHFxdWFkIHxBfD0oci0xMCkv'
    'Mi4KXF0KCumAkOainSBzYW1lLXBhcnQgZWRnZSDoqIjmlbjmt7flkIjkuInop5LlvaLvvIzl'
    'vpfliLAKXFsKdChIKT01fE18KzE1fEF8Ci1cc3VtX3hcc2lnbWFfeFxkZWdfTSh4KQotXHN1'
    'bV91XHpldGFfdVxkZWdfQSh1KStQLApcXQrlhbbkuK0KXFsKUD10KE0pK3QoQSkKK1xzdW1f'
    'e3h5XGluIE19fE5fRyh4KVxjYXAgTl9HKHkpXGNhcCBafAorXHN1bV97dXZcaW4gQX18Tl9H'
    'KHUpXGNhcCBOX0codilcY2FwIEt8LgpcXQrlm5vpoIXpg73mmK/pnZ7osqDmlbTmlbjoqIjm'
    'lbjvvIzmlYUgKipcKFBcZ2UwXCkqKuOAggoK5LulIFwoYVwpIOihqOekuuWNgeWAiyBcKGQ9'
    'NVwpIOmggum7nuS4rSBcKFxzaWdtYT0xXCkg55qE5pW46YeP77yMXChiXCkg54K6IFwoZD0y'
    'XCkg55qE6Leo5bqm5pW477yMXChjXGxlIGVcKSDngrrlhanlgIsgXChkPTFcKSDnmoTot6jl'
    'uqbmlbjvvIzljJbnsKHlvpcKXFsKVD1GLVAsXHFxdWFkCkY9MjMzK2IoYisyKStjKGMrMykr'
    'ZShlKzMpK1xzdW1fdVx6ZXRhX3UoXHpldGFfdS04KS4KXF0KCuaIkeaykuacieWRvOWPqyBj'
    'YW5kaWRhdGUg55qE5p6a6IiJ5oiWIG9iamVjdGl2ZSDlh73lvI/kvobph43lu7rmnInpmZDn'
    'i4DmhYvjgILnjajnq4vmnproiIkKXFsKMFxsZSBhXGxlMTAsXHF1YWQwXGxlIGJcbGU0LFxx'
    'dWFkMFxsZSBjXGxlIGVcbGU1LApcXQpcWwoyXGxlXHpldGFfMVxsZVxjZG90c1xsZVx6ZXRh'
    'XzVcbGU2LFxxcXVhZAphK2IrYytlPVxzdW1cemV0YQpcXQrmgbDlvpcgKio0LDEzMSoqIOWA'
    'i+eLgOaFi++8jOWFtuS4rSAqKjQsMDU3Kiog5YCL55SxIFwoRlxsZTI2NCxQXGdlMFwpIOeb'
    'tOaOpemWieWQiOOAggoK5Ymp6aSYNzTlgIvnmoTlrozmlbTluLPlpoLkuIvjgIJgemV0YWAg'
    '55qE5LqU5L2N5pW45Luj6KGo5o6S5bqP5b6M55qE5LqU5YCL5bqm5pW477yb5ZCM5LiA5qC8'
    '5Lit55qE5q+P5YCL5a2X5Liy6YO95piv5LiA5YCL542o56uL54uA5oWL44CCCgp8IFwoKGEs'
    'YixjLGUpXCkgfCB6ZXRhIHwg6JmV572uIHwKfC0tLXwtLS18LS0tfAp8ICgwLDMsNSw1KSB8'
    'IDIyMjI1IHwgcGFyaXR5IHwKfCAoMSw0LDUsNSkgfCAyMjIzNiwyMjI0NSwyMjMzNSwyMjM0'
    'NCB8IHBhcml0eSB8CnwgKDIsMyw1LDUpIHwgMjIyMzYgfCBwYXJpdHkgfAp8ICgzLDQsNSw1'
    'KSB8IDIyMjU2LDIyMzQ2LDIyMzU1LDIyNDQ1LDIzMzM2IHwgcGFyaXR5IHwKfCAoNCwzLDUs'
    'NSkgfCAyMjI1NiB8IHBhcml0eSB8CnwgKDUsNCw1LDUpIHwgMjIzNjYsMjI0NTYsMjI1NTUs'
    'MjMzNTYsMjM0NDYgfCBwYXJpdHkgfAp8ICg2LDMsNSw1KSB8IDIyMzY2IHwgcGFyaXR5IHwK'
    'fCAoNyw0LDUsNSkgfCAyMjU2NiwyMzQ2NiwyMzU1NiwyNDQ1NiwzMzM2NiB8IHBhcml0eSB8'
    'CnwgKDgsMyw1LDUpIHwgMjI1NjYgfCBwYXJpdHkgfAp8ICg5LDQsNSw1KSB8IDIzNjY2LDI0'
    'NTY2LDI1NTU2LDMzNTY2LDM0NDY2IHwgcGFyaXR5IHwKfCAoMTAsMyw1LDUpIHwgMjM2NjYg'
    'fCBwYXJpdHkgfAp8ICgwLDQsNSw1KSB8IDIyMjI2LDIyMjM1LDIyMjQ0IHwg54Sh5omA6ZyA'
    '6Zu26bue5ZyWIHwKfCAoMSwzLDUsNSnjgIEoMSw0LDQsNSkgfCDlkITngroyMjIyNiB8IOeE'
    'oeaJgOmcgOmbtum7nuWcliB8CnwgKDIsNCw1LDUpIHwgMjIyNDYsMjIyNTUsMjIzMzYsMjIz'
    'NDUgfCDnhKHmiYDpnIDpm7bpu57lnJYgfAp8ICg0LDQsNSw1KSB8IDIyMjY2LDIyMzU2LDIy'
    'NDQ2LDIyNDU1LDIzMzQ2LDIzMzU1IHwg54Sh5omA6ZyA6Zu26bue5ZyWIHwKfCAoNSwzLDUs'
    'NSnjgIEoNSw0LDQsNSkgfCDlkITngroyMjI2NiB8IOeEoeaJgOmcgOmbtum7nuWcliB8Cnwg'
    'KDYsNCw1LDUpIHwgMjI0NjYsMjI1NTYsMjMzNjYsMjM0NTYsMjM1NTUsMjQ0NDYsMzMzNTYg'
    'fCDnhKHmiYDpnIDpm7bpu57lnJYgfAp8ICg4LDQsNSw1KSB8IDIyNjY2LDIzNTY2LDI0NDY2'
    'LDI0NTU2LDMzNDY2LDMzNTU2IHwg54Sh5omA6ZyA6Zu26bue5ZyWIHwKfCAoOSwzLDUsNSnj'
    'gIEoOSw0LDQsNSkgfCDlkITngroyMjY2NiB8IOeEoeaJgOmcgOmbtum7nuWcliB8CnwgKDEw'
    'LDQsNSw1KSB8IDI0NjY2LDI1NTY2LDMzNjY2LDM0NTY2IHwg54Sh5omA6ZyA6Zu26bue5ZyW'
    'IHwKfCAoMCw0LDUsNSkgfCAyMjMzNCB8IOaJgOacieS9jumggum7numEsOaOpembhuWQiOWd'
    'h+S9v+afkOWAiyBcKFxsYW1iZGE8MFwpIHwKfCAoMiw0LDUsNSkgfCAyMjQ0NCB8IOWQjOS4'
    'iiB8CnwgKDAsNCw1LDUpIHwgMjMzMzMgfCDlsZXplosz5YCLIGNyaXRpY2FsIOmFjee9riB8'
    'CnwgKDIsNCw1LDUpIHwgMjMzMzUgfCDlsZXplosx5YCLIGNyaXRpY2FsIOmFjee9riB8Cnwg'
    'KDQsNCw1LDUpIHwgMzMzMzYgfCDlsZXplos15YCLIGNyaXRpY2FsIOmFjee9riB8CnwgKDgs'
    'NCw1LDUpIHwgMjU1NTUgfCDlsZXplosx5YCLIGNyaXRpY2FsIOmFjee9riB8CnwgKDEwLDQs'
    'NSw1KSB8IDM1NTU2LDQ0NDY2IHwg5ZCE5bGV6ZaLNeWAiyBjcml0aWNhbCDphY3nva4gfAoK'
    '5o6S6Zmk55CG55Sx5Lmf57aT542o56uL6amX6K2J77yaCgotICoqMzDlgIsgcGFyaXR5IOaO'
    'kumZpCoq77yaXChcc3VtXGRlZ19BPXItMTBcKSDlv4XpoIjngrrlgbbmlbjjgIIKLSAqKjM2'
    '5YCL6Zu26bue5ZyW5o6S6ZmkKirvvJrlrozmlbTmnproiInlhajpg6ggXCgyXnsxMH09MTAy'
    'NFwpIOWAiyBsYWJlbGxlZCBncmFwaHPvvIzmspLmnInnrKblkIjnmoTluqbmlbjlnJbvvJvl'
    'j6bpgJDkuIDpqZforYnkuoblv4XopoHpgormlbjkuI3nrYnlvI/nmoTpgZXlj43jgIIKLSAq'
    'KjLlgIsgaW5jaWRlbmNlIOaOkumZpCoq77ya5q2k5pmCIFwoYj00LGM9ZT01XCnvvIzkvYbo'
    'h7PlsJHlhanlgIsgemVybyDnmoQgXChcemV0YT0yXCnvvJvlpKflsI8055qEIFwoU19iXCkg'
    '54Sh5rOV5ZCM5pmC6YG/6ZaL5a6D5YCR77yM5b+F6YCg5oiQ6LKg55qE5Ymp6aSYIGluY2lk'
    'ZW5jZeOAggoK5LiK6L+w6YKK5pW45LiN562J5byP5piv77ya6IulIFwoXGRlbHRhXzFcZ2Vc'
    'Y2RvdHNcZ2VcZGVsdGFfNVwpIOeCuiBcKEFcKSDnmoTluqbmlbjvvIzku7vkvZXlkIjms5Xl'
    'nJbpg73lv4XpoIjmu7/otrMKXFsKXHN1bV97aT0xfV5rXGRlbHRhX2kKXGxlIGsoay0xKStc'
    'c3VtX3tpPWsrMX1eNVxtaW4oayxcZGVsdGFfaSkuClxdCuS4g+WAiyB6ZXRhIOWtl+S4siBg'
    'MjMzNTUsMjM1NTUsMzMzNTYsMzM0NjYsMzM1NTYsMzM2NjYsMzQ1NjZgIOWcqCBcKGs9Mlwp'
    'IOmBleWPje+8m+WFtuS7luiiq+atpOmhnuaOkumZpOeahOWtl+S4suWcqCBcKGs9MVwpIOW3'
    'sumBleWPjeOAguaykuacieS9v+eUqOacquitieaYjueahCBncmFwaGljYWxpdHnvvI9yZWFs'
    'aXphYmlsaXR5IOWBh+ioreOAggoK5pyA5b6MMjDlgIvphY3nva7nmoQgXChcbGFtYmRhX3U9'
    'XHpldGFfdS1cbWF0aGJmMV97U19ifS1cbWF0aGJmMV97U19jfS1cbWF0aGJmMV97U19lfVwp'
    'IOWdh+mdnuiyoO+8jOS4lOe4veWSjOeCuiBcKGFcbGUxMFwp77yM5Y+v5YiG6YWN6Iez5Y2B'
    '5YCL5pyA5aSa5LiA5qKdIGluY2lkZW5jZSDnmoQgc2luZ2xldG9uIGNvbHVtbnPjgILlsI3p'
    'gJnkupvphY3nva7vvIwKXFsKUFxnZSBMPVxzdW1fe1NcaW5ce1NfYixTX2MsU19lXH19ZShB'
    'W1NdKS4KXF0K5YWo6YOo6YO95pyJIFwoYj00LGM9ZT01XCnvvIzmlYUgXChTX2M9U19lPVpc'
    'KeOAguiLpSBcKHFcKSDmmK8gXChTX2JcKSDllK/kuIDpgbrmvI/nmoQgemVyb++8jApcWwpM'
    'PTN8QXwtXGRlZ19BKHEpLgpcXQoK5LiL6KGo5piO56K65ra16JOL5YWo6YOoMjDlgIvphY3n'
    'va7jgIJNYXNrIOeahOmggum7nueCujDoh7M077ybZ3JhcGggZWRnZSBiaXRzIOaMieWtl+WF'
    'uOW6j+aOkuWIl++8jOS4lCBcKFNfYz1TX2U9MzFcKeOAggoKfCBcKChhLGIsYyxlKVwpLCB6'
    'ZXRhIHwgQSBtYXNrIHwgXChTX2JcKSBtYXNrIOKGkiBcKExcKSB8IOmFjee9ruaVuCB8Cnwt'
    'LS18LS0tfC0tLXwtLS06fAp8ICgwLDQsNSw1KSwyMzMzMyB8IDE5MiwyODgsNTI4IHwg5q+P'
    '5YCL55qGMzDihpI2IHwgMyB8CnwgKDIsNCw1LDUpLDIzMzM1IHwgODMyIHwgMzDihpI5IHwg'
    'MSB8CnwgKDQsNCw1LDUpLDMzMzM2IHwgODQwIHwgMTXihpI477ybMjMsMjcsMjksMzDihpIx'
    'MSB8IDUgfAp8ICg4LDQsNSw1KSwyNTU1NSB8IDEwMDggfCAzMOKGkjE4IHwgMSB8CnwgKDEw'
    'LDQsNSw1KSwzNTU1NiB8IDEwMTYgfCAxNeKGkjE377ybMjMsMjcsMjnihpIxOO+8mzMw4oaS'
    'MjAgfCA1IHwKfCAoMTAsNCw1LDUpLDQ0NDY2IHwgMTAwNCB8IDE1LDIz4oaSMTfvvJsyNywy'
    'OSwzMOKGkjE5IHwgNSB8Cgrlhajpg6ggKipGPTI2NeOAgVDiiaVM4omlNioq77yM5omA5Lul'
    '6YCZMjDlgIvphY3nva7lnYfmnIkgXChUXGxlMjU5XCnjgILphY3lkIjnm7TmjqXplonlkIjn'
    'moQ0LDA1N+WAi+eLgOaFi++8jOW+l+WIsCAqKuWujOaVtCBwcm9maWxlIOeahCBcKFRcbGUy'
    'NjRcKSoq44CCCgrku7vkuIDlkIjms5UgcmVhbGl6YXRpb24g6YO96IO95YWI6YeN5paw5qiZ'
    '6KiYIHplcm9zIOS9vyB6ZXRhIOaOkuW6j++8jOWGjeS6pOaPm+WFqeWAiyBcKGQ9MVwpIOmg'
    'gum7nuS9vyBcKGNcbGUgZVwp44CC5p6a6IiJ5L+d55WZ5YWo6YOoIGxhYmVsbGVkIHplcm8g'
    'Z3JhcGhzIOiIh+aMh+WumuWkp+Wwj+eahOmEsOaOpembhuWQiO+8m+aJgOmBuuW/mOeahCBj'
    'b3JlIGdyYXBo44CBc2luZ2xldG9uIGNvbHVtbiDouqvliIbkuI3lvbHpn78gXChGXCkg5oiW'
    'IFwoTFwp44CC5Zug5q2k6LaF6ZuG5ZCI5a6M5pW05oCn5oiQ56uL44CCKirmspLmnInlrqPn'
    'qLEgVDI2NCDlj6/pgZTvvIzkuZ/mspLmnInorYnmmI7miJblrqPnqLEgY2FwMjYz44CCKioK'
    'ClJvdXRlLUIg5Y+m5aSW5Lul542o56uL55qE5qiZ57Gk6YG45Y+WIERQIOmHjeeul+WxgOmD'
    'qOS6pOmbhuaVuO+8jOeiuuiqje+8mgoKYGBgdGV4dArllq7npag6ICAgICAgICAgICAgIDE4'
    'NjExNDMyCuS4jeebuOS6pOelqOWwjTogICAgICAgICAxMDc4MDAK6YeN55aK5LiA5qiZ57Gk'
    '56Wo5bCNOiAgICAgIDU3NDAwMAp3ZWRnZTogICAgICAgICAgICAgICAgMjgwMArpnZ4gc3Vw'
    'cG9ydCB0cmlhbmdsZTogMjAyNzIKc3VwcG9ydCB0cmlhbmdsZTogICAgIDcwMDAK5LqU6YKK'
    'IHF1YXJ0ZXQ6ICAgICAgICAgIDExMgrlha3lgIsgcGFpciBsYWJlbHM6ICAgICAgNjc5CuWQ'
    'qyB0cmlwbGUg55qEIEs0OiAgICAgICA0NDgKYGBgCgrnlLHmraTph43lvpcgXChTXzE9Mzcy'
    'MjI4NjQwLFNfMj02MzgzODYwMCxXPTgyNyxVPTIzMTZcKe+8jOS4pumpl+itiSBLNCDnmoTp'
    'hLDln5/nvLrpgoroqIjmlbjkuIvnlYzjgIFjb250YWluZWQtdHJpcGxlIGNhcCDoiIcgXCg0'
    'LzdcKSBCb25mZXJyb25pIGNvcnJlY3Rpb27vvJoKXFsKS180PVxtYXhcIVxsZWZ0KDAsXGxl'
    'ZnRcbGNlaWxcZnJhY3syMzE2LTEwKDgyNy0zdCl9NFxyaWdodFxyY2VpbFxyaWdodCksClxx'
    'dWFkIEFfe1xtYXh9PVxsZmxvb3I1OTIvM1xyZmxvb3I9MTk3LApcXQpcWwpDPVxtaW4oS180'
    'LDE5NyksXHF1YWQKU180PVxtYXgoMTEyLDQ0OEMrNjc5KEtfNC1DKSksClxdClxbClNfMz0y'
    'ODAwKDgyNykrMTE4NzIodC0yMiktMzA4MDAuClxdCuacgOe1guaVtOaVuOS4iueVjOeCugpc'
    'WwpcbGVmdFxsY2VpbCBTXzEtU18yK1NfMy1cZnJhY3s0U180fXs3fVxyaWdodFxyY2VpbAo9'
    'U18xLVNfMitTXzMtXGxlZnRcbGZsb29yXGZyYWN7NFNfNH17N31ccmlnaHRccmZsb29yLgpc'
    'XQoKKioyMuiHszI2NeeahDI0NOmgheWFqOmDqOiIhyBzZWFsZWQgcmVzdWx0IOS4gOiHtCoq'
    '77yb5pawIGVudmVsb3BlIOaYrzIy6IezMjY055qEMjQz6aCF77yM5rKS5pyJ5Y+q5qqi5p+l'
    '56uv6bue5oiW5YGH6Kit5Zau6Kq/5oCn44CC6YCZ57WE5pW45pOa55qE5YWo6YOoIHJvdW5k'
    'aW5nIGdhcHMg6YO954K6MOOAggoKfCDpoIXnm64gfCDoiIogZW52ZWxvcGUgfCDmlrAgZW52'
    'ZWxvcGUgfAp8LS0tfC0tLTp8LS0tOnwKfCBhcmdtYXggVCB8IDI2NSB8IDI2NCB8CnwgSzQg'
    'fCA0OTkgfCA0OTIgfAp8IEFfTUFY77yPQyB8IDE5NyB8IDE5NyB8CnwgUzQgfCAyOTMzMTQg'
    'fCAyODg1NjEgfAp8IFMzIHwgNTE2OTY5NiB8IDUxNTc4MjQgfAp8IEJvdW5kIHwgMzEzMzky'
    'MTI4IHwgKiozMTMzODI5NzIqKiB8CgrlnKggVDI2NO+8jEs0IOeahOacquWPluaVtOWAvOeC'
    'uiBcKDk4My8yXCnvvIzmraPnorrlkJHkuIrlj5bmlbTngro0OTLvvJtTNCBjcmVkaXQg5oGw'
    '54K6MTY0ODky44CC5pS55ZaE5YC854K6ICoqOTE1Nioq44CCCgpGb2N1c2VkIHRlc3RzIOea'
    'hOWvpumam+WRveS7pOWmguS4i++8jOW3peS9nOebrumMhOeCuuaMh+WumiBkb25vcu+8mgoK'
    'YGBgc2gKUFlUSE9ORE9OVFdSSVRFQllURUNPREU9MSBQWVRFU1RfRElTQUJMRV9QTFVHSU5f'
    'QVVUT0xPQUQ9MSBcClBZVEhPTlBBVEg9L1VzZXJzL2tlbHZpbi9WaWJlQ29kaW5nLVdvcmtT'
    'cGFjZS8ud29ya3RyZWVzL01hdGhTdGF0aXN0aWNhbEFuYWx5c2lzL0I2NDlfTkVYVF9SRVNP'
    'TFZFRF9DT09XTkVSXzY2NTU1NTU1NTU1NTIxMTAwMDAwX1IxL3NyYyBcCi9Vc2Vycy9rZWx2'
    'aW4vVmliZUNvZGluZy1Xb3JrU3BhY2UvTWF0aFN0YXRpc3RpY2FsQW5hbHlzaXMvLnZlbnYv'
    'YmluL3B5dGhvbiAtQiAtIDw8J1BZJwppbXBvcnQgcmVzb3VyY2UKcmVzb3VyY2Uuc2V0cmxp'
    'bWl0KHJlc291cmNlLlJMSU1JVF9DUFUsICgxMTAsIDEyMCkpCmltcG9ydCBweXRlc3QKcmFp'
    'c2UgU3lzdGVtRXhpdChweXRlc3QubWFpbihbCiAgICAnLXEnLCAnLXAnLCAnbm86Y2FjaGVw'
    'cm92aWRlcicsCiAgICAndGVzdHMvdW5pdC90ZXN0X2I2NDlfbmV4dF9yZXNvbHZlZF9jb293'
    'bmVyXzY2NTU1NTU1NTU1NTIxMTAwMDAwX3IxLnB5JwpdKSkKUFkKYGBgCgrntZDmnpzvvJoq'
    'KjIwIHBhc3NlZCBpbiA0MC42OXPvvIxleGl0IGNvZGUgMCoq44CC6YCZ5piv6KOc5YWF6amX'
    '6K2J77yb5LiK6L+w5a6M5pW06LaF6ZuG5ZCI6K2J5piO5Y+m5aSW542o56uL5a6M5oiQ44CC'
    'Cgp8IOW/heimgeiyoOWQkeaqouafpSB8IOe1kOaenCB8CnwtLS18LS0tfAp8IFdyb25nIGZy'
    'b3plbiByZXN1bHQgU0hBIHwgUkVKRUNURUQgfAp8IFdyb25nIGRvbm9yIHJlc3VsdCBTSEEg'
    'fCBSRUpFQ1RFRO+8jOeNqOeri+i6q+WIhiBnYXRlIHwKfCBXcm9uZyBwcm9maWxlIHwgUkVK'
    'RUNURUQgfAp8IFdyb25nIHNvdXJjZSBjYXAgfCBSRUpFQ1RFRCB8CnwgTWlzc2luZyDOtuKJ'
    'pTIgfCBSRUpFQ1RFRCB8CnwgTWlzc2luZyBjcm9zcy1lZGdlIGVxdWFsaXR5IHwgUkVKRUNU'
    'RUQgfAp8IE1pc3NpbmcgcGFyaXR577yP5o2P6YCgIG9kZCB6ZXJvIGdyYXBoIHwgUkVKRUNU'
    'RUQgfAp8IE1pc3NpbmcgUCBsb3dlciBib3VuZCB8IFJFSkVDVEVEIHwKfCBJbmNvbXBsZXRl'
    'IDQxMzEtY2FzZSBjb3ZlcmFnZSB8IFJFSkVDVEVEIHwKfCBNaXNzaW5nIGNyaXRpY2FsIGNv'
    'bmZpZ3VyYXRpb24gfCBSRUpFQ1RFRCB8CnwgV3JvbmcgSzQgY2VpbGluZyB8IFJFSkVDVEVE'
    'IHwKfCBXcm9uZyBTNCBjcmVkaXQgfCBSRUpFQ1RFRCB8CnwgVW5zdXBwb3J0ZWQgY2FwMjYz'
    'IHwgUkVKRUNURUTvvJvkuI3ku6PooaggY2FwMjYzIOW3suiiq+WPjeitiSB8Cgroo5zlhYUg'
    'd2l0bmVzcyDkuZ/ntpPnjajnq4vph43nrpfvvJoyMiB0cmlwbGVz44CBMjcgcGFpcnPjgIE5'
    'M+WAi+S6kueVsCBncmFwaCBlZGdlc+OAgeavj+elqOWuuemHjzbjgIFwcm9maWxl5LiA6Ie0'
    '77yMXChUPTI1OSx0KEgpPTM0XCnjgIIKCmBgYHRleHQKUFJPT0ZfU0NPUEU6IEZVTExfUFJP'
    'RklMRQpNQVRIRU1BVElDQUxfVEhFT1JFTTog5omA5pyJ5oyH5a6aIHN1cHBvcnQgbW9kZWwg'
    '55qE5ZCI5rOVIHJlYWxpemF0aW9uIOWdh+aciSBU4omkMjY0CkxPQURfQkVBUklOR19QUkVN'
    'SVNFUzogcGFpci1saW5lYXJpdHnjgIF0aWNrZXQgY2FwYWNpdHk244CB5Zu65a6aIHByb2Zp'
    'bGXjgIFjcm9zcy1lZGdlIGJhbGFuY2UKWkVUQV9MT1dFUl9CT1VORDogMu+8jOWwjeavj+WA'
    'i+WQiOazlSByZWFsaXphdGlvbiDmiJDnq4sKRVhBQ1RfVFJJQU5HTEVfSURFTlRJVFk6IFZF'
    'UklGSUVE77yMVD0yOTMtdChIKT1GLVAKTk9OTkVHQVRJVkVfUkVNQUlOREVSOiBWRVJJRklF'
    'RO+8jOWbm+WAi+mdnuiyoOioiOaVuOS5i+WSjAoKU0NBTEFSX1NUQVRFX0NPVkVSQUdFOgog'
    'IFRPVEFMOiA0MTMxCiAgRElSRUNUTFlfQ0xPU0VEOiA0MDU3CiAgUkVNQUlOSU5HOiA3NApS'
    'RVNJRFVBTF9TVEFURV9BQ0NPVU5USU5HOgogIFBBUklUWV9FWENMVURFRDogMzAKICBaRVJP'
    'X0dSQVBIX0VYQ0xVREVEOiAzNgogIElOQ0lERU5DRV9FWENMVURFRDogMgogIFJFVEFJTkVE'
    'X1NDQUxBUl9TVEFURVM6IDYKICBFWFBBTkRFRF9DUklUSUNBTF9DT05GSUdVUkFUSU9OUzog'
    'MjAKQUxMX1JFTUFJTklOR19TVEFURVNfQUNDT1VOVEVEOiBZRVMKQ1JJVElDQUxfQlJBTkNI'
    'X1BST09GOiBGPTI2Ne+8jFDiiaU2ClJFTEFYQVRJT05fU1VQRVJTRVRfQ09NUExFVEU6IFZF'
    'UklGSUVECgpQUk9WRURfVF9DQVA6IDI2NApPTERfQk9VTkQ6IDMxMzM5MjEyOApORVdfQURN'
    'SVNTSUJMRV9CT1VORDogMzEzMzgyOTcyCk9XTkVSX0JPVU5EX0RFTFRBOiA5MTU2ClJPVVRF'
    'X0JfUkVDT1VOVDogUEFTU19BTExfMjQ0X1RFUk1T77yb5pawIGVudmVsb3BlMjQz6aCFCkVY'
    'QUNUX1JBVElPTkFMX0NIRUNLOiBQQVNTX0FMTF8yNDRfVEVSTVMKUk9VTkRJTkdfQ0hFQ0s6'
    'IFBBU1MKQVJHTUFYX1RFUk06ICgyNjQsMzEzMzgyOTcyLDQ5MiwxOTcsMjg4NTYxLDUxNTc4'
    'MjQpCkZPQ1VTRURfVEVTVF9FWElUX0NPREU6IDAKTkVHQVRJVkVfQ0FTRV9SRVNVTFRTOiAx'
    'My8xMyBSRUpFQ1RFRAoKQ09VTlRFUkVYQU1QTEVfU1RBVFVTOiDmnKzmrKHlrozmlbTotoXp'
    'm4blkIjnhKHpgZXlj40gVOKJpDI2NCDnmoTliIbmlK8KVU5QUk9WRURfQVNTVU1QVElPTlM6'
    'IE5PTkVfV0lUSElOX1NUQVRFRF9TVVBQT1JUX01PREVMCk1BVEVSSUFMX0ZJTkRJTkdTOiDn'
    'hKHlvbHpn7/lrprnkIbmiJYgYm91bmQg55qE57y66Zm3Ck1JU1NJTkdfRVZJREVOQ0U6IE5P'
    'TkVfRk9SX1NDSUVOVElGSUNfU0NPUEUKQ0FWRUFUOiBQYWNrZXQg55qE44CMNTTjgI3mt7fn'
    'lKjkuoYgc2NhbGFyIHN0YXRlcyDoiIcgZXhwYW5kZWQgY29uZmlndXJhdGlvbnMKCkNPVkVS'
    'RURfSVRFTVM6IOi6q+WIhuOAgeWujOaVtCBwcm9maWxlIOitieaYjuOAgeWFqOmDqCByZXNp'
    'ZHVhbCBhY2NvdW50aW5n44CBUm91dGUtQuOAgWZvY3VzZWQvbmVnYXRpdmUgY2hlY2tzCk1J'
    'U1NJTkdfSVRFTVM6IE5PTkVfV0lUSElOX0FVVEhPUklaRURfU0NPUEUKUkVVU0VEX0VWSURF'
    'TkNFOiBwaW5uZWQgc291cmNlL3Jlc3VsdCDkvZzngrrlj5flr6novLjlhaXvvJvmnKrku6Xo'
    'iIogUEFTUyDloLHlkYrku6Pmm7/pqZforYkKSU5WQUxJREFURURfRVZJREVOQ0U6IE5PTkUK'
    'VkVSSUZJQ0FUSU9OX1JVTl9DT1VOVFM6CiAgRk9DVVNFRF9QWVRFU1Q6IDEKICBJTkRFUEVO'
    'REVOVF9TQ0FMQVJfUkVDT05TVFJVQ1RJT046IDEKICBJTkRFUEVOREVOVF9FWENMVVNJT05f'
    'Q1JPU1NDSEVDSzogMQogIElOREVQRU5ERU5UX1JPVVRFX0JfQU5EX0xPQ0FMX0RQOiAxCiAg'
    'TkVHQVRJVkVfQ09OVFJPTF9BTkRfV0lUTkVTU19SVU46IDEKCkZSRVNIX0NPTlRFWFRfVkVS'
    'RElDVDogVkVSSUZJRURfV0lUSF9DQVZFQVRTCkZBTUlMWV9BVVRIT1JJVFlfQURPUFRJT046'
    'IE5PVF9SVU4KU09VUkNFX01VVEFUSU9OOiBOT05FCkdJVF9NVVRBVElPTjogTk9ORQpQUl9N'
    'VVRBVElPTjogTk9ORQpQUk9EVUNUSU9OX01VVEFUSU9OOiBOT05FCkZJTEVTWVNURU1fV1JJ'
    'VEVfTEVER0VSOiBOT05FCkhFQVZZX1NPTFZFUl9TVEFSVEVEOiBOTwpGVUxMX1NVSVRFOiBO'
    'T1RfUlVOCkdMT0JBTF9LMjBfT1BUSU1VTTogVU5LTk9XTgpORVdfV0lOTklOR19PVVRDT01F'
    'UzogMApgYGA='
).decode("utf-8")

CURSOR_ID = "66544333333333332222"
CURSOR_BOUND = 313_394_584
CURSOR_COUNT = 197
EXPECTED_FAMILY_BOUND = 313_394_584
EXPECTED_NEXT_BOUND = 313_392_308
EXPECTED_NEXT_OWNERS = ["66665555555421000000"]
INCUMBENT = 313_263_888
EXPECTED_ROWS = 4_647
EXPECTED_EVENTS_BEFORE = 22
EXPECTED_TOTAL_EVENTS = 23

SCALAR_ACCOUNTING: dict[str, int] = {
    "TOTAL_SCALAR_STATES": 4_131,
    "DIRECTLY_CLOSED": 4_057,
    "REMAINING_SCALAR_STATES": 74,
    "PARITY_EXCLUDED": 30,
    "ZERO_GRAPH_EXCLUDED": 36,
    "INCIDENCE_EXCLUDED": 2,
    "TOTAL_EXCLUDED": 68,
    "RETAINED_SCALAR_STATES": 6,
}
CONFIGURATION_ACCOUNTING: dict[str, Any] = {
    "EXPANDED_CRITICAL_CONFIGURATIONS": 20,
    "RELATION": "6_RETAINED_SCALAR_STATES -> 20_CONFIGURATIONS",
    "CRITICAL_CONFIGURATION_PROOF": "F=265; P>=6; therefore T<=259",
}
JUDGE_CAVEAT = "HISTORICAL_REMAINING_54_UNIT_MIXUP"
JUDGE_CAVEAT_IMPACT = "NON_BLOCKING_FOR_T264_MATHEMATICS"


@dataclass(frozen=True)
class DonorSpec:
    event_id: str
    task_id: str
    profile_id: str
    previous_bound: int
    previous_cap: int
    s4_base: int
    bound: int
    cap: int
    head: str
    tree: str
    result_path: str
    result_sha256: str
    source_path: str
    source_sha256: str
    test_path: str
    test_sha256: str
    historical_source: str


DONOR = DonorSpec(
    event_id=DONOR_EVENT_ID,
    task_id=DONOR_TASK_ID,
    profile_id=PROFILE_ID,
    previous_bound=313_392_128,
    previous_cap=265,
    s4_base=112,
    bound=313_382_972,
    cap=264,
    head=DONOR_HEAD,
    tree=DONOR_TREE,
    result_path=DONOR_RESULT_PATH,
    result_sha256=DONOR_RESULT_SHA256,
    source_path=DONOR_SOURCE_PATH,
    source_sha256=DONOR_SOURCE_SHA256,
    test_path=DONOR_TEST_PATH,
    test_sha256=DONOR_TEST_SHA256,
    historical_source=HISTORICAL_SOURCE,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def json_object(raw: bytes, message: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(message) from exc
    require(type(value) is dict, message)
    return cast(dict[str, Any], value)


def validate_base_provenance(
    head: str, tree: str, parent: str, result_sha256: str
) -> None:
    require(
        (head, tree, parent, result_sha256)
        == (BASE_HEAD, BASE_TREE, BASE_PARENT, BASE_RESULT_SHA256),
        "22-event base provenance differs from the fixed Git object identity",
    )


def verify_science_accounting(actual: Mapping[str, Any]) -> None:
    require(dict(actual) == SCALAR_ACCOUNTING, "scalar-state accounting mismatch")
    require(
        SCALAR_ACCOUNTING["RETAINED_SCALAR_STATES"] == 6,
        "retained scalar-state count mismatch",
    )
    require(
        CONFIGURATION_ACCOUNTING["EXPANDED_CRITICAL_CONFIGURATIONS"] == 20
        and CONFIGURATION_ACCOUNTING["RELATION"]
        == "6_RETAINED_SCALAR_STATES -> 20_CONFIGURATIONS",
        "critical configuration accounting mismatch",
    )
    require(
        SCALAR_ACCOUNTING["REMAINING_SCALAR_STATES"]
        == SCALAR_ACCOUNTING["PARITY_EXCLUDED"]
        + SCALAR_ACCOUNTING["ZERO_GRAPH_EXCLUDED"]
        + SCALAR_ACCOUNTING["INCIDENCE_EXCLUDED"]
        + SCALAR_ACCOUNTING["RETAINED_SCALAR_STATES"],
        "scalar-state accounting does not sum to 74",
    )
    require(
        SCALAR_ACCOUNTING["TOTAL_EXCLUDED"]
        == SCALAR_ACCOUNTING["PARITY_EXCLUDED"]
        + SCALAR_ACCOUNTING["ZERO_GRAPH_EXCLUDED"]
        + SCALAR_ACCOUNTING["INCIDENCE_EXCLUDED"],
        "excluded scalar-state accounting mismatch",
    )


def verify_judge_snapshot() -> dict[str, Any]:
    raw = JUDGE_FINAL_MESSAGE.encode("utf-8")
    require(
        sha256(raw) == JUDGE_FINAL_MESSAGE_SHA256,
        "pinned T264 Fresh-context Judge message SHA256 mismatch",
    )
    required_text = (
        "FRESH_CONTEXT_VERDICT: VERIFIED_WITH_CAVEATS",
        "JUDGE_MODE: FRESH_CONTEXT",
        f"JUDGE_SESSION_ID: {JUDGE_SESSION_ID}",
        f"REVIEWED_HEAD:\n{DONOR_HEAD}",
        f"REVIEWED_TREE:\n{DONOR_TREE}",
        f"REVIEWED_RESULT_SHA256:\n{DONOR_RESULT_SHA256}",
        f"SOURCE_SHA256:\n{DONOR_SOURCE_SHA256}",
        f"TESTS_SHA256:\n{DONOR_TEST_SHA256}",
        PROFILE_ID,
        "PROVED_T_CAP: 264",
        "OLD_BOUND: 313392128",
        "NEW_ADMISSIBLE_BOUND: 313382972",
        "OWNER_BOUND_DELTA: 9156",
        "TOTAL: 4131",
        "DIRECTLY_CLOSED: 4057",
        "REMAINING: 74",
        "PARITY_EXCLUDED: 30",
        "ZERO_GRAPH_EXCLUDED: 36",
        "INCIDENCE_EXCLUDED: 2",
        "RETAINED_SCALAR_STATES: 6",
        "EXPANDED_CRITICAL_CONFIGURATIONS: 20",
        "CAVEAT: Packet 的「54」混用了 scalar states 與 expanded configurations",
        "FAMILY_AUTHORITY_ADOPTION: NOT_RUN",
    )
    require(
        all(marker in JUDGE_FINAL_MESSAGE for marker in required_text),
        "pinned T264 Judge message does not bind the donor identity, verdict or caveat",
    )
    verify_science_accounting(SCALAR_ACCOUNTING)
    return {
        "THREAD_ID": JUDGE_THREAD_ID,
        "SESSION_ID": JUDGE_SESSION_ID,
        "JUDGE_MODE": "FRESH_CONTEXT",
        "VERDICT": "VERIFIED_WITH_CAVEATS",
        "REVIEWED_HEAD": DONOR_HEAD,
        "REVIEWED_TREE": DONOR_TREE,
        "DONOR_RESULT_SHA256": DONOR_RESULT_SHA256,
        "SOURCE_SHA256": DONOR_SOURCE_SHA256,
        "TEST_SHA256": DONOR_TEST_SHA256,
        "PROFILE_ID": PROFILE_ID,
        "PROVED_T_CAP": DONOR.cap,
        "OLD_BOUND": DONOR.previous_bound,
        "NEW_BOUND": DONOR.bound,
        "OWNER_DELTA": DONOR.previous_bound - DONOR.bound,
        "FINAL_MESSAGE_SHA256": JUDGE_FINAL_MESSAGE_SHA256,
        "FINAL_MESSAGE_SNAPSHOT": JUDGE_FINAL_MESSAGE,
        "SCALAR_ACCOUNTING": dict(SCALAR_ACCOUNTING),
        "CONFIGURATION_ACCOUNTING": dict(CONFIGURATION_ACCOUNTING),
        "CAVEAT": JUDGE_CAVEAT,
        "CAVEAT_IMPACT": JUDGE_CAVEAT_IMPACT,
    }


def verify_fixed_authorities() -> dict[str, Any]:
    four.verify_commit(ROOT, FROZEN_HEAD, FROZEN_TREE)
    six_raw = four.committed_blob(ROOT, FROZEN_HEAD, SIX_ROW_RESULT_PATH)
    seven_raw = four.committed_blob(ROOT, FROZEN_HEAD, four.FROZEN_RESULT_PATH)
    require(sha256(six_raw) == SIX_ROW_RESULT_SHA256, "six-row result SHA256 mismatch")
    require(sha256(seven_raw) == SEVEN_ROW_RESULT_SHA256, "seven-row result SHA256 mismatch")
    six_record = json_object(six_raw, "six-row result is invalid JSON")
    require(
        six_record.get("RESOLVED_ROW_BOUNDS", {}).get(PROFILE_ID) == DONOR.previous_bound,
        "six-row result does not contain the pinned old bound",
    )
    require(
        (ROOT / SIX_ROW_RESULT_PATH).read_bytes() == six_raw
        and (ROOT / four.FROZEN_RESULT_PATH).read_bytes() == seven_raw,
        "working Frozen result differs from its pinned Git blob",
    )
    return {
        "FROZEN_HEAD": FROZEN_HEAD,
        "FROZEN_TREE": FROZEN_TREE,
        "FROZEN_HEAD_TREE": "MATCH",
        "SIX_ROW_RESULT_SHA256": sha256(six_raw),
        "SEVEN_ROW_RESULT_SHA256": sha256(seven_raw),
        "SOURCE_ROW_BOUND_FROM_SIX_ROW_RESULT": DONOR.previous_bound,
    }


def verify_donor_record(
    record: Mapping[str, Any],
    spec: DonorSpec,
    frozen_row: four.Row,
    source_raw: bytes,
) -> str:
    try:
        source_doc = ast.get_docstring(ast.parse(source_raw.decode("utf-8")), clean=False)
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise ValueError("T264 donor source proof cannot be parsed") from exc
    proof = record.get("PROOF")
    require(type(proof) is str and bool(proof.strip()), "T264 donor proof is missing")
    require(source_doc == proof, "T264 donor proof differs from the committed source")
    source_row = record.get("FROZEN_IDENTITY", {}).get("SOURCE_ROW")
    require(type(source_row) is dict, "T264 frozen source row is missing")
    row = cast(dict[str, Any], source_row)
    require(
        (row.get("bound"), row.get("cap"), row.get("s4_base"), row.get("source"))
        == (
            frozen_row.bound,
            frozen_row.cap,
            frozen_row.s4_base,
            frozen_row.source,
        )
        == (
            spec.previous_bound,
            spec.previous_cap,
            spec.s4_base,
            spec.historical_source,
        ),
        "T264 donor source row differs from the replayed Frozen row",
    )
    claim = (
        record.get("TASK_ID"),
        record.get("TASK_STATUS"),
        record.get("JUDGE_MODE"),
        record.get("PROFILE_ID"),
        record.get("SOURCE_T_CAP"),
        record.get("TARGET_T_CAP"),
        record.get("PROVED_T_CAP"),
        record.get("SOURCE_S4_BASE"),
        record.get("OLD_BOUND"),
        record.get("NEW_ADMISSIBLE_BOUND"),
        record.get("EXPECTED_T264_BOUND"),
        record.get("OWNER_DELTA"),
        record.get("FAMILY_GAIN_CLAIMED"),
    )
    expected = (
        spec.task_id,
        "FULL_PROFILE_T264_PROVED_SELF_CHECK_ONLY",
        "SELF_CHECK_ONLY",
        spec.profile_id,
        spec.previous_cap,
        spec.cap,
        spec.cap,
        spec.s4_base,
        spec.previous_bound,
        spec.bound,
        spec.bound,
        spec.previous_bound - spec.bound,
        0,
    )
    require(claim == expected, "T264 donor profile, cap, bound or Worker status mismatch")
    frozen_identity = cast(dict[str, Any], record.get("FROZEN_IDENTITY"))
    require(
        frozen_identity.get("FROZEN_HEAD") == FROZEN_HEAD
        and frozen_identity.get("FROZEN_TREE") == FROZEN_TREE
        and frozen_identity.get("FROZEN_HEAD_TREE") == "MATCH"
        and frozen_identity.get("FROZEN_RESULT_SHA256") == SEVEN_ROW_RESULT_SHA256
        and frozen_identity.get("SOURCE_LOCATOR_KIND") == SOURCE_LOCATOR_KIND
        and frozen_identity.get("SOURCE_ROW_BOUND") == spec.previous_bound
        and frozen_identity.get("SOURCE_S4_BASE") == spec.s4_base
        and frozen_identity.get("STORED_BOUND_LOCATOR")
        == f"{SIX_ROW_RESULT_PATH}#/RESOLVED_ROW_BOUNDS/{spec.profile_id}",
        "T264 donor Frozen provenance or virtual source locator mismatch",
    )
    require(
        record.get("FULL_PROFILE_PROOF") is True
        and record.get("RELAXATION_SUPERSET_COMPLETE") is True
        and record.get("EXACT_TRIANGLE_IDENTITY") == "T=293-t(H)=F-P"
        and record.get("NONNEGATIVE_REMAINDER") == "SUM_OF_FOUR_CARDINALITIES"
        and record.get("GLOBAL_K20_OPTIMUM") == "UNKNOWN"
        and record.get("NEW_WINNING_OUTCOMES") == 0
        and record.get("UNPROVED_ASSUMPTIONS") == [],
        "T264 donor proof scope or claim exceeds the authorized profile result",
    )
    route = cast(dict[str, Any], record.get("ROUTE_B"))
    raw_terms = route.get("ALL_T_TERMS_22_THROUGH_265")
    require(
        type(raw_terms) is list and len(raw_terms) == 244,
        "T264 Route-B term coverage mismatch",
    )
    terms = cast(list[list[int]], raw_terms)
    require(
        [term[0] for term in terms] == list(range(22, 266)),
        "T264 Route-B envelope has a missing or reordered term",
    )
    best_old = max(terms, key=lambda term: term[1])
    best_new = max(terms[:-1], key=lambda term: term[1])
    require(
        best_old == [265, 313392128, 499, 197, 293314, 5169696]
        and best_new == [264, spec.bound, 492, 197, 288561, 5157824]
        and route.get("ARGMAX_TERM") == best_new
        and route.get("NEW_ENVELOPE_TERM_COUNT") == 243,
        "T264 Route-B argmax or envelope mismatch",
    )
    return sha256(cast(str, proof).encode("utf-8"))


def verify_t264_donor(
    root: Path, frozen_row: four.Row, spec: DonorSpec
) -> tuple[dict[str, Any], dict[str, Any], dict[str, bytes]]:
    four.verify_commit(root, spec.head, spec.tree)
    parents = cast(str, four.run_git(root, "rev-list", "--parents", "-n", "1", spec.head)).split()
    require(parents == [spec.head, FROZEN_HEAD], "T264 donor parent is not the Frozen HEAD")
    paths = {
        "RESULT": spec.result_path,
        "SOURCE": spec.source_path,
        "TEST": spec.test_path,
    }
    blobs = {
        name: four.committed_blob(root, spec.head, path)
        for name, path in paths.items()
    }
    require(sha256(blobs["RESULT"]) == spec.result_sha256, "T264 donor result SHA256 mismatch")
    require(sha256(blobs["SOURCE"]) == spec.source_sha256, "T264 donor source SHA256 mismatch")
    require(sha256(blobs["TEST"]) == spec.test_sha256, "T264 donor test SHA256 mismatch")
    record = json_object(blobs["RESULT"], "T264 donor result is invalid JSON")
    proof_sha = verify_donor_record(record, spec, frozen_row, blobs["SOURCE"])
    judge = verify_judge_snapshot()
    require(
        judge["REVIEWED_HEAD"] == spec.head
        and judge["REVIEWED_TREE"] == spec.tree
        and judge["DONOR_RESULT_SHA256"] == spec.result_sha256,
        "Fresh-context Judge reviewed a different T264 donor",
    )
    row_source = (
        f"git:{spec.head}@{spec.tree}:{spec.result_path}#PROOF:sha256={proof_sha}"
    )
    identity = {
        "EVENT_ID": spec.event_id,
        "TASK_ID": spec.task_id,
        "HEAD": spec.head,
        "TREE": spec.tree,
        "PARENT": FROZEN_HEAD,
        "HEAD_TREE": "MATCH",
        "RESULT_PATH": spec.result_path,
        "RESULT_SHA256": sha256(blobs["RESULT"]),
        "SOURCE_PATH": spec.source_path,
        "SOURCE_SHA256": sha256(blobs["SOURCE"]),
        "TEST_PATH": spec.test_path,
        "TEST_SHA256": sha256(blobs["TEST"]),
        "PROFILE_ID": spec.profile_id,
        "BOUND_BEFORE": spec.previous_bound,
        "CAP_BEFORE": spec.previous_cap,
        "S4_BASE": spec.s4_base,
        "BOUND_AFTER": spec.bound,
        "CAP_AFTER": spec.cap,
        "OWNER_BOUND_DELTA": spec.previous_bound - spec.bound,
        "WORKER_STATUS": record["TASK_STATUS"],
        "WORKER_JUDGE_MODE": record["JUDGE_MODE"],
        "PROOF_SCOPE": "FULL_PROFILE",
        "PROOF_SHA256": proof_sha,
        "PROOF_LOCATOR": row_source,
        "ROW_SOURCE": row_source,
        "HISTORICAL_SOURCE_LOCATOR": frozen_row.source,
        "SOURCE_LOCATOR_KIND": SOURCE_LOCATOR_KIND,
        "FRESH_CONTEXT_JUDGE": judge,
        "FAMILY_GAIN_CLAIMED_BY_DONOR": record["FAMILY_GAIN_CLAIMED"],
        "SCALAR_ACCOUNTING": dict(SCALAR_ACCOUNTING),
        "CONFIGURATION_ACCOUNTING": dict(CONFIGURATION_ACCOUNTING),
        "CAVEAT": JUDGE_CAVEAT,
        "CAVEAT_IMPACT": JUDGE_CAVEAT_IMPACT,
    }
    require(
        resolve_proof_locator(root, row_source) == proof_sha,
        "T264 proof locator does not resolve to the committed proof",
    )
    return record, identity, blobs


def resolve_proof_locator(root: Path, locator: str) -> str:
    match = re.fullmatch(
        r"git:([0-9a-f]{40})@([0-9a-f]{40}):([^#]+)#PROOF:sha256=([0-9a-f]{64})",
        locator,
    )
    require(match is not None, "proof locator is malformed")
    donor_head, donor_tree, result_path, expected_proof_sha = cast(
        re.Match[str], match
    ).groups()
    four.verify_commit(root, donor_head, donor_tree)
    raw = four.committed_blob(root, donor_head, result_path)
    record = json_object(raw, "proof locator result is invalid JSON")
    proof = record.get("PROOF")
    require(type(proof) is str, "proof locator has no string PROOF")
    actual = sha256(cast(str, proof).encode("utf-8"))
    require(actual == expected_proof_sha, "proof locator SHA256 does not match its proof")
    return actual


def expected_family() -> dict[str, Any]:
    return {
        "FAMILY_BOUND": EXPECTED_FAMILY_BOUND,
        "TIED_OWNERS": [CURSOR_ID],
        "NEXT_COMPETING_BOUND": EXPECTED_NEXT_BOUND,
        "NEXT_COMPETING_OWNERS": EXPECTED_NEXT_OWNERS,
        "CURSOR": {"ID": CURSOR_ID, "BOUND": CURSOR_BOUND},
    }


def verify_22_event_base() -> tuple[
    dict[str, Any],
    dict[str, four.Row],
    dict[str, four.Row],
    dict[str, four.Row],
    bytes,
]:
    verify_fixed_authorities()
    four.verify_commit(ROOT, BASE_HEAD, BASE_TREE)
    parents = cast(str, four.run_git(ROOT, "rev-list", "--parents", "-n", "1", BASE_HEAD)).split()
    require(
        parents == [BASE_HEAD, BASE_PARENT],
        "22-event base commit parent differs from the fixed 20-event source",
    )
    raw = four.committed_blob(ROOT, BASE_HEAD, BASE_RESULT_PATH)
    base_sha = sha256(raw)
    validate_base_provenance(BASE_HEAD, BASE_TREE, parents[1], base_sha)
    require(
        (ROOT / BASE_RESULT_PATH).read_bytes() == raw,
        "working 22-event result differs from its pinned Git blob",
    )
    recorded = json_object(raw, "pinned 22-event result is invalid JSON")

    twenty_result, frozen, after_twenty = twenty.build_candidate()
    twenty_raw = four.committed_blob(ROOT, BASE_HEAD, twenty.RESULT_PATH)
    require(
        (ROOT / twenty.RESULT_PATH).read_bytes() == twenty_raw
        and twenty.serialize_result(twenty_result) == twenty_raw
        and twenty_result.get("TOTAL_EVENTS") == 20
        and len(twenty_result.get("EVENT_HISTORY", [])) == 20,
        "20-event source replay differs from the fixed 22-event parent",
    )
    require(
        sha256(twenty_raw)
        == recorded.get("BASE_20_EVENT_AUTHORITY", {}).get("RESULT_SHA256"),
        "22-event result is bound to a different 20-event result",
    )

    records: dict[str, dict[str, Any]] = {}
    identities: dict[str, dict[str, Any]] = {}
    pins: list[nine.DonorPin] = []
    for spec in twenty_two.DONORS:
        frozen_row = frozen.get(spec.profile_id)
        require(frozen_row is not None, f"Frozen replay omitted 22-event profile {spec.profile_id}")
        target = cast(four.Row, frozen_row)
        require(
            after_twenty.get(spec.profile_id) == target
            and (target.bound, target.cap, target.s4_base, target.source)
            == (spec.previous_bound, spec.previous_cap, spec.s4_base, spec.historical_source),
            f"20-event replay changed the 22-event target {spec.profile_id}",
        )
        donor_record, identity, _blobs = twenty_two.verify_donor_artifact(
            ROOT, target, spec
        )
        records[spec.event_id] = donor_record
        identities[spec.event_id] = identity
        pins.append(twenty_two.donor_pin(spec, identity))

    family_before = four.family_frontier(after_twenty)
    four.verify_family_summary(
        family_before,
        twenty_two.expected_family(
            twenty_two.EXPECTED_BASE_NEXT_BOUND,
            twenty_two.EXPECTED_BASE_NEXT_OWNERS,
        ),
    )
    after_22, added_events = nine.apply_donor_events(
        after_twenty, pins, identities
    )
    previous_events = cast(list[dict[str, Any]], twenty_result["EVENT_HISTORY"])
    events_22 = [*previous_events, *added_events]
    sixteen.verify_unique_events(events_22)
    require(
        len(added_events) == 2
        and len(events_22) == EXPECTED_EVENTS_BEFORE
        and recorded.get("EVENT_HISTORY") == events_22,
        "pinned 22-event result does not replay from the fixed 20-event parent",
    )
    require(
        recorded.get("DONOR_IDENTITIES") == identities,
        "22-event donor identities differ from replayed commit/result/proof inputs",
    )
    full = four.seven.two.full_digest(after_22)
    bounds = four.seven.two.bounds_digest(after_22)
    family_after = four.family_frontier(after_22)
    four.verify_family_summary(family_after, expected_family())
    require(
        (len(frozen), len(after_22), full, bounds)
        == (EXPECTED_ROWS, EXPECTED_ROWS, BASE_FULL_DIGEST, BASE_BOUNDS_DIGEST)
        and (recorded.get("FULL_DIGEST"), recorded.get("BOUNDS_DIGEST"))
        == (BASE_FULL_DIGEST, BASE_BOUNDS_DIGEST),
        "22-event replay row count or full/bounds digest mismatch",
    )
    changed = {
        profile_id for profile_id in frozen if frozen[profile_id] != after_22[profile_id]
    }
    changed_from_base = {
        profile_id
        for profile_id in after_twenty
        if after_twenty[profile_id] != after_22[profile_id]
    }
    require(
        len(changed) == 21
        and len(frozen) - len(changed) == 4_626
        and changed_from_base == {spec.profile_id for spec in twenty_two.DONORS}
        and len(after_twenty) - len(changed_from_base) == 4_645,
        "22-event row mutation partition mismatch",
    )
    require(
        recorded.get("ROWS_BEFORE") == EXPECTED_ROWS
        and recorded.get("ROWS_AFTER") == EXPECTED_ROWS
        and recorded.get("TOTAL_EVENTS") == EXPECTED_EVENTS_BEFORE
        and recorded.get("DISTINCT_CHANGED_PROFILES") == 21
        and recorded.get("UNCHANGED_ROWS_FROM_FROZEN") == 4_626
        and recorded.get("CHANGED_ROWS_FROM_BASE") == 2
        and recorded.get("UNCHANGED_ROWS_FROM_BASE") == 4_645
        and recorded.get("ALL_NEW_PROOF_LOCATORS_RESOLVE") == "YES",
        "pinned 22-event result counts or proof-locator gate mismatch",
    )
    return recorded, frozen, after_twenty, after_22, raw


def validate_t264_result(
    record: Mapping[str, Any], frozen_row: four.Row, spec: DonorSpec = DONOR
) -> None:
    proof = record.get("PROOF")
    require(type(proof) is str, "T264 donor proof is missing")
    source_raw = four.committed_blob(ROOT, spec.head, spec.source_path)
    verify_donor_record(record, spec, frozen_row, source_raw)


def expect_rejected(action: Any, message: str) -> str:
    try:
        action()
    except (AssertionError, KeyError, TypeError, ValueError):
        return "PASS"
    raise ValueError(message)


def verify_negative_cases(
    frozen_row: four.Row,
    donor_record: Mapping[str, Any],
    base_rows: Mapping[str, four.Row],
    after_rows: Mapping[str, four.Row],
    family_result: Mapping[str, Any],
) -> dict[str, str]:
    wrong_sha = replace(DONOR, result_sha256="0" * 64)
    wrong_profile = replace(DONOR, profile_id="0" * 20)
    wrong_cap = replace(DONOR, cap=DONOR.cap - 1)
    wrong_bound = replace(DONOR, bound=DONOR.bound + 1)
    bad_proof = dict(donor_record)
    bad_proof["PROOF"] = "altered proof"
    unrelated = next(profile_id for profile_id in after_rows if profile_id != PROFILE_ID)
    changed_rows = dict(after_rows)
    changed_rows[unrelated] = replace(changed_rows[unrelated], source="unrelated-row-mutation")
    missing_cursor = dict(family_result)
    missing_cursor.pop("CURSOR", None)
    bad_accounting = dict(SCALAR_ACCOUNTING)
    bad_accounting["REMAINING_SCALAR_STATES"] += 1
    return {
        "WRONG_DONOR_SHA_REJECTED": expect_rejected(
            lambda: verify_t264_donor(ROOT, frozen_row, wrong_sha),
            "wrong T264 donor result SHA was accepted",
        ),
        "WRONG_PROFILE_REJECTED": expect_rejected(
            lambda: validate_t264_result(donor_record, frozen_row, wrong_profile),
            "wrong T264 profile was accepted",
        ),
        "WRONG_CAP_REJECTED": expect_rejected(
            lambda: validate_t264_result(donor_record, frozen_row, wrong_cap),
            "wrong T264 cap was accepted",
        ),
        "WRONG_BOUND_REJECTED": expect_rejected(
            lambda: validate_t264_result(donor_record, frozen_row, wrong_bound),
            "wrong T264 bound was accepted",
        ),
        "WRONG_PROOF_REJECTED": expect_rejected(
            lambda: validate_t264_result(bad_proof, frozen_row),
            "wrong T264 proof was accepted",
        ),
        "UNRELATED_ROW_CHANGE_REJECTED": expect_rejected(
            lambda: sixteen.verify_ledger_partition(
                base_rows, changed_rows, {PROFILE_ID}
            ),
            "unrelated ledger-row mutation was accepted",
        ),
        "CURSOR_OMISSION_REJECTED": expect_rejected(
            lambda: four.verify_family_summary(missing_cursor, expected_family()),
            "omitted unresolved cursor was accepted",
        ),
        "INCORRECT_SCALAR_ACCOUNTING_REJECTED": expect_rejected(
            lambda: verify_science_accounting(bad_accounting),
            "incorrect scalar-state accounting was accepted",
        ),
        "WRONG_BASE_PROVENANCE_REJECTED": expect_rejected(
            lambda: validate_base_provenance(
                "0" * 40, BASE_TREE, BASE_PARENT, BASE_RESULT_SHA256
            ),
            "wrong 22-event base provenance was accepted",
        ),
    }


def build_candidate() -> tuple[
    dict[str, Any],
    dict[str, four.Row],
    dict[str, four.Row],
    dict[str, four.Row],
]:
    base_result, frozen, _after_twenty, base_rows, base_raw = verify_22_event_base()
    frozen_target = frozen.get(PROFILE_ID)
    require(frozen_target is not None, "Frozen ledger omitted the T264 profile")
    frozen_row = cast(four.Row, frozen_target)
    require(
        base_rows.get(PROFILE_ID) == frozen_row
        and (frozen_row.bound, frozen_row.cap, frozen_row.s4_base, frozen_row.source)
        == (DONOR.previous_bound, DONOR.previous_cap, DONOR.s4_base, DONOR.historical_source),
        "22-event base does not retain the pinned old T264 row",
    )

    donor_record, donor_identity, donor_blobs = verify_t264_donor(
        ROOT, frozen_row, DONOR
    )
    pin = nine.DonorPin(
        event_id=DONOR.event_id,
        task_id=DONOR.task_id,
        profile_id=DONOR.profile_id,
        previous_bound=DONOR.previous_bound,
        previous_cap=DONOR.previous_cap,
        bound=DONOR.bound,
        cap=DONOR.cap,
        s4_base=DONOR.s4_base,
        head=DONOR.head,
        tree=DONOR.tree,
        result_path=DONOR.result_path,
        result_sha256=DONOR.result_sha256,
        source_path=DONOR.source_path,
        source_sha256=sha256(donor_blobs["SOURCE"]),
        test_path=DONOR.test_path,
        test_sha256=sha256(donor_blobs["TEST"]),
        proof_sha256=donor_identity["PROOF_SHA256"],
    )
    family_before = four.family_frontier(base_rows)
    four.verify_family_summary(family_before, expected_family())
    after_23, new_events = nine.apply_donor_events(
        base_rows, [pin], {DONOR.event_id: donor_identity}
    )
    require(
        len(new_events) == 1
        and new_events[0].get("PROFILE_ID") == PROFILE_ID
        and new_events[0].get("BOUND_BEFORE") == DONOR.previous_bound
        and new_events[0].get("BOUND_AFTER") == DONOR.bound
        and new_events[0].get("CAP_BEFORE") == DONOR.previous_cap
        and new_events[0].get("CAP_AFTER") == DONOR.cap
        and new_events[0].get("S4_BASE_BEFORE") == DONOR.s4_base
        and new_events[0].get("S4_BASE_AFTER") == DONOR.s4_base
        and new_events[0].get("SOURCE_BEFORE") == HISTORICAL_SOURCE
        and new_events[0].get("SOURCE_AFTER") == donor_identity["PROOF_LOCATOR"],
        "the T264 event differs from its one-row transition",
    )

    previous_events = cast(list[dict[str, Any]], base_result["EVENT_HISTORY"])
    events = [*previous_events, *new_events]
    sixteen.verify_unique_events(events)
    require(
        len(previous_events) == EXPECTED_EVENTS_BEFORE
        and len(new_events) == 1
        and len(events) == EXPECTED_TOTAL_EVENTS,
        "23-event history must retain 22 events and add exactly one",
    )
    changed_from_base = sixteen.verify_ledger_partition(
        base_rows, after_23, {PROFILE_ID}
    )
    changed_from_frozen = {
        profile_id for profile_id in frozen if frozen[profile_id] != after_23[profile_id]
    }
    require(
        len(changed_from_frozen) == 22
        and PROFILE_ID not in base_result["CHANGED_PROFILE_IDS_FROM_FROZEN"]
        and len(frozen) - len(changed_from_frozen) == 4_625
        and changed_from_base == {PROFILE_ID}
        and len(base_rows) - len(changed_from_base) == 4_646,
        "23-event changed/unchanged row partition mismatch",
    )

    before_full = four.seven.two.full_digest(base_rows)
    before_bounds = four.seven.two.bounds_digest(base_rows)
    full_digest = four.seven.two.full_digest(after_23)
    bounds_digest = four.seven.two.bounds_digest(after_23)
    require(
        (before_full, before_bounds) == (BASE_FULL_DIGEST, BASE_BOUNDS_DIGEST),
        "22-event base digest differs before applying T264",
    )
    family_after = four.family_frontier(after_23)
    four.verify_family_summary(family_after, expected_family())
    require(
        family_before["FAMILY_BOUND"] == family_after["FAMILY_BOUND"]
        and family_before["FAMILY_BOUND"] - family_after["FAMILY_BOUND"] == 0,
        "T264 owner delta must not be reported as Family gain",
    )

    cursor = cast(dict[str, Any], base_result["CURSOR_AUTHORITY"])
    require(
        cursor.get("ID") == CURSOR_ID
        and cursor.get("BOUND") == CURSOR_BOUND
        and cursor.get("COUNT") == CURSOR_COUNT
        and family_after.get("CURSOR") == {"ID": CURSOR_ID, "BOUND": CURSOR_BOUND},
        "unresolved cursor identity or count was not preserved",
    )
    resolved_above_incumbent = sum(
        row.bound > INCUMBENT for row in after_23.values()
    )
    require(
        resolved_above_incumbent == 1_364,
        "resolved profile count above the incumbent changed unexpectedly",
    )
    verify_science_accounting(SCALAR_ACCOUNTING)
    judge = cast(dict[str, Any], donor_identity["FRESH_CONTEXT_JUDGE"])
    negative_validations = verify_negative_cases(
        frozen_row, donor_record, base_rows, after_23, family_after
    )
    require(
        set(negative_validations.values()) == {"PASS"},
        "one or more negative integration controls were accepted",
    )

    transitions = cast(list[dict[str, Any]], base_result["EVENT_FAMILY_TRANSITIONS"])
    require(
        len(transitions) == 6,
        "22-event base must preserve its six historical Family transitions",
    )
    transitions_after = [
        *transitions,
        {
            "EVENT_ID": DONOR.event_id,
            "FAMILY_BOUND_BEFORE": family_before["FAMILY_BOUND"],
            "FAMILY_BOUND_AFTER": family_after["FAMILY_BOUND"],
            "TIED_OWNERS_AFTER": family_after["TIED_OWNERS"],
            "NEXT_COMPETING_BOUND_AFTER": family_after["NEXT_COMPETING_BOUND"],
            "NEXT_COMPETING_OWNERS_AFTER": family_after["NEXT_COMPETING_OWNERS"],
        },
    ]
    result: dict[str, Any] = {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "LOCAL_23_EVENT_CANDIDATE_REPLAYED",
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "FORMAL_AUTHORITY_ACCEPTANCE": "NOT_CLAIMED",
        "FORMAL_FAMILY_AUTHORITY": "NOT_ACCEPTED",
        "AUTHORITY_GATES": {
            "FROZEN_HEAD_TREE": "MATCH",
            "SIX_ROW_RESULT_SHA256": "MATCH",
            "SEVEN_ROW_RESULT_SHA256": "MATCH",
            "BASE_HEAD_TREE": "MATCH",
            "BASE_RESULT_SHA256": "MATCH",
            "DONOR_HEAD_TREE": "MATCH",
            "DONOR_RESULT_SHA256": "MATCH",
            "DONOR_SOURCE_SHA256": "MATCH",
            "DONOR_TEST_SHA256": "MATCH",
            "DONOR_JUDGE_IDENTITY": "MATCH",
            "ALL_PROOF_LOCATORS": "RESOLVED",
        },
        "FROZEN_AUTHORITY": base_result["FROZEN_AUTHORITY"],
        "BASE_22_EVENT_AUTHORITY": {
            "HEAD": BASE_HEAD,
            "TREE": BASE_TREE,
            "PARENT": BASE_PARENT,
            "RESULT_PATH": BASE_RESULT_PATH,
            "RESULT_SHA256": sha256(base_raw),
            "FULL_DIGEST": before_full,
            "BOUNDS_DIGEST": before_bounds,
            "EVENTS": EXPECTED_EVENTS_BEFORE,
            "REPLAY_MATCH": "YES",
        },
        "DONOR_IDENTITY": donor_identity,
        "INHERITED_22_EVENT_JUDGE": {
            "VERDICT": "REFUTED",
            "REASON": "POSTCOMMIT_HEAD_GUARD",
            "PRESERVED": "YES",
            "BASE_RESULT_SHA256": sha256(base_raw),
        },
        "INHERITED_CAVEATS_PRESERVED": base_result["INHERITED_CAVEATS_PRESERVED"],
        "T264_SCIENCE_JUDGE": judge,
        "T264_SCIENCE": {
            "PROFILE_ID": PROFILE_ID,
            "PROVED_T_CAP": DONOR.cap,
            "OLD_BOUND": DONOR.previous_bound,
            "NEW_BOUND": DONOR.bound,
            "OWNER_DELTA": DONOR.previous_bound - DONOR.bound,
            "SCALAR_ACCOUNTING": dict(SCALAR_ACCOUNTING),
            "CONFIGURATION_ACCOUNTING": dict(CONFIGURATION_ACCOUNTING),
            "COUNT_UNITS_NOT_MIXED": "YES",
            "JUDGE_CAVEAT": JUDGE_CAVEAT,
            "CAVEAT_IMPACT": JUDGE_CAVEAT_IMPACT,
        },
        "ROWS_BEFORE": len(frozen),
        "ROWS_AFTER": len(after_23),
        "OLD_EVENTS": EXPECTED_EVENTS_BEFORE,
        "PREVIOUS_EVENTS": len(previous_events),
        "NEW_EVENTS": len(new_events),
        "TOTAL_EVENTS": len(events),
        "DISTINCT_CHANGED_PROFILES_FROM_FROZEN": len(changed_from_frozen),
        "CHANGED_PROFILE_IDS_FROM_FROZEN": sorted(changed_from_frozen),
        "UNCHANGED_ROWS_FROM_FROZEN": len(frozen) - len(changed_from_frozen),
        "CHANGED_ROWS_FROM_BASE": len(changed_from_base),
        "UNCHANGED_ROWS_FROM_BASE": len(base_rows) - len(changed_from_base),
        "OWNER_OLD_CAP": DONOR.previous_cap,
        "OWNER_NEW_CAP": DONOR.cap,
        "OWNER_OLD_BOUND": DONOR.previous_bound,
        "OWNER_NEW_BOUND": DONOR.bound,
        "OWNER_DELTA": DONOR.previous_bound - DONOR.bound,
        "SOURCE_METADATA_BINDINGS": "VERIFIED",
        "ALL_PROOF_LOCATORS_RESOLVED": "YES",
        "UNRELATED_ROW_MUTATION": "NONE",
        "FULL_DIGEST": full_digest,
        "BOUNDS_DIGEST": bounds_digest,
        "NEW_FULL_DIGEST": full_digest,
        "NEW_BOUNDS_DIGEST": bounds_digest,
        "EVENT_HISTORY": events,
        "EVENT_FAMILY_TRANSITIONS": transitions_after,
        "FAMILY_BOUND_BEFORE": family_before["FAMILY_BOUND"],
        "FAMILY_BOUND_AFTER": family_after["FAMILY_BOUND"],
        "FAMILY_GAIN": family_before["FAMILY_BOUND"] - family_after["FAMILY_BOUND"],
        "MAX_OWNER": CURSOR_ID,
        "MAX_OWNER_TYPE": "UNRESOLVED_CURSOR",
        "MAXIMIZING_OWNERS": family_after["TIED_OWNERS"],
        "NEXT_DISTINCT_BOUND": family_after["NEXT_COMPETING_BOUND"],
        "NEXT_COMPETING_OWNERS": family_after["NEXT_COMPETING_OWNERS"],
        "RESOLVED_PROFILES_ABOVE_INCUMBENT": resolved_above_incumbent,
        "CURSOR_COUNT": cursor["COUNT"],
        "CURSOR_BOUND": cursor["BOUND"],
        "CURSOR_INCLUDED": "YES",
        "CURSOR_AUTHORITY": cursor,
        "UNADOPTED_197_PROFILE_CLASS_BOUND": "NOT_INTEGRATED",
        "NEW_WINNING_OUTCOMES": 0,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "NEGATIVE_VALIDATIONS": negative_validations,
        "FOCUSED_TEST_PATH": (
            "tests/unit/test_b649_t264_23_event_local_family_integration_r1.py"
        ),
        "FULL_SUITE": "NOT_RUN",
        "HEAVY_SOLVER_STARTED": "NO",
        "PUSH": "NOT_RUN",
        "PR": "NOT_RUN",
        "MERGE": "NOT_RUN",
        "PRODUCTION_MUTATION": "NONE",
    }
    require(
        result["FAMILY_GAIN"] == 0,
        "the 9156 Owner delta must not be treated as Family gain",
    )
    encoded = serialize_result(result)
    json_object(encoded, "23-event result serialization is invalid JSON")
    result_path = ROOT / RESULT_PATH
    if result_path.exists():
        require(
            result_path.read_bytes() == encoded,
            "saved 23-event result differs from the complete replay",
        )
    return result, frozen, base_rows, after_23


def serialize_result(result: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def write_result(result: Mapping[str, Any]) -> str:
    path = ROOT / RESULT_PATH
    raw = serialize_result(result)
    if path.exists():
        require(path.read_bytes() == raw, "refusing to replace a different result artifact")
    else:
        with path.open("xb") as output:
            output.write(raw)
        require(path.read_bytes() == raw, "result read-after-write mismatch")
    return sha256(raw)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="save the replayed result JSON")
    args = parser.parse_args()
    result, _frozen, _base_rows, _after = build_candidate()
    raw = serialize_result(result)
    result_sha = write_result(result) if args.write else sha256(raw)
    print(
        json.dumps(
            {
                "TASK_STATUS": result["TASK_STATUS"],
                "ROWS_AFTER": result["ROWS_AFTER"],
                "TOTAL_EVENTS": result["TOTAL_EVENTS"],
                "FULL_DIGEST": result["FULL_DIGEST"],
                "BOUNDS_DIGEST": result["BOUNDS_DIGEST"],
                "RESULT_SHA256": result_sha,
                "WORKTREE_HEAD": four.run_git(ROOT, "rev-parse", "HEAD"),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
