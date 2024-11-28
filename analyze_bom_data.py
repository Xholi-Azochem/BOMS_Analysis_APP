import pandas as pd
import streamlit as st

@st.cache_resource
def analyze_bom_data(bom_a_l, bom_m_z, dispensing_data=None, raw_materials=None):
    """
    Enhanced BOM data analysis with Dispensing and Raw Materials integration.
    """
    combined_bom = pd.concat([bom_a_l, bom_m_z], ignore_index=True)

    # Ensure component_usage is initialized
    component_usage = pd.DataFrame()

    # Product metrics and complexity
    def calculate_product_metrics(df):
        product_costs = df.groupby("FG Code").agg({
            "TOTCOST": "sum",
            "L2 Code": "count",
            "L2 CostInBOM": "sum",
            "L2 Unti Qty": "sum",
            "L3 Unit Qty": "sum"
        }).rename(columns={
            "L2 Code": "component_count",
            "L2 CostInBOM": "total_component_cost"
        })

        product_complexity = df.groupby("FG Code").agg({
            "L2 Code": lambda x: len(x.unique()),
            "L3 Code": lambda x: len(x.dropna().unique()),
            "L4 Code": lambda x: len(x.dropna().unique())
        }).sum(axis=1).sort_values(ascending=False)

        min_qty_to_produce = df.groupby("FG Code").agg({
            "L2 Unti Qty": "min",
            "L3 Unit Qty": "min"
        }).min(axis=1).rename("MIN_QTY_TO_PRODUCE")

        max_qty_to_produce = df.groupby("FG Code").agg({
            "L2 Unti Qty": "max",
            "L3 Unit Qty": "max"
        }).max(axis=1).rename("MAX_QTY_TO_PRODUCE")

        product_metrics = product_costs.join([min_qty_to_produce, max_qty_to_produce])
        return product_metrics, product_complexity

    def analyze_component_usage(df):
        component_usage = df.groupby("L2 Code").agg({
            "FG Code": lambda x: len(x.unique()),
            "L2 CostInBOM": "mean",
            "L2 Unti Qty": "mean"
        }).rename(columns={
            "FG Code": "used_in_products",
            "L2 CostInBOM": "avg_cost",
            "L2 Unti Qty": "avg_quantity"
        })
        return component_usage.sort_values("used_in_products", ascending=False)

    def calculate_cost_distribution(df):
        cost_stats = {
            "total_bom_cost": df["TOTCOST"].sum(),
            "avg_product_cost": df.groupby("FG Code")["TOTCOST"].sum().mean(),
            "cost_percentiles": df.groupby("FG Code")["TOTCOST"].sum().quantile([0.25, 0.5, 0.75]).to_dict()
        }
        return cost_stats

    # Calculate product metrics and complexity
    product_metrics, product_complexity = calculate_product_metrics(combined_bom)

    # Analyze component usage
    component_usage = analyze_component_usage(combined_bom)

    # Add dispensing data integration if provided
    if dispensing_data is not None:
        dispensing_summary = dispensing_data.groupby("Code").agg({
            "Qty": "sum",
            "Value": "sum"
        }).rename(columns={
            "Qty": "dispensed_qty",
            "Value": "dispensed_value"
        })
        # Merge dispensing data with component usage
        component_usage = component_usage.join(dispensing_summary, how="left")

    # Add raw materials integration if provided
    if raw_materials is not None:
        stock_summary = raw_materials.groupby("TRIMcode").agg({"SOH": "sum"})
        # Merge stock data with component usage
        component_usage = component_usage.join(stock_summary, how="left")

    # Cost distribution
    cost_distribution = calculate_cost_distribution(combined_bom)

    return {
        "product_metrics": product_metrics,
        "product_complexity": product_complexity,
        "component_usage": component_usage,
        "cost_distribution": cost_distribution
    }
