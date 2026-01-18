#!/usr/bin/env python3
"""
HDRP Dashboard - Main Application

Dash-based web UI for monitoring HDRP research runs.
Run with: python -m HDRP.dashboard.app
"""

import os
import sys
import json

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dash import Dash, html, dcc, callback, Output, Input, State, ctx, no_update, clientside_callback
import dash

from HDRP.dashboard.layout import create_layout
from HDRP.dashboard.pages.dashboard import create_dashboard_page
from HDRP.dashboard.pages.runs import create_runs_page
from HDRP.dashboard.pages.claims import create_claims_page
from HDRP.dashboard.pages.dag import create_dag_page
from HDRP.dashboard.pages.metrics import create_metrics_page
from HDRP.dashboard.pages.query import create_query_page
from HDRP.dashboard.pages.reports import create_reports_page
from HDRP.dashboard.data_loader import load_run, load_report_content


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


# Add SSE endpoint for progress streaming
@app.server.route('/api/progress/<run_id>')
def stream_progress(run_id: str):
    """
    Server-Sent Events endpoint for streaming execution progress.
    
    Usage in browser:
        const eventSource = new EventSource('/api/progress/{run_id}');
        eventSource.onmessage = (e) => {
            const data = JSON.parse(e.data);
            // Update UI with progress data
        };
    """
    import queue
    from flask import Response, stream_with_context
    from HDRP.dashboard.api import get_executor
    
    executor = get_executor()
    
    # Check if run exists
    status = executor.get_status(run_id)
    if not status:
        return Response(
            json.dumps({"error": f"Run {run_id} not found"}),
            status=404,
            mimetype='application/json'
        )
    
    # Subscribe to progress updates
    progress_queue = executor.subscribe(run_id)
    
    def generate():
        """Generate SSE events from progress queue."""
        try:
            while True:
                try:
                    # Wait for progress update (timeout to check if run is complete)
                    progress_data = progress_queue.get(timeout=1.0)
                    
                    # Format as SSE message
                    data = json.dumps(progress_data)
                    yield f"data: {data}\n\n"
                    
                    # Stop streaming if execution is complete
                    status = progress_data.get("status")
                    if status in ["completed", "failed", "cancelled"]:
                        break
                        
                except queue.Empty:
                    # Check if execution is still running
                    current_status = executor.get_status(run_id)
                    if current_status:
                        status = current_status.get("status")
                        if status in ["completed", "failed", "cancelled"]:
                            # Send final status before closing
                            data = json.dumps(current_status)
                            yield f"data: {data}\n\n"
                            break
                    # Continue waiting if still running
                    yield ": heartbeat\n\n"  # Keep connection alive
        except GeneratorExit:
            pass
        finally:
            # Unsubscribe when client disconnects
            executor.unsubscribe(run_id, progress_queue)
    
    response = Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',  # Disable buffering in nginx
            'Connection': 'keep-alive',
        }
    )
    return response


# Page routing callback
@callback(
    Output("page-content", "children"),
    Output("nav-dashboard", "className"),
    Output("nav-reports", "className"),
    Output("nav-runs", "className"),
    Output("nav-claims", "className"),
    Output("nav-dag", "className"),
    Output("nav-metrics", "className"),
    Output("nav-query", "className"),
    Input("url", "pathname"),
    Input("nav-dashboard", "n_clicks"),
    Input("nav-reports", "n_clicks"),
    Input("nav-runs", "n_clicks"),
    Input("nav-claims", "n_clicks"),
    Input("nav-dag", "n_clicks"),
    Input("nav-metrics", "n_clicks"),
    Input("nav-query", "n_clicks"),
    State("selected-run-id", "data"),
    prevent_initial_call=False,
)
def route_page(pathname, n_dash, n_reports, n_runs, n_claims, n_dag, n_metrics, n_query, selected_run_id):
    """Route to the appropriate page based on URL or navigation clicks."""
    
    # Determine which page to show
    triggered_id = ctx.triggered_id if ctx.triggered_id else None
    
    if triggered_id == "nav-reports" or pathname == "/reports":
        page = "reports"
    elif triggered_id == "nav-runs" or pathname == "/runs":
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
    if page == "reports":
        content = create_reports_page(selected_run_id)
    elif page == "runs":
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
        active if page == "reports" else base,
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


# Run selector callbacks for Reports page
@callback(
    Output("page-content", "children", allow_duplicate=True),
    Input("report-selector", "value"),
    prevent_initial_call=True,
)
def update_reports_page(run_id):
    """Update reports page when run is selected."""
    if run_id:
        return create_reports_page(run_id)
    return no_update


# Download report callback
@callback(
    Output("download-report", "data"),
    Input("download-report-btn", "n_clicks"),
    State("report-selector", "value"),
    prevent_initial_call=True,
)
def download_report(n_clicks, run_id):
    """Download the selected report as markdown."""
    if not n_clicks or not run_id:
        return no_update
    
    content = load_report_content(run_id)
    if not content:
        return no_update
    
    return dict(content=content, filename=f"report_{run_id[:8]}.md")


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


# Client-side callback for SSE connection
# This sets up EventSource and periodically updates the store with latest progress
clientside_callback(
    """
    function(runId, pollInterval) {
        // Initialize window variables if needed
        if (!window.hdrpSSEInitialized) {
            window.hdrpSSEInitialized = true;
            window.hdrpLatestProgress = null;
            window.hdrpEventSource = null;
        }
        
        if (!runId || runId === 'null' || runId === 'None') {
            // Clean up
            if (window.hdrpEventSource) {
                window.hdrpEventSource.close();
                window.hdrpEventSource = null;
            }
            window.hdrpLatestProgress = null;
            return null;
        }
        
        // Close existing connection if runId changed
        if (window.hdrpEventSource) {
            const currentUrl = window.hdrpEventSource.url;
            const expectedUrl = `/api/progress/${runId}`;
            if (!currentUrl.endsWith(expectedUrl)) {
                window.hdrpEventSource.close();
                window.hdrpEventSource = null;
            }
        }
        
        // Start SSE connection if not already connected
        if (!window.hdrpEventSource && typeof EventSource !== 'undefined') {
            const eventSource = new EventSource(`/api/progress/${runId}`);
            window.hdrpEventSource = eventSource;
            
            // Store progress data when SSE messages arrive
            eventSource.onmessage = function(event) {
                try {
                    const progressData = JSON.parse(event.data);
                    window.hdrpLatestProgress = progressData;
                } catch (e) {
                    console.error('Error parsing SSE data:', e);
                }
            };
            
            eventSource.onerror = function(error) {
                console.error('SSE connection error:', error);
                if (window.hdrpEventSource) {
                    window.hdrpEventSource.close();
                    window.hdrpEventSource = null;
                }
            };
        }
        
        // Return latest progress data (updated by EventSource onmessage)
        // This callback is triggered by pollInterval input, so we check
        // window.hdrpLatestProgress each time it runs
        return window.hdrpLatestProgress || null;
    }
    """,
    Output("sse-progress-data", "data"),
    [Input("current-run-id", "data"), Input("status-poll-interval", "n_intervals")],
    prevent_initial_call=False,
)


@callback(
    Output("query-output", "children"),
    Output("execution-status", "data", allow_duplicate=True),
    Output("status-poll-interval", "disabled", allow_duplicate=True),
    Output("cancel-query-btn", "style", allow_duplicate=True),
    Input("status-poll-interval", "n_intervals"),
    Input("sse-progress-data", "data"),  # Also triggered by SSE updates
    State("current-run-id", "data"),
    prevent_initial_call=True,
)
def poll_execution_status(n_intervals, sse_data, run_id):
    """Poll execution status and update display. Prefer SSE data when available."""
    if not run_id:
        return no_update, no_update, no_update, no_update
    
    from HDRP.dashboard.api import get_executor
    
    # Prefer SSE data if available, otherwise poll executor
    if sse_data:
        status_data = sse_data
    else:
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


# Toggle detailed progress section
@callback(
    Output("detailed-progress-content", "style"),
    Output("toggle-detailed-progress", "children"),
    Input("toggle-detailed-progress", "n_clicks"),
    State("detailed-progress-content", "style"),
    prevent_initial_call=True,
)
def toggle_detailed_progress(n_clicks, current_style):
    """Toggle the detailed progress section visibility."""
    if not current_style or current_style.get("display") == "none":
        # Show detailed progress
        return (
            {"display": "block", "padding": "16px"},
            [html.Span("▲", style={"marginRight": "8px", "transition": "transform 0.2s"}), "Hide Detailed Progress"],
        )
    else:
        # Hide detailed progress
        return (
            {"display": "none", "padding": "16px"},
            [html.Span("▼", style={"marginRight": "8px", "transition": "transform 0.2s"}), "Show Detailed Progress"],
        )


# Update detailed progress content
@callback(
    Output("detailed-progress-section", "style"),
    Output("stage-timeline", "children"),
    Output("live-stats", "children"),
    Output("activity-log", "children"),
    Input("status-poll-interval", "n_intervals"),
    State("current-run-id", "data"),
    prevent_initial_call=True,
)
def update_detailed_progress(n_intervals, run_id):
    """Update detailed progress information."""
    if not run_id:
        return no_update, no_update, no_update, no_update
    
    from HDRP.dashboard.api import get_executor
    from HDRP.dashboard.data_loader import get_latest_events, get_run_progress
    
    executor = get_executor()
    status_data = executor.get_status(run_id)
    
    if not status_data or status_data["status"] in ["completed", "failed", "cancelled"]:
        # Hide detailed section on completion
        return {"display": "none"}, no_update, no_update, no_update
    
    # Show detailed section during execution
    section_style = {"borderTop": "1px solid #30363d", "display": "block"}
    
    # Build stage timeline
    stages = [
        ("Initializing", 0, 10),
        ("Research", 10, 40),
        ("Verification", 40, 80),
        ("Synthesis", 80, 100),
    ]
    
    current_progress = status_data.get("progress_percent", 0)
    
    timeline_items = []
    for stage_name, start_pct, end_pct in stages:
        is_complete = current_progress >= end_pct
        is_current = start_pct <= current_progress < end_pct
        
        icon_style = {
            "display": "inline-block",
            "width": "20px",
            "height": "20px",
            "borderRadius": "50%",
            "marginRight": "12px",
            "border": "2px solid",
        }
        
        if is_complete:
            icon_style["backgroundColor"] = "#3fb950"
            icon_style["borderColor"] = "#3fb950"
            icon = "✓"
        elif is_current:
            icon_style["backgroundColor"] = "#58a6ff"
            icon_style["borderColor"] = "#58a6ff"
            icon = "●"
        else:
            icon_style["backgroundColor"] = "transparent"
            icon_style["borderColor"] = "#6e7681"
            icon = ""
        
        timeline_items.append(
            html.Div([
                html.Span(icon, style={**icon_style, "textAlign": "center", "lineHeight": "16px", "fontSize": "0.7rem"}),
                html.Span(
                    stage_name,
                    style={
                        "color": "#e6edf3" if (is_complete or is_current) else "#6e7681",
                        "fontWeight": "500" if is_current else "normal",
                    }
                ),
            ], style={"marginBottom": "8px", "display": "flex", "alignItems": "center"})
        )
    
    # Build live statistics
    stats = [
        ("Claims Extracted", status_data.get("claims_extracted", 0), "#58a6ff"),
        ("Claims Verified", status_data.get("claims_verified", 0), "#3fb950"),
        ("Claims Rejected", status_data.get("claims_rejected", 0), "#f85149"),
        ("Sources Processed", status_data.get("sources_processed", 0), "#a371f7"),
    ]
    
    stat_cards = []
    for label, value, color in stats:
        stat_cards.append(
            html.Div([
                html.Div(label, style={"fontSize": "0.75rem", "color": "#8b949e", "marginBottom": "4px"}),
                html.Div(str(value), style={"fontSize": "1.5rem", "fontWeight": "700", "color": color}),
            ], style={
                "padding": "12px",
                "backgroundColor": "#161b22",
                "borderRadius": "6px",
                "border": f"1px solid {color}33",
            })
        )
    
    # Build activity log from recent events
    try:
        recent_events = get_latest_events(run_id, since_line=max(0, n_intervals * 5 - 20))[-10:]  # Last 10 events
        
        if recent_events:
            log_lines = []
            for event in recent_events:
                timestamp = event.get("timestamp", "")[:19].replace("T", " ")
                event_name = event.get("event", "unknown")
                payload = event.get("payload", {})
                
                # Format event message
                if event_name == "claims_extracted":
                    msg = f"Extracted {payload.get('claims_count', 0)} claims from {payload.get('source_title', 'source')}"
                    color = "#58a6ff"
                elif event_name == "claim_verified":
                    msg = f"Verified claim: {payload.get('verdict', 'N/A')}"
                    color = "#3fb950"
                elif event_name == "claim_rejected":
                    msg = f"Rejected claim: {payload.get('reason', 'N/A')}"
                    color = "#f85149"
                else:
                    msg = event_name.replace("_", " ").title()
                    color = "#8b949e"
                    
                log_lines.append(
                    html.Div([
                        html.Span(f"[{timestamp}] ", style={"color": "#6e7681"}),
                        html.Span(msg, style={"color": color}),
                    ], style={"marginBottom": "4px"})
                )
            
            activity_display = log_lines
        else:
            activity_display = [html.Div("No recent activity...", style={"color": "#6e7681"})]
    except Exception:
        activity_display = [html.Div("Loading activity...", style={"color": "#6e7681"})]
    
    return section_style, timeline_items, stat_cards, activity_display



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
