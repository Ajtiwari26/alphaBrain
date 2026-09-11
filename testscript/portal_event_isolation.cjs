// Execute the actual portal event handlers without a browser or network.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

let ready;
let source;
const nodes = new Map();
function node(id) {
  if (!nodes.has(id)) {
    const classes = new Set();
    nodes.set(id, {
      classList: {add: x => classes.add(x), remove: x => classes.delete(x)},
      classes, appendChild() {}, textContent: '',
    });
  }
  return nodes.get(id);
}
const context = {
  document: {
    addEventListener: (_, callback) => { ready = callback; },
    getElementById: node,
    createElement: () => ({textContent: ''}),
  },
  window: {location: {search: '?task_id=task-A&project_id=project-A'}},
  localStorage: {getItem: () => 'test-session'},
  URLSearchParams, Date, console, setTimeout, clearTimeout,
  fetch: async url => ({ok: true, json: async () => url.includes('/trace')
    ? {task_state: 'review'} : {token: 'test-stream'}}),
  EventSource: class {
    constructor() { source = this; this.handlers = {}; }
    addEventListener(name, callback) { this.handlers[name] = callback; }
  },
};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../alpha_portal/portal.js'), 'utf8'), context);
(async () => {
  await ready();
  await new Promise(resolve => setImmediate(resolve));
  const completed = () => node('step-6').classes.has('active');
  assert.equal(completed(), false);
  const emit = data => source.handlers.task_update({data: JSON.stringify(data), lastEventId: '1'});
  emit({project_id: 'project-A', task_id: 'task-B', state: 'completed', event_type: 'task_promoted'});
  assert.equal(completed(), false, 'Other task must not complete selected task');
  emit({project_id: 'project-B', task_id: 'task-A', state: 'completed', event_type: 'task_promoted'});
  assert.equal(completed(), false, 'Other project must not complete selected task');
  emit({project_id: 'project-A', task_id: 'task-A', state: 'completed', event_type: 'senior_review_approved'});
  assert.equal(completed(), false, 'Legacy approval must not imply promotion');
  emit({project_id: 'project-A', task_id: 'task-A', state: 'completed', event_type: 'task_promoted'});
  assert.equal(completed(), true);
  console.log('Portal event isolation passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
