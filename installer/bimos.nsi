; ============================================================
;  BIMOS - Windows NSIS Installer Script
;  Requires: NSIS >= 3.09, MUI2
;  Build:  makensis installer/bimos.nsi
; ============================================================

!define APP_NAME        "BIMOS"
!ifndef APP_VERSION
!define APP_VERSION     "0.1.0"
!endif
!define APP_PUBLISHER   "BIMOS Project"
!define APP_URL         "https://github.com/your-org/bimos"
!define APP_EXE         "bimos.exe"
!define INSTALL_DIR     "$PROGRAMFILES64\${APP_NAME}"
!define UNINSTALL_KEY   "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"

; --- MUI2 Modern UI ---
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "WordFunc.nsh"

; --- Installer metadata ---
Name              "${APP_NAME} ${APP_VERSION}"
OutFile           "dist\BIMOS-${APP_VERSION}-Setup.exe"
InstallDir        "${INSTALL_DIR}"
InstallDirRegKey  HKLM "${UNINSTALL_KEY}" "InstallLocation"
RequestExecutionLevel admin
SetCompressor     /SOLID lzma
SetCompressorDictSize 32

; --- MUI Settings ---
!define MUI_ABORTWARNING
; OPTIONAL: MUI_ICON, MUI_UNICON (set by builder.py if assets exist)
; OPTIONAL: MUI_WELCOMEFINISHPAGE_BITMAP, MUI_UNWELCOMEFINISHPAGE_BITMAP
; OPTIONAL: MUI_HEADERIMAGE, MUI_HEADERIMAGE_BITMAP, MUI_HEADERIMAGE_RIGHT

; --- Pages ---
!insertmacro MUI_PAGE_WELCOME
; LICENSE_FILE_PATH will be replaced by builder.py
!insertmacro MUI_PAGE_LICENSE      "LICENSE_FILE_PATH"
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN              "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT         "Launch BIMOS now"
!define MUI_FINISHPAGE_RUN_NOTCHECKED
!insertmacro MUI_PAGE_FINISH

; --- Uninstaller pages ---
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; --- Languages ---
!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "Spanish"

; ============================================================
;  Components
; ============================================================
Section "BIMOS Core (required)" SecCore
    SectionIn RO                    ; cannot be deselected

    SetOutPath "$INSTDIR"
    ; BINARY_DIR_PATH and README_FILE_PATH will be replaced by builder.py
    File /r "BINARY_DIR_PATH\*.*"
    File "README_FILE_PATH"

    ; --- Desktop shortcut ---
    CreateShortcut "$DESKTOP\${APP_NAME}.lnk" \
        "$INSTDIR\${APP_EXE}" "-g" \
        "$INSTDIR\${APP_EXE}" 0

    ; --- Start Menu ---
    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    CreateShortcut  "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" \
        "$INSTDIR\${APP_EXE}" "-g" \
        "$INSTDIR\${APP_EXE}" 0
    CreateShortcut  "$SMPROGRAMS\${APP_NAME}\Uninstall ${APP_NAME}.lnk" \
        "$INSTDIR\Uninstall.exe"

    ; --- Registry: Add/Remove Programs ---
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "DisplayName"      "${APP_NAME}"
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "DisplayVersion"   "${APP_VERSION}"
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "Publisher"        "${APP_PUBLISHER}"
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "URLInfoAbout"     "${APP_URL}"
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "InstallLocation"  "$INSTDIR"
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "UninstallString"  "$INSTDIR\Uninstall.exe"
    WriteRegDWORD HKLM "${UNINSTALL_KEY}" "NoModify"         1
    WriteRegDWORD HKLM "${UNINSTALL_KEY}" "NoRepair"         1

    ; --- Add install dir to system PATH (no extra plugin needed) ---
    ReadRegStr $0 HKLM "SYSTEM\CurrentControlSet\Control\Session Manager\Environment" "Path"
    ; Only add if not already present
    ClearErrors
    ${WordFind} "$0" "$INSTDIR" "E+1" $1
    ${If} ${Errors}
        WriteRegExpandStr HKLM "SYSTEM\CurrentControlSet\Control\Session Manager\Environment" \
            "Path" "$0;$INSTDIR"
        ; Broadcast the change so open terminals pick it up immediately
        SendMessage ${HWND_BROADCAST} ${WM_WININICHANGE} 0 "STR:Environment" /TIMEOUT=5000
    ${EndIf}

    WriteUninstaller "$INSTDIR\Uninstall.exe"
SectionEnd

Section "-Docker images (optional)" SecDocker
    SetOutPath "$INSTDIR\dockers"
    ; DOCKERS_DIR_PATH will be replaced by builder.py
    File /r "DOCKERS_DIR_PATH\*.*"
SectionEnd

; --- Section descriptions ---
LangString DESC_SecCore   ${LANG_ENGLISH} "Core BIMOS application and GUI launcher."
LangString DESC_SecDocker ${LANG_ENGLISH} "Bundled Docker compose files for docking/MD pipelines."

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
    !insertmacro MUI_DESCRIPTION_TEXT ${SecCore}   $(DESC_SecCore)
    !insertmacro MUI_DESCRIPTION_TEXT ${SecDocker} $(DESC_SecDocker)
!insertmacro MUI_FUNCTION_DESCRIPTION_END

; ============================================================
;  Uninstaller
; ============================================================
Section "Uninstall"
    Delete "$INSTDIR\${APP_EXE}"
    Delete "$INSTDIR\README.md"
    Delete "$INSTDIR\Uninstall.exe"
    RMDir  /r "$INSTDIR\dockers"
    RMDir  "$INSTDIR"

    Delete "$DESKTOP\${APP_NAME}.lnk"
    RMDir  /r "$SMPROGRAMS\${APP_NAME}"

    ; --- Remove install dir from system PATH ---
    ReadRegStr $0 HKLM "SYSTEM\CurrentControlSet\Control\Session Manager\Environment" "Path"
    ; Strip ";$INSTDIR" or "$INSTDIR;" or just "$INSTDIR"
    ${WordReplace} $0 ";$INSTDIR" "" "+" $0
    ${WordReplace} $0 "$INSTDIR;" "" "+" $0
    ${WordReplace} $0 "$INSTDIR"  "" "+" $0
    WriteRegExpandStr HKLM "SYSTEM\CurrentControlSet\Control\Session Manager\Environment" "Path" "$0"
    SendMessage ${HWND_BROADCAST} ${WM_WININICHANGE} 0 "STR:Environment" /TIMEOUT=5000

    DeleteRegKey HKLM "${UNINSTALL_KEY}"
SectionEnd
