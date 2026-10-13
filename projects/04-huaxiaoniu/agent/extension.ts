import { spawn } from 'node:child_process';
import { Type } from '@earendil-works/pi-ai';
import type { ExtensionAPI } from '@earendil-works/pi-coding-agent';

const ALLOWED = ['project_list', 'project_read'];

export default function (pi: ExtensionAPI) {
  let calls = 0;
  let turns = 0;
  const children = new Set<ReturnType<typeof spawn>>();
  const python = process.env.XIAOMAO_PYTHON;
  const worker = process.env.XIAOMAO_WORKER;
  if (!python || !worker || !process.env.XIAOMAO_PROJECT_ROOT) throw new Error('Harness configuration missing');

  function run(tool: string, params: object, signal?: AbortSignal): Promise<any> {
    return new Promise((resolve, reject) => {
      if (signal?.aborted) return reject(new Error('Task stopped'));
      // No shell; executable and worker are fixed by the Python host, not the model.
      // The worker gets no provider credentials.
      const env: Record<string, string> = {};
      for (const name of ['SystemRoot', 'WINDIR', 'TEMP', 'TMP', 'PATH', 'XIAOMAO_PROJECT_ROOT']) {
        if (process.env[name]) env[name] = process.env[name]!;
      }
      env.PYTHONIOENCODING = 'utf-8';
      const child = spawn(python!, [worker!], { shell: false, windowsHide: true, env, stdio: ['pipe', 'pipe', 'pipe'] });
      children.add(child);
      let output = Buffer.alloc(0);
      let done = false;
      const stop = () => { child.kill(); finish(new Error('Tool stopped or timed out')); };
      const timer = setTimeout(stop, 8000);
      function finish(error?: Error, value?: any) {
        if (done) return;
        done = true;
        clearTimeout(timer);
        signal?.removeEventListener('abort', stop);
        children.delete(child);
        error ? reject(error) : resolve(value);
      }
      signal?.addEventListener('abort', stop, { once: true });
      child.on('error', () => finish(new Error('Python file worker could not start')));
      child.stdin.on('error', () => finish(new Error('Python file worker input failed')));
      child.stderr.resume(); // Never forward credential-bearing diagnostics.
      child.stdout.on('data', chunk => {
        output = Buffer.concat([output, chunk]);
        if (output.length > 512 * 1024) stop();
      });
      child.on('close', code => {
        if (done) return;
        try {
          const result = JSON.parse(output.toString('utf8'));
          if (code !== 0 || !result.ok) return finish(new Error('读取被拒绝：路径、凭据、类型或大小限制'));
          finish(undefined, result.data);
        } catch { finish(new Error('Python file worker returned invalid data')); }
      });
      child.stdin.end(JSON.stringify({ ...params, tool }));
    });
  }

  pi.registerTool({
    name: 'project_list', label: '列出项目文件',
    description: 'List permitted files inside the selected project. Paths are relative. Hidden, credential, dependency and build files are excluded. Max 200 entries.',
    parameters: Type.Object({ path: Type.Optional(Type.String()), depth: Type.Optional(Type.Integer({ minimum: 1, maximum: 4 })) }),
    async execute(_id, params, signal) {
      const data = await run('project_list', params, signal);
      return { content: [{ type: 'text' as const, text: JSON.stringify(data) }], details: { count: data.entries.length, truncated: data.truncated } };
    },
  });
  pi.registerTool({
    name: 'project_read', label: '读取项目文本',
    description: 'Read an allowed UTF-8 text file inside the selected project, max 64 KiB. No absolute paths, traversal, links, binary files or credentials. Cite the returned relative path.',
    parameters: Type.Object({ path: Type.String() }),
    async execute(_id, params, signal) {
      const data = await run('project_read', params, signal);
      return { content: [{ type: 'text' as const, text: JSON.stringify(data) }], details: { path: data.path, bytes: data.bytes, lines: data.lines } };
    },
  });
  pi.on('session_start', async () => { pi.setActiveTools(ALLOWED); });
  pi.on('before_agent_start', async () => { calls = 0; turns = 0; pi.setActiveTools(ALLOWED); });
  pi.on('tool_call', async (event, ctx) => {
    if (!ALLOWED.includes(event.toolName)) return { block: true, reason: 'Harness only allows project_list and project_read' };
    if (++calls > 24) { ctx.abort(); return { block: true, reason: 'Tool budget exceeded' }; }
  });
  pi.on('turn_start', async (_event, ctx) => { if (++turns > 12) ctx.abort(); });
  pi.on('session_shutdown', async () => { for (const child of children) child.kill(); children.clear(); });
  pi.registerCommand('harness-status', {
    description: 'Report trusted Harness tool configuration without a model request',
    handler: async (_args, ctx) => {
      ctx.ui.notify('XIAOMAO_HARNESS:' + JSON.stringify({ version: 1, tools: pi.getActiveTools(), maxTurns: 12, maxTools: 24 }), 'info');
    },
  });
}
