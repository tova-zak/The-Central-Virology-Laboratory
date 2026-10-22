"""Run the relevant offline backend suites without network or developer credentials.

Standalone live/manual diagnostics are deliberately excluded. Production access rules are
unchanged; access-control tests supply their own synthetic credentials as before.
"""
import os
from pathlib import Path
import socket
import sys

ROOT = Path(os.environ.get('PIPELINE_REGRESSION_ROOT', Path(__file__).resolve().parents[1])).resolve()
os.chdir(ROOT)
sys.path.insert(0, str(ROOT/'backend'))
os.environ['DEMO_MODE'] = 'true'
os.environ['DEPLOYMENT_MODE'] = 'local'
os.environ['TEMP_STORAGE_PATH'] = str(ROOT/'temp/offline-storage')
for name in list(os.environ):
    if name.startswith(('GEMINI_API', 'SUPABASE_')) or name in ('API_USERNAME', 'API_PASSWORD', 'APP_ENV_FILE'):
        del os.environ[name]
# An empty selected env file prevents accidental reads of a user's local .env.
empty_env = ROOT/'temp/offline-tests.env'
empty_env.parent.mkdir(exist_ok=True)
empty_env.write_text('', encoding='utf-8')
os.environ['APP_ENV_FILE'] = str(empty_env)
original_connect = socket.socket.connect
original_pair = socket.socketpair
making_pair = False
def internal_pair(*args, **kwargs):
    global making_pair
    making_pair = True
    try:
        return original_pair(*args, **kwargs)
    finally:
        making_pair = False
def offline_connect(sock, address):
    if making_pair and address[0] in ('127.0.0.1', '::1'):
        return original_connect(sock, address)
    raise RuntimeError('External network disabled by offline pipeline regression runner')
socket.socketpair = internal_pair
socket.socket.connect = offline_connect
socket.socket.connect_ex = offline_connect

SUITES = '''validation upload_limits timeout_abort storage_integrity state_persistence
sender_normalization segmentation saved_records_history renderer record_status reclassification
pipeline_proven_fixes persistence_proof page_export one_page_one_commitment multi_page_extraction
models mock_e2e hybrid_verification hybrid_preprocessing hybrid_ocr_mock hybrid_focused_retry
gemini_transport gemini_local_offline gemini_key_manager gemini_force_ipv4
gemini_error_scenarios gemini_client_initialization final_record_review extraction_pipeline_bounded
extraction_accuracy_policy export_policy export_integrity export_integration export_check_commitments
export exception_review eval_accuracy edit_permissions documents demo_mode_enforcement
commitment_preservation_e2e commitment_detection classification batch_lifecycle'''.split()
if __name__ == '__main__':
    import pytest
    paths = [f'backend/tests/test_{name}.py' for name in SUITES if (ROOT/f'backend/tests/test_{name}.py').exists()]
    raise SystemExit(pytest.main(paths + ['-q', '--tb=short', '--disable-warnings',
                                        '--basetemp=temp/pipeline-regression'] + sys.argv[1:]))
