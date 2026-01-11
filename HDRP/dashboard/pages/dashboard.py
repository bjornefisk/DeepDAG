"""
Dashboard overview page.

Shows summary statistics and quick access to recent runs.
"""

from dash import html, dcc
import plotly.graph_objects as go
import plotly.express as px

from HDRP.dashboard.data_loader import list_available_runs, get_run_summary_stats, load_run


def create_stat_card(label: str, value: str, color: str = "blue", change: str = None):
    """Create a stat card component."""
    children = [
        html.Div(label, className="stat-label"),
        html.Div(value, className="stat-value"),
    ]
    if change:
        is_positive = change.startswith("+")
        children.append(
            html.Div(
                change,
                className=f"stat-change {'positive' if is_positive else 'negative'}"
            )
        )
    
    return html.Div(className=f"stat-card {color}", children=children)


def create_dashboard_page():
    """Create the main dashboard overview page."""
    # Get summary stats
    stats = get_run_summary_stats()
    runs = list_available_runs()
    
    # Create verification rate chart
    verified_rate = stats.get('verification_rate', 0)
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=verified_rate * 100,
        title={'text': "Verification Rate", 'font': {'color': '#e6edf3'}},
        number={'suffix': '%', 'font': {'color': '#e6edf3'}},
        gauge={
            'axis': {'range': [0, 100], 'tickcolor': '#8b949e'},
            'bar': {'color': '#3fb950'},
            'bgcolor': '#21262d',
            'borderwidth': 0,
            'steps': [
                {'range': [0, 50], 'color': 'rgba(248, 81, 73, 0.2)'},
                {'range': [50, 75], 'color': 'rgba(210, 153, 34, 0.2)'},
                {'range': [75, 100], 'color': 'rgba(63, 185, 80, 0.2)'},
            ],
        }
    ))
    fig_gauge.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font={'color': '#e6edf3'},
        height=250,
        margin=dict(l=30, r=30, t=50, b=30),
    )
    
    # Recent runs mini-list
    recent_runs_items = []
    for run in runs[:5]:
        recent_runs_items.append(
            html.Div(
                className="run-item",
                children=[
                    html.Div(
                        className="run-info",
                        children=[
                            html.Div(run['run_id'][:16] + "...", className="run-id"),
                            html.Div(run.get('query', 'No query'), className="run-query"),
                            html.Div(run['timestamp'][:19] if run['timestamp'] else '', className="run-timestamp"),
                        ]
                    ),
                ],
                id={"type": "run-item", "index": run['run_id']},
            )
        )
    
    if not recent_runs_items:
        recent_runs_items = [
            html.Div(
                className="empty-state",
                children=[
                    html.Div("📋", className="empty-state-icon"),
                    html.Div("No runs found", className="empty-state-title"),
                    html.Div("Run a research query to see results here."),
                ]
            )
        ]
    
    return html.Div([
        # Page header
        html.Div(
            className="page-header",
            children=[
                html.H1("Dashboard", className="page-title"),
                html.P("Overview of HDRP research activity", className="page-subtitle"),
            ]
        ),
        
        # Stats grid
        html.Div(
            className="stats-grid",
            children=[
                create_stat_card("Total Runs", str(stats.get('total_runs', 0)), "blue"),
                create_stat_card("Total Claims", str(stats.get('total_claims', 0)), "purple"),
                create_stat_card("Verified Claims", str(stats.get('total_verified', 0)), "green"),
                create_stat_card(
                    "Verification Rate",
                    f"{stats.get('verification_rate', 0) * 100:.1f}%",
                    "cyan"
                ),
            ]
        ),
        
        # Two column layout
        html.Div(
            style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "24px"},
            children=[
                # Verification rate gauge
                html.Div(
                    className="card",
                    children=[
                        html.Div(
                            className="card-header",
                            children=[html.H3("Verification Rate", className="card-title")]
                        ),
                        dcc.Graph(figure=fig_gauge, config={'displayModeBar': False}),
                    ]
                ),
                
                # Recent runs
                html.Div(
                    className="card",
                    children=[
                        html.Div(
                            className="card-header",
                            children=[html.H3("Recent Runs", className="card-title")]
                        ),
                        html.Div(className="run-list", children=recent_runs_items),
                    ]
                ),
            ]
        ),
    ])
