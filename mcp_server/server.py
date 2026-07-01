"""MCP HTTP Server for GitHub API.

Supports: create_or_update_file, create_or_update_binary_file,
          get_file_contents, list_commits, workflow logs,
          commit status, workflow info, delete_file.

Token is passed via Authorization: Bearer <token> header.
"""

from flask import Flask, request, jsonify
import httpx
import json
import base64
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
GITHUB_API = "https://api.github.com"


@app.route('/mcp', methods=['POST'])
def mcp_handler():
    data = request.get_json()
    method = data.get('method')
    req_id = data.get('id')

    # Get token from Authorization header
    auth_header = request.headers.get('Authorization', '')
    token = None
    if auth_header.startswith('Bearer '):
        token = auth_header[7:]

    logger.info(f"Request: method={method}, id={req_id}, token={'present' if token else 'missing'}")

    # Initialize
    if method == 'initialize':
        return jsonify({
            "jsonrpc": "2.0",
            "result": {
                "protocolVersion": "0.1.0",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "mcp-github-server", "version": "0.2.0"}
            },
            "id": req_id
        })

    # Tools list
    if method == 'tools/list':
        return jsonify({
            "jsonrpc": "2.0",
            "result": {
                "tools": [
                    {
                        "name": "create_or_update_file",
                        "description": "Создаёт или обновляет ТЕКСТОВЫЙ файл в репозитории",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "owner": {"type": "string"},
                                "repo": {"type": "string"},
                                "path": {"type": "string"},
                                "content": {"type": "string"},
                                "message": {"type": "string"},
                                "branch": {"type": "string"},
                                "sha": {"type": "string"}
                            },
                            "required": ["owner", "repo", "path", "content", "message", "branch"]
                        }
                    },
                    {
                        "name": "create_or_update_binary_file",
                        "description": "Создаёт или обновляет БИНАРНЫЙ файл в репозитории (base64)",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "owner": {"type": "string"},
                                "repo": {"type": "string"},
                                "path": {"type": "string"},
                                "content_base64": {"type": "string", "description": "Base64-encoded content"},
                                "message": {"type": "string"},
                                "branch": {"type": "string"},
                                "sha": {"type": "string"}
                            },
                            "required": ["owner", "repo", "path", "content_base64", "message", "branch"]
                        }
                    },
                    {
                        "name": "get_file_contents",
                        "description": "Получает содержимое файла из репозитория",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "owner": {"type": "string"},
                                "repo": {"type": "string"},
                                "path": {"type": "string"},
                                "ref": {"type": "string"}
                            },
                            "required": ["owner", "repo", "path"]
                        }
                    },
                    {
                        "name": "delete_file",
                        "description": "Удаляет файл из GitHub репозитория",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "owner": {"type": "string"},
                                "repo": {"type": "string"},
                                "path": {"type": "string"},
                                "message": {"type": "string"},
                                "branch": {"type": "string"}
                            },
                            "required": ["owner", "repo", "path", "message", "branch"]
                        }
                    },
                    {
                        "name": "list_commits",
                        "description": "Получает список коммитов репозитория",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "owner": {"type": "string"},
                                "repo": {"type": "string"},
                                "sha": {"type": "string"}
                            },
                            "required": ["owner", "repo"]
                        }
                    },
                    {
                        "name": "get_latest_workflow_error",
                        "description": "Получает ошибку последней сборки через GitHub API",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "owner": {"type": "string"},
                                "repo": {"type": "string"}
                            },
                            "required": ["owner", "repo"]
                        }
                    },
                    {
                        "name": "get_workflow_run_logs",
                        "description": "Получает логи и причину падения конкретного workflow run",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "owner": {"type": "string"},
                                "repo": {"type": "string"},
                                "run_id": {"type": "integer"}
                            },
                            "required": ["owner", "repo", "run_id"]
                        }
                    },
                    {
                        "name": "get_full_workflow_logs",
                        "description": "Получает ПОЛНЫЕ логи всех jobs для конкретного workflow run",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "owner": {"type": "string"},
                                "repo": {"type": "string"},
                                "run_id": {"type": "integer"}
                            },
                            "required": ["owner", "repo", "run_id"]
                        }
                    },
                    {
                        "name": "get_workflow_by_file",
                        "description": "Получает последние запуски workflow по имени YAML файла",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "owner": {"type": "string"},
                                "repo": {"type": "string"},
                                "filename": {"type": "string"}
                            },
                            "required": ["owner", "repo", "filename"]
                        }
                    },
                    {
                        "name": "get_commit_status",
                        "description": "Получает статус проверок для конкретного коммита",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "owner": {"type": "string"},
                                "repo": {"type": "string"},
                                "sha": {"type": "string"}
                            },
                            "required": ["owner", "repo", "sha"]
                        }
                    }
                ]
            },
            "id": req_id
        })

    # Call tool
    if method == 'tools/call':
        params = data.get('params', {})
        tool_name = params.get('name')
        args = params.get('arguments', {})

        logger.info(f"Calling tool: {tool_name}")

        try:
            if not token:
                return jsonify({
                    "jsonrpc": "2.0",
                    "error": {"code": -32000, "message": "Missing Authorization token"},
                    "id": req_id
                })

            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28"
            }

            output = ""

            if tool_name == 'create_or_update_file':
                owner = args.get('owner')
                repo = args.get('repo')
                path = args.get('path')
                content = args.get('content')
                message = args.get('message')
                branch = args.get('branch')
                sha = args.get('sha')

                url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
                payload = {
                    "message": message,
                    "content": content,
                    "branch": branch
                }
                if sha:
                    payload["sha"] = sha

                with httpx.Client(timeout=30.0) as client:
                    res = client.put(url, headers=headers, json=payload)
                    if res.status_code in [200, 201]:
                        output = f"✅ Файл {path} успешно сохранён"
                    else:
                        output = f"❌ Ошибка: {res.status_code} - {res.text}"

            elif tool_name == 'create_or_update_binary_file':
                owner = args.get('owner')
                repo = args.get('repo')
                path = args.get('path')
                content_base64 = args.get('content_base64')
                message = args.get('message')
                branch = args.get('branch')
                sha = args.get('sha')

                url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
                payload = {
                    "message": message,
                    "content": content_base64,
                    "branch": branch
                }
                if sha:
                    payload["sha"] = sha

                with httpx.Client(timeout=30.0) as client:
                    res = client.put(url, headers=headers, json=payload)
                    if res.status_code in [200, 201]:
                        output = f"✅ Бинарный файл {path} успешно сохранён"
                    else:
                        output = f"❌ Ошибка: {res.status_code} - {res.text}"

            elif tool_name == 'get_file_contents':
                owner = args.get('owner')
                repo = args.get('repo')
                path = args.get('path')
                ref = args.get('ref')

                url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
                if ref:
                    url += f"?ref={ref}"

                with httpx.Client(timeout=30.0) as client:
                    res = client.get(url, headers=headers)
                    if res.status_code == 200:
                        data = res.json()
                        if "content" in data:
                            decoded = base64.b64decode(data["content"]).decode('utf-8', errors='replace')
                            output = decoded
                        else:
                            output = json.dumps(data, indent=2)
                    else:
                        output = f"❌ Ошибка: {res.status_code}"

            elif tool_name == 'delete_file':
                owner = args.get('owner')
                repo = args.get('repo')
                path = args.get('path')
                message = args.get('message')
                branch = args.get('branch')

                # First get the file SHA
                url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
                with httpx.Client(timeout=30.0) as client:
                    res = client.get(url, headers=headers)
                    if res.status_code == 200:
                        file_sha = res.json().get('sha')
                        payload = {
                            "message": message,
                            "sha": file_sha,
                            "branch": branch
                        }
                        res = client.delete(url, headers=headers, json=payload)
                        if res.status_code == 200:
                            output = f"✅ Файл {path} успешно удалён"
                        else:
                            output = f"❌ Ошибка удаления: {res.status_code} - {res.text}"
                    else:
                        output = f"❌ Файл не найден: {res.status_code}"

            elif tool_name == 'list_commits':
                owner = args.get('owner')
                repo = args.get('repo')
                sha = args.get('sha')

                url = f"{GITHUB_API}/repos/{owner}/{repo}/commits"
                if sha:
                    url += f"?sha={sha}"

                with httpx.Client(timeout=30.0) as client:
                    res = client.get(url, headers=headers)
                    if res.status_code == 200:
                        commits = res.json()
                        output = "\n".join([
                            f"{c['sha'][:7]} - {c['commit']['message'].splitlines()[0]}"
                            for c in commits[:10]
                        ])
                    else:
                        output = f"❌ Ошибка: {res.status_code}"

            elif tool_name == 'get_latest_workflow_error':
                owner = args.get('owner')
                repo = args.get('repo')

                with httpx.Client(timeout=30.0) as client:
                    url = f"{GITHUB_API}/repos/{owner}/{repo}/actions/runs?per_page=1"
                    res = client.get(url, headers=headers)

                    if res.status_code != 200:
                        output = f"❌ Ошибка API: {res.status_code}"
                    else:
                        runs_data = res.json()
                        workflow_runs = runs_data.get('workflow_runs') or []

                        if not workflow_runs:
                            output = "Нет запусков workflow"
                        else:
                            run_id = workflow_runs[0].get('id')
                            url = f"{GITHUB_API}/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"
                            res = client.get(url, headers=headers)
                            jobs = res.json().get('jobs', [])
                            failed = [j for j in jobs if j.get('conclusion') == 'failure']
                            output = f"❌ Ошибка в: {failed[0].get('name', 'unknown')}" if failed else "✅ Успех"

            elif tool_name == 'get_workflow_run_logs':
                owner = args.get('owner')
                repo = args.get('repo')
                run_id = args.get('run_id')

                with httpx.Client(timeout=30.0) as client:
                    url = f"{GITHUB_API}/repos/{owner}/{repo}/actions/runs/{run_id}"
                    res = client.get(url, headers=headers)
                    if res.status_code != 200:
                        output = f"❌ Ошибка: {res.status_code} - Запуск не найден"
                    else:
                        run_data = res.json()
                        url = f"{GITHUB_API}/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"
                        res = client.get(url, headers=headers)
                        jobs = res.json().get('jobs', [])

                        failed_jobs = [j for j in jobs if j.get('conclusion') == 'failure']

                        output = f"🏃 Запуск #{run_id}\n"
                        output += f"📌 Статус: {run_data.get('status')}\n"
                        output += f"📊 Результат: {run_data.get('conclusion')}\n"
                        output += f"🌿 Ветка: {run_data.get('head_branch')}\n"
                        output += f"🔖 Коммит: {run_data.get('head_sha', '')[:7]}\n\n"

                        if failed_jobs:
                            output += "❌ НАЙДЕНЫ ОШИБКИ:\n"
                            for job in failed_jobs:
                                output += f"\n📦 Job: {job.get('name')}\n"
                                output += f"   Статус: {job.get('status')}\n"
                                output += "\n   🔍 Проваленные шаги:\n"
                                for step in job.get('steps', []):
                                    if step.get('conclusion') == 'failure':
                                        output += f"   ❌ {step.get('name')}\n"
                        else:
                            output += "✅ Все проверки прошли успешно!"

            elif tool_name == 'get_full_workflow_logs':
                owner = args.get('owner')
                repo = args.get('repo')
                run_id = args.get('run_id')

                with httpx.Client(timeout=60.0) as client:
                    url = f"{GITHUB_API}/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"
                    res = client.get(url, headers=headers)
                    if res.status_code != 200:
                        output = f"❌ Ошибка: {res.status_code}"
                    else:
                        jobs = res.json().get('jobs', [])

                        output = f"📋 ПОЛНЫЕ ЛОГИ для запуска #{run_id}\n"
                        output += f"Всего jobs: {len(jobs)}\n"
                        output += "=" * 60 + "\n\n"

                        for job in jobs:
                            job_name = job.get('name', 'unknown')
                            output += f"📦 JOB: {job_name}\n"
                            output += f"   Статус: {job.get('status')}\n"
                            output += f"   Результат: {job.get('conclusion')}\n"

                            job_id = job.get('id')
                            if job_id:
                                try:
                                    url = f"{GITHUB_API}/repos/{owner}/{repo}/actions/jobs/{job_id}/logs"
                                    log_res = client.get(url, headers=headers, timeout=60.0)
                                    if log_res.status_code == 200:
                                        logs = log_res.text
                                        log_lines = logs.split('\n')
                                        output += f"\n   📄 ЛОГИ (первые 50 строк из {len(log_lines)}):\n"
                                        output += "   " + "-" * 40 + "\n"
                                        output += "\n".join(f"   {line}" for line in log_lines[:50])
                                        if len(log_lines) > 50:
                                            output += f"\n   ... (обрезано, всего {len(log_lines)} строк)"
                                        output += "\n   " + "-" * 40 + "\n"
                                    else:
                                        output += f"\n   ⚠️ Не удалось получить логи: {log_res.status_code}\n"
                                except Exception as e:
                                    output += f"\n   ⚠️ Ошибка при получении логов: {str(e)}\n"

                            output += "\n" + "-" * 40 + "\n\n"

            elif tool_name == 'get_workflow_by_file':
                owner = args.get('owner')
                repo = args.get('repo')
                filename = args.get('filename')

                with httpx.Client(timeout=30.0) as client:
                    url = f"{GITHUB_API}/repos/{owner}/{repo}/actions/workflows"
                    res = client.get(url, headers=headers)
                    if res.status_code != 200:
                        output = f"❌ Ошибка: {res.status_code}"
                    else:
                        workflows = res.json().get('workflows', [])
                        target = None
                        for wf in workflows:
                            if wf.get('name') == filename or wf.get('path', '').endswith(filename):
                                target = wf
                                break

                        if not target:
                            output = f"❌ Workflow '{filename}' не найден"
                        else:
                            url = f"{GITHUB_API}/repos/{owner}/{repo}/actions/workflows/{target['id']}/runs?per_page=5"
                            res = client.get(url, headers=headers)
                            runs = res.json().get('workflow_runs', [])

                            output = f"📄 Workflow: {target['name']}\n"
                            output += f"📁 Файл: {target['path']}\n\n"
                            output += f"📋 Последние {len(runs)} запусков:\n"
                            for run in runs:
                                icon = "✅" if run.get('conclusion') == 'success' else "❌" if run.get('conclusion') == 'failure' else "⏳"
                                output += f"  {icon} #{run['id']} - {run['head_sha'][:7]} - {run.get('conclusion', 'pending')} - {run['created_at'][:10]}\n"

            elif tool_name == 'get_commit_status':
                owner = args.get('owner')
                repo = args.get('repo')
                sha = args.get('sha')

                with httpx.Client(timeout=30.0) as client:
                    url = f"{GITHUB_API}/repos/{owner}/{repo}/commits/{sha}/status"
                    res = client.get(url, headers=headers)
                    if res.status_code != 200:
                        output = f"❌ Ошибка: {res.status_code} - Коммит не найден"
                    else:
                        status_data = res.json()

                        url = f"{GITHUB_API}/repos/{owner}/{repo}/commits/{sha}/check-runs"
                        res = client.get(url, headers=headers)
                        checks = res.json().get('check_runs', [])

                        output = f"🔖 Коммит: {sha}\n"
                        output += f"📊 Статус: {status_data.get('state', 'unknown')}\n\n"

                        if checks:
                            failed_checks = [c for c in checks if c.get('conclusion') == 'failure']
                            pending_checks = [c for c in checks if c.get('status') == 'in_progress']

                            if failed_checks:
                                output += f"❌ Проваленных проверок: {len(failed_checks)}\n"
                                for check in failed_checks:
                                    output += f"   - {check.get('name')}: {check.get('conclusion')}\n"

                            if pending_checks:
                                output += f"\n⏳ В процессе: {len(pending_checks)}\n"
                                for check in pending_checks:
                                    output += f"   - {check.get('name')}: {check.get('status')}\n"

                            successful = [c for c in checks if c.get('conclusion') == 'success']
                            if successful:
                                output += f"\n✅ Успешных проверок: {len(successful)}\n"
                        else:
                            output += "ℹ️ Нет проверок для этого коммита"

            else:
                raise Exception(f"Unknown tool: {tool_name}")

            return jsonify({
                "jsonrpc": "2.0",
                "result": {"content": [{"type": "text", "text": output}]},
                "id": req_id
            })

        except Exception as e:
            logger.error(f"Error: {str(e)}")
            return jsonify({
                "jsonrpc": "2.0",
                "error": {"code": -32000, "message": str(e)},
                "id": req_id
            })

    return jsonify({
        "jsonrpc": "2.0",
        "error": {"code": -32601, "message": "Method not found"},
        "id": req_id
    })


@app.route('/health')
def health():
    return jsonify({"status": "ok", "server": "mcp-github-server v0.2.0"})


def main():
    """Entry point for mcp-server command."""
    port = int(os.environ.get("PORT", 3001))
    debug = os.environ.get("DEBUG", "false").lower() == "true"
    logger.info(f"Starting MCP GitHub Server v0.2.0 on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)


if __name__ == '__main__':
    main()
