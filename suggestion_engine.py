import pandas as pd
from typing import List, Dict, Any
from datetime import datetime, timedelta


def get_recent_two_weeks_data(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "record_date" not in df.columns:
        return pd.DataFrame()

    df = df.copy()
    max_date = df["record_date"].max()

    if pd.isna(max_date):
        return pd.DataFrame()

    two_weeks_ago = max_date - timedelta(days=14)
    recent_df = df[df["record_date"] >= two_weeks_ago].copy()

    return recent_df


def calculate_replenishment_suggestions(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    recent_df = get_recent_two_weeks_data(df)
    if recent_df.empty:
        return pd.DataFrame()

    item_stats = (
        recent_df.groupby("item_name")
        .agg(
            近两周发放量=("issued_qty", "sum"),
            近两周回收量=("returned_qty", "sum"),
            近两周丢失量=("lost_qty", "sum"),
            发放次数=("record_date", "count"),
            最近发放日期=("record_date", "max"),
        )
        .reset_index()
    )

    item_stats["日均发放量"] = item_stats["近两周发放量"] / 14
    item_stats["净消耗量"] = item_stats["近两周发放量"] - item_stats["近两周回收量"]
    item_stats["丢失率"] = item_stats.apply(
        lambda x: x["近两周丢失量"] / x["近两周发放量"] if x["近两周发放量"] > 0 else 0,
        axis=1,
    )

    item_stats["建议补充数量"] = item_stats.apply(
        lambda x: calculate_suggested_qty(
            x["近两周发放量"],
            x["近两周丢失量"],
            x["近两周回收量"],
            x["发放次数"],
        ),
        axis=1,
    )

    item_stats["优先级"] = item_stats.apply(
        lambda x: calculate_priority(
            x["近两周发放量"],
            x["近两周丢失量"],
            x["净消耗量"],
            x["建议补充数量"],
        ),
        axis=1,
    )

    item_stats["补充理由"] = item_stats.apply(generate_reason, axis=1)

    result = item_stats[
        [
            "item_name",
            "近两周发放量",
            "近两周回收量",
            "近两周丢失量",
            "日均发放量",
            "丢失率",
            "发放次数",
            "最近发放日期",
            "建议补充数量",
            "优先级",
            "补充理由",
        ]
    ].copy()

    result = result[result["建议补充数量"] > 0]
    result = result.sort_values(["优先级", "建议补充数量"], ascending=[False, False])

    return result.reset_index(drop=True)


def calculate_suggested_qty(
    issued: float,
    lost: float,
    returned: float,
    issue_count: int,
) -> int:
    if issued <= 0:
        return 0

    daily_avg = issued / 14
    net_consumption = issued - returned
    lost_ratio = lost / issued if issued > 0 else 0

    safety_stock = daily_avg * 7
    expected_loss = daily_avg * 14 * lost_ratio

    suggested = safety_stock + expected_loss + (net_consumption * 0.3)

    if issue_count < 3:
        suggested = suggested * 0.7

    return max(0, int(suggested))


def calculate_priority(
    issued: float,
    lost: float,
    net_consumption: float,
    suggested_qty: int,
) -> int:
    score = 0

    if issued >= 50:
        score += 3
    elif issued >= 20:
        score += 2
    elif issued >= 5:
        score += 1

    lost_ratio = lost / issued if issued > 0 else 0
    if lost_ratio >= 0.3:
        score += 3
    elif lost_ratio >= 0.15:
        score += 2
    elif lost_ratio >= 0.05:
        score += 1

    if net_consumption >= 30:
        score += 3
    elif net_consumption >= 10:
        score += 2
    elif net_consumption >= 5:
        score += 1

    if suggested_qty >= 50:
        score += 2
    elif suggested_qty >= 20:
        score += 1

    return min(score, 10)


def generate_reason(row: pd.Series) -> str:
    reasons = []

    if row["近两周发放量"] >= 50:
        reasons.append("高频使用")
    elif row["近两周发放量"] >= 20:
        reasons.append("使用量较大")

    lost_ratio = row["丢失率"]
    if lost_ratio >= 0.3:
        reasons.append("丢失率极高")
    elif lost_ratio >= 0.15:
        reasons.append("丢失率较高")

    if row["净消耗量"] >= 20:
        reasons.append("净消耗量大")

    if row["建议补充数量"] >= 30:
        reasons.append("需大量补充")

    if not reasons:
        reasons.append("建议定期补充")

    return "、".join(reasons)


def get_suggestion_summary(suggestions: pd.DataFrame) -> Dict[str, Any]:
    if suggestions.empty:
        return {
            "total_items": 0,
            "high_priority": 0,
            "medium_priority": 0,
            "low_priority": 0,
            "total_suggested_qty": 0,
        }

    high = len(suggestions[suggestions["优先级"] >= 7])
    medium = len(suggestions[(suggestions["优先级"] >= 4) & (suggestions["优先级"] < 7)])
    low = len(suggestions[suggestions["优先级"] < 4])

    return {
        "total_items": len(suggestions),
        "high_priority": high,
        "medium_priority": medium,
        "low_priority": low,
        "total_suggested_qty": suggestions["建议补充数量"].sum(),
    }


def format_priority_label(priority: int) -> str:
    if priority >= 7:
        return "🔴 高"
    elif priority >= 4:
        return "🟡 中"
    else:
        return "🟢 低"
