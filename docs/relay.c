/*
*   SainSmart 16 Relay Module
*
*   To compile use: gcc -o relay relay.c -lhidapi-hidraw
*
*   Get HIDAPI library: https://github.com/signal11/hidapi.git
*
*   Other dependencies:
*     sudo apt-get install libudev-dev libusb-1.0-0-dev autotools-dev autoconf automake libtool 
*
*   To install libudev-dev on Ubuntu: 
*     https://launchpad.net/ubuntu/trusty/amd64/libudev-dev/204-5ubuntu20.14
*
*   Some useful links:
*     https://github.com/mvines/relay
*     http://www.signal11.us/oss/hidapi/
*     https://www.raspberrypi.org/forums/viewtopic.php?f=29&t=77538
*     https://github.com/ondrej1024/crelay/issues/6
*     
*/

#include <stdio.h>
#include <hidapi/hidapi.h>


// define constant
#define PRODUCT_ID 0x5020
#define VENDOR_ID  0x0416


// define command messages
const unsigned char open_cmd[] = {
    0xD2, 0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x48, 0x49, 0x44, 
    0x43, 0x80, 0x02, 0x00, 0x00 
};

unsigned char write_cmd[] = {
    0xC3, 0x0E, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x48, 0x49, 0x44,
    0x43, 0xEE, 0x01, 0x00, 0x00
};

const unsigned char close_cmd[] = {
    0x71, 0x0E, 0x71, 0x00, 0x00, 0x00, 0x11, 0x11, 0x00, 0x00, 0x48, 0x49, 0x44,
    0x43, 0x2A, 0x02, 0x00, 0x00
};


// define functions
void updateState(unsigned char * msg, unsigned int state) {
    msg[2] = state & 0xff;
    state = state >> 8;
    msg[3] = state & 0xff;
}

void updateCheckSum(unsigned char * msg) {
    int i;
    int chksum = 0;
    int len = msg[1];
    
    for (i=0; i < len; i++) {
        chksum += msg[i];
    }
    
    for (i=0; i < 4; i++) {
        msg[len++] = chksum & 0xff;
        chksum = chksum >> 8;
    }
}

hid_device * deviceOpen() {
    hid_device *handle;
    int res;
    
    handle = hid_open(VENDOR_ID, PRODUCT_ID, NULL);
    
    if (handle != NULL){
        res = hid_write(handle, open_cmd, sizeof(open_cmd));
        
        if (res != sizeof(open_cmd))
            return NULL;
    }
    
    return handle;
}

void deviceClose(hid_device *handle) {
    if (handle != NULL)
        hid_write(handle, close_cmd, sizeof(close_cmd));
}

int setRelays(hid_device *handle, unsigned short state) {
    if (handle == NULL)
        return -1;
        
    updateState(write_cmd, state);
    updateCheckSum(write_cmd);
        
    int res = hid_write(handle, write_cmd, sizeof(write_cmd));
        
    if (res != sizeof(write_cmd))
        return -1;
            
    return 0;      // OK
}

int main( int argc, char *argv[]) {
    int res;
    int state;
    hid_device *handle;
    
    if (argc == 2) {
        res = sscanf(argv[1], "%04x", & state);
        printf("res=%d, state=%02x\n", res, state);
        
        if (res == 1) {
            handle = deviceOpen();
            res = setRelays(handle, state);
            deviceClose(handle);
            
            return res;
        }
    }
    
    printf("Use: './relay ffff' for all relays on\n");
    printf("Use: './relay 0000' for all relays off\n");
            
    return -1;
}
