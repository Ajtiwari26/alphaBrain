document.addEventListener('DOMContentLoaded', async () => {
    const logBox = document.getElementById('telemetry-log');
    const statusBadge = document.getElementById('sse-status');
    const taskIdSpan = document.getElementById('task-id');
    
    const urlParams = new URLSearchParams(window.location.search);
    const taskId = urlParams.get('task_id') || 'tsk_pending';
    const projectId = urlParams.get('project_id') || 'prj_default';
    taskIdSpan.textContent = '#' + taskId;

    function logEvent(msg) {
        const div = document.createElement('div');
        div.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
        logBox.appendChild(div);
        logBox.scrollTop = logBox.scrollHeight;
    }

    const accessToken = localStorage.getItem('access_token') || 'test-token';
    const headers = { 'Authorization': `Bearer ${accessToken}` };

    // Function to update milestone UI
    function updateMilestones(state) {
        const states = ['received', 'in_progress', 'review', 'completed'];
        let currentIndex = states.indexOf(state.toLowerCase());
        if (currentIndex === -1) currentIndex = 0; // default to received

        for (let i = 1; i <= 4; i++) {
            const circle = document.getElementById(`step-${i}`);
            const line = document.getElementById(`line-${i}`);
            
            if (i <= currentIndex + 1) {
                if (circle) circle.classList.add('active');
                if (line) line.classList.add('active');
            } else {
                if (circle) circle.classList.remove('active');
                if (line) line.classList.remove('active');
            }
        }
    }

    // Try to fetch task trace to update milestones
    if (taskId !== 'tsk_pending') {
        try {
            const traceRes = await fetch(`/api/portal/tasks/${taskId}/trace`, { headers });
            if (traceRes.ok) {
                const traceData = await traceRes.json();
                const state = traceData.provenance?.state || 'in_progress';
                updateMilestones(state);
                logEvent(`Loaded trace for ${taskId}, state: ${state}`);
            } else {
                logEvent(`Could not load trace for ${taskId}: ${traceRes.status}`);
            }
        } catch (e) {
            logEvent(`Error fetching task trace: ${e.message}`);
        }
    } else {
        updateMilestones('received');
    }

    // Fetch stream token and initialize SSE
    let eventSource = null;
    let reconnectTimeout = null;
    let lastEventId = null;

    async function connectSSE() {
        try {
            const tokenRes = await fetch(`/api/portal/projects/${projectId}/stream/token`, { method: 'POST', headers });
            if (!tokenRes.ok) throw new Error(`Token fetch failed: ${tokenRes.status}`);
            
            const { token } = await tokenRes.json();
            let url = `/api/portal/projects/${projectId}/stream?token=${encodeURIComponent(token)}`;
            if (lastEventId) {
                url += `&last_event_id=${encodeURIComponent(lastEventId)}`;
            }
            eventSource = new EventSource(url);
            
            eventSource.onopen = () => {
                statusBadge.textContent = 'Live Connected';
                statusBadge.className = 'px-3 py-1 bg-green-900/30 text-green-400 text-sm font-semibold rounded-full border border-green-800';
                logEvent('Connected to SSE stream.');
            };

            const handleEvent = (e) => {
                if (e.lastEventId) lastEventId = e.lastEventId;
            };

            eventSource.addEventListener('heartbeat', (e) => {
                handleEvent(e);
                logEvent(`Heartbeat received: ${e.data}`);
            });

            eventSource.addEventListener('task_update', (e) => {
                handleEvent(e);
                logEvent(`Task update received: ${e.data}`);
                try {
                    const data = JSON.parse(e.data);
                    if (data.state) {
                        updateMilestones(data.state);
                    }
                } catch (err) {}
            });

            eventSource.onmessage = (e) => {
                handleEvent(e);
                logEvent(`Message received: ${e.data}`);
            };

            eventSource.onerror = (e) => {
                if (eventSource.readyState === EventSource.CLOSED) {
                    statusBadge.textContent = 'Disconnected';
                    statusBadge.className = 'px-3 py-1 bg-red-900/30 text-red-400 text-sm font-semibold rounded-full border border-red-800';
                    logEvent('Connection closed, attempting to re-authenticate...');
                    clearTimeout(reconnectTimeout);
                    reconnectTimeout = setTimeout(connectSSE, 3000);
                } else {
                    logEvent('Connection lost, browser is reconnecting natively...');
                }
            };
        } catch (err) {
            logEvent(`Failed to initialize EventSource: ${err.message}`);
            clearTimeout(reconnectTimeout);
            reconnectTimeout = setTimeout(connectSSE, 3000);
        }
    }

    connectSSE();
});
