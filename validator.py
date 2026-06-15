import pandas as pd
from typing import Dict, List, Any
from data_loader import REQUIRED_FIELDS


def check_missing_columns(raw_df: pd.DataFrame, mapping: Dict[str, Any]) -> List[str]:
    missing = []
    for standard_field, raw_col in mapping.items():
        if raw_col is None or raw_col not in raw_df.columns:
            missing.append(standard_field)
    return missing


def check_duplicate_records(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    key_cols = ["record_date", "item_name", "group_name", "handler_name"]
    available_keys = [col for col in key_cols if col in df.columns]

    if not available_keys:
        return pd.DataFrame()

    duplicates_mask = df.duplicated(subset=available_keys, keep=False)
    return df[duplicates_mask].copy()


def check_abnormal_quantity(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    required = ["issued_qty", "returned_qty", "lost_qty"]
    for col in required:
        if col not in df.columns:
            return pd.DataFrame()

    df = df.copy()
    df["total_out"] = df["returned_qty"] + df["lost_qty"]
    mask = (df["issued_qty"] < df["total_out"]) & (df["issued_qty"] > 0)

    abnormal = df[mask].copy()
    abnormal["差异数量"] = abnormal["total_out"] - abnormal["issued_qty"]

    return abnormal[REQUIRED_FIELDS + ["差异数量"]]


def check_negative_quantity(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    numeric_cols = ["issued_qty", "returned_qty", "lost_qty"]
    mask = pd.Series(False, index=df.index)

    for col in numeric_cols:
        if col in df.columns:
            mask = mask | (df[col] < 0)

    return df[mask].copy()


def check_invalid_dates(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "record_date" not in df.columns:
        return pd.DataFrame()

    mask = df["record_date"].isna()
    return df[mask].copy()


def check_empty_key_fields(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    key_cols = ["item_name", "group_name"]
    mask = pd.Series(False, index=df.index)

    for col in key_cols:
        if col in df.columns:
            mask = mask | (df[col].astype(str).str.strip() == "")

    return df[mask].copy()


def validate_all(df: pd.DataFrame, raw_df: pd.DataFrame, mapping: Dict[str, Any]) -> Dict[str, Any]:
    results = {
        "missing_columns": check_missing_columns(raw_df, mapping),
        "duplicate_records": check_duplicate_records(df),
        "abnormal_quantity": check_abnormal_quantity(df),
        "negative_quantity": check_negative_quantity(df),
        "invalid_dates": check_invalid_dates(df),
        "empty_keys": check_empty_key_fields(df),
    }

    summary = []
    if results["missing_columns"]:
        summary.append(f"缺失字段: {', '.join(results['missing_columns'])}")

    if not results["duplicate_records"].empty:
        summary.append(f"重复记录: {len(results['duplicate_records'])} 条")

    if not results["abnormal_quantity"].empty:
        summary.append(f"数量异常: {len(results['abnormal_quantity'])} 条")

    if not results["negative_quantity"].empty:
        summary.append(f"负数数量: {len(results['negative_quantity'])} 条")

    if not results["invalid_dates"].empty:
        summary.append(f"无效日期: {len(results['invalid_dates'])} 条")

    if not results["empty_keys"].empty:
        summary.append(f"关键字段为空: {len(results['empty_keys'])} 条")

    results["summary"] = summary
    results["has_errors"] = len(summary) > 0

    return results


FIELD_NAMES_CN = {
    "record_date": "记录日期",
    "item_name": "物料名称",
    "group_name": "小组名称",
    "issued_qty": "发放数量",
    "returned_qty": "回收数量",
    "lost_qty": "丢失数量",
    "handler_name": "处理人",
    "note": "备注",
}
