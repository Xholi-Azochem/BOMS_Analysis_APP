import pandas as pd 
import streamlit as st


@st.cache_resource
def generate_insights(analysis_results):
    insights = []

    top_complex = analysis_results["product_complexity"].head()
    insights.append(f"Most complex products: {', '.join(top_complex.index)}")

    cost_dist = analysis_results["cost_distribution"]
    insights.append(f"Average product cost: R{cost_dist['avg_product_cost']:.2f}")

    common_components = analysis_results["component_usage"].head()
    insights.append(f"Most commonly used components: {', '.join(common_components.index)}")

    product_metrics = analysis_results["product_metrics"]
    insights.append(f"Minimum and Maximum Quantities to Produce:")
    for fg_code in product_metrics.index:
        min_qty = product_metrics.loc[fg_code, "MIN_QTY_TO_PRODUCE"]
        max_qty = product_metrics.loc[fg_code, "MAX_QTY_TO_PRODUCE"]
        insights.append(f"FG Code {fg_code}: Min = {min_qty}, Max = {max_qty}")

    # Stock insights
    component_usage = analysis_results["component_usage"]
    stock_shortages = component_usage[component_usage["SOH"] < component_usage["avg_quantity"]]
    if not stock_shortages.empty:
        insights.append(f"Components with insufficient stock: {', '.join(stock_shortages.index)}")
    else:
        insights.append("All components have sufficient stock levels for average usage.")

    return insights
