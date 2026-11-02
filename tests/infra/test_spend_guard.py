"""The hourly spend guard: switches the relay off past the monthly cap and back on next month."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import yaml

import spend_guard

NOW = dt.datetime(2026, 11, 20, 12, 0, tzinfo=dt.UTC)
ENV = {
    "API_ID": "abc123",
    "STAGE_NAME": "prod",
    "MONTHLY_MESSAGE_CAP": "1000",
    "NORMAL_RATE": "20",
    "NORMAL_BURST": "40",
    "RESERVED_CONCURRENCY": "0",
    "GUARDED_FUNCTIONS": "connect-fn,router-fn",
    "ALARM_TOPIC_ARN": "arn:aws:sns:us-east-2:1:topic",
}


class FakeCloudWatch:
    def __init__(self, messages: float, connects: float) -> None:
        self.values = {"MessageCount": messages, "ConnectCount": connects}
        self.calls: list[dict[str, Any]] = []

    def get_metric_statistics(self, **kw: Any) -> dict[str, Any]:
        self.calls.append(kw)
        v = self.values[kw["MetricName"]]
        return {"Datapoints": [{"Sum": v / 2}, {"Sum": v / 2}]}


class FakeApiGw:
    def __init__(self, rate: int = 20, burst: int = 40) -> None:
        self.settings = {"ThrottlingRateLimit": rate, "ThrottlingBurstLimit": burst}

    def get_stage(self, ApiId: str, StageName: str) -> dict[str, Any]:
        return {"DefaultRouteSettings": dict(self.settings)}

    def update_stage(
        self, ApiId: str, StageName: str, DefaultRouteSettings: dict[str, int]
    ) -> None:
        self.settings.update(DefaultRouteSettings)


class FakeLambda:
    def __init__(self) -> None:
        self.concurrency: dict[str, int | None] = {}

    def put_function_concurrency(
        self, FunctionName: str, ReservedConcurrentExecutions: int
    ) -> None:
        self.concurrency[FunctionName] = ReservedConcurrentExecutions

    def delete_function_concurrency(self, FunctionName: str) -> None:
        self.concurrency[FunctionName] = None


class FakeSns:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    def publish(self, **kw: Any) -> None:
        self.sent.append(kw)


def test_under_cap_does_nothing() -> None:
    api, lam, sns = FakeApiGw(), FakeLambda(), FakeSns()
    out = spend_guard.run(api, lam, FakeCloudWatch(400, 100), sns, ENV, NOW)
    assert out == {"used": 500, "cap": 1000, "was_off": False, "action": "none"}
    assert api.settings == {"ThrottlingRateLimit": 20, "ThrottlingBurstLimit": 40}
    assert lam.concurrency == {} and sns.sent == []


def test_counts_from_the_first_of_the_month() -> None:
    cw = FakeCloudWatch(1, 1)
    spend_guard.run(FakeApiGw(), FakeLambda(), cw, FakeSns(), ENV, NOW)
    assert {c["StartTime"] for c in cw.calls} == {dt.datetime(2026, 11, 1, tzinfo=dt.UTC)}
    assert {c["MetricName"] for c in cw.calls} == {"MessageCount", "ConnectCount"}


def test_over_cap_switches_off_and_emails() -> None:
    api, lam, sns = FakeApiGw(), FakeLambda(), FakeSns()
    out = spend_guard.run(api, lam, FakeCloudWatch(900, 100), sns, ENV, NOW)
    assert out["action"] == "switched_off"
    assert api.settings == {"ThrottlingRateLimit": 0, "ThrottlingBurstLimit": 0}
    assert lam.concurrency == {"connect-fn": 0, "router-fn": 0}
    assert len(sns.sent) == 1 and "cap" in sns.sent[0]["Subject"]


def test_already_off_is_not_emailed_again() -> None:
    api, sns = FakeApiGw(0, 0), FakeSns()
    out = spend_guard.run(api, FakeLambda(), FakeCloudWatch(5000, 0), sns, ENV, NOW)
    assert out["action"] == "none" and sns.sent == []


def test_new_month_switches_back_on() -> None:
    api, lam = FakeApiGw(0, 0), FakeLambda()
    lam.concurrency = {"connect-fn": 0, "router-fn": 0}
    out = spend_guard.run(api, lam, FakeCloudWatch(10, 2), FakeSns(), ENV, NOW)
    assert out["action"] == "switched_on"
    assert api.settings == {"ThrottlingRateLimit": 20, "ThrottlingBurstLimit": 40}
    assert lam.concurrency == {"connect-fn": None, "router-fn": None}


def test_switch_on_restores_router_reservation() -> None:
    api, lam = FakeApiGw(0, 0), FakeLambda()
    spend_guard.run(
        api, lam, FakeCloudWatch(0, 0), FakeSns(), {**ENV, "RESERVED_CONCURRENCY": "5"}, NOW
    )
    assert lam.concurrency == {"connect-fn": None, "router-fn": 5}


def test_no_topic_still_switches_off() -> None:
    api, sns = FakeApiGw(), FakeSns()
    out = spend_guard.run(
        api, FakeLambda(), FakeCloudWatch(2000, 0), sns, {**ENV, "ALARM_TOPIC_ARN": ""}, NOW
    )
    assert out["action"] == "switched_off" and sns.sent == []


class _CfnLoader(yaml.SafeLoader):
    pass


_CfnLoader.add_multi_constructor("!", lambda loader, suffix, node: None)


def test_template_wires_the_guard() -> None:
    tpl = yaml.load(
        (Path(__file__).parents[2] / "infra" / "template.yaml").read_text(encoding="utf-8"),
        _CfnLoader,
    )
    assert tpl["Parameters"]["MonthlyMessageCap"]["Default"] > 0
    fn = tpl["Resources"]["SpendGuardFunction"]["Properties"]
    assert fn["Handler"] == "spend_guard.handler"
    assert fn["Events"]["Hourly"]["Properties"]["Schedule"] == "rate(1 hour)"
    # the budget's notification list must stay as deployed: changing it makes CloudFormation replace the budget
    notes = tpl["Resources"]["CostBudget"]["Properties"]["NotificationsWithSubscribers"]
    assert [n["Notification"]["NotificationType"] for n in notes] == ["ACTUAL"]
