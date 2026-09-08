#include <stdbool.h>
#include <stddef.h>

typedef enum { IDLE, BUSY, DONE, ERROR } state_t;
static volatile state_t state = IDLE;
static const unsigned char *owned_buffer;
static void (*completion)(bool ok);
extern void board_dma_start(const unsigned char *buffer, size_t length);
extern bool board_dma_ok(void);

/* Called by the main loop; successful return means submitted, not completed. */
bool driver_submit(const unsigned char *buffer, size_t length, void (*callback)(bool)) {
    if (state != IDLE || buffer == NULL || length == 0) return false;
    owned_buffer = buffer;
    completion = callback;
    state = BUSY;
    board_dma_start(buffer, length);
    return true;
}

/* Called by the DMA interrupt vector. The callback therefore runs in ISR context. */
void DMA_IRQHandler(void) {
    bool ok = board_dma_ok();
    state = ok ? DONE : ERROR;
    owned_buffer = NULL;
    if (completion != NULL) completion(ok);
}

/* Called by the main loop after observing the terminal state. */
bool driver_reset(void) {
    if (state != DONE && state != ERROR) return false;
    completion = NULL;
    state = IDLE;
    return true;
}
