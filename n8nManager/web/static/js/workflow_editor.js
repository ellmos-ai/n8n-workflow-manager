/** Visual workflow editor backed by the REST API. */
let editorNetwork = null;
let editorNodes = null;
let editorEdges = null;
let currentNodeCatalog = [];
let currentWorkflowId = null;
let baseWorkflow = {};

function visualNode(node) {
    return {
        id: node.id,
        label: node.label,
        x: node.x,
        y: node.y,
        color: {background: node.color || '#4285f4', border: node.color || '#4285f4'},
        shape: 'box',
        font: {color: '#fff', size: 14},
        shadow: true,
        n8n_type: node.n8n_type || 'n8n-nodes-base.set',
        n8n_params: node.n8n_params || {},
        n8n_id: node.n8n_id || crypto.randomUUID(),
        type_version: node.type_version || 1,
    };
}

function initEditor(containerId, graphData, nodeCatalog, workflowId, workflowData = {}) {
    currentNodeCatalog = nodeCatalog || [];
    currentWorkflowId = workflowId;
    baseWorkflow = structuredClone(workflowData || {});
    renderCatalog();
    const container = document.getElementById(containerId);
    editorNodes = new vis.DataSet(graphData.nodes.map(visualNode));
    editorEdges = new vis.DataSet(graphData.edges.map(edge => ({
        id: edge.id,
        from: edge.from,
        to: edge.to,
        arrows: 'to',
        color: {color: '#888'},
        smooth: {type: 'cubicBezier'},
        connection_type: edge.connection_type || 'main',
        source_output: edge.source_output || 0,
        target_input: edge.target_input || 0,
    })));
    editorNetwork = new vis.Network(container, {nodes: editorNodes, edges: editorEdges}, {
        physics: false,
        manipulation: {
            enabled: true,
            addNode(data, callback) {
                callback(visualNode({...data, label: 'New Node'}));
            },
            addEdge(data, callback) {
                if (data.from === data.to && !confirm('Create a self-connection?')) return callback(null);
                callback({...data, arrows: 'to', connection_type: 'main', source_output: 0, target_input: 0});
            },
        },
        interaction: {hover: true},
    });
    editorNetwork.on('selectNode', params => showPropertyPanel(params.nodes[0]));
}

function initCreator(containerId, nodeCatalog) {
    initEditor(containerId, {nodes: [], edges: []}, nodeCatalog, null, {
        name: 'New Workflow', settings: {executionOrder: 'v1'}, active: false, tags: [],
    });
}

function renderCatalog() {
    const list = document.getElementById('node-catalog-list');
    if (!list) return;
    list.replaceChildren();
    const categories = {};
    currentNodeCatalog.forEach(node => {
        const category = node.category || 'other';
        (categories[category] ||= []).push(node);
    });
    Object.entries(categories).forEach(([category, nodes]) => {
        const heading = document.createElement('h4');
        heading.textContent = category;
        list.appendChild(heading);
        nodes.forEach(node => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'catalog-btn';
            button.style.borderLeft = `4px solid ${node.color || '#666'}`;
            button.textContent = node.display_name || node.node_type;
            button.title = node.description || '';
            button.addEventListener('click', () => addNodeFromCatalog(node));
            list.appendChild(button);
        });
    });
}

function addNodeFromCatalog(catalogNode) {
    if (!editorNodes) return;
    const count = editorNodes.length;
    const id = crypto.randomUUID();
    editorNodes.add(visualNode({
        id,
        label: `${catalogNode.display_name || catalogNode.node_type} ${count + 1}`,
        color: catalogNode.color || '#666',
        x: 150 + count * 40,
        y: 150 + count * 30,
        n8n_type: catalogNode.node_type,
        n8n_id: id,
    }));
    editorNetwork.selectNodes([id]);
    showPropertyPanel(id);
}

function labeledControl(labelText, control) {
    const label = document.createElement('label');
    label.className = 'property-field';
    const caption = document.createElement('span');
    caption.textContent = labelText;
    label.append(caption, control);
    return label;
}

function showPropertyPanel(nodeId) {
    const panel = document.getElementById('property-panel');
    const node = editorNodes.get(nodeId);
    if (!panel || !node) return;
    const name = document.createElement('input');
    name.value = node.label || '';
    name.maxLength = 200;
    const type = document.createElement('input');
    type.value = node.n8n_type || '';
    type.maxLength = 300;
    const parameters = document.createElement('textarea');
    parameters.rows = 12;
    parameters.value = JSON.stringify(node.n8n_params || {}, null, 2);
    const save = document.createElement('button');
    save.type = 'button';
    save.className = 'btn btn-primary';
    save.textContent = 'Apply node changes';
    save.addEventListener('click', () => {
        let parsed;
        try {
            parsed = JSON.parse(parameters.value || '{}');
        } catch (error) {
            alert(`Parameters must be valid JSON: ${error.message}`);
            return;
        }
        if (!name.value.trim() || !type.value.trim()) {
            alert('Node name and type are required.');
            return;
        }
        editorNodes.update({id: nodeId, label: name.value.trim(), n8n_type: type.value.trim(), n8n_params: parsed});
    });
    panel.replaceChildren(
        labeledControl('Name', name),
        labeledControl('n8n type', type),
        labeledControl('Parameters (JSON)', parameters),
        save,
    );
}

function serializeWorkflow(name) {
    const positions = editorNetwork.getPositions();
    const nodes = editorNodes.get().map(node => ({
        parameters: node.n8n_params || {},
        type: node.n8n_type,
        typeVersion: node.type_version || 1,
        position: [Math.round(positions[node.id]?.x || node.x || 0), Math.round(positions[node.id]?.y || node.y || 0)],
        id: String(node.n8n_id || node.id),
        name: node.label,
    }));
    const names = new Map(editorNodes.get().map(node => [node.id, node.label]));
    const connections = {};
    editorEdges.get().forEach(edge => {
        const source = names.get(edge.from);
        const target = names.get(edge.to);
        if (!source || !target) return;
        const type = edge.connection_type || 'main';
        const output = Number(edge.source_output || 0);
        connections[source] ||= {};
        connections[source][type] ||= [];
        while (connections[source][type].length <= output) connections[source][type].push([]);
        connections[source][type][output].push({node: target, type, index: Number(edge.target_input || 0)});
    });
    return {...baseWorkflow, name, nodes, connections};
}

async function saveWorkflow() {
    const decision = prompt('Why are you changing this workflow?');
    if (!decision?.trim()) return;
    const name = baseWorkflow.name || document.querySelector('.editor-header h1')?.textContent.replace(/^Editor:\s*/, '') || 'Workflow';
    const data = serializeWorkflow(name);
    const response = await apiClient.put(`/api/workflows/${currentWorkflowId}`, {
        name, workflow_json: JSON.stringify(data), decision: decision.trim(),
    });
    if (!response.ok) return alert(`Save failed: ${response.detail || 'unknown error'}`);
    baseWorkflow = data;
    alert('Workflow saved.');
}

async function saveNewWorkflow() {
    const name = document.getElementById('workflow-name')?.value.trim() || 'New Workflow';
    const decision = prompt('Why are you creating this workflow?', 'Created in the visual editor');
    if (!decision?.trim()) return;
    const data = serializeWorkflow(name);
    const response = await apiClient.post('/api/workflows', {
        name, workflow_json: JSON.stringify(data), decision: decision.trim(),
    });
    if (!response.ok) return alert(`Create failed: ${response.detail || 'unknown error'}`);
    location.href = `/viewer/${response.id}`;
}
