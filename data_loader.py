import pandas as pd
import io
from typing import Optional, Dict, List


REQUIRED_FIELDS = [
    "record_date",
    "item_name",
    "group_name",
    "issued_qty",
    "returned_qty",
    "lost_qty",
    "handler_name",
    "note",
]

FIELD_CANDIDATES = {
    "record_date": ["日期", "记录日期", "date", "record_date", "发生日期"],
    "item_name": ["物料名称", "物料名", "物品名称", "item", "item_name", "物资名称"],
    "group_name": ["小组", "班组", "组别", "group", "group_name", "部门"],
    "issued_qty": ["发放数量", "发放量", "发出数量", "issued", "issued_qty", "出库数量"],
    "returned_qty": ["回收数量", "回收量", "归还数量", "returned", "returned_qty", "入库数量"],
    "lost_qty": ["丢失数量", "丢失量", "遗失数量", "lost", "lost_qty", "损耗数量"],
    "handler_name": ["处理人", "经办人", "负责人", "handler", "handler_name", "管理员"],
    "note": ["备注", "说明", "note", "remark", "描述"],
}


def read_csv_from_upload(uploaded_file) -> Optional[pd.DataFrame]:
    if uploaded_file is None:
        return None
    try:
        df = pd.read_csv(uploaded_file)
        return df
    except Exception as e:
        raise ValueError(f"CSV 文件读取失败: {str(e)}")


def detect_column_mapping(raw_df: pd.DataFrame) -> Dict[str, Optional[str]]:
    mapping = {}
    raw_columns = [str(col).strip() for col in raw_df.columns]

    for standard_field, candidates in FIELD_CANDIDATES.items():
        matched = None
        for candidate in candidates:
            for raw_col in raw_columns:
                if candidate.lower() == raw_col.lower():
                    matched = raw_col
                    break
            if matched:
                break
        mapping[standard_field] = matched

    return mapping


def apply_column_mapping(raw_df: pd.DataFrame, mapping: Dict[str, Optional[str]]) -> pd.DataFrame:
    rename_dict = {}
    for standard_field, raw_col in mapping.items():
        if raw_col and raw_col in raw_df.columns:
            rename_dict[raw_col] = standard_field

    df = raw_df.rename(columns=rename_dict)

    for field in REQUIRED_FIELDS:
        if field not in df.columns:
            df[field] = None

    return df[REQUIRED_FIELDS].copy()


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if "record_date" in df.columns:
        df["record_date"] = pd.to_datetime(df["record_date"], errors="coerce")

    numeric_cols = ["issued_qty", "returned_qty", "lost_qty"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    text_cols = ["item_name", "group_name", "handler_name", "note"]
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).fillna("").str.strip()
            df.loc[df[col] == "nan", col] = ""

    return df


def detect_non_numeric(raw_df: pd.DataFrame, mapping: Dict[str, Optional[str]]) -> pd.DataFrame:
    numeric_standard = ["issued_qty", "returned_qty", "lost_qty"]
    numeric_raw = []
    for std in numeric_standard:
        raw_col = mapping.get(std)
        if raw_col and raw_col in raw_df.columns:
            numeric_raw.append((std, raw_col))

    if not numeric_raw:
        return pd.DataFrame()

    bad_rows = pd.DataFrame()
    for std, raw_col in numeric_raw:
        series = raw_df[raw_col]
        coerced = pd.to_numeric(series, errors="coerce")
        mask = series.notna() & coerced.isna()
        if mask.any():
            subset = raw_df.loc[mask].copy()
            subset["异常字段"] = raw_col
            subset["原始值"] = series[mask].astype(str)
            bad_rows = pd.concat([bad_rows, subset], ignore_index=True)

    return bad_rows


def get_unique_values(df: pd.DataFrame, column: str) -> List[str]:
    if column not in df.columns:
        return []
    values = df[column].dropna().astype(str).unique().tolist()
    values = [v for v in values if v and v != "nan"]
    return sorted(values)
