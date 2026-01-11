"""
Run history page.

Lists all research runs with filtering and selection.
"""

from dash import html, dcc, dash_table
from HDRP.dashboard.data_loader import list_available_runs


def create_runs_page():
    """Create the run history page."""
    runs = list_available_runs()
    
    # Format runs for table
    table_data = []
    for run in runs:
        table_data.append({
            'run_id': run['run_id'],
            'query': run.get('query', '') or 'N/A',
            'timestamp': run['timestamp'][:19] if run['timestamp'] else '',
            'size': f"{run['size_bytes'] / 1024:.1f} KB",
        })
    
    return html.Div([
        # Page header
        html.Div(
            className="page-header",
            children=[
                html.H1("Run History", className="page-title"),
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
                                    placeholder="Search runs by ID or query...",
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
                        {"name": "Run ID", "id": "run_id"},
                        {"name": "Query", "id": "query"},
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
                        {"if": {"column_id": "run_id"}, "fontFamily": "monospace", "color": "#39c5cf"},
                        {"if": {"column_id": "query"}, "maxWidth": "400px", "overflow": "hidden", "textOverflow": "ellipsis"},
                    ],
                    style_data_conditional=[
                        {
                            "if": {"state": "selected"},
                            "backgroundColor": "rgba(88, 166, 255, 0.1)",
                            "border": "1px solid #58a6ff",
                        },
                    ],
                    style_as_list_view=True,
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
