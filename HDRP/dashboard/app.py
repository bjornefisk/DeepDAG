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
        # Use full_run_id if available, otherwise run_id
        run_id = table_data[selected_rows[0]].get("full_run_id") or table_data[selected_rows[0]]["run_id"]
        return run_id
    return None


# Query execution callbacks
@callback(
    Output("execution-status", "data"),
    Output("current-run-id", "data"),
    Output("query-status", "style"),
    Output("status-poll-interval", "disabled"),
    Output("cancel-query-btn", "style"),
    Input("submit-query-btn", "n_clicks"),
    State("query-input", "value"),
    State("provider-selector", "value"),
    State("max-results-input", "value"),
    State("verbose-selector", "value"),
    prevent_initial_call=True,
)
def submit_query(n_clicks, query, provider, max_results, verbose):
    """Handle query submission."""
    if not n_clicks or not query or not query.strip():
        return no_update, no_update, no_update, no_update, no_update
    
    from HDRP.dashboard.api import get_executor
    
    # Start execution
    executor = get_executor()
    run_id = executor.execute_query(
        query=query.strip(),
        provider=provider,
        mode="python",  # Default to Python mode for simplicity
        max_results=max_results,
        verbose=verbose,
    )
    
    # Show status card and enable polling
    return (
        {"status": "running"},
        run_id,
        {"marginTop": "24px", "display": "block"},
        False,  # Enable polling
        {"fontSize": "0.875rem", "padding": "4px 12px", "display": "inline-block"},  # Show cancel button
    )


@callback(
    Output("query-input", "value"),
    Output("max-results-input", "value"),
    Output("verbose-selector", "value"),
    Input("clear-query-btn", "n_clicks"),
    prevent_initial_call=True,
)
def clear_query_form(n_clicks):
    """Clear the query form."""
    if not n_clicks:
        return no_update, no_update, no_update
    return "", 10, False


@callback(
    Output("query-output", "children"),
    Output("execution-status", "data", allow_duplicate=True),
    Output("status-poll-interval", "disabled", allow_duplicate=True),
    Output("cancel-query-btn", "style", allow_duplicate=True),
    Input("status-poll-interval", "n_intervals"),
    State("current-run-id", "data"),
    prevent_initial_call=True,
)
def poll_execution_status(n_intervals, run_id):
    """Poll execution status and update display."""
    if not run_id:
        return no_update, no_update, no_update, no_update
    
    from HDRP.dashboard.api import get_executor
    
    executor = get_executor()
    status_data = executor.get_status(run_id)
    
    if not status_data:
        return "Execution not found.", {"status": "error"}, True, {"display": "none"}
    
    status = status_data["status"]
    
    # Build status display
    output = html.Div([
        html.Div([
            html.Strong("Run ID: "),
            html.Code(run_id[:8] + "...", style={"color": "#58a6ff"}),
        ], style={"marginBottom": "8px"}),
        
        html.Div([
            html.Strong("Status: "),
            html.Span(
                status.upper(),
                style={
                    "color": "#3fb950" if status == "completed" else
                           "#f85149" if status == "failed" else
                           "#d29922" if status == "cancelled" else "#58a6ff",
                    "fontWeight": "bold",
                }
            ),
        ], style={"marginBottom": "8px"}),
        
        html.Div([
            html.Strong("Progress: "),
            html.Span(f"{status_data['progress_percent']:.0f}%"),
        ], style={"marginBottom": "8px"}),
        
        html.Div([
            html.Div(
                style={
                    "width": f"{status_data['progress_percent']}%",
                    "height": "8px",
                    "backgroundColor": "#3fb950" if status == "completed" else "#58a6ff",
                    "borderRadius": "4px",
                    "transition": "width 0.3s ease",
                }
            ),
        ], style={
            "width": "100%",
            "height": "8px",
            "backgroundColor": "#21262d",
            "borderRadius": "4px",
            "marginBottom": "16px",
            "overflow": "hidden",
        }),
        
        html.Div([
            html.Strong("Current Stage: "),
            html.Span(status_data["current_stage"]),
        ], style={"marginBottom": "8px"}),
        
        # Show claim stats if available
        html.Div([
            html.Div([
                html.Strong("Claims Extracted: "),
                html.Span(str(status_data.get("claims_extracted", 0))),
            ], style={"marginRight": "16px", "display": "inline-block"}),
            html.Div([
                html.Strong("Verified: "),
                html.Span(str(status_data.get("claims_verified", 0)), style={"color": "#3fb950"}),
            ], style={"marginRight": "16px", "display": "inline-block"}),
            html.Div([
                html.Strong("Rejected: "),
                html.Span(str(status_data.get("claims_rejected", 0)), style={"color": "#f85149"}),
            ], style={"display": "inline-block"}),
        ], style={"marginBottom": "16px"}) if status_data.get("claims_extracted", 0) > 0 else None,
        
        # Show error message if failed
        html.Div([
            html.Strong("Error: ", style={"color": "#f85149"}),
            html.Pre(
                status_data["error_message"],
                style={
                    "backgroundColor": "#21262d",
                    "padding": "12px",
                    "borderRadius": "6px",
                    "marginTop": "8px",
                    "whiteSpace": "pre-wrap",
                    "wordWrap": "break-word",
                }
            ),
        ]) if status_data.get("error_message") else None,
        
        # Show completion message with link to run history
        html.Div([
            html.Div("✓ Execution completed successfully!", style={"marginBottom": "12px", "color": "#3fb950", "fontSize": "1.1rem"}),
            html.Div([
                html.Span("View in "),
                dcc.Link(
                    "Run History",
                    href="/runs",
                    style={"color": "#58a6ff", "textDecoration": "none", "fontWeight": "bold"},
                ),
                html.Span(" or check "),
                dcc.Link(
                    "Claims",
                    href="/claims",
                    style={"color": "#58a6ff", "textDecoration": "none", "fontWeight": "bold"},
                ),
            ]),
        ], style={
            "marginTop": "16px",
            "padding": "12px",
            "backgroundColor": "rgba(63, 185, 80, 0.1)",
            "borderRadius": "6px",
            "border": "1px solid #3fb950",
        }) if status == "completed" else None,
    ])
    
    # Disable polling if execution is complete
    should_poll = status in ["queued", "running"]
    hide_cancel = {"fontSize": "0.875rem", "padding": "4px 12px", "display": "none"} if not should_poll else no_update
    
    return output, {"status": status}, not should_poll, hide_cancel


@callback(
    Output("execution-status", "data", allow_duplicate=True),
    Output("query-output", "children", allow_duplicate=True),
    Input("cancel-query-btn", "n_clicks"),
    State("current-run-id", "data"),
    prevent_initial_call=True,
)
def cancel_query(n_clicks, run_id):
    """Cancel running query."""
    if not n_clicks or not run_id:
        return no_update, no_update
    
    from HDRP.dashboard.api import get_executor
    
    executor = get_executor()
    cancelled = executor.cancel_query(run_id)
    
    if cancelled:
        return (
            {"status": "cancelled"},
            html.Div("Query execution cancelled.", style={"color": "#d29922"}),
        )
    
    return no_update, html.Div("Failed to cancel query.", style={"color": "#f85149"})



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
