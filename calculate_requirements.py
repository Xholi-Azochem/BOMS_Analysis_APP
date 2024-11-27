import pandas as pd
import numpy as np

import pandas as pd

def calculate_requirements(product, quantity_desired, analysis_results, dispensing_data, raw_materials):
    """Calculate required quantities and stock sufficiency."""
    component_usage = analysis_results["component_usage"]
    requirements = []
    for component in component_usage.index:
        avg_qty_per_unit = component_usage.loc[component, "avg_quantity"]
        required_qty = avg_qty_per_unit * quantity_desired
        stock_qty = raw_materials[raw_materials["TRIMcode"] == component]["SOH"].sum() if component in raw_materials["TRIMcode"].values else 0
        sufficient = stock_qty >= required_qty
        requirements.append({
            "Component": component,
            "Required Quantity": required_qty,
            "Stock Quantity": stock_qty,
            "Sufficient Stock": "Yes" if sufficient else "No"
        })
    return pd.DataFrame(requirements)




def generate_requirement_report(requirements_df):
    """
    Generate a detailed report of component requirements.
    
    Parameters:
    - requirements_df: DataFrame with calculated requirements.
    
    Returns:
    - List of report lines.
    """
    report = []
    
    # Total unique components
    total_components = len(requirements_df)
    report.append(f"Total Unique Components: {total_components}")
    
    # Total required quantity
    total_required_qty = requirements_df['Required Quantity'].sum()
    report.append(f"Total Required Quantity Across All Components: {total_required_qty:.2f}")
    
    # Components with insufficient stock
    insufficient_stock = requirements_df[requirements_df['Sufficient Stock'] == 'No']
    if not insufficient_stock.empty:
        report.append("Components with Insufficient Stock:")
        for _, row in insufficient_stock.iterrows():
            report.append(f"- {row['Component']}: Required {row['Required Quantity']}, Stock {row['Stock Quantity']}")
    
    return report

