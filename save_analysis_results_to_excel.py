import pandas as pd

def save_analysis_results_to_excel(analysis_results, buffer):
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        analysis_results["product_metrics"].to_excel(writer, sheet_name="Product_Metrics")
        analysis_results["product_complexity"].to_excel(writer, sheet_name="Product_Complexity")
        analysis_results["component_usage"].to_excel(writer, sheet_name="Component_Usage")
        cost_dist = pd.DataFrame.from_dict(analysis_results["cost_distribution"], orient="index", columns=["Value"])
        cost_dist.to_excel(writer, sheet_name="Cost_Distribution")
