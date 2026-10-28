"""Read-only workspace self-check; does not invoke an AI or inspect other projects."""
import json
from pathlib import Path
import sys

from _common import SafetyError, checked_path
from install_workspace import installation_report, payload

ROOT = Path(__file__).resolve().parents[1]


def main():
    try:
        root = checked_path(ROOT, directory=True)
        if (root / 'runtime/setup-receipt.json').exists():
            result = installation_report(root)
            result['status'] = 'USER_CHANGES_PRESERVED' if result['changed_files'] else 'INSTALLED_FILES_UNCHANGED'
        else:
            data = payload(root)
            result = {'status': 'SOURCE_STRUCTURE_READY', 'public_files': len(data),
                      'ai_acceptance': 'NOT_TESTED', 'written': False}
    except (SafetyError, OSError, ValueError, TypeError) as exc:
        print(json.dumps({'status': 'FAILED', 'reason': str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 3 if result.get('changed_files') else 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
