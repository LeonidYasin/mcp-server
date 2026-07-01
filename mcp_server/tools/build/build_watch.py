"""Build monitoring and auto-fix tools."""

import time
from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


def _safe_utf8(text: str) -> str:
    try:
        return text.encode('utf-8', errors='replace').decode('utf-8')
    except Exception:
        return str(text)


def _get_build_status(client: GitHubClient, owner: str, repo: str, run_id: int) -> dict:
    """Get build status and jobs."""
    run = client.get_workflow_run(owner, repo, run_id)
    jobs = client.get_workflow_jobs(owner, repo, run_id)
    
    status = run.get('status', 'unknown')
    conclusion = run.get('conclusion', 'unknown')
    
    failed_jobs = [j for j in jobs if j.get('conclusion') == 'failure']
    success_jobs = [j for j in jobs if j.get('conclusion') == 'success']
    running_jobs = [j for j in jobs if j.get('status') == 'in_progress']
    
    return {
        'status': status,
        'conclusion': conclusion,
        'total_jobs': len(jobs),
        'failed': failed_jobs,
        'success': success_jobs,
        'running': running_jobs,
        'run': run
    }


def _detect_android_error(logs: str) -> dict:
    """Detect Android build error type."""
    if 'Android resource linking failed' in logs:
        return {
            'type': 'missing_strings_xml',
            'message': 'Missing or invalid strings.xml',
            'file': 'android/app/src/main/res/values/strings.xml',
            'content': '<resources>\n    <string name="app_name">Synapse</string>\n</resources>\n'
        }
    if 'Could not find com.android.tools.build:gradle' in logs:
        return {
            'type': 'gradle_version_error',
            'message': 'Incorrect Gradle version',
            'file': 'android/build.gradle',
            'content': '// Fix Gradle version in build.gradle'
        }
    if 'signingConfig' in logs and 'storeFile' in logs:
        return {
            'type': 'missing_keystore',
            'message': 'Missing signing keystore configuration',
            'file': 'android/app/build.gradle',
            'content': '// Add signingConfigs to build.gradle'
        }
    return {'type': 'unknown', 'message': 'Unknown Android error'}


def _detect_ios_error(logs: str) -> dict:
    """Detect iOS build error type."""
    if 'No such module' in logs:
        return {
            'type': 'missing_pod',
            'message': 'Missing CocoaPods dependency',
            'file': 'ios/Podfile',
            'content': 'platform :ios, \'13.0\'\n\ntarget \'synapse\' do\n  use_frameworks!\n  # Add your pods here\nend\n'
        }
    if 'Info.plist' in logs and 'not found' in logs:
        return {
            'type': 'missing_infoplist',
            'message': 'Missing Info.plist',
            'file': 'ios/synapse/Info.plist',
            'content': '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n<plist version="1.0">\n<dict>\n    <key>CFBundleDevelopmentRegion</key>\n    <string>en</string>\n    <key>CFBundleDisplayName</key>\n    <string>Synapse</string>\n    <key>CFBundleExecutable</key>\n    <string>$(EXECUTABLE_NAME)</string>\n    <key>CFBundleIdentifier</key>\n    <string>$(PRODUCT_BUNDLE_IDENTIFIER)</string>\n    <key>CFBundleInfoDictionaryVersion</key>\n    <string>6.0</string>\n    <key>CFBundleName</key>\n    <string>$(PRODUCT_NAME)</string>\n    <key>CFBundlePackageType</key>\n    <string>APPL</string>\n    <key>CFBundleShortVersionString</key>\n    <string>1.0</string>\n    <key>CFBundleSignature</key>\n    <string>????</string>\n    <key>CFBundleVersion</key>\n    <string>1</string>\n    <key>LSRequiresIPhoneOS</key>\n    <true/>\n</dict>\n</plist>\n'
        }
    if 'xcodebuild' in logs and 'error:' in logs.lower():
        return {
            'type': 'xcode_error',
            'message': 'Xcode build error',
            'file': 'ios/synapse.xcodeproj/project.pbxproj',
            'content': '// Check Xcode project configuration'
        }
    return {'type': 'unknown', 'message': 'Unknown iOS error'}


@mcp_tool(
    name="watch_build",
    description="Monitor a workflow build and return result when completed",
    parameters={
        "owner": {"type": "string", "description": "Repository owner"},
        "repo": {"type": "string", "description": "Repository name"},
        "run_id": {"type": "integer", "description": "Workflow run ID to watch"},
        "interval": {"type": "integer", "description": "Check interval in seconds (default: 10)"},
        "timeout": {"type": "integer", "description": "Max wait time in seconds (default: 600)"},
    },
    required=["owner", "repo", "run_id"],
)
def watch_build(client: GitHubClient, owner: str, repo: str, run_id: int, interval: int = 10, timeout: int = 600) -> str:
    """Watch build progress and return result."""
    elapsed = 0
    last_status = None
    
    result_lines = [
        f"🔍 Watching build #{run_id}",
        f"📦 Repository: {owner}/{repo}",
        f"⏱️ Check interval: {interval}s, Timeout: {timeout}s",
        ""
    ]
    
    while elapsed < timeout:
        try:
            info = _get_build_status(client, owner, repo, run_id)
            status = info['status']
            conclusion = info['conclusion']
            
            if status != last_status:
                result_lines.append(f"⏳ Status: {status} (elapsed: {elapsed}s)")
                if info['running']:
                    result_lines.append(f"   🏃 Running jobs: {len(info['running'])}")
                if info['success']:
                    result_lines.append(f"   ✅ Success: {len(info['success'])}")
                if info['failed']:
                    result_lines.append(f"   ❌ Failed: {len(info['failed'])}")
                last_status = status
            
            if status == 'completed':
                result_lines.append("")
                if conclusion == 'success':
                    result_lines.append("🎉 BUILD SUCCESSFUL!")
                    result_lines.append(f"✅ {len(info['success'])} jobs passed")
                else:
                    result_lines.append("❌ BUILD FAILED!")
                    result_lines.append(f"❌ Failed jobs: {len(info['failed'])}")
                    for job in info['failed']:
                        result_lines.append(f"   📦 {job.get('name')} - {job.get('conclusion')}")
                
                result_lines.append("")
                result_lines.append(f"📊 Total jobs: {info['total_jobs']}")
                result_lines.append(f"🔄 Run URL: https://github.com/{owner}/{repo}/actions/runs/{run_id}")
                return _safe_utf8('\n'.join(result_lines))
            
            time.sleep(interval)
            elapsed += interval
            
        except Exception as e:
            return _safe_utf8(f"❌ Error watching build: {e}")
    
    return _safe_utf8(f"⏰ Timeout ({timeout}s) reached. Build still in progress. Check manually: https://github.com/{owner}/{repo}/actions/runs/{run_id}")


def _create_or_update_file_with_sha(client: GitHubClient, owner: str, repo: str, path: str, content: str, message: str, branch: str = "main") -> dict:
    """Create or update a file, automatically getting SHA if needed."""
    # Try to get existing file SHA
    try:
        existing = client.get_file(owner, repo, path, branch)
        sha = existing.get('sha')
        if sha:
            # File exists, update it
            result = client.create_or_update_file(owner, repo, path, content, message, branch, sha)
            return {'action': 'updated', 'sha': sha, 'result': result}
    except Exception:
        # File doesn't exist, create it
        pass
    
    # Create new file
    result = client.create_or_update_file(owner, repo, path, content, message, branch)
    return {'action': 'created', 'sha': None, 'result': result}


@mcp_tool(
    name="auto_fix_build",
    description="Auto-detect and fix common build errors (Android/iOS)",
    parameters={
        "owner": {"type": "string", "description": "Repository owner"},
        "repo": {"type": "string", "description": "Repository name"},
        "run_id": {"type": "integer", "description": "Workflow run ID with the error"},
        "platform": {"type": "string", "description": "Platform: android or ios"},
    },
    required=["owner", "repo", "run_id", "platform"],
)
def auto_fix_build(client: GitHubClient, owner: str, repo: str, run_id: int, platform: str) -> str:
    """Auto-fix build errors."""
    try:
        # Get logs
        jobs = client.get_workflow_jobs(owner, repo, run_id)
        
        # Find failed job for platform
        platform_job_name = f"build-{platform}"
        target_job = None
        for job in jobs:
            if platform_job_name in job.get('name', '').lower():
                target_job = job
                break
        
        if not target_job:
            return _safe_utf8(f"❌ No {platform} job found in run #{run_id}")
        
        job_id = target_job.get('id')
        logs = client.get_job_logs(owner, repo, job_id)
        
        # Detect error type
        if platform == 'android':
            detection = _detect_android_error(logs)
        else:
            detection = _detect_ios_error(logs)
        
        result_lines = [
            f"🔧 AUTO-FIX BUILD ({platform.upper()})",
            f"📦 Repository: {owner}/{repo}",
            f"🆔 Run: #{run_id}",
            f"📋 Detected: {detection['type']}",
            f"📝 Message: {detection['message']}",
            ""
        ]
        
        if detection['type'] == 'unknown':
            result_lines.append("❌ Unknown error. Manual intervention required.")
            result_lines.append("")
            result_lines.append("📋 Last 20 lines of logs:")
            for line in logs.split('\n')[-20:]:
                result_lines.append(f"  {_safe_utf8(line)}")
            return _safe_utf8('\n'.join(result_lines))
        
        # Fix by creating/updating file
        file_path = detection['file']
        file_content = detection['content']
        
        result_lines.append(f"📄 Processing file: {file_path}")
        
        # Check if file exists and get SHA
        existing_sha = None
        try:
            existing = client.get_file(owner, repo, file_path)
            if existing:
                existing_sha = existing.get('sha')
                result_lines.append(f"📂 File exists, SHA: {existing_sha[:7] if existing_sha else 'N/A'}...")
        except Exception:
            result_lines.append("📂 File does not exist, creating new...")
        
        # Create or update file with SHA using the file_ops tool
        try:
            from mcp_server.tools.github.file_ops import create_or_update_file as create_file_tool
            
            # Call with all required parameters
            result = create_file_tool(
                client=client,
                owner=owner,
                repo=repo,
                path=file_path,
                content=file_content,
                message=f"Auto-fix: Add/update {file_path}",
                branch="main",
                sha=existing_sha
            )
            result_lines.append(f"✅ File processed: {file_path}")
            if existing_sha:
                result_lines.append(f"🔄 Updated existing file (SHA: {existing_sha[:7] if existing_sha else 'N/A'}...)")
            else:
                result_lines.append("✨ Created new file")
            result_lines.append("")
            result_lines.append("🔄 Next steps:")
            result_lines.append("1. Push the changes to trigger a new build")
            result_lines.append("2. Or use watch_build to monitor the new run")
        except Exception as e:
            result_lines.append(f"❌ Failed to process file: {e}")
        
        return _safe_utf8('\n'.join(result_lines))
        
    except Exception as e:
        return _safe_utf8(f"❌ Error in auto-fix: {e}")
