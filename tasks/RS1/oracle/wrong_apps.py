# One literal: each wrong app is the reference with one stated behaviour broken; `reds` is the exact set of hidden test
# ids it turns red, by assertion. `edits` apply to the reference overlay, each `old` exactly once.
WRONG_APPS = {
    "wa-id-str": {
        "edits": [{"file": "prometheus_client/ledger.py",
                   "old": '            return int(json.loads(payload)["id"])\n',
                   "new": '            return str(json.loads(payload)["id"])\n'}],
        "reds": ["test_returns_the_new_event_id_as_an_int"]},
    "wa-path": {
        "edits": [{"file": "prometheus_client/ledger.py",
                   "old": '"/v1/events"', "new": '"/events"'}],
        "reds": ["test_posts_name_and_value_as_json_to_v1_events", "test_a_trailing_slash_on_base_url_is_accepted"]},
    "wa-swallow": {
        "edits": [{"file": "prometheus_client/ledger.py",
                   "old": '                raise LedgerError(f"ledger request failed: {exc}") from exc\n',
                   "new": "                return None\n"}],
        "reds": ["test_a_400_reply_raises_ledger_error", "test_an_unreachable_service_raises_ledger_error"]},
    "wa-leak-urlerror": {
        "edits": [{"file": "prometheus_client/ledger.py",
                   "old": '                raise LedgerError(f"ledger request failed: {exc}") from exc\n',
                   "new": "                raise\n"}],
        "reds": ["test_a_400_reply_raises_ledger_error", "test_an_unreachable_service_raises_ledger_error"]},
    "wa-slash": {
        "edits": [{"file": "prometheus_client/ledger.py",
                   "old": 'base_url.rstrip("/") + "/v1/events"', "new": 'base_url + "/v1/events"'}],
        "reds": ["test_a_trailing_slash_on_base_url_is_accepted"]},
    "wa-import": {
        "edits": [{"file": "prometheus_client/ledger.py",
                   "old": "ATTEMPTS = 3\n",
                   "new": "ATTEMPTS = 3\ntry:\n    urllib.request.urlopen(\"http://127.0.0.1:9/\", timeout=0.2)\nexcept OSError:\n    pass\n"}],
        "reds": ["test_importing_the_module_has_no_side_effect"]},
}
