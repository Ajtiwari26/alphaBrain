document.addEventListener('DOMContentLoaded', async () => {
    const logBox = document.getElementById('telemetry-log');
    const statusBadge = document.getElementById('sse-status');
    const taskIdSpan = document.getElementById('task-id');
    
    // Get task ID from URL or default
    const urlParams = new URLSearchParams(window.location.search);
    const taskId = urlParams.get('task_id') || 'tsk_pending';
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
    try {
        const tokenRes = await fetch('/api/portal/stream/token', { method: 'POST', headers });
        if (!tokenRes.ok) throw new Error(`Token fetch failed: ${tokenRes.status}`);
        
        const { token } = await tokenRes.json();
        const eventSource = new EventSource(`/api/portal/stream?token=${encodeURIComponent(token)}`);
        
        eventSource.onopen = () => {
            statusBadge.textContent = 'Live Connected';
            statusBadge.className = 'px-3 py-1 bg-green-900/30 text-green-400 text-sm font-semibold rounded-full border border-green-800';
            logEvent('Connected to SSE stream.');
        };

        eventSource.addEventListener('heartbeat', (e) => {
            logEvent(`Heartbeat received: ${e.data}`);
        });

        eventSource.onmessage = (e) => {
            logEvent(`Message received: ${e.data}`);
        };

        eventSource.onerror = (e) => {
            statusBadge.textContent = 'Disconnected';
            statusBadge.className = 'px-3 py-1 bg-red-900/30 text-red-400 text-sm font-semibold rounded-full border border-red-800';
            logEvent('Connection lost or error occurred.');
            eventSource.close();
        };
    } catch (err) {
        logEvent(`Failed to initialize EventSource: ${err.message}`);
    }
});
