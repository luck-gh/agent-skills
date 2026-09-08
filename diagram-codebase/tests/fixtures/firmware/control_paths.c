/* Architecture review input only: do not execute hardware or startup loops. */
extern int initialize_device(void);
extern int register_interrupts(void);
extern void heartbeat(void);
extern int configure_shared_clock(void);
extern int configure_channel(int channel);
extern void write_log(int code);
extern int set_gain(int gain);
static int committed_mode;

#define RETURN_IF_ERROR(code) do { if ((code) != 0) return (code); } while (0)

int initialize_interrupts(void) {
    int error = register_interrupts();
    if (error != 0) return error;
    return 0;
}

void startup(void) {
    if (initialize_device() != 0) {
        while (1) {}
    }
    initialize_interrupts();
    while (1) heartbeat();
}

int apply_mode(int mode) {
    int error = configure_shared_clock();
    RETURN_IF_ERROR(error);
    for (int channel = 0; channel < 2; ++channel) {
        error = configure_channel(channel);
        RETURN_IF_ERROR(error);
    }
    committed_mode = mode;
    return 0;
}

int dispatch(int command) {
    int error = 0;
    if (command == 0) return 0;
    write_log(command);
    if (command == 1) error = apply_mode(1);
    else if (command == 2) set_gain(3);
    else return -2;
    if (error != 0) {
        write_log(error);
        return error;
    }
    return 0;
}
