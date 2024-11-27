import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
from analyze_bom_data import analyze_bom_data
from calculate_requirements import calculate_requirements
from generate_insights import generate_insights
from data_utils import clean_data, optimize_memory
import functools
from io import BytesIO
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

def save_analysis_results_to_excel(analysis_results, buffer):
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        analysis_results["product_metrics"].to_excel(writer, sheet_name="Product_Metrics")
        analysis_results["product_complexity"].to_excel(writer, sheet_name="Product_Complexity")
        analysis_results["component_usage"].to_excel(writer, sheet_name="Component_Usage")
        cost_dist = pd.DataFrame.from_dict(analysis_results["cost_distribution"], orient="index", columns=["Value"])
        cost_dist.to_excel(writer, sheet_name="Cost_Distribution")



 #Modify the search_and_requirements_page function to include more error logging
def search_and_requirements_page(analysis_results, bom_a_l, bom_m_z, dispensing_data, raw_materials):
    """Render the Search & Requirements page."""
    st.title("Search & Requirements")

    # User inputs for product search
    product = st.text_input("Enter Product Code")
    quantity_desired = st.number_input("Enter Desired Quantity", min_value=0, step=1)

    if product and quantity_desired > 0:
        st.subheader(f"Requirements for Producing {quantity_desired} Units of {product}")

        # Calculate requirements with custom method
        try:
            # Log input parameters
            logger.info(f"Calculating requirements for Product: {product}, Quantity: {quantity_desired}")
            
            # Use custom requirements calculation
            requirements = calculate_custom_requirements(
                product, 
                quantity_desired, 
                bom_a_l, 
                bom_m_z, 
                analysis_results
            )

            # Fallback to original method if custom method fails
            if requirements.empty:
                logger.warning("Custom requirements calculation failed. Falling back to original method.")
                requirements = calculate_requirements(
                    product, 
                    quantity_desired, 
                    analysis_results, 
                    dispensing_data, 
                    raw_materials
                )

            if not requirements.empty:
                st.dataframe(requirements)
            else:
                st.warning(f"No requirements found for product: {product}")
        except Exception as e:
            # Log the full error
            logger.error(f"Error calculating requirements: {e}", exc_info=True)
            st.error(f"Error calculating requirements: {e}")
# Set page config
st.set_page_config(page_title="Enhanced BOM Analysis", layout="wide")

# Custom CSS for styling
st.markdown("""
    <style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 5px;
        padding: 20px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    }
    div[data-testid="metric-container"] {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 5px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
        width: 100%;
    }
    </style>
""", unsafe_allow_html=True)

# Sidebar navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Select Page",
    ["Overview", "Product Metrics", "Component Analysis", "Cost Analysis", "Search & Requirements"]
)

# File upload section in sidebar
st.sidebar.header("Upload Files")
uploaded_bom_a_l = st.sidebar.file_uploader("Upload BOM Data (A-L)", type=["csv", "xlsx"])
uploaded_bom_m_z = st.sidebar.file_uploader("Upload BOM Data (M-Z)", type=["csv", "xlsx"])
uploaded_dispensing = st.sidebar.file_uploader("Upload Dispensing Data", type=["csv", "xlsx"])
uploaded_raw_materials = st.sidebar.file_uploader("Upload Raw Materials Data", type=["csv", "xlsx"])


def create_metric_card(title, value, delta=None):
    """Create a styled metric card."""
    col1, col2 = st.columns([1, 1])
    with col1:
        st.metric(label=title, value=value, delta=delta)


def overview_page(analysis_results):
    """Render the Overview page."""
    st.title("BOM Analysis Overview")

    # Metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Products", len(analysis_results["product_metrics"]))
    with col2:
        avg_cost = analysis_results["cost_distribution"]["avg_product_cost"]
        st.metric("Average Product Cost", f"R{avg_cost:.2f}")
    with col3:
        st.metric("Total Components", len(analysis_results["component_usage"]))

     # Product Complexity Chart
    st.subheader("Top 10 Most Complex Products")
    complexity_df = analysis_results["product_complexity"].head(10).reset_index()
    complexity_df.columns = ['Product Code', 'Complexity Score']
    fig = px.bar(complexity_df, x="Product Code", y="Complexity Score", color="Complexity Score",
                 title="Top 10 Most Complex Products", color_continuous_scale="Viridis")
    st.plotly_chart(fig, use_container_width=True)

    # Key Insights
    st.subheader("Key Insights")
    insights = generate_insights(analysis_results)
    for insight in insights:
        st.info(insight)



def product_metrics_page(analysis_results):
    """Product Metrics Analysis Page."""
    st.title("Product Metrics Analysis")

    # Select product
    products = analysis_results["product_metrics"].index.tolist()
    selected_product = st.selectbox("Select Product to Analyze", ["All Products"] + products)

    if selected_product == "All Products":
        st.subheader("Aggregate Metrics for All Products")
        total_components = analysis_results["product_metrics"]["component_count"].sum()
        total_cost = analysis_results["product_metrics"]["TOTCOST"].sum()

        col1, col2 = st.columns(2)
        with col1:
            create_metric_card("Total Components", total_components)
        with col2:
            create_metric_card("Total Cost", f"R{total_cost:,.2f}")
    else:
        st.subheader(f"Metrics for Product: {selected_product}")
        product_data = analysis_results["product_metrics"].loc[selected_product]

        col1, col2, col3 = st.columns(3)
        with col1:
            create_metric_card("Component Count", product_data["component_count"])
        with col2:
            create_metric_card("Total Cost", f"R{product_data['TOTCOST']:,.2f}")
        with col3:
            create_metric_card("Component Cost", f"R{product_data['total_component_cost']:,.2f}")


def component_analysis_page(analysis_results):
    """Component Analysis Page."""
    st.title("Component Analysis")

    # Top Components Usage
    st.subheader("Most Used Components")
    top_components = analysis_results["component_usage"].head(10)
    fig = px.bar(top_components, y=top_components.index, x="used_in_products", orientation="h",
                 title="Top 10 Most Used Components")
    st.plotly_chart(fig, use_container_width=True)

    # Component Cost vs Quantity
    st.subheader("Component Cost vs Quantity Distribution")
    fig = px.scatter(analysis_results["component_usage"], x="avg_cost", y="avg_quantity",
                     size="used_in_products", color="avg_cost",
                     title="Component Cost vs Quantity Distribution")
    st.plotly_chart(fig, use_container_width=True)


def cost_analysis_page(analysis_results):
    """Cost Analysis Page."""
    st.title("Cost Analysis")

    # Metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total BOM Cost", f"R{analysis_results['cost_distribution']['total_bom_cost']:,.2f}")
    with col2:
        st.metric("Average Product Cost", f"R{analysis_results['cost_distribution']['avg_product_cost']:,.2f}")
    with col3:
        median_cost = analysis_results['cost_distribution']['cost_percentiles'][0.5]
        st.metric("Median Cost", f"R{median_cost:,.2f}")


# Memoization decorator for performance
@functools.lru_cache(maxsize=128)
def cached_requirements_calculation(product, quantity_desired, analysis_results_json, dispensing_data_json, raw_materials_json):
    """Cached version of requirement calculation to improve performance."""
    # Convert JSON back to DataFrames
    analysis_results = {k: pd.DataFrame(v) if isinstance(v, list) else v for k, v in analysis_results_json.items()}
    dispensing_data = pd.DataFrame(dispensing_data_json)
    raw_materials = pd.DataFrame(raw_materials_json)
    
    return calculate_requirements(product, quantity_desired, analysis_results, dispensing_data, raw_materials)




def get_previous_l2_qty(product, bom_data):
    """
    Find the previous L2 Unti Qty for a specific product.
    
    Args:
        product (str): Product code to search for
        bom_data (pd.DataFrame): Combined BOM data
    
    Returns:
        float: Previous L2 Unti Qty if found, else None
    """
    # Filter for exact product match
    product_data = bom_data[bom_data['Assly Part Number'].str.strip() == product.strip()]
    
    if not product_data.empty:
        # Sort by any additional criteria if needed (e.g., most recent date)
        l2_qty = product_data['L2 Unti Qty'].dropna()
        return l2_qty.mean() if not l2_qty.empty else None
    
    return None

def get_column_name(df, possible_names):
    """
    Find the first matching column name from a list of possible names.
    
    Args:
        df (pd.DataFrame): Input DataFrame
        possible_names (list): List of possible column names to check
    
    Returns:
        str: Matching column name or None
    """
    for name in possible_names:
        if name in df.columns:
            return name
    return None

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
        'description': ['Description', 'Component Description', 'Item Description', 'Part Description']
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


def search_and_requirements_page(analysis_results, bom_a_l, bom_m_z, dispensing_data, raw_materials):
    """Render the Search & Requirements page with enhanced requirements information."""
    st.title("Search & Requirements")

    # User inputs for product search
    product = st.text_input("Enter Product Code")
    quantity_desired = st.number_input("Enter Desired Quantity", min_value=0, step=1, value=1)

    if product and quantity_desired > 0:
        st.subheader(f"Requirements for Producing {quantity_desired} Units of {product}")

        # Calculate requirements with custom method
        try:
            # Use custom requirements calculation
            requirements = calculate_custom_requirements(
                product, 
                quantity_desired, 
                bom_a_l, 
                bom_m_z, 
                analysis_results
            )

            if not requirements.empty:
                # Color coding for stock status
                def color_status(val):
                    color = 'green' if val == 'Sufficient' else 'red'
                    return f'color: {color}'

                # Display requirements in a styled table
                st.dataframe(
                    requirements.style.applymap(color_status, subset=['Stock Status']), 
                    use_container_width=True,
                    column_config={
                        "Component Code": st.column_config.TextColumn("Component Code"),
                        "Description": st.column_config.TextColumn("Description"),
                        "Unit Quantity per Product": st.column_config.NumberColumn("Unit Quantity per Product", format="%.2f"),
                        "Total Unit Quantity": st.column_config.NumberColumn("Total Unit Quantity", format="%.2f"),
                        "Stock on Hand": st.column_config.NumberColumn("Stock on Hand", format="%.2f"),
                        "Stock Status": st.column_config.TextColumn("Stock Status")
                    }
                )
                
                # Additional metrics
                total_components = len(requirements)
                total_required_qty = requirements['Total Unit Quantity'].sum()
                insufficient_stock_count = len(requirements[requirements['Stock Status'] == 'Insufficient'])
                
                # Create columns for metrics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Unique Components", total_components)
                with col2:
                    st.metric("Total Required Quantity", f"{total_required_qty:.2f}")
                with col3:
                    st.metric("Components with Insufficient Stock", insufficient_stock_count)
                
                # Warning for insufficient stock
                if insufficient_stock_count > 0:
                    st.warning(f"{insufficient_stock_count} components have insufficient stock for the desired quantity.")
                    
                    # Show details of components with insufficient stock
                    insufficient_components = requirements[requirements['Stock Status'] == 'Insufficient']
                    st.subheader("Components with Insufficient Stock")
                    st.dataframe(
                        insufficient_components[['Component Code', 'Description', 'Total Unit Quantity', 'Stock on Hand']], 
                        use_container_width=True
                    )
            else:
                st.warning(f"No requirements found for product: {product}")
        except Exception as e:
            st.error(f"Error calculating requirements: {e}")
# Main workflow
if all([uploaded_bom_a_l, uploaded_bom_m_z, uploaded_dispensing, uploaded_raw_materials]):
    try:
        # Load data
        bom_a_l = pd.read_excel(uploaded_bom_a_l) if uploaded_bom_a_l.name.endswith(".xlsx") else pd.read_csv(uploaded_bom_a_l)
        bom_m_z = pd.read_excel(uploaded_bom_m_z) if uploaded_bom_m_z.name.endswith(".xlsx") else pd.read_csv(uploaded_bom_m_z)
        dispensing_data = pd.read_excel(uploaded_dispensing) if uploaded_dispensing.name.endswith(".xlsx") else pd.read_csv(uploaded_dispensing)
        raw_materials = pd.read_excel(uploaded_raw_materials) if uploaded_raw_materials.name.endswith(".xlsx") else pd.read_csv(uploaded_raw_materials)

        # Clean and optimize data
        numeric_columns_bom = ["TOTCOST", "L2 CostInBOM", "L2 Unti Qty", "L3 Unit Qty"]
        numeric_columns_dispensing = ["Qty", "Value"]
        numeric_columns_raw_materials = ["SOH"]

        bom_a_l = optimize_memory(clean_data(bom_a_l, numeric_columns_bom))
        bom_m_z = optimize_memory(clean_data(bom_m_z, numeric_columns_bom))
        dispensing_data = optimize_memory(clean_data(dispensing_data, numeric_columns_dispensing))
        raw_materials = optimize_memory(clean_data(raw_materials, numeric_columns_raw_materials))

        # Analyze data
        analysis_results = analyze_bom_data(bom_a_l, bom_m_z, dispensing_data, raw_materials)

        # Render selected page
        if page == "Overview":
            overview_page(analysis_results)
        elif page == "Product Metrics":
            product_metrics_page(analysis_results)
        elif page == "Component Analysis":
            component_analysis_page(analysis_results)
        elif page == "Cost Analysis":
            cost_analysis_page(analysis_results)
        else:
            # Pass all required arguments
            search_and_requirements_page(
                analysis_results, 
                bom_a_l, 
                bom_m_z, 
                dispensing_data, 
                raw_materials
            )

    except Exception as e:
        st.error(f"An error occurred during analysis: {e}")
else:
    st.info("Please upload all required files to proceed.")
