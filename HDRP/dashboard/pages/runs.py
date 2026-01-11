"""
Run history page.

Lists all research runs with filtering and selection.
"""

from dash import html, dcc, dash_table
from HDRP.dashboard.data_loader import list_available_runs
from HDRP.dashboard.layout import create_info_tooltip


def create_runs_page():
    """Create the run history page."""
    runs = list_available_runs()
    
    # Format runs for table
    table_data = []
    for run in runs:
        # Shorten run_id to first 8 characters for better display
        short_run_id = run['run_id'][:8] if len(run['run_id']) > 8 else run['run_id']
        query_text = run.get('query', '') or 'Untitled Research'
        # Truncate very long queries for table display
        if len(query_text) > 60:
            query_display = query_text[:57] + '...'
        else:
            query_display = query_text
        
        table_data.append({
            'query': query_display,
            'run_id': short_run_id,
            'full_run_id': run['run_id'],  # Store full ID for selection
            'full_query': query_text,  # Store full query for tooltip/details
            'timestamp': run['timestamp'][:19] if run['timestamp'] else '',
            'size': f"{run['size_bytes'] / 1024:.1f} KB",
        })
    
    return html.Div([
        # Page header
        html.Div(
            className="page-header",
            children=[
                html.Div([
                    html.H1("Run History", className="page-title", style={"display": "inline-block", "marginRight": "0"}),
                    create_info_tooltip(
                        "run-history-info",
                        "Browse and review all past research executions. Each run represents a completed query with its associated claims, DAG structure, and metrics. Click on a row to view details."
                    ),
                ]),
                html.P("Browse past research executions", className="page-subtitle"),
            ]
        ),
        
        # Controls
        html.Div(
            className="card",
            style={"marginBottom": "24px"},
            children=[
                html.Div(
                    style={"display": "flex", "gap": "16px", "alignItems": "center"},
                    children=[
                        html.Div(
                            className="form-group",
                            style={"flex": "1", "marginBottom": "0"},
                            children=[
                                dcc.Input(
                                    id="run-search-input",
                                    type="text",
                                    placeholder="Search runs by query or ID...",
                                    className="form-input",
                                ),
                            ]
                        ),
                        html.Button(
                            "Refresh",
                            id="refresh-runs-btn",
                            className="btn btn-secondary",
                        ),
                    ]
                ),
            ]
        ),
        
        # Runs table
        html.Div(
            className="card",
            children=[
                html.Div(
                    className="card-header",
                    children=[
                        html.H3("All Runs", className="card-title"),
                        html.Span(f"{len(runs)} runs found", style={"color": "#8b949e"}),
                    ]
                ),
                
                dash_table.DataTable(
                    id="runs-table",
                    columns=[
                        {"name": "Query", "id": "query"},
                        {"name": "ID", "id": "run_id"},
                        {"name": "Timestamp", "id": "timestamp"},
                        {"name": "Size", "id": "size"},
                    ],
                    data=table_data,
                    row_selectable="single",
                    selected_rows=[],
                    page_size=15,
                    style_table={"overflowX": "auto"},
                    style_header={
                        "backgroundColor": "#21262d",
                        "color": "#8b949e",
                        "fontWeight": "600",
                        "textTransform": "uppercase",
                        "fontSize": "0.8rem",
                        "letterSpacing": "0.04em",
                        "padding": "12px 16px",
                        "borderBottom": "1px solid #30363d",
                    },
                    style_cell={
                        "backgroundColor": "#1c2128",
                        "color": "#e6edf3",
                        "padding": "14px 16px",
                        "borderBottom": "1px solid #30363d",
                        "textAlign": "left",
                        "fontFamily": "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
                    },
                    style_cell_conditional=[
                        {"if": {"column_id": "query"}, "fontWeight": "500", "maxWidth": "450px", "minWidth": "250px"},
                        {"if": {"column_id": "run_id"}, "fontFamily": "monospace", "color": "#8b949e", "fontSize": "0.85rem", "maxWidth": "100px"},
                        {"if": {"column_id": "timestamp"}, "color": "#8b949e", "fontSize": "0.85rem"},
                        {"if": {"column_id": "size"}, "color": "#8b949e", "fontSize": "0.85rem", "maxWidth": "80px"},
                    ],
                    style_data_conditional=[
                        {
                            "if": {"state": "selected"},
                            "backgroundColor": "rgba(88, 166, 255, 0.1)",
                            "border": "1px solid #58a6ff",
                        },
                    ],
                    style_as_list_view=True,
                    tooltip_data=[
                        {
                            'query': {'value': row['full_query'], 'type': 'markdown'},
                            'run_id': {'value': f"**Full ID:** {row['full_run_id']}", 'type': 'markdown'},
                        }
                        for row in table_data
                    ],
                    tooltip_duration=None,
                ),
            ]
        ),
        
        # Selected run details panel
        html.Div(
            id="selected-run-details",
            className="card",
            style={"marginTop": "24px", "display": "none"},
            children=[
                html.Div(
                    className="card-header",
                    children=[html.H3("Run Details", className="card-title")]
                ),
                html.Div(id="run-details-content"),
            ]
        ),
    ])
