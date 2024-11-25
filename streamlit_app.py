import streamlit as st
import pandas as pd
import plotly
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
from analyze_bom_data import analyze_bom_data
from generate_insights import generate_insights
from save_analysis_results_to_excel import save_analysis_results_to_excel

# Set page config
st.set_page_config(page_title="BOM Analysis Dashboard", layout="wide")

# Custom CSS for styling
st.markdown("""
    <style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 5px;
        padding: 20px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    }
    .wide-metric {
        min-width: 400px;  /* Increased width for average cost metric */
    }
    div[data-testid="metric-container"] {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 5px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
        width: 100%;
    }
    /* Make the average cost metric wider */
    div[data-testid="metric-container"]:has(label:contains("Average Product Cost")) {
        width: 150%;
        margin-right: -50%;
    }
    </style>
""", unsafe_allow_html=True)


# Sidebar navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio("Select Page", 
    ["Overview", "Product Metrics", "Component Analysis", "Cost Analysis"])

# File upload section in sidebar
st.sidebar.header("Upload BOM Files")
uploaded_file_a_l = st.sidebar.file_uploader("Upload BOM Data (A-L)", type=["csv", "xlsx"])
uploaded_file_m_z = st.sidebar.file_uploader("Upload BOM Data (M-Z)", type=["csv", "xlsx"])

def create_metric_card(title, value, delta=None):
    col1, col2 = st.columns([1, 1])
    with col1:
        st.metric(label=title, value=value, delta=delta)

def overview_page(analysis_results):
    st.title("BOM Analysis Overview")
    
    # Modified column layout to give more space to the average cost metric
    col1, col2, col3 = st.columns([1, 1.5, 1])  # Adjusted column widths
    with col1:
        total_products = len(analysis_results["product_metrics"])
        create_metric_card("Total Products", total_products)
    
    with col2:
        avg_cost = analysis_results["cost_distribution"]["avg_product_cost"]
        # Format with thousands separator
        formatted_cost = "R{:,.2f}".format(avg_cost)
        create_metric_card("Average Product Cost", formatted_cost)
    
    with col3:
        total_components = len(analysis_results["component_usage"])
        create_metric_card("Total Components", total_components)

    # Product Complexity Chart
    st.subheader("Product Complexity Distribution")

    # Convert the complexity data to a DataFrame for better manipulation
    complexity_df = analysis_results["product_complexity"].head(10).reset_index()
    complexity_df.columns = ['Product Code', 'Complexity Score']

    # Create a color scale based on complexity scores
    fig = px.bar(
        complexity_df,
        x='Product Code',
        y='Complexity Score',
        title='Top 10 Most Complex Products',
        # Add color gradient based on complexity score
        color='Complexity Score',
        # Choose a color scheme - you can try different options:
        # 'Viridis', 'Plasma', 'Blues', 'RdYlBu', etc.
        color_continuous_scale='Viridis',
        # Add hover data
        hover_data={
            'Product Code': True,
            'Complexity Score': ':.2f'
        }
    )

    # Customize the layout
    fig.update_layout(
        # Adjust bar width
        bargap=0.2,
        # Add background color
        plot_bgcolor='white',
        # Customize title
        title={
            'text': 'Top 10 Most Complex Products',
            'y':0.95,
            'x':0.5,
            'xanchor': 'center',
            'yanchor': 'top',
            'font': {'size': 20}
        },
        # Customize x-axis
        xaxis={
            'title': 'Product Code',
            'tickangle': -45,
            'gridcolor': 'lightgray',
            'showgrid': False
        },
        # Customize y-axis
        yaxis={
            'title': 'Complexity Score',
            'gridcolor': 'lightgray',
            'showgrid': True
        },
        # Add border
        shapes=[
            dict(
                type='rect',
                xref='paper',
                yref='paper',
                x0=0,
                y0=0,
                x1=1,
                y1=1,
                line={'width': 1, 'color': 'lightgray'}
            )
        ]
    )

    # Update color bar
    fig.update_coloraxes(
        colorbar_title='Complexity<br>Score',
        colorbar_thickness=15,
        colorbar_len=0.6,
        colorbar_title_font={'size': 12}
    )

    # Show the chart
    st.plotly_chart(fig, use_container_width=True)

    # Generated Insights
    st.subheader("Key Insights")
    insights = generate_insights(analysis_results)
    for insight in insights:
        st.info(insight)

def product_metrics_page(analysis_results):
    st.title("Product Metrics Analysis")
    
    # Add "All Products" to the product selector options
    products = analysis_results["product_metrics"].index.tolist()
    products.insert(0, "All Products")  # Add "All Products" at the beginning of the list
    selected_product = st.selectbox("Select Product to Analyze", products)
    
    if selected_product == "All Products":
        # Show aggregate statistics and visualizations for all products
        st.subheader("Aggregate Metrics for All Products")
        
        # Aggregate Metrics
        total_components = analysis_results["product_metrics"]["component_count"].sum()
        total_cost = analysis_results["product_metrics"]["TOTCOST"].sum()
        total_component_cost = analysis_results["product_metrics"]["total_component_cost"].sum()
        
        col1, col2, col3 = st.columns([0.9, 1.7, 1.6])
        with col1:
            create_metric_card("Total Components", total_components)
        with col2:
            create_metric_card("Total Cost", f"R{total_cost:,.0f}")
        with col3:
            create_metric_card("Total Component Cost", f"R{total_component_cost:,.0f}")
        
        # Visualization: Bar chart for total cost by product
        st.subheader("Total Cost by Product")
        fig = px.bar(
            analysis_results["product_metrics"], 
            x=analysis_results["product_metrics"].index, 
            y="TOTCOST",
            title="Total Cost for All Products",
            labels={"x": "Product", "TOTCOST": "Total Cost"}
        )
        st.plotly_chart(fig, use_container_width=True)
        
    else:
        # Show metrics for the selected product
        st.subheader(f"Metrics for Product: {selected_product}")
        product_data = analysis_results["product_metrics"].loc[selected_product]
        
        col1, col2, col3 = st.columns(3)
        with col1:
            create_metric_card("Component Count", int(product_data["component_count"]))
        with col2:
            create_metric_card("Total Cost", f"R{product_data['TOTCOST']:,.2f}")
        with col3:
            create_metric_card("Component Cost", f"R{product_data['total_component_cost']:,.2f}")

        # Visualization: Production quantity range
        st.subheader("Production Quantity Range")
        qty_data = {
            'Type': ['Minimum', 'Maximum'],
            'Quantity': [product_data['MIN_QTY_TO_PRODUCE'], product_data['MAX_QTY_TO_PRODUCE']]
        }
        fig = px.bar(qty_data, x='Type', y='Quantity',
                     title=f"Production Quantity Range for {selected_product}")
        st.plotly_chart(fig, use_container_width=True)

def component_analysis_page(analysis_results):
    st.title("Component Analysis")
    
    # Top Components Usage Chart
    st.subheader("Most Used Components")
    top_components = analysis_results["component_usage"].head(10)
    fig = px.bar(top_components, y=top_components.index, x='used_in_products',
                 title="Top 10 Most Used Components",
                 labels={"used_in_products": "Number of Products",
                        "index": "Component Code"})
    st.plotly_chart(fig, use_container_width=True)
    
    # Component Cost Analysis
    st.subheader("Component Cost Analysis")
    fig = px.scatter(analysis_results["component_usage"],
                    x='avg_cost', y='avg_quantity',
                    hover_data=['used_in_products'],
                    title="Component Cost vs Quantity Distribution")
                    
    st.plotly_chart(fig, use_container_width=True)

def cost_analysis_page(analysis_results):
    st.title("Cost Analysis")
    
    # Cost Distribution Stats
    col1, col2, col3 = st.columns([1.6, 1.3, 1])


    with col1:
        create_metric_card("Total BOM Cost", 
                         f"R{analysis_results['cost_distribution']['total_bom_cost']:,.0f}")
    with col2:
        create_metric_card("Ave Prod Cost",
                         f"R{analysis_results['cost_distribution']['avg_product_cost']:,.1f}")
    with col3:
        create_metric_card("Median Cost",
                         f"R{analysis_results['cost_distribution']['cost_percentiles'][0.5]:,.2f}")

    # Cost Distribution Chart
    product_costs = analysis_results["product_metrics"]["TOTCOST"]
    fig = px.histogram(product_costs,
                      title="Product Cost Distribution",
                      labels={"value": "Cost (R)", "count": "Number of Products"})
    st.plotly_chart(fig, use_container_width=True)
    
    # Cost Percentiles
    st.subheader("Cost Percentiles")
    percentiles = pd.Series(analysis_results["cost_distribution"]["cost_percentiles"])
    fig = go.Figure(data=[go.Box(y=product_costs)])
    fig.update_layout(title="Product Cost Box Plot")
    st.plotly_chart(fig, use_container_width=True)

if uploaded_file_a_l and uploaded_file_m_z:
    try:
        # Load BOM Data
        bom_a_l = pd.read_excel(uploaded_file_a_l) if uploaded_file_a_l.name.endswith(".xlsx") else pd.read_csv(uploaded_file_a_l)
        bom_m_z = pd.read_excel(uploaded_file_m_z) if uploaded_file_m_z.name.endswith(".xlsx") else pd.read_csv(uploaded_file_m_z)
        
        # Analyze Data
        analysis_results = analyze_bom_data(bom_a_l, bom_m_z)
        
        # Display selected page
        if page == "Overview":
            overview_page(analysis_results)
        elif page == "Product Metrics":
            product_metrics_page(analysis_results)
        elif page == "Component Analysis":
            component_analysis_page(analysis_results)
        else:
            cost_analysis_page(analysis_results)
        
        # Download button
        st.sidebar.subheader("Download Analysis")
        buffer = BytesIO()
        save_analysis_results_to_excel(analysis_results, buffer)
        buffer.seek(0)
        
        st.sidebar.download_button(
            label="Download Analysis Results",
            data=buffer,
            file_name="bom_analysis_results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
    except Exception as e:
        st.error(f"An error occurred during analysis: {e}")
else:
    st.info("Please upload both BOM files (A-L and M-Z) to proceed.")
