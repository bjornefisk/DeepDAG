"""
New Query page.

Form to submit new research queries.
"""

from dash import html, dcc
from HDRP.dashboard.layout import create_info_tooltip


def create_query_page():
    """Create the new query submission page."""
    return html.Div([
        # Page header
        html.Div(
            className="page-header",
            children=[
                html.Div([
                    html.H1("New Query", className="page-title", style={"display": "inline-block", "marginRight": "0"}),
                    create_info_tooltip(
                        "query-info",
                        "Submit a new research query for HDRP to process. Your query will be decomposed into sub-questions, researched across sources, and synthesized into a verified report with claims and citations."
                    ),
                ]),
                html.P("Submit a new research query to HDRP", className="page-subtitle"),
            ]
        ),
        
        # Query form
        html.Div(
            className="card",
            style={"maxWidth": "800px"},
            children=[
                html.Div(
                    className="card-header",
                    children=[html.H3("Research Query", className="card-title")]
                ),
                
                # Query input
                html.Div(
                    className="form-group",
                    children=[
                        html.Label("Query", className="form-label"),
                        dcc.Textarea(
                            id="query-input",
                            placeholder="Enter your research query...\n\nExample: What are the latest trends in AI research for 2025?",
                            className="form-input",
                            style={"height": "120px", "resize": "vertical"},
                        ),
                    ]
                ),
                
                # Provider selection
                html.Div(
                    className="form-group",
                    children=[
                        html.Label("Search Provider", className="form-label"),
                        dcc.Dropdown(
                            id="provider-selector",
                            options=[
                                {'label': 'Simulated (Testing)', 'value': 'simulated'},
                                {'label': 'Google Custom Search', 'value': 'google'},
                            ],
                            value='simulated',
                            clearable=False,
                            style={"backgroundColor": "#21262d"},
                        ),
                    ]
                ),
                
                # Advanced options
                html.Details(
                    style={"marginBottom": "24px"},
                    children=[
                        html.Summary(
                            "Advanced Options",
                            style={"cursor": "pointer", "color": "#8b949e", "marginBottom": "16px"}
                        ),
                        html.Div(
                            style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "16px"},
                            children=[
                                html.Div(
                                    className="form-group",
                                    style={"marginBottom": "0"},
                                    children=[
                                        html.Label("Max Results", className="form-label"),
                                        dcc.Input(
                                            id="max-results-input",
                                            type="number",
                                            value=10,
                                            min=1,
                                            max=50,
                                            className="form-input",
                                        ),
                                    ]
                                ),
                                html.Div(
                                    className="form-group",
                                    style={"marginBottom": "0"},
                                    children=[
                                        html.Label("Verbose Logging", className="form-label"),
                                        dcc.Dropdown(
                                            id="verbose-selector",
                                            options=[
                                                {'label': 'Yes', 'value': True},
                                                {'label': 'No', 'value': False},
                                            ],
                                            value=False,
                                            clearable=False,
                                            style={"backgroundColor": "#21262d"},
                                        ),
                                    ]
                                ),
                            ]
                        ),
                    ]
                ),
                
                # Submit button
                html.Div(
                    style={"display": "flex", "gap": "12px"},
                    children=[
                        html.Button(
                            "Run Query",
                            id="submit-query-btn",
                            className="btn btn-primary",
                        ),
                        html.Button(
                            "Clear",
                            id="clear-query-btn",
                            className="btn btn-secondary",
                        ),
                    ]
                ),
            ]
        ),
        
        # Status/output area with detailed progress tracker
        html.Div(
            id="query-status",
            className="card",
            style={"marginTop": "24px", "display": "none"},
            children=[
                html.Div(
                    className="card-header",
                    children=[
                        html.H3("Execution Status", className="card-title", style={"display": "inline-block", "marginRight": "12px"}),
                        html.Button(
                            "Cancel",
                            id="cancel-query-btn",
                            className="btn btn-secondary",
                            style={"fontSize": "0.875rem", "padding": "4px 12px", "display": "none"},
                        ),
                    ],
                    style={"display": "flex", "justifyContent": "space-between", "alignItems": "center"},
                ),
                
                # Main status summary
                html.Div(id="query-output", style={"padding": "16px"}),
                
                # Expandable detailed progress section
                html.Div(
                    id="detailed-progress-section",
                    style={"borderTop": "1px solid #30363d", "display": "none"},
                    children=[
                        # Toggle button
                        html.Button(
                            [
                                html.Span("▼", id="progress-toggle-icon", style={"marginRight": "8px", "transition": "transform 0.2s"}),
                                "Show Detailed Progress"
                            ],
                            id="toggle-detailed-progress",
                            className="btn btn-secondary",
                            style={
                                "width": "100%",
                                "textAlign": "left",
                                "borderRadius": "0",
                                "border": "none",
                                "borderBottom": "1px solid #30363d",
                                "padding": "12px 16px",
                            },
                            n_clicks=0,
                        ),
                        
                        # Detailed progress content (hidden by default)
                        html.Div(
                            id="detailed-progress-content",
                            style={"display": "none", "padding": "16px"},
                            children=[
                                # Stage timeline
                                html.Div([
                                    html.H4("Pipeline Stages", style={"fontSize": "0.95rem", "marginBottom": "12px", "color": "#8b949e"}),
                                    html.Div(id="stage-timeline", children=[]),
                                ], style={"marginBottom": "20px"}),
                                
                                # Live statistics
                                html.Div([
                                    html.H4("Live Statistics", style={"fontSize": "0.95rem", "marginBottom": "12px", "color": "#8b949e"}),
                                    html.Div(
                                        id="live-stats",
                                        style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(150px, 1fr))", "gap": "12px"},
                                        children=[],
                                    ),
                                ], style={"marginBottom": "20px"}),
                                
                                # Recent activity log
                                html.Div([
                                    html.H4("Recent Activity", style={"fontSize": "0.95rem", "marginBottom": "12px", "color": "#8b949e"}),
                                    html.Div(
                                        id="activity-log",
                                        style={
                                            "maxHeight": "200px",
                                            "overflowY": "auto",
                                            "backgroundColor": "#0d1117",
                                            "borderRadius": "6px",
                                            "padding": "12px",
                                            "fontFamily": "monospace",
                                            "fontSize": "0.85rem",
                                        },
                                        children=[html.Div("Waiting for activity...", style={"color": "#6e7681"})],
                                    ),
                                ]),
                            ],
                        ),
                    ],
                ),
            ]
        ),
        
        # Hidden state stores for execution tracking
        dcc.Store(id="execution-status", data=None),
        dcc.Store(id="current-run-id", data=None),
        
        # Polling interval for status updates (disabled by default)
        dcc.Interval(
            id="status-poll-interval",
            interval=2000,  # 2 seconds
            disabled=True,
            n_intervals=0,
        ),

        
        # Info card
        html.Div(
            className="card",
            style={"marginTop": "24px", "background": "linear-gradient(135deg, rgba(88, 166, 255, 0.1), rgba(163, 113, 247, 0.1))"},
            children=[
                html.Div(
                    style={"display": "flex", "gap": "16px", "alignItems": "flex-start"},
                    children=[
                        html.Span("💡", style={"fontSize": "1.5rem"}),
                        html.Div([
                            html.H4("How it works", style={"margin": "0 0 8px", "color": "#e6edf3"}),
                            html.Ul(
                                style={"margin": "0", "paddingLeft": "20px", "color": "#8b949e", "lineHeight": "1.6"},
                                children=[
                                    html.Li("HDRP decomposes your query into sub-questions"),
                                    html.Li("Each sub-question is researched independently"),
                                    html.Li("Claims are extracted and verified against sources"),
                                    html.Li("A final report is synthesized from verified claims"),
                                ]
                            ),
                        ]),
                    ]
                ),
            ]
        ),
    ])
