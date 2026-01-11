#!/usr/bin/env python3
"""
HDRP Dashboard - Main Application

Dash-based web UI for monitoring HDRP research runs.
Run with: python -m HDRP.dashboard.app
"""

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dash import Dash, html, dcc, callback, Output, Input, State, ctx, no_update
import dash

from HDRP.dashboard.layout import create_layout
from HDRP.dashboard.pages.dashboard import create_dashboard_page
from HDRP.dashboard.pages.runs import create_runs_page
from HDRP.dashboard.pages.claims import create_claims_page
from HDRP.dashboard.pages.dag import create_dag_page
from HDRP.dashboard.pages.metrics import create_metrics_page
from HDRP.dashboard.pages.query import create_query_page
from HDRP.dashboard.data_loader import load_run


# Initialize the Dash app
app = Dash(
    __name__,
    title="HDRP Dashboard",
    update_title=None,
    suppress_callback_exceptions=True,
    assets_folder="assets",
)

# Set the layout
app.layout = create_layout()


# Page routing callback
@callback(
    Output("page-content", "children"),
    Output("nav-dashboard", "className"),
    Output("nav-runs", "className"),
    Output("nav-claims", "className"),
    Output("nav-dag", "className"),
    Output("nav-metrics", "className"),
    Output("nav-query", "className"),
    Input("url", "pathname"),
    Input("nav-dashboard", "n_clicks"),
    Input("nav-runs", "n_clicks"),
    Input("nav-claims", "n_clicks"),
    Input("nav-dag", "n_clicks"),
    Input("nav-metrics", "n_clicks"),
    Input("nav-query", "n_clicks"),
    State("selected-run-id", "data"),
    prevent_initial_call=False,
)
def route_page(pathname, n_dash, n_runs, n_claims, n_dag, n_metrics, n_query, selected_run_id):
    """Route to the appropriate page based on URL or navigation clicks."""
    
    # Determine which page to show
    triggered_id = ctx.triggered_id if ctx.triggered_id else None
    
    if triggered_id == "nav-runs" or pathname == "/runs":
        page = "runs"
    elif triggered_id == "nav-claims" or pathname == "/claims":
        page = "claims"
    elif triggered_id == "nav-dag" or pathname == "/dag":
        page = "dag"
    elif triggered_id == "nav-metrics" or pathname == "/metrics":
        page = "metrics"
    elif triggered_id == "nav-query" or pathname == "/query":
        page = "query"
    else:
        page = "dashboard"
    
    # Generate page content
    if page == "runs":
        content = create_runs_page()
    elif page == "claims":
        content = create_claims_page(selected_run_id)
    elif page == "dag":
        content = create_dag_page(selected_run_id)
    elif page == "metrics":
        content = create_metrics_page(selected_run_id)
    elif page == "query":
        content = create_query_page()
    else:
        content = create_dashboard_page()
    
    # Set active nav link classes
    base = "nav-link"
    active = "nav-link active"
    
    return (
        content,
        active if page == "dashboard" else base,
        active if page == "runs" else base,
        active if page == "claims" else base,
        active if page == "dag" else base,
        active if page == "metrics" else base,
        active if page == "query" else base,
    )


# Run selector callbacks for Claims page
@callback(
    Output("page-content", "children", allow_duplicate=True),
    Input("claims-run-selector", "value"),
    prevent_initial_call=True,
)
def update_claims_page(run_id):
    """Update claims page when run is selected."""
    if run_id:
        return create_claims_page(run_id)
    return no_update


# Run selector callbacks for DAG page
@callback(
    Output("page-content", "children", allow_duplicate=True),
    Input("dag-run-selector", "value"),
    prevent_initial_call=True,
)
def update_dag_page(run_id):
    """Update DAG page when run is selected."""
    if run_id:
        return create_dag_page(run_id)
    return no_update


# DAG layout update
@callback(
    Output("dag-cytoscape", "layout"),
    Input("dag-layout-selector", "value"),
    prevent_initial_call=True,
)
def update_dag_layout(layout_name):
    """Update DAG layout."""
    if layout_name == "dagre":
        return {'name': 'dagre', 'rankDir': 'TB', 'spacingFactor': 1.5}
    elif layout_name == "breadthfirst":
        return {'name': 'breadthfirst', 'roots': '[id = "query"]', 'spacingFactor': 1.5}
    else:
        return {'name': layout_name}


# Run selector callbacks for Metrics page
@callback(
    Output("page-content", "children", allow_duplicate=True),
    Input("metrics-run-selector", "value"),
    prevent_initial_call=True,
)
def update_metrics_page(run_id):
    """Update metrics page when run is selected."""
    if run_id:
        return create_metrics_page(run_id)
    return no_update


# Store selected run from runs table
@callback(
    Output("selected-run-id", "data"),
    Input("runs-table", "selected_rows"),
    State("runs-table", "data"),
    prevent_initial_call=True,
)
def store_selected_run(selected_rows, table_data):
    """Store the selected run ID."""
    if selected_rows and table_data:
        run_id = table_data[selected_rows[0]]["run_id"]
        return run_id
    return None


def main():
    """Run the dashboard server."""
    import argparse
    
    parser = argparse.ArgumentParser(description="HDRP Dashboard")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8050, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    
    args = parser.parse_args()
    
    print(f"\n{'='*50}")
    print("  HDRP Dashboard")
    print(f"{'='*50}")
    print(f"  URL: http://{args.host}:{args.port}")
    print(f"  Debug: {args.debug}")
    print(f"{'='*50}\n")
    
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
