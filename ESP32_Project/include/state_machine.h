#ifndef STATE_MACHINE_H
#define STATE_MACHINE_H

#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    BOOT,
    WIFI_OK,
    TIME_SYNCED,
    CLAIMING,
    RUNNING,
    ERROR_RECOVERY
} app_state_t;

void app_state_machine_tick(void);
app_state_t app_get_current_state(void);
bool app_is_running(void);
void app_force_reclaim(void);

#ifdef __cplusplus
}
#endif

#endif // STATE_MACHINE_H