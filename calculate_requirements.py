import pandas as pd

def calculate_requirements(product, quantity_desired, analysis_results, dispensing_data, raw_materials):
    """
    Calculate component requirements for a given product and quantity.
    Compare required quantities against current stock levels.
    """
    # Fetch the BOM for the selected product
    product_bom = analysis_results["product_metrics"].loc[product]
    component_usage = analysis_results["component_usage"]

    # Calculate component requirements
    requirements = []
    for component in component_usage.index:
        # Get average quantity per unit and scale by desired quantity
        avg_qty_per_unit = component_usage.loc[component, "avg_quantity"]
        required_qty = avg_qty_per_unit * quantity_desired

        # Fetch current stock
        stock_row = raw_materials[raw_materials["TRIMcode"] == component]
        stock_qty = stock_row["SOH"].sum() if not stock_row.empty else 0

        # Determine if stock is sufficient
        sufficient = stock_qty >= required_qty

        # Append to requirements
        requirements.append({
            "Component": component,
            "Required Quantity": required_qty,
            "Stock Quantity": stock_qty,
            "Sufficient Stock": "Yes" if sufficient else "No"
        })

    # Convert to DataFrame
    return pd.DataFrame(requirements)
