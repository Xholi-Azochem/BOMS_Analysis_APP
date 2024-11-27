import pandas as pd
import streamlit as st



def analyze_bom_data(bom_a_l, bom_m_z, dispensing_data=None, raw_materials=None):
    """Analyze BOM data and return metrics, complexity, and usage."""
    combined_bom = pd.concat([bom_a_l, bom_m_z], ignore_index=True)

    # Product metrics
    product_metrics = combined_bom.groupby("FG Code").agg({
        "TOTCOST": "sum",
        "L2 Code": "count",
        "L2 CostInBOM": "sum",
        "L2 Unti Qty": "sum",
        "L3 Unit Qty": "sum"
    }).rename(columns={
        "L2 Code": "component_count",
        "L2 CostInBOM": "total_component_cost"
    })

    # Complexity
    product_complexity = combined_bom.groupby("FG Code")[["L2 Code", "L3 Code", "L4 Code"]].nunique().sum(axis=1)

    # Component usage
    component_usage = combined_bom.groupby("L2 Code").agg({
        "FG Code": lambda x: len(x.unique()),
        "L2 CostInBOM": "mean",
        "L2 Unti Qty": "mean"
    }).rename(columns={
        "FG Code": "used_in_products",
        "L2 CostInBOM": "avg_cost",
        "L2 Unti Qty": "avg_quantity"
    })

    # Integrate dispensing data
    if dispensing_data is not None:
        dispensing_summary = dispensing_data.groupby("Code").agg({
            "Qty": "sum",
            "Value": "sum"
        }).rename(columns={
            "Qty": "dispensed_qty",
            "Value": "dispensed_value"
        })
        component_usage = component_usage.join(dispensing_summary, how="left")

    # Integrate raw materials
    if raw_materials is not None:
        stock_summary = raw_materials.groupby("TRIMcode").agg({"SOH": "sum"})
        component_usage = component_usage.join(stock_summary, how="left")

    # Cost distribution
    cost_distribution = {
        "total_bom_cost": combined_bom["TOTCOST"].sum(),
        "avg_product_cost": combined_bom.groupby("FG Code")["TOTCOST"].sum().mean(),
        "cost_percentiles": combined_bom.groupby("FG Code")["TOTCOST"].sum().quantile([0.25, 0.5, 0.75]).to_dict()
    }

    return {
        "product_metrics": product_metrics,
        "product_complexity": product_complexity,
        "component_usage": component_usage,
        "cost_distribution": cost_distribution
    }
