"""
Dashboard layout module.

Defines the main layout structure with sidebar navigation
and page content container.
"""

from dash import html, dcc


def create_info_tooltip(tooltip_id, text):
    """Create an info icon with tooltip."""
    return html.Span([
        html.Span(
            "ⓘ",
            id=tooltip_id,
            style={
                "cursor": "help",
                "marginLeft": "8px",
                "color": "#8b949e",
                "fontSize": "0.9rem",
                "fontWeight": "normal",
            }
        ),
        dcc.Tooltip(
            text,
            target=tooltip_id,
            style={
                "backgroundColor": "#1c2128",
                "border": "1px solid #30363d",
                "borderRadius": "6px",
                "padding": "8px 12px",
                "fontSize": "0.85rem",
                "maxWidth": "300px",
            }
        )
    ])


def create_sidebar():
    """Create the sidebar navigation."""
    return html.Div(
        className="sidebar",
        children=[
            # Header
            html.Div(
                className="sidebar-header",
                children=[
                    html.Div(
                        className="sidebar-logo",
                        children=[
                            # DAG icon
                            html.Span("◈", style={"fontSize": "1.5rem"}),
                            html.Span("HDRP"),
                        ]
                    ),
                ]
            ),
            
            # Navigation sections
            html.Div(
                className="nav-section",
                children=[
                    html.Div("Overview", className="nav-section-title"),
                    html.Div(
                        id="nav-dashboard",
                        className="nav-link active",
                        children=[
                            html.Span("Dashboard"),
                        ],
                        **{"data-page": "dashboard"}
                    ),
                ]
            ),
            
            html.Div(
                className="nav-section",
                children=[
                    html.Div("Research", className="nav-section-title"),
                    html.Div(
                        id="nav-runs",
                        className="nav-link",
                        children=[
                            html.Span("Run History"),
                        ],
                        **{"data-page": "runs"}
                    ),
                    html.Div(
                        id="nav-claims",
                        className="nav-link",
                        children=[
                            html.Span("Claims"),
                        ],
                        **{"data-page": "claims"}
                    ),
                    html.Div(
                        id="nav-dag",
                        className="nav-link",
                        children=[
                            html.Span("DAG View"),
                        ],
                        **{"data-page": "dag"}
                    ),
                ]
            ),
            
            html.Div(
                className="nav-section",
                children=[
                    html.Div("Analytics", className="nav-section-title"),
                    html.Div(
                        id="nav-metrics",
                        className="nav-link",
                        children=[
                            html.Span("Metrics"),
                        ],
                        **{"data-page": "metrics"}
                    ),
                ]
            ),
            
            html.Div(
                className="nav-section",
                children=[
                    html.Div("Actions", className="nav-section-title"),
                    html.Div(
                        id="nav-query",
                        className="nav-link",
                        children=[
                            html.Span("New Query"),
                        ],
                        **{"data-page": "query"}
                    ),
                ]
            ),
        ]
    )


def create_main_content():
    """Create the main content area."""
    return html.Div(
        className="main-content",
        children=[
            # Page content will be rendered here
            html.Div(id="page-content"),
            
            # Store for current page
            dcc.Store(id="current-page", data="dashboard"),
            
            # Store for selected run
            dcc.Store(id="selected-run-id", data=None),
            
            # URL location for routing
            dcc.Location(id="url", refresh=False),
        ]
    )


def create_layout():
    """Create the main dashboard layout."""
    return html.Div(
        className="dashboard-container",
        children=[
            create_sidebar(),
            create_main_content(),
        ]
    )
