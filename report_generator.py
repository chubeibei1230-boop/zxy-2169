import pandas as pd
from datetime import datetime
from typing import Dict, Any
import io


def generate_summary_report(
    original_df: pd.DataFrame,
    filtered_df: pd.DataFrame,
    summary_stats: Dict[str, Any],
    trend_df: pd.DataFrame,
    ranking_df: pd.DataFrame,
    workload_df: pd.DataFrame,
    pending_df: pd.DataFrame,
    suggestions_df: pd.DataFrame,
    filters: Dict[str, Any],
    inventory_ledger: pd.DataFrame = None,
    low_stock_alerts: pd.DataFrame = None,
    abnormal_inventory: pd.DataFrame = None,
) -> bytes:
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        _write_cover_sheet(writer, original_df, filtered_df, summary_stats, filters)
        _write_summary_sheet(writer, filtered_df, summary_stats)
        _write_trend_sheet(writer, trend_df)
        _write_ranking_sheet(writer, ranking_df)
        _write_workload_sheet(writer, workload_df)
        _write_pending_sheet(writer, pending_df)
        _write_suggestions_sheet(writer, suggestions_df)
        _write_inventory_ledger_sheet(writer, inventory_ledger)
        _write_inventory_alerts_sheet(writer, low_stock_alerts, abnormal_inventory)
        _write_filtered_data_sheet(writer, filtered_df)

    output.seek(0)
    return output.getvalue()


def _write_cover_sheet(writer, original_df, filtered_df, summary_stats, filters):
    data = []
    data.append(["志愿服务物料流转分析报告"])
    data.append([])
    data.append(["生成时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    data.append([])
    data.append(["数据概览"])
    data.append(["原始数据记录数", len(original_df)])
    data.append(["筛选后记录数", len(filtered_df)])
    data.append(["筛选后占比", f"{len(filtered_df)/len(original_df)*100:.1f}%" if len(original_df) > 0 else "0%"])
    data.append([])
    data.append(["筛选条件"])
    data.append(["日期范围", f"{filters.get('start_date', '未设置')} 至 {filters.get('end_date', '未设置')}"])
    data.append(["物料名称", ", ".join(filters.get("item_names", [])) or "全部"])
    data.append(["小组", ", ".join(filters.get("groups", [])) or "全部"])
    data.append(["处理人", ", ".join(filters.get("handlers", [])) or "全部"])
    data.append(["异常状态", filters.get("abnormal_status", "全部")])
    data.append([])
    data.append(["核心指标"])
    data.append(["总发放量", summary_stats.get("total_issued", 0)])
    data.append(["总回收量", summary_stats.get("total_returned", 0)])
    data.append(["总丢失量", summary_stats.get("total_lost", 0)])
    data.append(["回收率", f"{summary_stats.get('return_rate', 0)*100:.1f}%"])
    data.append(["丢失率", f"{summary_stats.get('lost_rate', 0)*100:.1f}%"])
    data.append(["涉及物料种类", summary_stats.get("unique_items", 0)])
    data.append(["涉及小组数", summary_stats.get("unique_groups", 0)])
    data.append(["涉及处理人数", summary_stats.get("unique_handlers", 0)])

    df = pd.DataFrame(data)
    df.to_excel(writer, sheet_name="报告封面", index=False, header=False)

    worksheet = writer.sheets["报告封面"]
    for column in worksheet.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        worksheet.column_dimensions[column_letter].width = adjusted_width


def _write_summary_sheet(writer, filtered_df, summary_stats):
    data = []
    data.append(["指标名称", "数值", "说明"])
    data.append(["记录总数", summary_stats.get("total_records", 0), "筛选范围内的记录条数"])
    data.append(["总发放量", summary_stats.get("total_issued", 0), "所有物料发放数量总和"])
    data.append(["总回收量", summary_stats.get("total_returned", 0), "所有物料回收数量总和"])
    data.append(["总丢失量", summary_stats.get("total_lost", 0), "所有物料丢失数量总和"])
    data.append(["净使用量", summary_stats.get("total_issued", 0) - summary_stats.get("total_returned", 0) - summary_stats.get("total_lost", 0), "发放-回收-丢失"])
    data.append(["回收率", f"{summary_stats.get('return_rate', 0)*100:.1f}%", "回收量/发放量"])
    data.append(["丢失率", f"{summary_stats.get('lost_rate', 0)*100:.1f}%", "丢失量/发放量"])
    data.append(["物料种类数", summary_stats.get("unique_items", 0), "涉及的不同物料数量"])
    data.append(["小组数", summary_stats.get("unique_groups", 0), "涉及的不同小组数量"])
    data.append(["处理人数", summary_stats.get("unique_handlers", 0), "涉及的不同处理人数量"])

    df = pd.DataFrame(data[1:], columns=data[0])
    df.to_excel(writer, sheet_name="核心指标", index=False)

    worksheet = writer.sheets["核心指标"]
    for column in worksheet.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 30)
        worksheet.column_dimensions[column_letter].width = adjusted_width


def _write_trend_sheet(writer, trend_df):
    if trend_df.empty:
        df = pd.DataFrame([["暂无数据"]])
        df.to_excel(writer, sheet_name="发放量趋势", index=False, header=False)
        return

    trend_df = trend_df.copy()
    trend_df["date"] = pd.to_datetime(trend_df["date"]).dt.strftime("%Y-%m-%d")
    trend_df.to_excel(writer, sheet_name="发放量趋势", index=False)

    worksheet = writer.sheets["发放量趋势"]
    for column in worksheet.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 15)
        worksheet.column_dimensions[column_letter].width = adjusted_width


def _write_ranking_sheet(writer, ranking_df):
    if ranking_df.empty:
        df = pd.DataFrame([["暂无数据"]])
        df.to_excel(writer, sheet_name="回收差异排行", index=False, header=False)
        return

    ranking_df = ranking_df.copy()
    ranking_df["综合回收率"] = ranking_df["综合回收率"].apply(lambda x: f"{x*100:.1f}%")
    ranking_df["平均回收率"] = ranking_df["平均回收率"].apply(lambda x: f"{x*100:.1f}%")
    ranking_df.to_excel(writer, sheet_name="回收差异排行", index=False)

    worksheet = writer.sheets["回收差异排行"]
    for column in worksheet.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 15)
        worksheet.column_dimensions[column_letter].width = adjusted_width


def _write_workload_sheet(writer, workload_df):
    if workload_df.empty:
        df = pd.DataFrame([["暂无数据"]])
        df.to_excel(writer, sheet_name="小组负载", index=False, header=False)
        return

    workload_df = workload_df.copy()
    workload_df["回收率"] = workload_df["回收率"].apply(lambda x: f"{x*100:.1f}%")
    workload_df["丢失率"] = workload_df["丢失率"].apply(lambda x: f"{x*100:.1f}%")
    workload_df.to_excel(writer, sheet_name="小组负载", index=False)

    worksheet = writer.sheets["小组负载"]
    for column in worksheet.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 15)
        worksheet.column_dimensions[column_letter].width = adjusted_width


def _write_pending_sheet(writer, pending_df):
    if pending_df.empty:
        df = pd.DataFrame([["暂无待跟进记录"]])
        df.to_excel(writer, sheet_name="待跟进记录", index=False, header=False)
        return

    pending_df = pending_df.copy()
    if "record_date" in pending_df.columns:
        pending_df["record_date"] = pd.to_datetime(pending_df["record_date"]).dt.strftime("%Y-%m-%d")
    pending_df.to_excel(writer, sheet_name="待跟进记录", index=False)

    worksheet = writer.sheets["待跟进记录"]
    for column in worksheet.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 20)
        worksheet.column_dimensions[column_letter].width = adjusted_width


def _write_suggestions_sheet(writer, suggestions_df):
    if suggestions_df.empty:
        df = pd.DataFrame([["暂无补充建议"]])
        df.to_excel(writer, sheet_name="补充建议", index=False, header=False)
        return

    suggestions_df = suggestions_df.copy()
    suggestions_df["丢失率"] = suggestions_df["丢失率"].apply(lambda x: f"{x*100:.1f}%")
    if "最近发放日期" in suggestions_df.columns:
        suggestions_df["最近发放日期"] = pd.to_datetime(suggestions_df["最近发放日期"]).dt.strftime("%Y-%m-%d")
    suggestions_df.to_excel(writer, sheet_name="补充建议", index=False)

    worksheet = writer.sheets["补充建议"]
    for column in worksheet.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 20)
        worksheet.column_dimensions[column_letter].width = adjusted_width


def _write_inventory_ledger_sheet(writer, inventory_ledger):
    if inventory_ledger is None or inventory_ledger.empty:
        df = pd.DataFrame([["暂无库存台账数据"]])
        df.to_excel(writer, sheet_name="库存台账", index=False, header=False)
        return

    ledger_df = inventory_ledger.copy()

    if "丢失率" in ledger_df.columns:
        ledger_df["丢失率"] = ledger_df["丢失率"].apply(lambda x: f"{x*100:.1f}%")
    if "最近活动日期" in ledger_df.columns:
        ledger_df["最近活动日期"] = pd.to_datetime(ledger_df["最近活动日期"]).dt.strftime("%Y-%m-%d")

    column_mapping = {
        "item_name": "物料名称",
        "initial_stock": "期初库存",
        "safety_stock": "安全库存",
        "总发放量": "累计发放",
        "总回收量": "累计回收",
        "总丢失量": "累计丢失",
        "净消耗量": "净消耗",
        "丢失率": "丢失率",
        "当前可用库存": "当前库存",
        "库存差额": "库存差额",
        "库存状态": "库存状态",
        "预警级别": "预警级别",
        "建议补充数量": "建议补充数量",
        "异常标记": "异常标记",
        "发放次数": "发放次数",
        "最近活动日期": "最近活动日期",
    }
    ledger_df = ledger_df.rename(columns=column_mapping)

    ledger_df.to_excel(writer, sheet_name="库存台账", index=False)

    worksheet = writer.sheets["库存台账"]
    for column in worksheet.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 20)
        worksheet.column_dimensions[column_letter].width = adjusted_width


def _write_inventory_alerts_sheet(writer, low_stock_alerts, abnormal_inventory):
    if (low_stock_alerts is None or low_stock_alerts.empty) and (abnormal_inventory is None or abnormal_inventory.empty):
        df = pd.DataFrame([["暂无库存预警数据"]])
        df.to_excel(writer, sheet_name="预警清单", index=False, header=False)
        return

    if low_stock_alerts is not None and not low_stock_alerts.empty:
        low_df = low_stock_alerts.copy()
        if "丢失率" in low_df.columns:
            low_df["丢失率"] = low_df["丢失率"].apply(lambda x: f"{x*100:.1f}%")
        if "最近活动日期" in low_df.columns:
            low_df["最近活动日期"] = pd.to_datetime(low_df["最近活动日期"]).dt.strftime("%Y-%m-%d")
        low_df["预警类型"] = "低库存预警"
    else:
        low_df = pd.DataFrame()

    if abnormal_inventory is not None and not abnormal_inventory.empty:
        abn_df = abnormal_inventory.copy()
        if "丢失率" in abn_df.columns:
            abn_df["丢失率"] = abn_df["丢失率"].apply(lambda x: f"{x*100:.1f}%")
        if "最近活动日期" in abn_df.columns:
            abn_df["最近活动日期"] = pd.to_datetime(abn_df["最近活动日期"]).dt.strftime("%Y-%m-%d")
        abn_df["预警类型"] = "异常库存预警"
    else:
        abn_df = pd.DataFrame()

    combined = pd.concat([low_df, abn_df], ignore_index=True)

    if combined.empty:
        df = pd.DataFrame([["暂无库存预警数据"]])
        df.to_excel(writer, sheet_name="预警清单", index=False, header=False)
        return

    column_mapping = {
        "预警类型": "预警类型",
        "item_name": "物料名称",
        "initial_stock": "期初库存",
        "safety_stock": "安全库存",
        "当前可用库存": "当前库存",
        "库存状态": "库存状态",
        "预警级别": "预警级别",
        "异常标记": "异常说明",
        "总发放量": "累计发放",
        "总回收量": "累计回收",
        "总丢失量": "累计丢失",
        "丢失率": "丢失率",
        "建议补充数量": "建议补充数量",
        "最近活动日期": "最近活动日期",
    }

    available_cols = [col for col in column_mapping.keys() if col in combined.columns]
    combined = combined[available_cols].copy()
    combined = combined.rename(columns=column_mapping)

    combined.to_excel(writer, sheet_name="预警清单", index=False)

    worksheet = writer.sheets["预警清单"]
    for column in worksheet.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 20)
        worksheet.column_dimensions[column_letter].width = adjusted_width


def _write_filtered_data_sheet(writer, filtered_df):
    if filtered_df.empty:
        df = pd.DataFrame([["暂无数据"]])
        df.to_excel(writer, sheet_name="筛选后明细", index=False, header=False)
        return

    data_df = filtered_df.copy()
    if "record_date" in data_df.columns:
        data_df["record_date"] = pd.to_datetime(data_df["record_date"]).dt.strftime("%Y-%m-%d")

    column_mapping = {
        "record_date": "记录日期",
        "item_name": "物料名称",
        "group_name": "小组名称",
        "issued_qty": "发放数量",
        "returned_qty": "回收数量",
        "lost_qty": "丢失数量",
        "handler_name": "处理人",
        "note": "备注",
    }
    data_df = data_df.rename(columns=column_mapping)

    data_df.to_excel(writer, sheet_name="筛选后明细", index=False)

    worksheet = writer.sheets["筛选后明细"]
    for column in worksheet.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 20)
        worksheet.column_dimensions[column_letter].width = adjusted_width


def get_report_filename() -> str:
    now = datetime.now()
    return f"志愿服务物料流转分析报告_{now.strftime('%Y%m%d_%H%M%S')}.xlsx"
