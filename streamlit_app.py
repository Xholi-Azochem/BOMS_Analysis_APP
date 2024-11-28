import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
from analyze_bom_data import analyze_bom_data
from calculate_requirements import calculate_requirements, calculate_custom_requirements
from generate_insights import generate_insights
from search_and_requirements_page import search_and_requirements_page
from save_analysis_results_to_excel import save_analysis_results_to_excel
from metric_card import create_metric_card
from data_utils import clean_data, optimize_memory
import functools
from io import BytesIO
import logging
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.holtwinters import ExponentialSmoothing

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

# Initialize session state variables if not already present
if 'data_loaded' not in st.session_state:
    st.session_state.data_loaded = False
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = None
if 'bom_a_l' not in st.session_state:
    st.session_state.bom_a_l = None
if 'bom_m_z' not in st.session_state:
    st.session_state.bom_m_z = None
if 'dispensing_data' not in st.session_state:
    st.session_state.dispensing_data = None
if 'raw_materials' not in st.session_state:
    st.session_state.raw_materials = None

# Sidebar navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Select Page",
    ["Overview", "Product Metrics", "Component Analysis", "Cost Analysis", "Search & Requirements"]
)

# File upload section in sidebar
st.sidebar.header("Upload Files")
uploaded_bom_a_l = st.sidebar.file_uploader("Upload BOM Data (A-L)", type=["csv", "xlsx"], key="bom_a_l_upload")
uploaded_bom_m_z = st.sidebar.file_uploader("Upload BOM Data (M-Z)", type=["csv", "xlsx"], key="bom_m_z_upload")
uploaded_dispensing = st.sidebar.file_uploader("Upload Dispensing Data", type=["csv", "xlsx"], key="dispensing_upload")
uploaded_raw_materials = st.sidebar.file_uploader("Upload Raw Materials Data", type=["csv", "xlsx"], key="raw_materials_upload")

# Add a button to trigger data processing
if st.sidebar.button("Process Data", key="process_data_btn"):
    try:
        # Load data
        st.session_state.bom_a_l = pd.read_excel(uploaded_bom_a_l) if uploaded_bom_a_l.name.endswith(".xlsx") else pd.read_csv(uploaded_bom_a_l)
        st.session_state.bom_m_z = pd.read_excel(uploaded_bom_m_z) if uploaded_bom_m_z.name.endswith(".xlsx") else pd.read_csv(uploaded_bom_m_z)
        st.session_state.dispensing_data = pd.read_excel(uploaded_dispensing) if uploaded_dispensing.name.endswith(".xlsx") else pd.read_csv(uploaded_dispensing)
        st.session_state.raw_materials = pd.read_excel(uploaded_raw_materials) if uploaded_raw_materials.name.endswith(".xlsx") else pd.read_csv(uploaded_raw_materials)

        # Clean and optimize data
        numeric_columns_bom = ["TOTCOST", "L2 CostInBOM", "L2 Unti Qty", "L3 Unit Qty"]
        numeric_columns_dispensing = ["Qty", "Value"]
        numeric_columns_raw_materials = ["SOH"]

        st.session_state.bom_a_l = optimize_memory(clean_data(st.session_state.bom_a_l, numeric_columns_bom))
        st.session_state.bom_m_z = optimize_memory(clean_data(st.session_state.bom_m_z, numeric_columns_bom))
        st.session_state.dispensing_data = optimize_memory(clean_data(st.session_state.dispensing_data, numeric_columns_dispensing))
        st.session_state.raw_materials = optimize_memory(clean_data(st.session_state.raw_materials, numeric_columns_raw_materials))

        # Analyze data
        st.session_state.analysis_results = analyze_bom_data(
            st.session_state.bom_a_l, 
            st.session_state.bom_m_z, 
            st.session_state.dispensing_data, 
            st.session_state.raw_materials
        )
        
        st.session_state.data_loaded = True
        st.sidebar.success("Data processed successfully!")
    except Exception as e:
        st.sidebar.error(f"An error occurred during data processing: {e}")

def overview_page():
    """Render the Overview page."""
    if not st.session_state.data_loaded:
        st.warning("Please upload and process data first.")
        return

    st.title("BOM Analysis Overview")

    # Metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Products", len(st.session_state.analysis_results["product_metrics"]))
    with col2:
        avg_cost = st.session_state.analysis_results["cost_distribution"]["avg_product_cost"]
        st.metric("Average Product Cost", f"R{avg_cost:.2f}")
    with col3:
        st.metric("Total Components", len(st.session_state.analysis_results["component_usage"]))

    # Product Complexity Chart
    st.subheader("Top 10 Most Complex Products")
    complexity_df = st.session_state.analysis_results["product_complexity"].head(10).reset_index()
    complexity_df.columns = ['Product Code', 'Complexity Score']
    fig = px.bar(complexity_df, x="Product Code", y="Complexity Score", color="Complexity Score",
                 title="Top 10 Most Complex Products", color_continuous_scale="Viridis")
    st.plotly_chart(fig, use_container_width=True)
    analysis_results = st.session_state.analysis_results["product_complexity"].reset_index()
    st.subheader("Product Complexity Heatmap")
    complexity_df = analysis_results
    complexity_df.columns = ['Product Code', 'Complexity Score']
    fig = px.density_heatmap(
        complexity_df,
        x="Product Code",
        y="Complexity Score",
        color_continuous_scale="Blues",
        title="Complexity Distribution by Product"
    )
    st.plotly_chart(fig, use_container_width=True)


    # Holt-Winters Stock Dispensing Forecast
    if not st.session_state.dispensing_data.empty:
        st.subheader("Stock Dispensing Forecast Using Holt-Winters")
        try:
            # Convert "Date" column to datetime
            st.session_state.dispensing_data["Date"] = pd.to_datetime(st.session_state.dispensing_data["Date"], errors="coerce")
            
            # Drop rows with invalid or missing dates
            dispensing_data = st.session_state.dispensing_data.dropna(subset=["Date"])
            
            # Sort data by date
            dispensing_data = dispensing_data.sort_values("Date")
            
            # Check if data is non-empty
            if not dispensing_data.empty:
                # Fit the Holt-Winters model
                model = ExponentialSmoothing(
                    dispensing_data["Qty"],
                    trend="add",
                    seasonal="add",
                    seasonal_periods=12
                )
                fitted_model = model.fit()
                
                # Forecast for 30 steps
                forecast = fitted_model.forecast(steps=30)
                
                # Create a forecast DataFrame
                forecast_dates = pd.date_range(
                    start=dispensing_data["Date"].iloc[-1], periods=30, freq="D"
                )
                forecast_df = pd.DataFrame({"Date": forecast_dates, "Qty": forecast})
                
                # Plot original and forecasted data
                fig = px.line(dispensing_data, x="Date", y="Qty", title="Holt-Winters Stock Forecast")
                fig.add_scatter(x=forecast_df["Date"], y=forecast_df["Qty"], mode="lines", name="Forecast")
                st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error(f"An error occurred while processing the Dispensing Data: {e}")

# Similar modifications for other pages (product_metrics_page, component_analysis_page, cost_analysis_page)
def product_metrics_page():
    """Product Metrics Analysis Page."""
    if not st.session_state.data_loaded:
        st.warning("Please upload and process data first.")
        return

    st.title("Product Metrics Analysis")

    # Select product
    products = st.session_state.analysis_results["product_metrics"].index.tolist()
    selected_product = st.selectbox("Select Product to Analyze", ["All Products"] + products)

    if selected_product == "All Products":
        st.subheader("Aggregate Metrics for All Products")
        total_components = st.session_state.analysis_results["product_metrics"]["component_count"].sum()
        total_cost = st.session_state.analysis_results["product_metrics"]["TOTCOST"].sum()

        col1, col2 = st.columns(2)
        with col1:
            create_metric_card("Total Components", total_components)
        with col2:
            create_metric_card("Total Cost", f"R{total_cost:,.2f}")
    else:
        st.subheader(f"Metrics for Product: {selected_product}")
        product_data = st.session_state.analysis_results["product_metrics"].loc[selected_product]

        col1, col2, col3 = st.columns(3)
        with col1:
            create_metric_card("Component Count", product_data["component_count"])
        with col2:
            create_metric_card("Total Cost", f"R{product_data['TOTCOST']:,.2f}")
        with col3:
            create_metric_card("Component Cost", f"R{product_data['total_component_cost']:,.2f}")
   
    st.subheader("Compare Products")
    product_1 = st.selectbox("Select First Product", st.session_state.analysis_results["product_metrics"].index)
    product_2 = st.selectbox("Select Second Product", st.session_state.analysis_results["product_metrics"].index)

    comparison = pd.DataFrame({
        "Metric": ["Total Cost", "Component Count"],
        "Product 1": [st.session_state.analysis_results["product_metrics"].loc[product_1, "TOTCOST"], 
                    st.session_state.analysis_results["product_metrics"].loc[product_1, "component_count"]],
        "Product 2": [st.session_state.analysis_results["product_metrics"].loc[product_2, "TOTCOST"], 
                    st.session_state.analysis_results["product_metrics"].loc[product_2, "component_count"]],
    })
    st.table(comparison)

def component_analysis_page():
    """Component Analysis Page."""
    if not st.session_state.data_loaded:
        st.warning("Please upload and process data first.")
        return

    st.title("Component Analysis")

    # Top Components Usage
    st.subheader("Most Used Components")
    top_components = st.session_state.analysis_results["component_usage"].head(10)
    fig = px.bar(top_components, y=top_components.index, x="used_in_products", orientation="h",
                 title="Top 10 Most Used Components")
    st.plotly_chart(fig, use_container_width=True)

    # Component Cost vs Quantity Correlation
    st.subheader("Component Cost vs Quantity Correlation")
    fig = px.scatter(
        st.session_state.analysis_results["component_usage"],
        x="avg_cost",
        y="avg_quantity",
        size="used_in_products",
        color="avg_cost",
        hover_name=st.session_state.analysis_results["component_usage"].index,
        title="Cost vs Quantity Correlation",
        labels={"avg_cost": "Average Cost", "avg_quantity": "Average Quantity"}
    )
    st.plotly_chart(fig, use_container_width=True)

def cost_analysis_page():
    """Cost Analysis Page."""
    if not st.session_state.data_loaded:
        st.warning("Please upload and process data first.")
        return

    st.title("Cost Analysis")

    # Metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total BOM Cost", f"R{st.session_state.analysis_results['cost_distribution']['total_bom_cost']:,.2f}")
    with col2:
        st.metric("Average Product Cost", f"R{st.session_state.analysis_results['cost_distribution']['avg_product_cost']:,.2f}")
    with col3:
        median_cost = st.session_state.analysis_results['cost_distribution']['cost_percentiles'][0.5]
        st.metric("Median Cost", f"R{median_cost:,.2f}")
    
    st.subheader("Cost Distribution Across Products")
    cost_df = st.session_state.analysis_results["product_metrics"][["TOTCOST"]].reset_index()
    fig = px.box(
        cost_df,
        y="TOTCOST",
        points="all",
        title="Product Cost Distribution",
        labels={"TOTCOST": "Total Cost"},
    )
    st.plotly_chart(fig, use_container_width=True)

def search_and_requirements_page():
    """Render the Search & Requirements page with enhanced requirements information."""
    if not st.session_state.data_loaded:
        st.warning("Please upload and process data first.")
        return

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
                st.session_state.bom_a_l, 
                st.session_state.bom_m_z, 
                st.session_state.analysis_results
            )

            if not requirements.empty:
                # Color coding for stock status
                def color_status(val):
                    color = 'green' if val == 'Sufficient' else 'red'
                    return f'color: {color}'

                # Display requirements in a styled table
                st.dataframe(
                    requirements.style.applymap(color_status, subset=['Stock Status']), 
                    use_container_width=True
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
def main():
    if page == "Overview":
        overview_page()
    elif page == "Product Metrics":
        product_metrics_page()
    elif page == "Component Analysis":
        component_analysis_page()
    elif page == "Cost Analysis":
        cost_analysis_page()
    elif page == "Search & Requirements":
        search_and_requirements_page()

# Call the main function
main()
