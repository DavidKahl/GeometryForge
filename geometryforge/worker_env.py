"""Minimal worker environment. Process separation is not a security sandbox."""
import os


def worker_environment():
    allowed = {'PATH', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'PATHEXT', 'TEMP', 'TMP',
               'USERPROFILE', 'HOME', 'APPDATA', 'LOCALAPPDATA', 'PROGRAMDATA',
               'PROGRAMFILES', 'PROGRAMFILES(X86)', 'COMMONPROGRAMFILES',
               'NUMBER_OF_PROCESSORS', 'PROCESSOR_ARCHITECTURE', 'SYSTEMDRIVE',
               'HOMEDRIVE', 'HOMEPATH', 'LANG', 'LC_ALL', 'DISPLAY',
               'VTK_DEFAULT_OPENGL_WINDOW', 'LP_NUM_THREADS',
               'SESI_LMHOST', 'HOUDINI_LICENSE_SERVER', 'HOUDINI_USER_PREF_DIR'}
    return {k: v for k, v in os.environ.items() if k.upper() in allowed}
