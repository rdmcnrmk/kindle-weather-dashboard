#!/bin/sh
# Give KOReader ownership of the sleep screen for this app session only.
# No persistent settings or firmware files are changed. USB blanket is untouched.
set -u
APP_ROOT=${HAVA_PANOSU_ROOT:-/mnt/us}
restore_ad=0
report() {
    printf '%s\n' "$1"
    if [ -x "$APP_ROOT/libkh/bin/fbink" ]; then
        "$APP_ROOT/libkh/bin/fbink" -m "$1" || :
    fi
}
cleanup() {
    result=$?
    trap - EXIT HUP INT TERM
    if [ "$restore_ad" -eq 1 ]; then
        printf '%s\n' 'KindleWeather: restoring native ad_screensaver'
        lipc-set-prop -s com.lab126.blanket load ad_screensaver || :
    fi
    exit "$result"
}
trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
printf '\n=== KindleWeather 1.1.0 session %s ===\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
if ! modules=$(lipc-get-prop com.lab126.blanket load); then
    report 'Cannot read the sleep service. Dashboard was not started.'
    exit 1
fi
printf 'KindleWeather: native blanket before: %s\n' "$modules"
case "$modules" in
    *ad_screensaver*)
        # Set the cleanup flag before the request: even a partial failure must
        # restore the original module when this process exits.
        restore_ad=1
        if ! lipc-set-prop -s com.lab126.blanket unload ad_screensaver; then
            report 'Cannot take over the sleep screen. Dashboard was not started.'
            exit 1
        fi
        if ! modules=$(lipc-get-prop com.lab126.blanket load); then
            report 'Sleep screen verification failed. Dashboard was not started.'
            exit 1
        fi
        case "$modules" in
            *ad_screensaver*)
                report 'The system still owns the sleep screen. Dashboard was not started.'
                exit 1
                ;;
        esac
        ;;
esac
printf 'KindleWeather: native blanket during app: %s\n' "$modules"
/bin/sh "$APP_ROOT/koreader/koreader.sh" --kual
exit "$?"
