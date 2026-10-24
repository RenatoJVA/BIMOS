/*
 * BIMOS macOS launcher.
 *
 * A compiled launcher (instead of a shell script) gives the app bundle a real
 * Mach-O main executable, which is what codesign/Gatekeeper expect. It resolves
 * its own path, then execs the Nuitka binary that lives under
 * Contents/Resources/bimos/ adding the "-g" flag that starts the desktop UI.
 */

#include <limits.h>
#include <mach-o/dyld.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv) {
    char executable[PATH_MAX];
    uint32_t size = sizeof(executable);
    if (_NSGetExecutablePath(executable, &size) != 0) {
        fprintf(stderr, "BIMOS: executable path too long\n");
        return 1;
    }

    char resolved[PATH_MAX];
    if (realpath(executable, resolved) == NULL) {
        perror("BIMOS: realpath");
        return 1;
    }

    /* resolved == <bundle>/Contents/MacOS/BIMOS */
    char *slash = strrchr(resolved, '/');
    if (slash == NULL) {
        fprintf(stderr, "BIMOS: unexpected executable path\n");
        return 1;
    }
    *slash = '\0';

    char binary[PATH_MAX];
    int written = snprintf(binary, sizeof(binary), "%s/../Resources/bimos/bimos.bin", resolved);
    if (written < 0 || (size_t)written >= sizeof(binary)) {
        fprintf(stderr, "BIMOS: bundle path too long\n");
        return 1;
    }

    /* Nuitka's app bundle keeps the standalone tree in Contents/MacOS; the
       fallback layout keeps it in Contents/Resources/bimos. Support both. */
    if (access(binary, X_OK) != 0) {
        written = snprintf(binary, sizeof(binary), "%s/bimos.bin", resolved);
        if (written < 0 || (size_t)written >= sizeof(binary)) {
            fprintf(stderr, "BIMOS: bundle path too long\n");
            return 1;
        }
    }

    /* argv[0] = binary, argv[1] = "-g", then any arguments passed by the user. */
    char **child_argv = calloc((size_t)argc + 2, sizeof(char *));
    if (child_argv == NULL) {
        fprintf(stderr, "BIMOS: out of memory\n");
        return 1;
    }
    child_argv[0] = binary;
    child_argv[1] = "-g";
    for (int i = 1; i < argc; i++) {
        child_argv[i + 1] = argv[i];
    }
    child_argv[argc + 1] = NULL;

    execv(binary, child_argv);
    perror("BIMOS: execv");
    return 1;
}
