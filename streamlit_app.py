import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
from analyze_bom_data import analyze_bom_data
from generate_insights import generate_insights
from save_analysis_results_to_excel import save_analysis_results_to_excel
from calculate_requirements import calculate_requirements
import dask.dataframe as dd


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
    """Overview page for BOM analysis."""
    st.title("BOM Analysis Overview")

    # Metrics
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col1:
        total_products = len(analysis_results["product_metrics"])
        create_metric_card("Total Products", total_products)

    with col2:
        avg_cost = analysis_results["cost_distribution"]["avg_product_cost"]
        formatted_cost = f"R{avg_cost:,.2f}"
        create_metric_card("Average Product Cost", formatted_cost)

    with col3:
        total_components = len(analysis_results["component_usage"])
        create_metric_card("Total Components", total_components)

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


def search_and_requirements_page(analysis_results, dispensing_data, raw_materials):
    """Search page to analyze product requirements and stock availability."""
    st.title("Search & Requirements")

    # User inputs
    product = st.text_input("Enter Product Code")
    quantity_desired = st.number_input("Desired Quantity", min_value=0, step=1)

    if product and quantity_desired > 0:
        st.subheader(f"Requirements for Producing {quantity_desired} Units of {product}")

        # Calculate requirements
        try:
            requirements = calculate_requirements(
                product, quantity_desired, analysis_results, dispensing_data, raw_materials
            )

            # Display requirements
            if not requirements.empty:
                st.table(requirements)
            else:
                st.warning(f"No requirements found for product: {product}")
        except Exception as e:
            st.error(f"Error calculating requirements: {e}")


if all([uploaded_bom_a_l, uploaded_bom_m_z, uploaded_dispensing, uploaded_raw_materials]):
    try:
        # Function to clean and convert numeric columns
        def clean_data(df, numeric_columns):
            """
            Ensures that specified numeric columns in the dataframe are properly converted.
            Non-numeric values are replaced with 0.
            """
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df

        # Load raw files
        bom_a_l = dd.read_csv(uploaded_bom_a_l) if uploaded_bom_a_l.name.endswith(".xlsx") else pd.read_csv(uploaded_bom_a_l)
        bom_m_z = dd.read_csv(uploaded_bom_m_z) if uploaded_bom_m_z.name.endswith(".xlsx") else pd.read_csv(uploaded_bom_m_z)
        dispensing_data = dd.read_csv(uploaded_dispensing) if uploaded_dispensing.name.endswith(".xlsx") else pd.read_csv(uploaded_dispensing)
        raw_materials = dd.read_csv(uploaded_raw_materials) if uploaded_raw_materials.name.endswith(".xlsx") else pd.read_csv(uploaded_raw_materials)

        # Convert to pandas DataFrame when necessary
        bom_a_l = bom_a_l.compute()
        bom_m_z = bom_m_z.compute()
        
        # Define numeric columns to clean
        numeric_columns_bom = ["TOTCOST", "L2 CostInBOM", "L2 Unti Qty", "L3 Unit Qty"]
        numeric_columns_dispensing = ["Qty", "Cost", "Value"]
        numeric_columns_raw_materials = ["SOH", "Cost", "Value"]

        # Clean data
        bom_a_l = clean_data(bom_a_l, numeric_columns_bom)
        bom_m_z = clean_data(bom_m_z, numeric_columns_bom)
        dispensing_data = clean_data(dispensing_data, numeric_columns_dispensing)
        raw_materials = clean_data(raw_materials, numeric_columns_raw_materials)

        # Analyze data
        analysis_results = analyze_bom_data(bom_a_l, bom_m_z, dispensing_data, raw_materials)


        # Display selected page
        if page == "Overview":
            overview_page(analysis_results)
        elif page == "Product Metrics":
            product_metrics_page(analysis_results)
        elif page == "Component Analysis":
            component_analysis_page(analysis_results)
        elif page == "Cost Analysis":
            cost_analysis_page(analysis_results)
        else:
            search_and_requirements_page(analysis_results, dispensing_data, raw_materials)

        # Download button
        st.sidebar.subheader("Download Analysis")
        buffer = BytesIO()
        save_analysis_results_to_excel(analysis_results, buffer)
        buffer.seek(0)

        st.sidebar.download_button(
            label="Download Analysis Results",
            data=buffer,
            file_name="enhanced_bom_analysis_results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"An error occurred during analysis: {e}")
else:
    st.info("Please upload all required files to proceed.")
