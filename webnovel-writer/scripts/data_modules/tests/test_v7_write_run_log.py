"""F4 回归：v7 写链的步骤落账由 CLI 自己完成。

背景：写链的崩溃粒度靠 ``run_last.log``（崩溃后靠最后一条判断卡在哪），前提是每个
步骤完成后有落账。**此前这一步完全依赖模型记得手调**
``run-log --event <step> --append``——那条要求只写在 SKILL.md 里、没有任何机器闸。
实测在快模型上必然漏：fantasy01-v2 的 ch40 日志只剩 ``write-start`` 一行，
doctor 因此长期报 ``run_log.step_coverage``。

修法：由执行该步骤的工具自己落账（``v7_write._log_write_step``）。
"""

from __future__ import annotations

import json

import pytest

import v7_write


def _decision_file(repo, chapter: int):
    path = repo / f"决策-{chapter:04d}.json"
    path.write_text(
        json.dumps({"chapter": chapter, "title": f"第{chapter}章", "pov": "苏小白", "entities": ["苏小白"]},
                   ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def _log_records(repo):
    log = repo / ".webnovel" / "logs" / "run_last.log"
    if not log.is_file():
        return []
    return [json.loads(ln) for ln in log.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _repo(tmp_path):
    (tmp_path / "工作区").mkdir(parents=True, exist_ok=True)
    return tmp_path


def test_decision_logs_step_without_model_action(tmp_path):
    """跑 decision 就该留痕——不需要任何人在外面调 run-log。"""
    repo = _repo(tmp_path)

    assert v7_write.main(["decision", "--repo", str(repo), "--json", str(_decision_file(repo, 7))]) == 0

    events = [rec["event"] for rec in _log_records(repo)]
    assert events == ["v7-decision"]
    assert _log_records(repo)[0]["payload"]["chapter"] == 7


def test_consecutive_steps_append_for_same_chapter(tmp_path):
    """同章连续步骤应追加，而不是互相覆盖。"""
    repo = _repo(tmp_path)
    decision = _decision_file(repo, 7)

    assert v7_write.main(["decision", "--repo", str(repo), "--json", str(decision)]) == 0
    assert v7_write.main(["pack", "--repo", str(repo), "--chapter", "7", "--json", str(decision)]) == 0

    events = [rec["event"] for rec in _log_records(repo)]
    assert events == ["v7-decision", "v7-pack"]


def test_new_chapter_starts_a_fresh_log(tmp_path):
    """换章应覆盖重开——否则漏调 write-start 时多章日志会混在一起。"""
    repo = _repo(tmp_path)

    assert v7_write.main(["decision", "--repo", str(repo), "--json", str(_decision_file(repo, 7))]) == 0
    assert v7_write.main(["decision", "--repo", str(repo), "--json", str(_decision_file(repo, 8))]) == 0

    records = _log_records(repo)
    assert [rec["event"] for rec in records] == ["v7-decision"]
    assert records[0]["payload"]["chapter"] == 8, "换章后旧章记录不应残留"


def test_logging_failure_does_not_break_the_chain(tmp_path, monkeypatch):
    """记账是旁路不是门禁：落账失败不得影响写链本身。"""
    repo = _repo(tmp_path)

    def _boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("data_modules.run_logger.write_run_log", _boom)

    assert v7_write.main(["decision", "--repo", str(repo), "--json", str(_decision_file(repo, 7))]) == 0
    assert (repo / "工作区" / "决策卡-0007.md").is_file()


def test_rejected_settle_is_recorded_as_rejected(tmp_path, monkeypatch):
    """门禁拒绝也要留痕——崩溃/拒绝的现场同样需要可定位。"""
    repo = _repo(tmp_path)
    decision = _decision_file(repo, 7)
    draft = repo / "工作区" / "草稿-0007.md"
    draft.write_text("正文", encoding="utf-8")

    def _reject(*args, **kwargs):
        raise v7_write.GateRejected("门禁拒绝", {"review": {"blocking_count": 1}})

    monkeypatch.setattr(v7_write, "settle", _reject)

    code = v7_write.main([
        "settle", "--repo", str(repo), "--chapter", "7",
        "--draft", str(draft), "--json", str(decision), "--summary", "摘要",
    ])

    assert code == 2
    records = _log_records(repo)
    assert records[-1]["event"] == "v7-settle"
    assert records[-1]["payload"]["status"] == "rejected"


def test_doctor_recognizes_v7_events_as_step_coverage(tmp_path):
    """doctor 必须认得 v7-* 事件，否则 v7 书仓会被误报"未追加步骤日志"。"""
    from data_modules.doctor import _run_log_checks

    repo = _repo(tmp_path)
    logs = repo / ".webnovel" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "run_last.log").write_text(
        "\n".join([
            json.dumps({"event": "write-start", "payload": {"chapter": 7}}, ensure_ascii=False),
            json.dumps({"event": "v7-decision", "payload": {"chapter": 7}}, ensure_ascii=False),
        ]) + "\n",
        encoding="utf-8",
    )

    checks = {c["id"]: c for c in _run_log_checks(repo)}
    assert checks["run_log.step_coverage"]["status"] == "ok"


def test_doctor_still_warns_when_only_write_start(tmp_path):
    """守住反向：真的只有 write-start 时仍要告警（别把闸门一起拆了）。"""
    from data_modules.doctor import _run_log_checks

    repo = _repo(tmp_path)
    logs = repo / ".webnovel" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "run_last.log").write_text(
        json.dumps({"event": "write-start", "payload": {"chapter": 7}}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    checks = {c["id"]: c for c in _run_log_checks(repo)}
    assert checks["run_log.step_coverage"]["status"] == "warning"


@pytest.mark.parametrize("action_event", ["v7-pack", "v7-check", "v7-settle"])
def test_every_v7_event_counts(tmp_path, action_event):
    """逐个确认四种 v7 事件都被 doctor 认作步骤落账。"""
    from data_modules.doctor import _STEP_LOG_EVENTS

    assert action_event in _STEP_LOG_EVENTS
