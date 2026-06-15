import pandas as pd
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from data_loader import REQUIRED_FIELDS


def filter_by_date(df: pd.DataFrame, start_date: Optional[datetime], end_date: Optional[datetime]) -> pd.DataFrame:
    if df.empty:
        return df

    if "record_date" not in df.columns:
        return df

    if df["record_date"].isna().all():
        return df

    df = df.copy()

    if start_date is not None:
        df = df[df["record_date"] >= pd.Timestamp(start_date)]

    if end_date is not None:
        df = df[df["record_date"] <= pd.Timestamp(end_date) + pd.Timedelta(days=1)]

    return df


def filter_by_item_name(df: pd.DataFrame, item_names: Optional[List[str]]) -> pd.DataFrame:
    if df.empty or not item_names or "item_name" not in df.columns:
        return df

    return df[df["item_name"].isin(item_names)].copy()


def filter_by_group(df: pd.DataFrame, groups: Optional[List[str]]) -> pd.DataFrame:
    if df.empty or not groups or "group_name" not in df.columns:
        return df

    return df[df["group_name"].isin(groups)].copy()


def filter_by_handler(df: pd.DataFrame, handlers: Optional[List[str]]) -> pd.DataFrame:
    if df.empty or not handlers or "handler_name" not in df.columns:
        return df

    return df[df["handler_name"].isin(handlers)].copy()


def filter_by_abnormal_status(df: pd.DataFrame, status: Optional[str]) -> pd.DataFrame:
    if df.empty or status is None or status == "全部":
        return df

    df = df.copy()
    df["total_out"] = df["returned_qty"] + df["lost_qty"]

    if status == "异常":
        mask = (df["issued_qty"] < df["total_out"]) & (df["issued_qty"] > 0)
    elif status == "正常":
        mask = (df["issued_qty"] >= df["total_out"]) | (df["issued_qty"] == 0)
    elif status == "有丢失":
        mask = df["lost_qty"] > 0
    elif status == "待回收":
        mask = (df["issued_qty"] > df["total_out"]) & (df["issued_qty"] > 0)
    else:
        return df

    return df[mask].copy()


def apply_all_filters(
    df: pd.DataFrame,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    item_names: Optional[List[str]] = None,
    groups: Optional[List[str]] = None,
    handlers: Optional[List[str]] = None,
    abnormal_status: Optional[str] = None,
) -> pd.DataFrame:
    if df.empty:
        return df

    result = df.copy()
    result = filter_by_date(result, start_date, end_date)
    result = filter_by_item_name(result, item_names)
    result = filter_by_group(result, groups)
    result = filter_by_handler(result, handlers)
    result = filter_by_abnormal_status(result, abnormal_status)

    return result


def calculate_issued_trend(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "record_date" not in df.columns or "issued_qty" not in df.columns:
        return pd.DataFrame()

    df = df.copy()
    df["date"] = df["record_date"].dt.date

    trend = (
        df.groupby("date")
        .agg(
            发放总量=("issued_qty", "sum"),
            回收总量=("returned_qty", "sum"),
            丢失总量=("lost_qty", "sum"),
            记录条数=("record_date", "count"),
        )
        .reset_index()
    )

    trend["净使用量"] = trend["发放总量"] - trend["回收总量"] - trend["丢失总量"]
    return trend.sort_values("date")


def calculate_return_diff_ranking(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "item_name" not in df.columns:
        return pd.DataFrame()

    df = df.copy()
    df["差异量"] = df["issued_qty"] - df["returned_qty"] - df["lost_qty"]
    df["回收率"] = df.apply(
        lambda x: x["returned_qty"] / x["issued_qty"] if x["issued_qty"] > 0 else 0,
        axis=1,
    )

    ranking = (
        df.groupby("item_name")
        .agg(
            发放总量=("issued_qty", "sum"),
            回收总量=("returned_qty", "sum"),
            丢失总量=("lost_qty", "sum"),
            差异总量=("差异量", "sum"),
            平均回收率=("回收率", "mean"),
        )
        .reset_index()
    )

    ranking["综合回收率"] = ranking.apply(
        lambda x: x["回收总量"] / x["发放总量"] if x["发放总量"] > 0 else 0,
        axis=1,
    )

    return ranking.sort_values("差异总量", ascending=False)


def calculate_group_workload(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "group_name" not in df.columns:
        return pd.DataFrame()

    workload = (
        df.groupby("group_name")
        .agg(
            处理记录数=("record_date", "count"),
            发放总量=("issued_qty", "sum"),
            回收总量=("returned_qty", "sum"),
            丢失总量=("lost_qty", "sum"),
            涉及物料种类=("item_name", "nunique"),
        )
        .reset_index()
    )

    workload["回收率"] = workload.apply(
        lambda x: x["回收总量"] / x["发放总量"] if x["发放总量"] > 0 else 0,
        axis=1,
    )

    workload["丢失率"] = workload.apply(
        lambda x: x["丢失总量"] / x["发放总量"] if x["发放总量"] > 0 else 0,
        axis=1,
    )

    return workload.sort_values("处理记录数", ascending=False)


def calculate_pending_records(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    df = df.copy()
    df["待回收量"] = df["issued_qty"] - df["returned_qty"] - df["lost_qty"]

    mask = (df["待回收量"] > 0) | (df["lost_qty"] > 0)
    pending = df[mask].copy()

    pending["状态"] = pending.apply(
        lambda x: "待回收" if x["待回收量"] > 0 and x["lost_qty"] == 0
        else ("已丢失" if x["lost_qty"] > 0 and x["待回收量"] <= 0
        else "待回收+已丢失"),
        axis=1,
    )

    return pending[REQUIRED_FIELDS + ["待回收量", "状态"]].sort_values(
        ["状态", "record_date"], ascending=[True, False]
    )


def calculate_summary_stats(df: pd.DataFrame) -> Dict[str, Any]:
    if df.empty:
        return {
            "total_records": 0,
            "total_issued": 0,
            "total_returned": 0,
            "total_lost": 0,
            "unique_items": 0,
            "unique_groups": 0,
            "unique_handlers": 0,
            "return_rate": 0,
            "lost_rate": 0,
        }

    total_issued = df["issued_qty"].sum()
    total_returned = df["returned_qty"].sum()
    total_lost = df["lost_qty"].sum()

    return {
        "total_records": len(df),
        "total_issued": total_issued,
        "total_returned": total_returned,
        "total_lost": total_lost,
        "unique_items": df["item_name"].nunique(),
        "unique_groups": df["group_name"].nunique(),
        "unique_handlers": df["handler_name"].nunique(),
        "return_rate": total_returned / total_issued if total_issued > 0 else 0,
        "lost_rate": total_lost / total_issued if total_issued > 0 else 0,
    }
