#include "not_installed_sdk.h"
#define RETURN_IF_ERROR(x) do { if (x) return -1; } while (0)
typedef void (*callback_t)(void);
extern void register_handler(callback_t callback);
static void handler(void) { signal_ready(); }

#if BOARD_A
static int apply(void) { return configure_a(); }
#elif BOARD_B
static int apply(void) { return configure_b(); }
#else
static int apply(void) { return configure_generic(); }
#endif

int dispatch(int enabled, callback_t callback) {
    const char *example = "fake_call()";
    /* comment_call(); */
    if (!enabled) return 0;
    register_handler(handler);
    callback();
    RETURN_IF_ERROR(apply());
    return 1;
}
