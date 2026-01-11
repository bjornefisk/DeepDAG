"""
New Query page.

Form to submit new research queries.
"""

from dash import html, dcc


def create_query_page():
    """Create the new query submission page."""
    return html.Div([
        # Page header
        html.Div(
            className="page-header",
            children=[
                html.H1("New Query", className="page-title"),
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
        
        # Status/output area
        html.Div(
            id="query-status",
            className="card",
            style={"marginTop": "24px", "display": "none"},
            children=[
                html.Div(
                    className="card-header",
                    children=[html.H3("Execution Status", className="card-title")]
                ),
                html.Div(id="query-output"),
            ]
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
