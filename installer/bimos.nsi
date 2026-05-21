; ============================================================
;  BIMOS — Windows NSIS Installer Script
;  Requires: NSIS >= 3.09, MUI2
;  Build:  makensis installer/bimos.nsi
; ============================================================

!define APP_NAME        "BIMOS"
!define APP_VERSION     "0.1.0"
!define APP_PUBLISHER   "BIMOS Project"
!define APP_URL         "https://github.com/your-org/bimos"
!define APP_EXE         "bimos.exe"
!define INSTALL_DIR     "$PROGRAMFILES64\${APP_NAME}"
!define UNINSTALL_KEY   "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"

; ── MUI2 Modern UI ───────────────────────────────────────────
!include "MUI2.nsh"
!include "LogicLib.nsh"

; ── Installer metadata ───────────────────────────────────────
Name              "${APP_NAME} ${APP_VERSION}"
OutFile           "dist\BIMOS-${APP_VERSION}-Setup.exe"
InstallDir        "${INSTALL_DIR}"
InstallDirRegKey  HKLM "${UNINSTALL_KEY}" "InstallLocation"
RequestExecutionLevel admin
SetCompressor     /SOLID lzma
SetCompressorDictSize 32

; ── MUI Settings ─────────────────────────────────────────────
!define MUI_ABORTWARNING
!define MUI_ICON                  "installer\assets\bimos.ico"
!define MUI_UNICON                "installer\assets\bimos.ico"
!define MUI_WELCOMEFINISHPAGE_BITMAP   "installer\assets\wizard_banner.bmp"
!define MUI_UNWELCOMEFINISHPAGE_BITMAP "installer\assets\wizard_banner.bmp"
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_BITMAP    "installer\assets\header.bmp"
!define MUI_HEADERIMAGE_RIGHT

; ── Pages ────────────────────────────────────────────────────
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE      "installer\assets\LICENSE.rtf"
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN         "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT    "Launch BIMOS now"
!define MUI_FINISHPAGE_SHOWREADME  "$INSTDIR\README.md"
!insertmacro MUI_PAGE_FINISH

; ── Uninstaller pages ────────────────────────────────────────
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; ── Languages ────────────────────────────────────────────────
!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "Spanish"

; ============================================================
;  Components
; ============================================================
Section "BIMOS Core (required)" SecCore
    SectionIn RO                    ; cannot be deselected

    SetOutPath "$INSTDIR"
    File "backend\dist\bimos.exe"
    File "backend\README.md"

    ; ── Desktop shortcut ────────────────────────────────────
    CreateShortcut "$DESKTOP\${APP_NAME}.lnk" \
        "$INSTDIR\${APP_EXE}" "BIMOS_GUI" \
        "$INSTDIR\${APP_EXE}" 0

    ; ── Start Menu ──────────────────────────────────────────
    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    CreateShortcut  "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" \
        "$INSTDIR\${APP_EXE}" "BIMOS_GUI" \
        "$INSTDIR\${APP_EXE}" 0
    CreateShortcut  "$SMPROGRAMS\${APP_NAME}\Uninstall ${APP_NAME}.lnk" \
        "$INSTDIR\Uninstall.exe"

    ; ── Registry: Add/Remove Programs ───────────────────────
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "DisplayName"      "${APP_NAME}"
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "DisplayVersion"   "${APP_VERSION}"
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "Publisher"        "${APP_PUBLISHER}"
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "URLInfoAbout"     "${APP_URL}"
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "InstallLocation"  "$INSTDIR"
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "UninstallString"  "$INSTDIR\Uninstall.exe"
    WriteRegDWORD HKLM "${UNINSTALL_KEY}" "NoModify"         1
    WriteRegDWORD HKLM "${UNINSTALL_KEY}" "NoRepair"         1

    ; ── PATH registration ───────────────────────────────────
    EnVar::SetHKLM
    EnVar::AddValue "PATH" "$INSTDIR"

    WriteUninstaller "$INSTDIR\Uninstall.exe"
SectionEnd

Section "Docker images (recommended)" SecDocker
    SetOutPath "$INSTDIR\dockers"
    File /r "backend\dockers\*.*"
SectionEnd

; ── Section descriptions ─────────────────────────────────────
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

    EnVar::SetHKLM
    EnVar::DeleteValue "PATH" "$INSTDIR"

    DeleteRegKey HKLM "${UNINSTALL_KEY}"
SectionEnd
