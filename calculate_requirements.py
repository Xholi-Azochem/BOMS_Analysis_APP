import pandas as pd
import numpy as np
import streamlit as st
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

# @functools.lru_cache(maxsize=128)
def calculate_custom_requirements(product, quantity_desired, bom_a_l, bom_m_z, analysis_results):
    """
    Calculate detailed product requirements with enhanced information including:
    - Component descriptions
    - Stock on Hand (SOH)
    - Availability for order fulfillment
    """
    # Combine BOMs
    combined_bom = pd.concat([bom_a_l, bom_m_z], ignore_index=True)
    
    # Identify critical columns dynamically
    possible_columns = {
        'assly': ['Assly Part Number', 'Assembly Part Number', 'Product', 'ProductCode', 'FG Code'],
        'component': ['Component', 'ComponentCode', 'Part Number', 'PartNumber', 'L2 Code'],
        'qty': ['L2 Unti Qty', 'L2 Unit Quantity', 'UnitQuantity', 'Unit Qty'],
        'description': ['Description', 'L2 Description','Component Description', 'Item Description', 'Part Description']
    }
    
    # Find matching columns
    assly_col = next((col for col in possible_columns['assly'] if col in combined_bom.columns), None)
    component_col = next((col for col in possible_columns['component'] if col in combined_bom.columns), None)
    qty_col = next((col for col in possible_columns['qty'] if col in combined_bom.columns), None)
    description_col = next((col for col in possible_columns['description'] if col in combined_bom.columns), None)
    
    # Validate critical columns
    if not all([assly_col, component_col, qty_col]):
        st.error("Could not find required columns in the BOM data.")
        return pd.DataFrame()
    
    # Find product BOM
    def find_product_bom(product):
        # Multiple search strategies
        strategies = [
            lambda df: df[df[assly_col].astype(str).str.strip() == str(product).strip()],
            lambda df: df[df[assly_col].astype(str).str.strip().str.lower() == str(product).strip().lower()],
            lambda df: df[df[assly_col].astype(str).str.contains(str(product), case=False, na=False)]
        ]
        
        for strategy in strategies:
            result = strategy(combined_bom)
            if not result.empty:
                return result
        
        return pd.DataFrame()
    
    # Find product BOM
    product_bom = find_product_bom(product)
    
    if product_bom.empty:
        st.warning(f"No BOM found for product: {product}")
        return pd.DataFrame()
    
    # Prepare requirements DataFrame
    requirements = []
    
    # Get component usage data and raw materials data for stock information
    component_usage = analysis_results.get('component_usage', pd.DataFrame())
    
    for _, row in product_bom.iterrows():
        # Extract component information
        component = str(row[component_col]) if pd.notna(row[component_col]) else 'Unknown'
        unit_qty = row[qty_col] if pd.notna(row[qty_col]) else 1
        total_qty = unit_qty * quantity_desired
        
        # Get description (if available)
        component_desc = 'N/A'
        if description_col and description_col in row.index:
            component_desc = str(row[description_col]) if pd.notna(row[description_col]) else 'N/A'
        
        # Check stock availability
        stock_qty = 0
        if not component_usage.empty:
            # Try to find stock quantity
            stock_entry = component_usage[component_usage.index == component]
            if not stock_entry.empty and 'SOH' in stock_entry.columns:
                stock_qty = stock_entry['SOH'].values[0]
        
        # Determine stock sufficiency
        stock_sufficient = stock_qty >= total_qty
        stock_status = 'Sufficient' if stock_sufficient else 'Insufficient'
        
        requirements.append({
            'Component Code': component,
            'Description': component_desc,
            'Unit Quantity per Product': unit_qty,
            'Total Unit Quantity': total_qty,
            'Stock on Hand': stock_qty,
            'Stock Status': stock_status
        })
    
    # Convert to DataFrame and remove duplicates
    requirements_df = pd.DataFrame(requirements).drop_duplicates(subset=['Component Code'])
    
    # Sort by Total Unit Quantity in descending order
    requirements_df = requirements_df.sort_values('Total Unit Quantity', ascending=False)
    
    return requirements_df
