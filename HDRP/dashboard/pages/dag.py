"""
DAG visualization page.

Shows the research DAG using Cytoscape for interactivity.
"""

from dash import html, dcc
import dash_cytoscape as cyto
from HDRP.dashboard.data_loader import load_run, list_available_runs, get_demo_data


def create_dag_page(run_id: str = None):
    """Create the DAG visualization page."""
    # Get run data
    if run_id:
        run_data = load_run(run_id)
    else:
        runs = list_available_runs()
        if runs:
            run_data = load_run(runs[0]['run_id'])
        else:
            run_data = get_demo_data()
    
    # Build Cytoscape elements from claims/DAG data
    elements = _build_cytoscape_elements(run_data)
    
    # Run selector dropdown
    runs = list_available_runs()
    run_options = [{'label': f"{r['run_id'][:16]}...", 'value': r['run_id']} for r in runs[:20]]
    current_run_id = run_data.run_id if run_data else None
    
    return html.Div([
        # Page header
        html.Div(
            className="page-header",
            children=[
                html.H1("DAG Visualization", className="page-title"),
                html.P("Interactive view of the research dependency graph", className="page-subtitle"),
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
                                    id="dag-run-selector",
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
                                html.Label("Layout", className="form-label"),
                                dcc.Dropdown(
                                    id="dag-layout-selector",
                                    options=[
                                        {'label': 'Hierarchical (Top-Down)', 'value': 'dagre'},
                                        {'label': 'Breadthfirst', 'value': 'breadthfirst'},
                                        {'label': 'Circle', 'value': 'circle'},
                                        {'label': 'Concentric', 'value': 'concentric'},
                                        {'label': 'Grid', 'value': 'grid'},
                                        {'label': 'Force-Directed', 'value': 'cose'},
                                    ],
                                    value='dagre',
                                    clearable=False,
                                    style={"backgroundColor": "#21262d"},
                                ),
                            ]
                        ),
                        html.Div(
                            style={"display": "flex", "gap": "8px"},
                            children=[
                                html.Button("Fit View", id="dag-fit-btn", className="btn btn-secondary"),
                                html.Button("Reset", id="dag-reset-btn", className="btn btn-secondary"),
                            ]
                        ),
                    ]
                ),
            ]
        ),
        
        # DAG visualization
        html.Div(
            className="card",
            children=[
                html.Div(
                    className="card-header",
                    children=[
                        html.H3("Research DAG", className="card-title"),
                        html.Div(
                            style={"display": "flex", "gap": "16px", "fontSize": "0.85rem"},
                            children=[
                                html.Div([
                                    html.Span("●", style={"color": "#58a6ff", "marginRight": "6px"}),
                                    "Query",
                                ]),
                                html.Div([
                                    html.Span("●", style={"color": "#a371f7", "marginRight": "6px"}),
                                    "Researcher",
                                ]),
                                html.Div([
                                    html.Span("●", style={"color": "#d29922", "marginRight": "6px"}),
                                    "Critic",
                                ]),
                                html.Div([
                                    html.Span("●", style={"color": "#3fb950", "marginRight": "6px"}),
                                    "Verified",
                                ]),
                                html.Div([
                                    html.Span("●", style={"color": "#f85149", "marginRight": "6px"}),
                                    "Rejected",
                                ]),
                            ]
                        ),
                    ]
                ),
                
                cyto.Cytoscape(
                    id='dag-cytoscape',
                    elements=elements,
                    layout={'name': 'dagre', 'rankDir': 'TB', 'spacingFactor': 1.5},
                    style={'width': '100%', 'height': '600px', 'backgroundColor': '#21262d'},
                    stylesheet=[
                        # Node styles
                        {
                            'selector': 'node',
                            'style': {
                                'label': 'data(label)',
                                'text-valign': 'center',
                                'text-halign': 'center',
                                'color': '#e6edf3',
                                'font-size': '11px',
                                'font-weight': '500',
                                'text-wrap': 'wrap',
                                'text-max-width': '120px',
                                'padding': '12px',
                                'width': 'label',
                                'height': 'label',
                                'shape': 'roundrectangle',
                            }
                        },
                        # Query node
                        {
                            'selector': 'node[type = "query"]',
                            'style': {
                                'background-color': '#58a6ff',
                                'border-color': '#79b8ff',
                                'border-width': '2px',
                            }
                        },
                        # Researcher node
                        {
                            'selector': 'node[type = "researcher"]',
                            'style': {
                                'background-color': '#a371f7',
                                'border-color': '#bc8cff',
                                'border-width': '2px',
                            }
                        },
                        # Critic node
                        {
                            'selector': 'node[type = "critic"]',
                            'style': {
                                'background-color': '#d29922',
                                'border-color': '#e3b341',
                                'border-width': '2px',
                            }
                        },
                        # Verified claim
                        {
                            'selector': 'node[type = "verified"]',
                            'style': {
                                'background-color': '#3fb950',
                                'border-color': '#56d364',
                                'border-width': '2px',
                            }
                        },
                        # Rejected claim
                        {
                            'selector': 'node[type = "rejected"]',
                            'style': {
                                'background-color': '#f85149',
                                'border-color': '#ff7b72',
                                'border-width': '2px',
                            }
                        },
                        # Synthesizer node
                        {
                            'selector': 'node[type = "synthesizer"]',
                            'style': {
                                'background-color': '#39c5cf',
                                'border-color': '#56d4dd',
                                'border-width': '2px',
                            }
                        },
                        # Edge styles
                        {
                            'selector': 'edge',
                            'style': {
                                'curve-style': 'bezier',
                                'target-arrow-shape': 'triangle',
                                'target-arrow-color': '#6e7681',
                                'line-color': '#6e7681',
                                'width': 2,
                                'arrow-scale': 1.2,
                            }
                        },
                        # Selected node
                        {
                            'selector': ':selected',
                            'style': {
                                'border-width': '4px',
                                'border-color': '#ffffff',
                            }
                        },
                    ],
                    minZoom=0.3,
                    maxZoom=2.5,
                ),
            ]
        ),
        
        # Node details panel
        html.Div(
            id="dag-node-details",
            className="card",
            style={"marginTop": "24px", "display": "none"},
            children=[
                html.Div(
                    className="card-header",
                    children=[html.H3("Node Details", className="card-title")]
                ),
                html.Div(id="dag-node-content"),
            ]
        ),
    ])


def _build_cytoscape_elements(run_data) -> list:
    """Build Cytoscape elements from run data."""
    elements = []
    
    if not run_data:
        return elements
    
    # Add query node
    query_label = run_data.query[:40] + "..." if len(run_data.query) > 40 else run_data.query
    elements.append({
        'data': {'id': 'query', 'label': query_label or 'Query', 'type': 'query'}
    })
    
    # Track unique sources for grouping
    sources = {}
    
    # Add claim nodes and edges
    for idx, claim in enumerate(run_data.claims):
        claim_id = f"claim-{idx}"
        claim_label = claim.statement[:35] + "..." if len(claim.statement) > 35 else claim.statement
        
        # Determine node type based on verification status
        if claim.is_verified is True:
            node_type = "verified"
        elif claim.is_verified is False:
            node_type = "rejected"
        else:
            node_type = "researcher"
        
        elements.append({
            'data': {
                'id': claim_id,
                'label': claim_label,
                'type': node_type,
                'statement': claim.statement,
                'source_url': claim.source_url,
                'confidence': claim.confidence,
            }
        })
        
        # Add edge from query to claim
        elements.append({
            'data': {'source': 'query', 'target': claim_id}
        })
        
        # Group by source
        if claim.source_url:
            if claim.source_url not in sources:
                sources[claim.source_url] = []
            sources[claim.source_url].append(claim_id)
    
    # Add synthesizer node if there are verified claims
    verified_claims = [c for c in run_data.claims if c.is_verified is True]
    if verified_claims:
        elements.append({
            'data': {'id': 'synthesizer', 'label': 'Report', 'type': 'synthesizer'}
        })
        
        # Connect verified claims to synthesizer
        for idx, claim in enumerate(run_data.claims):
            if claim.is_verified is True:
                elements.append({
                    'data': {'source': f"claim-{idx}", 'target': 'synthesizer'}
                })
    
    return elements
