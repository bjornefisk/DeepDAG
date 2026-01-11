"""
Claims viewer page.

Interactive table showing atomic claims with filtering and details.
"""

from dash import html, dcc, dash_table
from HDRP.dashboard.data_loader import load_run, list_available_runs, get_demo_data
from HDRP.dashboard.layout import create_info_tooltip


def create_claims_page(run_id: str = None):
    """Create the claims viewer page."""
    # Get run data
    if run_id:
        run_data = load_run(run_id)
    else:
        # Use most recent run or demo data
        runs = list_available_runs()
        if runs:
            run_data = load_run(runs[0]['run_id'])
        else:
            run_data = get_demo_data()
    
    # Format claims for table
    table_data = []
    if run_data and run_data.claims:
        for claim in run_data.claims:
            status = "Pending"
            if claim.is_verified is True:
                status = "Verified"
            elif claim.is_verified is False:
                status = "Rejected"
            
            table_data.append({
                'id': claim.claim_id[:12] + "..." if len(claim.claim_id) > 12 else claim.claim_id,
                'statement': claim.statement[:150] + "..." if len(claim.statement) > 150 else claim.statement,
                'source': claim.source_title or claim.source_url or "N/A",
                'confidence': f"{claim.confidence * 100:.0f}%",
                'status': status,
                'entailment': f"{claim.entailment_score:.2f}" if claim.entailment_score else "N/A",
            })
    
    # Run selector dropdown
    runs = list_available_runs()
    run_options = []
    for r in runs[:20]:
        query = r.get('query', '') or 'Untitled Research'
        # Truncate long queries
        if len(query) > 50:
            query_display = query[:47] + '...'
        else:
            query_display = query
        # Show query with short run ID
        label = f"{query_display} ({r['run_id'][:8]})"
        run_options.append({'label': label, 'value': r['run_id']})

    
    current_run_id = run_data.run_id if run_data else None
    
    return html.Div([
        # Page header
        html.Div(
            className="page-header",
            children=[
                html.Div([
                    html.H1("Claims Viewer", className="page-title", style={"display": "inline-block", "marginRight": "0"}),
                    create_info_tooltip(
                        "claims-info",
                        "View atomic claims extracted from research runs. Each claim shows verification status, confidence scores, source information, and entailment metrics. Use filters to find specific claims."
                    ),
                ]),
                html.P("View and filter atomic claims from research runs", className="page-subtitle"),
            ]
        ),
        
        # Controls
        html.Div(
            className="card",
            style={"marginBottom": "24px"},
            children=[
                html.Div(
                    style={"display": "grid", "gridTemplateColumns": "1fr 1fr 1fr", "gap": "16px", "alignItems": "end"},
                    children=[
                        html.Div(
                            className="form-group",
                            style={"marginBottom": "0"},
                            children=[
                                html.Label("Select Run", className="form-label"),
                                dcc.Dropdown(
                                    id="claims-run-selector",
                                    options=run_options,
                                    value=current_run_id,
                                    placeholder="Select a run...",
                                    style={"backgroundColor": "#21262d"},
                                ),
                            ]
                        ),
                        html.Div(
                            className="form-group",
                            style={"marginBottom": "0"},
                            children=[
                                html.Label("Filter Status", className="form-label"),
                                dcc.Dropdown(
                                    id="claims-status-filter",
                                    options=[
                                        {'label': 'All', 'value': 'all'},
                                        {'label': 'Verified', 'value': 'verified'},
                                        {'label': 'Rejected', 'value': 'rejected'},
                                        {'label': 'Pending', 'value': 'pending'},
                                    ],
                                    value='all',
                                    clearable=False,
                                    style={"backgroundColor": "#21262d"},
                                ),
                            ]
                        ),
                        html.Div(
                            className="form-group",
                            style={"marginBottom": "0"},
                            children=[
                                dcc.Input(
                                    id="claims-search-input",
                                    type="text",
                                    placeholder="Search claims...",
                                    className="form-input",
                                ),
                            ]
                        ),
                    ]
                ),
            ]
        ),
        
        # Stats bar
        html.Div(
            className="stats-grid",
            children=[
                html.Div(
                    className="stat-card blue",
                    children=[
                        html.Div("Total Claims", className="stat-label"),
                        html.Div(str(len(table_data)), className="stat-value"),
                    ]
                ),
                html.Div(
                    className="stat-card green",
                    children=[
                        html.Div("Verified", className="stat-label"),
                        html.Div(
                            str(sum(1 for c in table_data if c['status'] == 'Verified')),
                            className="stat-value"
                        ),
                    ]
                ),
                html.Div(
                    className="stat-card red",
                    children=[
                        html.Div("Rejected", className="stat-label"),
                        html.Div(
                            str(sum(1 for c in table_data if c['status'] == 'Rejected')),
                            className="stat-value"
                        ),
                    ]
                ),
                html.Div(
                    className="stat-card cyan",
                    children=[
                        html.Div("Avg Confidence", className="stat-label"),
                        html.Div(
                            f"{sum(float(c['confidence'].rstrip('%')) for c in table_data) / len(table_data):.0f}%" if table_data else "N/A",
                            className="stat-value"
                        ),
                    ]
                ),
            ]
        ),
        
        # Claims table
        html.Div(
            className="card",
            children=[
                html.Div(
                    className="card-header",
                    children=[
                        html.H3("Claims", className="card-title"),
                        html.Span(f"{len(table_data)} claims", style={"color": "#8b949e"}),
                    ]
                ),
                
                dash_table.DataTable(
                    id="claims-table",
                    columns=[
                        {"name": "ID", "id": "id"},
                        {"name": "Statement", "id": "statement"},
                        {"name": "Source", "id": "source"},
                        {"name": "Confidence", "id": "confidence"},
                        {"name": "Status", "id": "status"},
                        {"name": "Entailment", "id": "entailment"},
                    ],
                    data=table_data,
                    row_selectable="single",
                    selected_rows=[],
                    page_size=10,
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
                        {"if": {"column_id": "id"}, "fontFamily": "monospace", "color": "#39c5cf", "width": "100px"},
                        {"if": {"column_id": "statement"}, "maxWidth": "400px", "whiteSpace": "normal"},
                        {"if": {"column_id": "source"}, "maxWidth": "200px", "overflow": "hidden", "textOverflow": "ellipsis"},
                        {"if": {"column_id": "confidence"}, "width": "90px", "textAlign": "center"},
                        {"if": {"column_id": "status"}, "width": "90px", "textAlign": "center"},
                        {"if": {"column_id": "entailment"}, "width": "90px", "textAlign": "center"},
                    ],
                    style_data_conditional=[
                        {
                            "if": {"filter_query": "{status} = Verified", "column_id": "status"},
                            "backgroundColor": "rgba(63, 185, 80, 0.15)",
                            "color": "#3fb950",
                        },
                        {
                            "if": {"filter_query": "{status} = Rejected", "column_id": "status"},
                            "backgroundColor": "rgba(248, 81, 73, 0.15)",
                            "color": "#f85149",
                        },
                        {
                            "if": {"filter_query": "{status} = Pending", "column_id": "status"},
                            "backgroundColor": "rgba(210, 153, 34, 0.15)",
                            "color": "#d29922",
                        },
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
        
        # Claim details panel
        html.Div(
            id="claim-details-panel",
            className="card",
            style={"marginTop": "24px", "display": "none"},
            children=[
                html.Div(
                    className="card-header",
                    children=[html.H3("Claim Details", className="card-title")]
                ),
                html.Div(id="claim-details-content"),
            ]
        ),
    ])
