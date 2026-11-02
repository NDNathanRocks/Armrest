"""Hard monthly cost cap for the relay (AWS has no built-in spending cap; budgets only email).

Runs hourly. It sums this calendar month's API Gateway messages and connects. Past
MONTHLY_MESSAGE_CAP it switches the relay off: stage throttle 0 and reserved concurrency 0 on the
connect and router functions, so nothing more is billed (open sockets accrue only
connection-minutes, a fraction of a cent). The owner is emailed. When a new month starts the count
is back under the cap and the next run switches the relay on again.

Phones keep working on the home Wi-Fi (LAN mode) while the relay is off. A `sam deploy` also
resets the throttle, so redeploying is the manual "switch it back on now".
"""

from __future__ import annotations

import datetime as dt
import logging
import os
from collections.abc import Mapping
from typing import Any

log = logging.getLogger()
log.setLevel(logging.INFO)


def _int(env: Mapping[str, str], name: str, default: int = 0) -> int:
    try:
        return int(env.get(name, default))
    except ValueError:
        return default


def month_start(now: dt.datetime) -> dt.datetime:
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def month_usage(cloudwatch: Any, api_id: str, now: dt.datetime) -> int:
    """Messages + connects since the 1st of this month (UTC)."""
    total = 0.0
    for metric in ("MessageCount", "ConnectCount"):
        resp = cloudwatch.get_metric_statistics(
            Namespace="AWS/ApiGateway",
            MetricName=metric,
            Dimensions=[{"Name": "ApiId", "Value": api_id}],
            StartTime=month_start(now),
            EndTime=now,
            Period=86400,
            Statistics=["Sum"],
        )
        total += sum(p["Sum"] for p in resp.get("Datapoints", []))
    return int(total)


def is_switched_off(apigw: Any, api_id: str, stage: str) -> bool:
    settings = apigw.get_stage(ApiId=api_id, StageName=stage).get("DefaultRouteSettings", {})
    return bool(
        settings.get("ThrottlingRateLimit") == 0 and settings.get("ThrottlingBurstLimit") == 0
    )


def switch_off(apigw: Any, lam: Any, api_id: str, stage: str, functions: list[str]) -> None:
    apigw.update_stage(
        ApiId=api_id,
        StageName=stage,
        DefaultRouteSettings={"ThrottlingRateLimit": 0, "ThrottlingBurstLimit": 0},
    )
    for name in functions:
        lam.put_function_concurrency(FunctionName=name, ReservedConcurrentExecutions=0)


def switch_on(
    apigw: Any,
    lam: Any,
    api_id: str,
    stage: str,
    functions: list[str],
    rate: int,
    burst: int,
    reserved: int,
) -> None:
    for name in functions:
        lam.delete_function_concurrency(FunctionName=name)
    if reserved > 0 and functions:
        # the router (last in the list) carries the optional ReservedConcurrency stack parameter
        lam.put_function_concurrency(
            FunctionName=functions[-1], ReservedConcurrentExecutions=reserved
        )
    apigw.update_stage(
        ApiId=api_id,
        StageName=stage,
        DefaultRouteSettings={"ThrottlingRateLimit": rate, "ThrottlingBurstLimit": burst},
    )


def run(
    apigw: Any, lam: Any, cloudwatch: Any, sns: Any, env: Mapping[str, str], now: dt.datetime
) -> dict[str, Any]:
    api_id, stage = env["API_ID"], env["STAGE_NAME"]
    cap = int(env["MONTHLY_MESSAGE_CAP"])
    functions = [f for f in env.get("GUARDED_FUNCTIONS", "").split(",") if f]
    topic = env.get("ALARM_TOPIC_ARN", "")
    used = month_usage(cloudwatch, api_id, now)
    off = is_switched_off(apigw, api_id, stage)
    action = "none"
    if used >= cap and not off:
        switch_off(apigw, lam, api_id, stage, functions)
        action = "switched_off"
        if topic:
            sns.publish(
                TopicArn=topic,
                Subject="Armrest relay switched off: monthly cap reached",
                Message=(
                    f"The relay handled {used:,} messages this month, past the cap of {cap:,}. "
                    "It is off until the 1st of next month (UTC) so it cannot cost more. "
                    "Phones still work on the home Wi-Fi. "
                    "Run `sam deploy` in infra/ to switch it back on sooner."
                ),
            )
    elif used < cap and off:
        switch_on(
            apigw,
            lam,
            api_id,
            stage,
            functions,
            int(env["NORMAL_RATE"]),
            int(env["NORMAL_BURST"]),
            _int(env, "RESERVED_CONCURRENCY"),
        )
        action = "switched_on"
    result = {"used": used, "cap": cap, "was_off": off, "action": action}
    log.info("spend_guard %s", result)
    return result


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    import boto3

    return run(
        boto3.client("apigatewayv2"),
        boto3.client("lambda"),
        boto3.client("cloudwatch"),
        boto3.client("sns"),
        dict(os.environ),
        dt.datetime.now(dt.UTC),
    )
