"""
Metrics dashboard page.

Shows performance, quality, and trajectory metrics with charts.
"""

from dash import html, dcc
import plotly.graph_objects as go
import plotly.express as px
from HDRP.dashboard.data_loader import load_run, list_available_runs, get_demo_data
from HDRP.dashboard.layout import create_info_tooltip


def create_metrics_page(run_id: str = None):
    """Create the metrics dashboard page."""
    # Get run data
    if run_id:
        run_data = load_run(run_id)
    else:
        runs = list_available_runs()
        if runs:
            run_data = load_run(runs[0]['run_id'])
        else:
            run_data = get_demo_data()
    
    # Build charts
    claims_chart = _create_claims_breakdown_chart(run_data)
    confidence_chart = _create_confidence_distribution_chart(run_data)
    metrics_chart = _create_metrics_radar_chart(run_data)
    timeline_chart = _create_execution_timeline_chart(run_data)
    
    # Run selector dropdown
    runs = list_available_runs()
    run_options = [{'label': f"{r['run_id'][:16]}...", 'value': r['run_id']} for r in runs[:20]]
    current_run_id = run_data.run_id if run_data else None
    
    return html.Div([
        # Page header
        html.Div(
            className="page-header",
            children=[
                html.Div([
                    html.H1("Metrics Dashboard", className="page-title", style={"display": "inline-block", "marginRight": "0"}),
                    create_info_tooltip(
                        "metrics-info",
                        "Comprehensive analytics for research runs including execution performance, claim quality metrics, confidence distributions, and source coverage. Compare metrics across different runs."
                    ),
                ]),
                html.P("Performance, quality, and trajectory analysis", className="page-subtitle"),
            ]
        ),
        
        # Controls
        html.Div(
            className="card",
            style={"marginBottom": "24px"},
            children=[
                html.Div(
                    style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "16px", "alignItems": "end"},
                    children=[
                        html.Div(
                            className="form-group",
                            style={"marginBottom": "0"},
                            children=[
                                html.Label("Select Run", className="form-label"),
                                dcc.Dropdown(
                                    id="metrics-run-selector",
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
                                html.Label("Compare With", className="form-label"),
                                dcc.Dropdown(
                                    id="metrics-compare-selector",
                                    options=run_options,
                                    value=None,
                                    placeholder="Select another run to compare...",
                                    style={"backgroundColor": "#21262d"},
                                ),
                            ]
                        ),
                    ]
                ),
            ]
        ),
        
        # Stats summary
        html.Div(
            className="stats-grid",
            children=[
                html.Div(
                    className="stat-card blue",
                    children=[
                        html.Div("Execution Time", className="stat-label"),
                        html.Div(f"{run_data.execution_time_ms:.0f} ms" if run_data else "N/A", className="stat-value"),
                    ]
                ),
                html.Div(
                    className="stat-card green",
                    children=[
                        html.Div("Precision", className="stat-label"),
                        html.Div(
                            f"{run_data.verified_claims / run_data.total_claims * 100:.1f}%" if run_data and run_data.total_claims else "N/A",
                            className="stat-value"
                        ),
                    ]
                ),
                html.Div(
                    className="stat-card purple",
                    children=[
                        html.Div("Unique Sources", className="stat-label"),
                        html.Div(str(run_data.unique_sources) if run_data else "0", className="stat-value"),
                    ]
                ),
                html.Div(
                    className="stat-card cyan",
                    children=[
                        html.Div("Claims/Source", className="stat-label"),
                        html.Div(
                            f"{run_data.total_claims / run_data.unique_sources:.1f}" if run_data and run_data.unique_sources else "N/A",
                            className="stat-value"
                        ),
                    ]
                ),
            ]
        ),
        
        # Charts row 1
        html.Div(
            style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "24px", "marginBottom": "24px"},
            children=[
                html.Div(
                    className="card",
                    children=[
                        html.Div(
                            className="card-header",
                            children=[html.H3("Claims Breakdown", className="card-title")]
                        ),
                        dcc.Graph(figure=claims_chart, config={'displayModeBar': False}),
                    ]
                ),
                html.Div(
                    className="card",
                    children=[
                        html.Div(
                            className="card-header",
                            children=[html.H3("Confidence Distribution", className="card-title")]
                        ),
                        dcc.Graph(figure=confidence_chart, config={'displayModeBar': False}),
                    ]
                ),
            ]
        ),
        
        # Charts row 2
        html.Div(
            style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "24px"},
            children=[
                html.Div(
                    className="card",
                    children=[
                        html.Div(
                            className="card-header",
                            children=[html.H3("Quality Metrics", className="card-title")]
                        ),
                        dcc.Graph(figure=metrics_chart, config={'displayModeBar': False}),
                    ]
                ),
                html.Div(
                    className="card",
                    children=[
                        html.Div(
                            className="card-header",
                            children=[html.H3("Run Details", className="card-title")]
                        ),
                        _create_details_table(run_data),
                    ]
                ),
            ]
        ),
    ])


def _create_claims_breakdown_chart(run_data) -> go.Figure:
    """Create a donut chart showing claims breakdown."""
    verified = run_data.verified_claims if run_data else 0
    rejected = run_data.rejected_claims if run_data else 0
    pending = (run_data.total_claims - verified - rejected) if run_data else 0
    
    fig = go.Figure(data=[go.Pie(
        labels=['Verified', 'Rejected', 'Pending'],
        values=[verified, rejected, pending],
        hole=0.55,
        marker=dict(colors=['#3fb950', '#f85149', '#d29922']),
        textinfo='label+value',
        textfont=dict(color='#e6edf3', size=12),
        hoverinfo='label+percent+value',
    )])
    
    fig.update_layout(
        paper_bgcolor='transparent',
        plot_bgcolor='transparent',
        font=dict(color='#e6edf3'),
        height=280,
        margin=dict(l=20, r=20, t=20, b=20),
        showlegend=False,
        annotations=[
            dict(
                text=f'{verified + rejected + pending}',
                x=0.5, y=0.5,
                font=dict(size=28, color='#e6edf3', weight='bold'),
                showarrow=False
            )
        ],
    )
    
    return fig


def _create_confidence_distribution_chart(run_data) -> go.Figure:
    """Create a histogram of confidence scores."""
    confidences = [c.confidence for c in run_data.claims] if run_data and run_data.claims else []
    
    fig = go.Figure(data=[go.Histogram(
        x=confidences,
        nbinsx=10,
        marker=dict(color='#58a6ff', line=dict(width=1, color='#79b8ff')),
    )])
    
    fig.update_layout(
        paper_bgcolor='transparent',
        plot_bgcolor='transparent',
        font=dict(color='#e6edf3'),
        height=280,
        margin=dict(l=40, r=20, t=20, b=40),
        xaxis=dict(
            title='Confidence',
            tickformat='.0%',
            gridcolor='#30363d',
            zerolinecolor='#30363d',
        ),
        yaxis=dict(
            title='Count',
            gridcolor='#30363d',
            zerolinecolor='#30363d',
        ),
        bargap=0.1,
    )
    
    return fig


def _create_metrics_radar_chart(run_data) -> go.Figure:
    """Create a radar chart for quality metrics."""
    metrics = run_data.metrics if run_data else {}
    quality = metrics.get('quality', {})
    
    categories = ['Precision', 'Recall', 'Entailment', 'Coverage', 'Efficiency']
    values = [
        quality.get('precision', 0.5),
        quality.get('completeness', 0.5),
        quality.get('entailment_score', 0.5),
        min(run_data.unique_sources / 5, 1) if run_data else 0.5,  # Normalized
        min(run_data.verified_claims / 10, 1) if run_data else 0.5,  # Normalized
    ]
    
    fig = go.Figure(data=go.Scatterpolar(
        r=values + [values[0]],  # Close the polygon
        theta=categories + [categories[0]],
        fill='toself',
        fillcolor='rgba(88, 166, 255, 0.2)',
        line=dict(color='#58a6ff', width=2),
        marker=dict(color='#58a6ff', size=8),
    ))
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 1],
                tickfont=dict(color='#8b949e', size=10),
                gridcolor='#30363d',
            ),
            angularaxis=dict(
                tickfont=dict(color='#e6edf3', size=11),
                gridcolor='#30363d',
            ),
            bgcolor='transparent',
        ),
        paper_bgcolor='transparent',
        font=dict(color='#e6edf3'),
        height=280,
        margin=dict(l=60, r=60, t=30, b=30),
        showlegend=False,
    )
    
    return fig


def _create_execution_timeline_chart(run_data) -> go.Figure:
    """Create a timeline of execution events."""
    # Placeholder - would need event timestamps
    fig = go.Figure()
    fig.update_layout(
        paper_bgcolor='transparent',
        plot_bgcolor='transparent',
        height=200,
        margin=dict(l=20, r=20, t=20, b=20),
    )
    return fig


def _create_details_table(run_data) -> html.Div:
    """Create a details table for the run."""
    if not run_data:
        return html.Div("No data available", style={"color": "#8b949e", "padding": "20px"})
    
    metrics = run_data.metrics or {}
    performance = metrics.get('performance', {})
    quality = metrics.get('quality', {})
    
    rows = [
        ("Run ID", run_data.run_id),
        ("Query", run_data.query[:80] + "..." if len(run_data.query) > 80 else run_data.query),
        ("Timestamp", run_data.timestamp[:19] if run_data.timestamp else "N/A"),
        ("Status", run_data.status.capitalize()),
        ("Total Claims", str(run_data.total_claims)),
        ("Verified Claims", str(run_data.verified_claims)),
        ("Rejected Claims", str(run_data.rejected_claims)),
        ("Unique Sources", str(run_data.unique_sources)),
        ("Execution Time", f"{run_data.execution_time_ms:.0f} ms" if run_data.execution_time_ms else "N/A"),
        ("Search Calls", str(performance.get('search_calls_count', 'N/A'))),
    ]
    
    return html.Table(
        className="data-table",
        style={"width": "100%"},
        children=[
            html.Tbody([
                html.Tr([
                    html.Td(label, style={"color": "#8b949e", "width": "40%"}),
                    html.Td(value, style={"fontWeight": "500"}),
                ]) for label, value in rows
            ])
        ]
    )
