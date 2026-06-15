import pandas as pd
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta


def init_inventory_params(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "item_name" not in df.columns:
        return pd.DataFrame(columns=["item_name", "initial_stock", "safety_stock"])

    unique_items = sorted(df["item_name"].dropna().unique().tolist())
    unique_items = [item for item in unique_items if item and item != "nan"]

    params = pd.DataFrame({
        "item_name": unique_items,
        "initial_stock": 0,
        "safety_stock": 0,
    })
    return params


def calculate_inventory_ledger(
    df: pd.DataFrame,
    inventory_params: pd.DataFrame,
) -> pd.DataFrame:
    if df.empty or "item_name" not in df.columns:
        return pd.DataFrame()

    if inventory_params is None or inventory_params.empty:
        inventory_params = init_inventory_params(df)

    item_stats = (
        df.groupby("item_name")
        .agg(
            总发放量=("issued_qty", "sum"),
            总回收量=("returned_qty", "sum"),
            总丢失量=("lost_qty", "sum"),
            发放次数=("record_date", "count"),
            最近活动日期=("record_date", "max"),
        )
        .reset_index()
    )

    item_stats["净消耗量"] = item_stats["总发放量"] - item_stats["总回收量"]
    item_stats["丢失率"] = item_stats.apply(
        lambda x: x["总丢失量"] / x["总发放量"] if x["总发放量"] > 0 else 0,
        axis=1,
    )

    merged = item_stats.merge(
        inventory_params[["item_name", "initial_stock", "safety_stock"]],
        on="item_name",
        how="left",
    )

    merged["initial_stock"] = merged["initial_stock"].fillna(0).astype(int)
    merged["safety_stock"] = merged["safety_stock"].fillna(0).astype(int)

    merged["当前可用库存"] = (
        merged["initial_stock"]
        - merged["总发放量"]
        + merged["总回收量"]
    )

    merged["库存状态"] = merged.apply(determine_stock_status, axis=1)

    merged["库存差额"] = merged["当前可用库存"] - merged["safety_stock"]

    merged["建议补充数量"] = merged.apply(calculate_suggested_replenishment, axis=1)

    merged["预警级别"] = merged.apply(determine_alert_level, axis=1)

    merged["异常标记"] = merged.apply(detect_abnormal_inventory, axis=1)

    result_columns = [
        "item_name",
        "initial_stock",
        "safety_stock",
        "总发放量",
        "总回收量",
        "总丢失量",
        "净消耗量",
        "丢失率",
        "当前可用库存",
        "库存差额",
        "库存状态",
        "预警级别",
        "建议补充数量",
        "异常标记",
        "发放次数",
        "最近活动日期",
    ]

    result = merged[result_columns].copy()
    result = result.sort_values(["预警级别", "建议补充数量"], ascending=[False, False])
    return result.reset_index(drop=True)


def determine_stock_status(row: pd.Series) -> str:
    current = row["当前可用库存"]
    safety = row["safety_stock"]

    if current < 0:
        return "负库存"
    elif current == 0:
        return "库存为零"
    elif current < safety:
        return "库存不足"
    elif current < safety * 1.5:
        return "库存偏低"
    else:
        return "库存充足"


def calculate_suggested_replenishment(row: pd.Series) -> int:
    current = row["当前可用库存"]
    safety = row["safety_stock"]
    issued = row["总发放量"]
    lost = row["总丢失量"]

    if issued <= 0:
        if current < safety:
            return max(0, int(safety - current))
        return 0

    lost_ratio = lost / issued if issued > 0 else 0

    days_range = 30
    daily_avg = issued / days_range if days_range > 0 else issued / 14
    safety_stock_target = max(safety, int(daily_avg * 7))

    base_suggestion = safety_stock_target - current

    if lost_ratio >= 0.2:
        base_suggestion += int(daily_avg * 14 * lost_ratio)

    if row.get("发放次数", 0) >= 10:
        base_suggestion += int(daily_avg * 3)

    return max(0, int(base_suggestion))


def determine_alert_level(row: pd.Series) -> int:
    score = 0
    current = row["当前可用库存"]
    safety = row["safety_stock"]
    issued = row["总发放量"]
    lost_ratio = row["丢失率"]

    if current < 0:
        score += 10
    elif current == 0:
        score += 8
    elif current < safety * 0.3:
        score += 7
    elif current < safety * 0.5:
        score += 5
    elif current < safety:
        score += 3
    elif current < safety * 1.5:
        score += 1

    if lost_ratio >= 0.3:
        score += 3
    elif lost_ratio >= 0.15:
        score += 2
    elif lost_ratio >= 0.05:
        score += 1

    if issued >= 200:
        score += 2
    elif issued >= 100:
        score += 1

    return min(score, 10)


def detect_abnormal_inventory(row: pd.Series) -> str:
    flags = []

    if row["当前可用库存"] < 0:
        flags.append("负库存异常")

    if row["总回收量"] > row["总发放量"] and row["总发放量"] > 0:
        flags.append("回收量超过发放量")

    if row["丢失率"] >= 0.3 and row["总发放量"] > 0:
        flags.append("丢失率过高(≥30%)")

    if row["总丢失量"] >= 50:
        flags.append("丢失数量较大")

    if row["总发放量"] > 0 and row["净消耗量"] < 0:
        flags.append("净消耗为负(回收异常)")

    return "、".join(flags) if flags else "正常"


def get_inventory_summary(ledger: pd.DataFrame) -> Dict[str, Any]:
    if ledger.empty:
        return {
            "total_items": 0,
            "stock_sufficient": 0,
            "stock_low": 0,
            "stock_insufficient": 0,
            "stock_zero": 0,
            "stock_negative": 0,
            "alert_high": 0,
            "alert_medium": 0,
            "alert_low": 0,
            "total_suggested_qty": 0,
            "total_current_stock": 0,
            "abnormal_count": 0,
        }

    stock_sufficient = len(ledger[ledger["库存状态"] == "库存充足"])
    stock_low = len(ledger[ledger["库存状态"] == "库存偏低"])
    stock_insufficient = len(ledger[ledger["库存状态"] == "库存不足"])
    stock_zero = len(ledger[ledger["库存状态"] == "库存为零"])
    stock_negative = len(ledger[ledger["库存状态"] == "负库存"])

    alert_high = len(ledger[ledger["预警级别"] >= 7])
    alert_medium = len(ledger[(ledger["预警级别"] >= 4) & (ledger["预警级别"] < 7)])
    alert_low = len(ledger[ledger["预警级别"] < 4])

    abnormal = ledger[ledger["异常标记"] != "正常"]

    return {
        "total_items": len(ledger),
        "stock_sufficient": stock_sufficient,
        "stock_low": stock_low,
        "stock_insufficient": stock_insufficient,
        "stock_zero": stock_zero,
        "stock_negative": stock_negative,
        "alert_high": alert_high,
        "alert_medium": alert_medium,
        "alert_low": alert_low,
        "total_suggested_qty": int(ledger["建议补充数量"].sum()),
        "total_current_stock": int(ledger["当前可用库存"].sum()),
        "abnormal_count": len(abnormal),
    }


def format_alert_label(level: int) -> str:
    if level >= 7:
        return "🔴 紧急"
    elif level >= 4:
        return "🟡 注意"
    else:
        return "🟢 正常"


def get_low_stock_alerts(ledger: pd.DataFrame) -> pd.DataFrame:
    if ledger.empty:
        return pd.DataFrame()

    low_stock = ledger[ledger["预警级别"] >= 4].copy()
    return low_stock.sort_values("预警级别", ascending=False).reset_index(drop=True)


def get_abnormal_inventory(ledger: pd.DataFrame) -> pd.DataFrame:
    if ledger.empty:
        return pd.DataFrame()

    abnormal = ledger[ledger["异常标记"] != "正常"].copy()
    return abnormal.reset_index(drop=True)


def filter_ledger(
    ledger: pd.DataFrame,
    stock_status: Optional[str] = None,
    alert_level: Optional[str] = None,
    has_abnormal: Optional[bool] = None,
    item_names: Optional[List[str]] = None,
) -> pd.DataFrame:
    if ledger.empty:
        return ledger

    result = ledger.copy()

    if item_names:
        result = result[result["item_name"].isin(item_names)]

    if stock_status and stock_status != "全部":
        result = result[result["库存状态"] == stock_status]

    if alert_level:
        if alert_level == "紧急(≥7)":
            result = result[result["预警级别"] >= 7]
        elif alert_level == "注意(4-6)":
            result = result[(result["预警级别"] >= 4) & (result["预警级别"] < 7)]
        elif alert_level == "正常(<4)":
            result = result[result["预警级别"] < 4]

    if has_abnormal is True:
        result = result[result["异常标记"] != "正常"]
    elif has_abnormal is False:
        result = result[result["异常标记"] == "正常"]

    return result.reset_index(drop=True)
