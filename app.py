import streamlit as st
import pandas as pd
from datetime import datetime, date
import io
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_loader import (
    read_csv_from_upload,
    detect_column_mapping,
    apply_column_mapping,
    normalize_dataframe,
    get_unique_values,
    REQUIRED_FIELDS,
)
from validator import (
    validate_all,
    check_abnormal_quantity,
    check_duplicate_records,
    check_duplicate_mapping,
    FIELD_NAMES_CN,
)
from filter_engine import (
    apply_all_filters,
    calculate_issued_trend,
    calculate_return_diff_ranking,
    calculate_group_workload,
    calculate_pending_records,
    calculate_summary_stats,
)
from suggestion_engine import (
    calculate_replenishment_suggestions,
    get_suggestion_summary,
    format_priority_label,
)
from report_generator import (
    generate_summary_report,
    get_report_filename,
)


st.set_page_config(
    page_title="志愿服务物料流转分析",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
    <style>
    .main {
        padding: 1rem 2rem;
    }
    .stMetric {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #007bff;
    }
    .high-priority {
        background-color: #fff3f3;
        border-left: 4px solid #dc3545;
    }
    .medium-priority {
        background-color: #fffbf0;
        border-left: 4px solid #ffc107;
    }
    .low-priority {
        background-color: #f3fff5;
        border-left: 4px solid #28a745;
    }
    </style>
""", unsafe_allow_html=True)


def render_upload_section():
    st.header("📁 数据上传")
    uploaded_file = st.file_uploader("请上传 CSV 格式的物料流转记录文件", type=["csv"])

    if "raw_df" not in st.session_state:
        st.session_state.raw_df = None
    if "normalized_df" not in st.session_state:
        st.session_state.normalized_df = None
    if "column_mapping" not in st.session_state:
        st.session_state.column_mapping = None
    if "validation_results" not in st.session_state:
        st.session_state.validation_results = None

    if uploaded_file is not None:
        try:
            raw_df = read_csv_from_upload(uploaded_file)
            if raw_df is not None:
                st.session_state.raw_df = raw_df
                st.success(f"✅ 成功读取 {len(raw_df)} 条记录")

                with st.expander("查看原始数据预览"):
                    st.dataframe(raw_df.head(10), use_container_width=True)

                render_column_mapping(raw_df)

        except ValueError as e:
            st.error(f"❌ {str(e)}")


def render_column_mapping(raw_df):
    st.subheader("🔗 字段映射配置")

    detected_mapping = detect_column_mapping(raw_df)

    if st.session_state.column_mapping is None:
        st.session_state.column_mapping = detected_mapping

    raw_columns = list(raw_df.columns) + ["-- 不映射 --"]

    col1, col2 = st.columns(2)
    mapping = {}

    with col1:
        for i, field in enumerate(REQUIRED_FIELDS[:4]):
            field_cn = FIELD_NAMES_CN.get(field, field)
            default_idx = 0
            if st.session_state.column_mapping.get(field) in raw_columns:
                default_idx = raw_columns.index(st.session_state.column_mapping[field])
            elif detected_mapping.get(field) in raw_columns:
                default_idx = raw_columns.index(detected_mapping[field])

            selected = st.selectbox(
                f"{field_cn} ({field})",
                options=raw_columns,
                index=default_idx,
                key=f"map_{field}",
            )
            mapping[field] = selected if selected != "-- 不映射 --" else None

    with col2:
        for i, field in enumerate(REQUIRED_FIELDS[4:]):
            field_cn = FIELD_NAMES_CN.get(field, field)
            default_idx = 0
            if st.session_state.column_mapping.get(field) in raw_columns:
                default_idx = raw_columns.index(st.session_state.column_mapping[field])
            elif detected_mapping.get(field) in raw_columns:
                default_idx = raw_columns.index(detected_mapping[field])

            selected = st.selectbox(
                f"{field_cn} ({field})",
                options=raw_columns,
                index=default_idx,
                key=f"map_{field}",
            )
            mapping[field] = selected if selected != "-- 不映射 --" else None

    st.session_state.column_mapping = mapping

    if st.button("✅ 确认映射并处理数据", type="primary"):
        dup_mapping = check_duplicate_mapping(mapping)
        if dup_mapping:
            for col, fields in dup_mapping.items():
                fields_cn = [FIELD_NAMES_CN.get(f, f) for f in fields]
                st.error(f"❌ 列「{col}」被重复映射到: {', '.join(fields_cn)}，请调整映射后重试")
            st.stop()

        mapped_df = apply_column_mapping(raw_df, mapping)
        normalized_df = normalize_dataframe(mapped_df)
        st.session_state.normalized_df = normalized_df

        validation_results = validate_all(normalized_df, raw_df, mapping)
        st.session_state.validation_results = validation_results

        st.success("✅ 数据处理完成")


def render_validation_results():
    if st.session_state.validation_results is None:
        return

    results = st.session_state.validation_results

    st.header("⚠️ 数据质量检查")

    if results["summary"]:
        for msg in results["summary"]:
            st.warning(msg)
    else:
        st.success("✅ 未发现数据质量问题")

    col1, col2 = st.columns(2)

    with col1:
        if not results["missing_columns"]:
            st.info("✅ 所有必需字段已映射")
        else:
            missing_cn = [FIELD_NAMES_CN.get(f, f) for f in results["missing_columns"]]
            st.error(f"❌ 缺失字段: {', '.join(missing_cn)}")

        if not results["invalid_dates"].empty:
            with st.expander(f"⚠️ 无效日期记录 ({len(results['invalid_dates'])} 条)"):
                st.dataframe(results["invalid_dates"], use_container_width=True)

        if not results["empty_keys"].empty:
            with st.expander(f"⚠️ 关键字段为空 ({len(results['empty_keys'])} 条)"):
                st.dataframe(results["empty_keys"], use_container_width=True)

    with col2:
        if not results["duplicate_records"].empty:
            with st.expander(f"⚠️ 重复记录 ({len(results['duplicate_records'])} 条)"):
                st.dataframe(results["duplicate_records"], use_container_width=True)

        if not results["abnormal_quantity"].empty:
            with st.expander(f"⚠️ 数量异常记录 ({len(results['abnormal_quantity'])} 条)"):
                st.dataframe(results["abnormal_quantity"], use_container_width=True)

        if not results["negative_quantity"].empty:
            with st.expander(f"⚠️ 负数数量记录 ({len(results['negative_quantity'])} 条)"):
                st.dataframe(results["negative_quantity"], use_container_width=True)

    if not results.get("non_numeric", pd.DataFrame()).empty:
        with st.expander(f"⚠️ 非数字数量记录 ({len(results['non_numeric'])} 条，已被转为 0)"):
            st.warning("以下记录的数量字段包含非数字值，已自动转为 0，请核实原始数据")
            st.dataframe(results["non_numeric"], use_container_width=True)


def render_filter_sidebar(df):
    st.sidebar.header("🔍 筛选条件")

    has_valid_dates = not df.empty and "record_date" in df.columns and df["record_date"].notna().any()

    if has_valid_dates:
        min_date = df["record_date"].min().date()
        max_date = df["record_date"].max().date()
    else:
        min_date = date.today()
        max_date = date.today()

    if has_valid_dates:
        start_date = st.sidebar.date_input(
            "开始日期",
            value=min_date,
            min_value=min_date,
            max_value=max_date,
        )

        end_date = st.sidebar.date_input(
            "结束日期",
            value=max_date,
            min_value=min_date,
            max_value=max_date,
        )
    else:
        st.sidebar.warning("⚠️ 未检测到有效日期列，日期筛选已禁用")
        start_date = None
        end_date = None

    item_names = get_unique_values(df, "item_name")
    selected_items = st.sidebar.multiselect(
        "物料名称",
        options=item_names,
        default=[],
        placeholder="选择物料名称（不选则为全部）",
    )

    groups = get_unique_values(df, "group_name")
    selected_groups = st.sidebar.multiselect(
        "小组",
        options=groups,
        default=[],
        placeholder="选择小组（不选则为全部）",
    )

    handlers = get_unique_values(df, "handler_name")
    selected_handlers = st.sidebar.multiselect(
        "处理人",
        options=handlers,
        default=[],
        placeholder="选择处理人（不选则为全部）",
    )

    abnormal_status = st.sidebar.selectbox(
        "异常状态",
        options=["全部", "正常", "异常", "有丢失", "待回收"],
        index=0,
    )

    filters = {
        "start_date": start_date,
        "end_date": end_date,
        "item_names": selected_items if selected_items else None,
        "groups": selected_groups if selected_groups else None,
        "handlers": selected_handlers if selected_handlers else None,
        "abnormal_status": abnormal_status,
    }

    return filters


def render_summary_metrics(stats):
    st.header("📊 核心指标概览")

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("记录总数", f"{stats['total_records']:,}")
    with col2:
        st.metric("总发放量", f"{stats['total_issued']:,}")
    with col3:
        st.metric("总回收量", f"{stats['total_returned']:,}")
    with col4:
        st.metric("总丢失量", f"{stats['total_lost']:,}")
    with col5:
        st.metric("物料种类", f"{stats['unique_items']:,}")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("回收率", f"{stats['return_rate']*100:.1f}%")
    with col2:
        st.metric("丢失率", f"{stats['lost_rate']*100:.1f}%")
    with col3:
        st.metric("涉及小组数", f"{stats['unique_groups']:,}")
    with col4:
        st.metric("涉及处理人数", f"{stats['unique_handlers']:,}")


def render_trend_chart(trend_df):
    st.subheader("📈 发放量趋势")

    if trend_df.empty:
        st.info("暂无趋势数据")
        return

    chart_data = trend_df.set_index("date")[["发放总量", "回收总量", "丢失总量"]]
    st.line_chart(chart_data, use_container_width=True)

    with st.expander("查看趋势明细"):
        st.dataframe(trend_df, use_container_width=True)


def render_ranking_chart(ranking_df):
    st.subheader("🏆 回收差异排行")

    if ranking_df.empty:
        st.info("暂无排行数据")
        return

    chart_data = ranking_df.head(15).set_index("item_name")["差异总量"].sort_values(ascending=True)
    st.bar_chart(chart_data, use_container_width=True, horizontal=True)

    display_df = ranking_df.copy()
    display_df["综合回收率"] = display_df["综合回收率"].apply(lambda x: f"{x*100:.1f}%")
    display_df["平均回收率"] = display_df["平均回收率"].apply(lambda x: f"{x*100:.1f}%")

    with st.expander("查看回收差异明细"):
        st.dataframe(display_df, use_container_width=True)


def render_workload_chart(workload_df):
    st.subheader("👥 小组负载分析")

    if workload_df.empty:
        st.info("暂无小组负载数据")
        return

    chart_data = workload_df.set_index("group_name")[["处理记录数", "发放总量", "回收总量"]]
    st.bar_chart(chart_data, use_container_width=True)

    display_df = workload_df.copy()
    display_df["回收率"] = display_df["回收率"].apply(lambda x: f"{x*100:.1f}%")
    display_df["丢失率"] = display_df["丢失率"].apply(lambda x: f"{x*100:.1f}%")

    with st.expander("查看小组负载明细"):
        st.dataframe(display_df, use_container_width=True)


def render_pending_records(pending_df):
    st.subheader("⏰ 待跟进记录")

    if pending_df.empty:
        st.success("✅ 暂无待跟进记录")
        return

    status_counts = pending_df["状态"].value_counts()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("待回收", status_counts.get("待回收", 0))
    with col2:
        st.metric("已丢失", status_counts.get("已丢失", 0))
    with col3:
        st.metric("待回收+已丢失", status_counts.get("待回收+已丢失", 0))

    display_df = pending_df.copy()
    display_df["record_date"] = display_df["record_date"].dt.strftime("%Y-%m-%d")

    with st.expander("查看待跟进明细"):
        st.dataframe(display_df, use_container_width=True)


def render_suggestions(suggestions_df):
    st.header("💡 补充建议")

    if suggestions_df.empty:
        st.info("暂无补充建议（数据不足两周）")
        return

    summary = get_suggestion_summary(suggestions_df)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("需补充物料", f"{summary['total_items']} 种")
    with col2:
        st.metric("高优先级", f"{summary['high_priority']} 种")
    with col3:
        st.metric("中优先级", f"{summary['medium_priority']} 种")
    with col4:
        st.metric("建议补充总量", f"{summary['total_suggested_qty']:,}")

    display_df = suggestions_df.copy()
    display_df["优先级"] = display_df["优先级"].apply(format_priority_label)
    display_df["丢失率"] = display_df["丢失率"].apply(lambda x: f"{x*100:.1f}%")
    display_df["最近发放日期"] = display_df["最近发放日期"].dt.strftime("%Y-%m-%d")
    display_df["日均发放量"] = display_df["日均发放量"].round(1)

    display_columns = [
        "item_name", "优先级", "建议补充数量",
        "近两周发放量", "近两周回收量", "近两周丢失量",
        "日均发放量", "丢失率", "补充理由"
    ]

    high_priority = display_df[display_df["优先级"].str.contains("高")]
    medium_priority = display_df[display_df["优先级"].str.contains("中")]
    low_priority = display_df[display_df["优先级"].str.contains("低")]

    if not high_priority.empty:
        st.subheader("🔴 高优先级补充")
        for _, row in high_priority.iterrows():
            with st.container():
                st.markdown(f"""
                    <div class='high-priority' style='padding: 1rem; border-radius: 0.5rem; margin-bottom: 0.5rem;'>
                        <strong>{row['item_name']}</strong> — 建议补充 <strong>{row['建议补充数量']}</strong> 件
                        <br><small>理由：{row['补充理由']} | 近两周发放 {row['近两周发放量']} 件，丢失 {row['近两周丢失量']} 件</small>
                    </div>
                """, unsafe_allow_html=True)

    if not medium_priority.empty:
        st.subheader("🟡 中优先级补充")
        for _, row in medium_priority.iterrows():
            with st.container():
                st.markdown(f"""
                    <div class='medium-priority' style='padding: 1rem; border-radius: 0.5rem; margin-bottom: 0.5rem;'>
                        <strong>{row['item_name']}</strong> — 建议补充 <strong>{row['建议补充数量']}</strong> 件
                        <br><small>理由：{row['补充理由']} | 近两周发放 {row['近两周发放量']} 件，丢失 {row['近两周丢失量']} 件</small>
                    </div>
                """, unsafe_allow_html=True)

    if not low_priority.empty:
        st.subheader("🟢 低优先级补充")
        for _, row in low_priority.iterrows():
            with st.container():
                st.markdown(f"""
                    <div class='low-priority' style='padding: 1rem; border-radius: 0.5rem; margin-bottom: 0.5rem;'>
                        <strong>{row['item_name']}</strong> — 建议补充 <strong>{row['建议补充数量']}</strong> 件
                        <br><small>理由：{row['补充理由']} | 近两周发放 {row['近两周发放量']} 件，丢失 {row['近两周丢失量']} 件</small>
                    </div>
                """, unsafe_allow_html=True)

    with st.expander("查看完整补充建议表"):
        st.dataframe(display_df[display_columns], use_container_width=True)


def render_download_section(original_df, filtered_df, filters, stats, trend, ranking, workload, pending, suggestions):
    st.sidebar.markdown("---")
    st.sidebar.header("📥 报告下载")

    filters_display = {
        "start_date": filters["start_date"].strftime("%Y-%m-%d") if filters["start_date"] else "未设置",
        "end_date": filters["end_date"].strftime("%Y-%m-%d") if filters["end_date"] else "未设置",
        "item_names": filters["item_names"] or [],
        "groups": filters["groups"] or [],
        "handlers": filters["handlers"] or [],
        "abnormal_status": filters["abnormal_status"] or "全部",
    }

    try:
        report_data = generate_summary_report(
            original_df,
            filtered_df,
            stats,
            trend,
            ranking,
            workload,
            pending,
            suggestions,
            filters_display,
        )

        st.sidebar.download_button(
            label="📄 下载筛选后摘要报告",
            data=report_data,
            file_name=get_report_filename(),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        st.sidebar.info("报告包含：封面、核心指标、发放趋势、回收差异、小组负载、待跟进记录、补充建议、筛选后明细")
    except Exception as e:
        st.sidebar.error(f"生成报告失败: {str(e)}")


def render_data_preview(filtered_df):
    st.header("📋 数据明细")

    if filtered_df.empty:
        st.warning("筛选后无数据")
        return

    display_df = filtered_df.copy()
    display_df["record_date"] = display_df["record_date"].dt.strftime("%Y-%m-%d")

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
    display_df = display_df.rename(columns=column_mapping)

    st.dataframe(display_df, use_container_width=True)
    st.caption(f"共 {len(filtered_df)} 条记录")


def main():
    st.title("📦 志愿服务物料流转分析系统")
    st.markdown("---")

    render_upload_section()

    if st.session_state.normalized_df is not None and not st.session_state.normalized_df.empty:
        render_validation_results()

        df = st.session_state.normalized_df
        filters = render_filter_sidebar(df)

        filtered_df = apply_all_filters(
            df,
            start_date=filters["start_date"],
            end_date=filters["end_date"],
            item_names=filters["item_names"],
            groups=filters["groups"],
            handlers=filters["handlers"],
            abnormal_status=filters["abnormal_status"],
        )

        stats = calculate_summary_stats(filtered_df)
        trend = calculate_issued_trend(filtered_df)
        ranking = calculate_return_diff_ranking(filtered_df)
        workload = calculate_group_workload(filtered_df)
        pending = calculate_pending_records(filtered_df)
        suggestions = calculate_replenishment_suggestions(filtered_df)

        render_summary_metrics(stats)

        tab1, tab2, tab3, tab4 = st.tabs(["发放量趋势", "回收差异排行", "小组负载", "待跟进记录"])
        with tab1:
            render_trend_chart(trend)
        with tab2:
            render_ranking_chart(ranking)
        with tab3:
            render_workload_chart(workload)
        with tab4:
            render_pending_records(pending)

        render_suggestions(suggestions)
        render_data_preview(filtered_df)
        render_download_section(df, filtered_df, filters, stats, trend, ranking, workload, pending, suggestions)


if __name__ == "__main__":
    main()
