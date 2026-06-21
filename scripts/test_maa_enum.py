import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

try:
    import maa.controller as c
    print('import ok', flush=True)
    print('type:', type(c.MaaAdbInputMethodEnum), flush=True)
    x = c.MaaAdbInputMethodEnum.AdbShell
    print('AdbShell:', x, flush=True)
    print('AdbShell value:', x.value, flush=True)
except Exception as e:
    print('Error:', e, flush=True)
    import traceback
    traceback.print_exc()