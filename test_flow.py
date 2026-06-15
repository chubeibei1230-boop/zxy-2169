import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_loader import (
    read_csv_from_upload,
    detect_column_mapping,
    apply_column_mapping,
    normalize_dataframe,
)
from validator import validate_all, check_abnormal_quantity, check_duplicate_records
from filter_engine import (
    apply_all_filters,
    calculate_issued_trend,
    calculate_return_diff_ranking,
    calculate_group_workload,
    calculate_pending_records,
    calculate_summary_stats,
)
from suggestion_engine import calculate_replenishment_suggestions, get_suggestion_summary
from report_generator import generate_summary_report

print("=" * 60)
print("测试数据处理流程")
print("=" * 60)

with open("sample_data.csv", "rb") as f:
    raw_df = read_csv_from_upload(f)

print(f"\n1. 读取原始数据: {len(raw_df)} 条")
print(f"   原始列名: {list(raw_df.columns)}")

mapping = detect_column_mapping(raw_df)
print(f"\n2. 检测字段映射:")
for k, v in mapping.items():
    print(f"   {k} -> {v}")

mapped_df = apply_column_mapping(raw_df, mapping)
normalized_df = normalize_dataframe(mapped_df)
print(f"\n3. 数据标准化完成: {len(normalized_df)} 条")

validation = validate_all(normalized_df, raw_df, mapping)
print(f"\n4. 数据校验结果:")
if validation["summary"]:
    for msg in validation["summary"]:
        print(f"   ⚠️  {msg}")
else:
    print("   ✅ 未发现数据质量问题")

abnormal = check_abnormal_quantity(normalized_df)
print(f"\n5. 数量异常记录: {len(abnormal)} 条")

duplicates = check_duplicate_records(normalized_df)
print(f"6. 重复记录: {len(duplicates)} 条")

filtered_df = apply_all_filters(normalized_df, abnormal_status="全部")
print(f"\n7. 筛选后数据: {len(filtered_df)} 条")

stats = calculate_summary_stats(filtered_df)
print(f"\n8. 核心指标:")
print(f"   总发放量: {stats['total_issued']}")
print(f"   总回收量: {stats['total_returned']}")
print(f"   总丢失量: {stats['total_lost']}")
print(f"   回收率: {stats['return_rate']*100:.1f}%")
print(f"   丢失率: {stats['lost_rate']*100:.1f}%")

trend = calculate_issued_trend(filtered_df)
print(f"\n9. 趋势数据: {len(trend)} 天")

ranking = calculate_return_diff_ranking(filtered_df)
print(f"10. 回收差异排行: {len(ranking)} 种物料")

workload = calculate_group_workload(filtered_df)
print(f"11. 小组负载: {len(workload)} 个小组")

pending = calculate_pending_records(filtered_df)
print(f"12. 待跟进记录: {len(pending)} 条")

suggestions = calculate_replenishment_suggestions(normalized_df)
print(f"\n13. 补充建议: {len(suggestions)} 种物料")
if not suggestions.empty:
    summary = get_suggestion_summary(suggestions)
    print(f"    高优先级: {summary['high_priority']} 种")
    print(f"    中优先级: {summary['medium_priority']} 种")
    print(f"    低优先级: {summary['low_priority']} 种")
    print(f"    建议补充总量: {summary['total_suggested_qty']} 件")

filters_display = {
    "start_date": "2026-06-01",
    "end_date": "2026-06-15",
    "item_names": [],
    "groups": [],
    "handlers": [],
    "abnormal_status": "全部",
}

report_data = generate_summary_report(
    normalized_df, filtered_df, stats, trend, ranking, workload, pending, suggestions, filters_display
)
print(f"\n14. 报告生成成功: {len(report_data)} 字节")

with open("test_report.xlsx", "wb") as f:
    f.write(report_data)
print("    已保存为 test_report.xlsx")

print("\n" + "=" * 60)
print("✅ 所有测试通过！")
print("=" * 60)
