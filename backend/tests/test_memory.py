"""The assistant remembers between visits. The model is stubbed: these tests are about what gets saved and sent."""

import pytest

from app import assistant_memory as memory
from app.ai import tools
from tests.conftest import start_claim


@pytest.fixture()
def model(monkeypatch):
    """Records what the model was given and answers with a numbered reply."""
    calls = []

    def fake(messages, lang, ctx):
        calls.append({"messages": messages, "ctx": ctx})
        return f"answer {len(calls)}"

    monkeypatch.setattr(tools, "assistant", fake)
    return calls


def say(api, text, **scope):
    return api.post("/assistant/chat", json={"message": text, **scope})


def test_conversation_survives_closing_the_assistant(api, model):
    cid = start_claim(api)
    say(api, "Why is my room rent a problem?", claim_id=cid)
    t = api.get(f"/assistant/thread?claim_id={cid}").json()
    assert [m["role"] for m in t["messages"]] == ["user", "assistant"]
    assert t["messages"][0]["content"] == "Why is my room rent a problem?" and t["messages"][1]["content"] == "answer 1"
    assert t["messages"][0]["at"] and t["last_at"]


def _age_thread(cid, hours):
    """Pretend the last messages were sent some hours ago."""
    from datetime import datetime, timedelta

    from app import store
    t = memory.load(memory.thread_id(cid, None))
    for m in t["messages"]:
        m["at"] = (datetime.fromisoformat(m["at"]) - timedelta(hours=hours)).isoformat(timespec="seconds")
    store.put("thread", t)


def test_next_visit_gives_the_model_the_earlier_conversation(api, model):
    cid = start_claim(api)
    say(api, "first question", claim_id=cid)
    _age_thread(cid, 2)
    say(api, "Let us continue", claim_id=cid)
    sent = model[-1]
    assert [m["content"] for m in sent["messages"]] == ["first question", "answer 1", "Let us continue"]
    assert sent["ctx"]["previous_session_ended"]
    assert "at" not in sent["messages"][0]


def test_back_to_back_messages_are_not_a_new_visit(api, model):
    cid = start_claim(api)
    say(api, "first question", claim_id=cid)
    say(api, "and another", claim_id=cid)
    assert "previous_session_ended" not in model[-1]["ctx"]


def test_recap_says_what_happened_and_rules_say_what_is_next(api, model):
    cid = start_claim(api)
    say(api, "Is the room rent deduction fair?", claim_id=cid)
    t = api.get(f"/assistant/thread?claim_id={cid}").json()
    assert t["recap"] is None and t["recap_pending"] is True  # the thread itself never waits on the AI
    assert t["next_step"] == "Finish your documents and the claim form, then check your payout."
    assert "Is the room rent deduction fair?" in api.get(f"/assistant/thread/recap?claim_id={cid}").json()["recap"]
    t = api.get(f"/assistant/thread?claim_id={cid}").json()
    assert t["recap"] and t["recap_pending"] is False  # cached now


def test_next_step_follows_the_claim(api, model):
    cid = start_claim(api)
    api.post(f"/claims/{cid}/fill-mode", json={"mode": "ai"})
    api.post(f"/claims/{cid}/intimate")
    api.post(f"/claims/{cid}/submit")
    step = lambda: api.get(f"/assistant/thread?claim_id={cid}").json()["next_step"]  # noqa: E731
    assert "reviewing" in step()
    api.post(f"/claims/{cid}/advance")
    c = api.post(f"/claims/{cid}/advance").json()
    assert "query" in step()
    api.post(f"/claims/{cid}/tasks/{c['tasks'][0]['id']}", json={"note": "x"})
    api.post(f"/claims/{cid}/advance")
    assert "6,000" in step() and "review" in step()
    api.post(f"/claims/{cid}/appeal/send", json={"step": "insurer", "text": "x"})
    assert "appeal is with the insurer" in step()
    assert api.post(f"/claims/{cid}/advance").json()["decision"]["amount_approved"] == 68400
    assert "will pay" in step()
    assert api.post(f"/claims/{cid}/advance").json()["status"] == "settled"
    assert "settled" in step()


def test_a_fresh_thread_has_no_recap(api, model):
    t = api.get("/assistant/thread").json()
    assert t["messages"] == [] and t["recap"] is None


def test_claims_and_policies_keep_separate_threads(api, model):
    one = start_claim(api)
    two = start_claim(api)
    say(api, "about claim one", claim_id=one)
    say(api, "about the policy", policy_id="pol_shield")
    assert [m["content"] for m in api.get(f"/assistant/thread?claim_id={two}").json()["messages"]] == []
    assert len(api.get(f"/assistant/thread?claim_id={one}").json()["messages"]) == 2
    assert api.get("/assistant/thread?policy_id=pol_shield").json()["messages"][0]["content"] == "about the policy"


def test_a_failed_answer_saves_nothing(api):
    cid = start_claim(api)
    assert say(api, "hello", claim_id=cid).status_code == 502  # conftest runs with no Sarvam key
    assert api.get(f"/assistant/thread?claim_id={cid}").json()["messages"] == []


def test_attachment_goes_to_the_model_but_is_not_stored_as_the_message(api, model):
    cid = start_claim(api)
    api.post("/assistant/chat", json={"message": "What is this?", "attachment": "SMS: claim query", "claim_id": cid})
    assert "SMS: claim query" in model[-1]["messages"][-1]["content"]
    m = api.get(f"/assistant/thread?claim_id={cid}").json()["messages"][0]
    assert m["content"] == "What is this?" and m["image"] is True


def test_follow_up_questions_still_see_the_screenshot(api, model):
    cid = start_claim(api)
    api.post("/assistant/chat", json={"message": "What is this?", "attachment": "SMS: submit pharmacy bills by 7 Nov", "claim_id": cid})
    say(api, "By when do I need to do it?", claim_id=cid)
    assert "submit pharmacy bills by 7 Nov" in model[-1]["messages"][0]["content"]


def test_long_threads_are_summarised_not_dropped(api, model):
    cid = start_claim(api)
    for i in range(14):
        say(api, f"question {i}", claim_id=cid)
    last = model[-1]
    assert len(last["messages"]) == memory.MODEL_WINDOW + 1
    assert "question 0" in last["ctx"]["earlier_conversation_summary"] or "question" in last["ctx"]["earlier_conversation_summary"]
    assert len(api.get(f"/assistant/thread?claim_id={cid}").json()["messages"]) == 28


def test_recap_is_cached_until_the_conversation_moves(api, model, monkeypatch):
    cid = start_claim(api)
    say(api, "one", claim_id=cid)
    n = []
    monkeypatch.setattr(tools, "recap_conversation", lambda m, s, lang, next_step=None: n.append(1) or "recap")
    api.get(f"/assistant/thread?claim_id={cid}")
    assert len(n) == 0  # opening the chat never calls the AI
    api.get(f"/assistant/thread/recap?claim_id={cid}")
    api.get(f"/assistant/thread/recap?claim_id={cid}")
    assert len(n) == 1
    api.get(f"/assistant/thread/recap?claim_id={cid}&lang=hi-IN")
    assert len(n) == 2  # a new language needs a new recap


def test_clear_chat_delete_claim_and_delete_my_data_all_remove_it(api, model):
    cid = start_claim(api)
    say(api, "one", claim_id=cid)
    api.delete(f"/assistant/thread?claim_id={cid}")
    assert api.get(f"/assistant/thread?claim_id={cid}").json()["messages"] == []
    say(api, "two", claim_id=cid)
    api.delete(f"/claims/{cid}")
    assert api.get(f"/assistant/thread?claim_id={cid}").json()["messages"] == []
    say(api, "three")
    api.delete("/me/data")
    assert api.get("/assistant/thread").json()["messages"] == []


def test_older_clients_sending_full_history_are_still_saved(api, model):
    api.post("/assistant/chat", json={"messages": [{"role": "user", "content": "old style"}]})
    assert api.get("/assistant/thread").json()["messages"][0]["content"] == "old style"


def test_the_model_is_told_the_rule_based_next_step(api, model):
    cid = start_claim(api)
    say(api, "what now?", claim_id=cid)
    assert model[-1]["ctx"]["claim"]["next_step"] == "Finish your documents and the claim form, then check your payout."
